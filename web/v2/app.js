/* ──────────────────────────────────────────────────────────────────────────
   Document Translator — v2 client logic
   Backend endpoints (shared with the legacy /index.ejs UI):
      POST /upload      → multipart/form-data: file + sourceLanguage +
                          targetLanguage + translationEngine + aiModel
                          → { ok, jobId, cacheHit }
      GET  /status/:id  → { status, progress, filename, filename2,
                            filename3, error }
      GET  /download/<name> → docx bytes
      POST /subscribe   → JSON { email } → { ok, message }

   Polling-based (no SSE). Two files queue sequentially.
   ────────────────────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  const POLL_INTERVAL_MS = 4000;
  const MAX_WAIT_MS      = 40 * 60 * 1000;   // 40 min per file
  const MAX_FILES        = 2;
  const MAX_FILE_BYTES   = 50 * 1024 * 1024; // 50 MB

  // Match what's exposed in legacy index.ejs's languageDb so a user
  // moving between UIs sees identical options.
  const LANGUAGES = [
    { name: 'English',                value: 'en',    deepl: false },
    { name: 'Arabic',                 value: 'ar',    deepl: true  },
    { name: 'Bulgarian',              value: 'bg',    deepl: true  },
    { name: 'Chinese (Simplified)',   value: 'zh-CN', deepl: true  },
    { name: 'Chinese (Traditional)',  value: 'zh-TW', deepl: true  },
    { name: 'Czech',                  value: 'cs',    deepl: true  },
    { name: 'French',                 value: 'fr',    deepl: true  },
    { name: 'German',                 value: 'de',    deepl: true  },
    { name: 'Hindi',                  value: 'hi',    deepl: true  },
    { name: 'Hungarian',              value: 'hu',    deepl: true  },
    { name: 'Indonesian',             value: 'id',    deepl: true  },
    { name: 'Italian',                value: 'it',    deepl: true  },
    { name: 'Japanese',               value: 'ja',    deepl: true  },
    { name: 'Korean',                 value: 'ko',    deepl: true  },
    { name: 'Malay',                  value: 'ms',    deepl: true  },
    { name: 'Mongolian',              value: 'mn',    deepl: true  },
    { name: 'Nepali',                 value: 'ne',    deepl: true  },
    { name: 'Persian',                value: 'fa',    deepl: true  },
    { name: 'Polish',                 value: 'pl',    deepl: true  },
    { name: 'Punjabi',                value: 'pa',    deepl: true  },
    { name: 'Romanian',               value: 'ro',    deepl: true  },
    { name: 'Russian',                value: 'ru',    deepl: true  },
    { name: 'Spanish',                value: 'es',    deepl: true  },
    { name: 'Telugu',                 value: 'te',    deepl: true  },
    { name: 'Thai',                   value: 'th',    deepl: false },
    { name: 'Ukrainian',              value: 'uk',    deepl: true  },
    { name: 'Urdu',                   value: 'ur',    deepl: true  },
    { name: 'Vietnamese',             value: 'vi',    deepl: true  },
  ];

  const LS_KEYS = { source: 'v2.savedSourceLang', target: 'v2.savedTargetLang', theme: 'v2.theme' };

  function lsGet(k, def) { try { return localStorage.getItem(k) ?? def; } catch (_) { return def; } }
  function lsSet(k, v)   { try { localStorage.setItem(k, v); } catch (_) {} }

  // Expose the Alpine factory at module load time (Alpine reads x-data="docTranslator()").
  window.docTranslator = function () {
    return {
      // ── State ────────────────────────────────────────────────────────────
      languages: LANGUAGES,
      sourceLanguage: lsGet(LS_KEYS.source, 'en'),
      targetLanguage: lsGet(LS_KEYS.target, 'fa'),
      engine: 'chatgpt-polish',
      aiModel: 'gpt-5.5',
      files: [],
      dragActive: false,

      running: false,
      currentJobIndex: 0,
      currentFileName: '',
      progress: 0,
      progressLabel: 'Ready',

      results: [],
      error: '',

      newsletterEmail: '',
      newsletterPending: false,
      newsletterMessage: '',
      newsletterOk: false,

      theme: lsGet(LS_KEYS.theme, 'light'),

      // ── Init ─────────────────────────────────────────────────────────────
      init() {
        document.documentElement.setAttribute('data-theme', this.theme);
        // Pick a sensible default engine for the saved target language.
        this.onLanguageChange();
        // Sync <html lang=...> so screen readers + Google Translate detect
        // the actual page language. Tracks targetLanguage when it's RTL.
        this.syncHtmlLang();
      },

      // Update <html lang> to reflect the active target language for RTL
      // locales (fa, ar, he). For LTR targets the page chrome stays English,
      // so `lang="en"` remains the right value.
      syncHtmlLang() {
        const rtl = { fa: 'fa', ar: 'ar', he: 'he' };
        const next = rtl[this.targetLanguage] || 'en';
        document.documentElement.setAttribute('lang', next);
      },

      // ── Computed helpers ────────────────────────────────────────────────
      get targetLanguages() {
        // Cannot translate to the same language as the source.
        return this.languages.filter(l => l.value !== this.sourceLanguage);
      },

      get availableEngines() {
        const isFa = this.targetLanguage === 'fa';
        const tgt  = this.languages.find(l => l.value === this.targetLanguage);
        const deeplOk = !!(tgt && tgt.deepl);
        const opts = [
          { value: 'google',         label: 'Google Translate' },
          { value: 'chatgpt',        label: 'OpenAI API' },
        ];
        if (deeplOk) opts.unshift({ value: 'deepl', label: 'DeepL' });
        if (isFa)    opts.push({ value: 'chatgpt-polish', label: 'OpenAI Translation + Polish (Persian)' });
        return opts;
      },

      get showAiModel() {
        return this.engine === 'chatgpt' || this.engine === 'chatgpt-polish';
      },

      get canTranslate() {
        return this.files.length > 0 && !!this.targetLanguage && !!this.engine;
      },

      // ── Persistence on selection change ─────────────────────────────────
      onLanguageChange() {
        lsSet(LS_KEYS.source, this.sourceLanguage);
        lsSet(LS_KEYS.target, this.targetLanguage);

        // If the user just picked Persian and chatgpt-polish is available,
        // it's the right default. Otherwise prefer DeepL when available,
        // else Google.
        if (!this.availableEngines.find(o => o.value === this.engine)) {
          if (this.targetLanguage === 'fa') this.engine = 'chatgpt-polish';
          else if (this.availableEngines.find(o => o.value === 'deepl')) this.engine = 'deepl';
          else this.engine = 'google';
        }
        this.onEngineChange();
        this.syncHtmlLang();
      },

      onEngineChange() {
        // Nothing else to do today; kept as a hook so the AI-model row
        // appears/disappears naturally with `showAiModel`.
      },

      // ── File handling ───────────────────────────────────────────────────
      onDrop(e) {
        this.dragActive = false;
        const list = Array.from(e.dataTransfer?.files || []);
        this.acceptFiles(list);
      },

      onFileChosen(e) {
        const list = Array.from(e.target.files || []);
        this.acceptFiles(list);
        e.target.value = ''; // allow re-selecting the same file
      },

      acceptFiles(list) {
        this.error = '';
        for (const f of list) {
          if (this.files.length >= MAX_FILES) break;
          if (!f.name.toLowerCase().endsWith('.docx')) {
            this.error = `Skipped “${f.name}” — only .docx files are supported.`;
            continue;
          }
          if (f.size > MAX_FILE_BYTES) {
            this.error = `Skipped “${f.name}” — exceeds 50 MB limit.`;
            continue;
          }
          this.files.push(f);
        }
      },

      removeFile(idx) {
        this.files.splice(idx, 1);
      },

      formatBytes(n) {
        if (n < 1024) return `${n} B`;
        if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
        return `${(n / (1024 * 1024)).toFixed(1)} MB`;
      },

      // ── Translation flow ────────────────────────────────────────────────
      async translate() {
        if (!this.canTranslate || this.running) return;
        this.running = true;
        this.error = '';
        this.results = [];
        this.progress = 0;

        try {
          for (let i = 0; i < this.files.length; i++) {
            this.currentJobIndex = i;
            this.currentFileName = this.files[i].name;
            this.progress = 0;
            this.progressLabel = 'Uploading…';
            await this.translateOne(this.files[i]);
          }
        } catch (e) {
          this.error = e?.message || 'Unknown error.';
        } finally {
          this.running = false;
        }
      },

      async translateOne(file) {
        const fd = new FormData();
        fd.append('file', file, file.name);
        fd.append('sourceLanguage',    this.sourceLanguage);
        fd.append('targetLanguage',    this.targetLanguage);
        fd.append('translationEngine', this.engine);
        if (this.showAiModel) fd.append('aiModel', this.aiModel);
        if (this.engine === 'deepl' || this.engine === 'google') {
          // legacy backend expects splitTranslate flag; keep parity.
          fd.append('splitTranslate', 'true');
        }

        const upRes = await fetch('/upload', { method: 'POST', body: fd });
        if (!upRes.ok) throw new Error(`Upload failed (${upRes.status})`);
        const upData = await upRes.json();
        if (!upData.ok) throw new Error(upData.comment || 'Upload rejected');

        const wasCached = !!upData.cacheHit;
        if (wasCached) {
          this.progress = 100;
          this.progressLabel = 'Cached';
        }

        const status = await this.pollStatus(upData.jobId);
        this.collectResults(status, file.name, wasCached);
      },

      async pollStatus(jobId) {
        const start = Date.now();
        while (Date.now() - start < MAX_WAIT_MS) {
          await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
          let res;
          try {
            res = await fetch('/status/' + encodeURIComponent(jobId));
          } catch (_) { continue; } // transient network — retry
          if (!res.ok) continue;
          const data = await res.json();
          if (typeof data.progress === 'number') {
            this.progress = data.progress;
            this.progressLabel = labelForProgress(data.progress);
          }
          if (data.status === 'done')  return data;
          if (data.status === 'error') throw new Error(data.error || 'Translation failed.');
        }
        throw new Error('Timed out after 40 minutes.');
      },

      collectResults(status, sourceName, wasCached) {
        const push = (filename, suffixLabel) => {
          if (!filename) return;
          this.results.push({
            label:    `${stripPrefix(filename)} — ${suffixLabel}`,
            filename: stripPrefix(filename),
            href:     '/download/' + encodeURIComponent(filename),
            fromCache: wasCached,
          });
        };
        push(status.filename,  'translated');
        push(status.filename2, 'aligned (double)');
        push(status.filename3, 'aligned (classic)');
      },

      // ── Theme toggle ────────────────────────────────────────────────────
      toggleTheme() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', this.theme);
        lsSet(LS_KEYS.theme, this.theme);
      },

      // ── Newsletter ──────────────────────────────────────────────────────
      async subscribe() {
        const email = (this.newsletterEmail || '').trim();
        if (!email) return;
        this.newsletterPending = true;
        this.newsletterMessage = '';
        try {
          const res = await fetch('/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
          });
          const data = await res.json().catch(() => ({}));
          this.newsletterOk = !!data.ok;
          this.newsletterMessage = this.newsletterOk
            ? (data.message === 'already subscribed'
                ? 'You are already on the list — thanks.'
                : 'Subscribed. Welcome!')
            : (data.message || 'Could not subscribe.');
          if (this.newsletterOk) this.newsletterEmail = '';
        } catch (e) {
          this.newsletterOk = false;
          this.newsletterMessage = 'Network error. Please try again.';
        } finally {
          this.newsletterPending = false;
        }
      },
    };
  };

  // ── Helpers shared by the factory ─────────────────────────────────────────

  function stripPrefix(name) {
    // The launcher prefixes saved files with `<ms>-` for collision safety;
    // strip that for the user-facing label.
    return name.replace(/^\d{10,}-/, '');
  }

  function labelForProgress(pct) {
    if (pct >= 100) return 'Finalizing…';
    if (pct >= 90)  return 'Saving output…';
    if (pct >= 75)  return 'Aligning subtitles…';
    if (pct >= 65)  return 'Polishing translation…';
    if (pct >= 30)  return 'Translating…';
    if (pct >= 15)  return 'Sending to engine…';
    if (pct >= 10)  return 'Backend started…';
    if (pct >= 5)   return 'Queued…';
    return 'Starting…';
  }
})();
