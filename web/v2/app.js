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
   i18n: see web/v2/i18n.json. Loaded once during init() before render.
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

  const LS_KEYS = {
    source: 'v2.savedSourceLang',
    target: 'v2.savedTargetLang',
    theme:  'v2.theme',
    locale: 'v2.locale',
  };

  function lsGet(k, def) { try { return localStorage.getItem(k) ?? def; } catch (_) { return def; } }
  function lsSet(k, v)   { try { localStorage.setItem(k, v); } catch (_) {} }

  // Best-effort initial locale: persisted choice → navigator language
  // prefix → 'en'. Persian Speakers landing on this page get a Persian
  // UI without any clicks. The user can flip via the header toggle.
  function detectLocale() {
    const saved = lsGet(LS_KEYS.locale, null);
    if (saved === 'en' || saved === 'fa') return saved;
    const nav = (navigator.language || 'en').toLowerCase();
    if (nav.startsWith('fa')) return 'fa';
    return 'en';
  }

  // The progressLabel mapping has 9 buckets; each maps to an i18n key
  // resolved at render time so the spinner text reads in the active locale.
  // Order matters — first match wins.
  const PROGRESS_BUCKETS = [
    [100, 'progress_finalizing'],
    [ 90, 'progress_saving'],
    [ 75, 'progress_aligning'],
    [ 65, 'progress_polishing'],
    [ 30, 'progress_translating'],
    [ 15, 'progress_sending'],
    [ 10, 'progress_backend'],
    [  5, 'progress_queued'],
    [  0, 'progress_starting'],
  ];

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
      progressKey: 'progress_ready',     // i18n key — `progressLabel` getter resolves it

      results: [],
      error: '',

      newsletterEmail: '',
      newsletterPending: false,
      newsletterMessage: '',
      newsletterOk: false,

      theme: lsGet(LS_KEYS.theme, 'light'),
      locale: detectLocale(),
      i18n: { en: {}, fa: {} },

      // ── Init ─────────────────────────────────────────────────────────────
      async init() {
        document.documentElement.setAttribute('data-theme', this.theme);
        // Load i18n strings BEFORE Alpine paints the body — bound t() lookups
        // would otherwise show raw keys for one frame.
        await this.loadI18n();
        // Pick a sensible default engine for the saved target language.
        this.onLanguageChange();
        this.syncHtmlLang();
      },

      async loadI18n() {
        try {
          const res = await fetch('/v2/i18n.json', { cache: 'no-cache' });
          if (res.ok) this.i18n = await res.json();
        } catch (_) {
          // Network failure — keep the empty default; t() falls back to keys.
        }
      },

      // Translate a key. Falls back: active locale → English → key itself.
      // {placeholders} can be filled by passing an object as second arg.
      t(key, vars) {
        const here = (this.i18n && this.i18n[this.locale]) || {};
        const en   = (this.i18n && this.i18n.en)           || {};
        let out = (here[key] ?? en[key] ?? key);
        if (vars && typeof out === 'string') {
          for (const k of Object.keys(vars)) {
            out = out.replaceAll(`{${k}}`, String(vars[k]));
          }
        }
        return out;
      },

      // <html dir + lang> tracks the UI locale. Body chrome reads RTL when
      // the locale is Persian/Arabic regardless of the document target.
      syncHtmlLang() {
        const rtl = { fa: 'fa', ar: 'ar', he: 'he' };
        document.documentElement.setAttribute('lang', rtl[this.locale] || 'en');
        document.documentElement.setAttribute('dir',  this.locale === 'fa' ? 'rtl' : 'ltr');
      },

      toggleLocale() {
        this.locale = this.locale === 'fa' ? 'en' : 'fa';
        lsSet(LS_KEYS.locale, this.locale);
        this.syncHtmlLang();
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

      // Progress label getter — resolves the bucket key to a localised string
      // every time it's read, so toggling locale mid-job updates the spinner.
      get progressLabel() {
        return this.t(this.progressKey);
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
            this.error = this.t('err_skipped_not_docx', { name: f.name });
            continue;
          }
          if (f.size > MAX_FILE_BYTES) {
            this.error = this.t('err_skipped_too_big', { name: f.name });
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
            this.progressKey = 'progress_uploading';
            await this.translateOne(this.files[i]);
          }
        } catch (e) {
          this.error = e?.message || this.t('err_unknown');
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
        if (!upRes.ok) throw new Error(this.t('err_upload_failed', { status: upRes.status }));
        const upData = await upRes.json();
        if (!upData.ok) throw new Error(upData.comment || this.t('err_upload_rejected'));

        const wasCached = !!upData.cacheHit;
        if (wasCached) {
          this.progress = 100;
          this.progressKey = 'progress_cached';
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
            this.progressKey = bucketKey(data.progress);
          }
          if (data.status === 'done')  return data;
          if (data.status === 'error') throw new Error(data.error || this.t('err_translation_failed'));
        }
        throw new Error(this.t('err_timeout'));
      },

      collectResults(status, sourceName, wasCached) {
        const push = (filename, suffixKey) => {
          if (!filename) return;
          this.results.push({
            label:    `${stripPrefix(filename)} — ${this.t(suffixKey)}`,
            filename: stripPrefix(filename),
            href:     '/download/' + encodeURIComponent(filename),
            fromCache: wasCached,
          });
        };
        push(status.filename,  'results_translated');
        push(status.filename2, 'results_double');
        push(status.filename3, 'results_classic');
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
                ? this.t('newsletter_already')
                : this.t('newsletter_welcome'))
            : (data.message || this.t('newsletter_failed'));
          if (this.newsletterOk) this.newsletterEmail = '';
        } catch (e) {
          this.newsletterOk = false;
          this.newsletterMessage = this.t('newsletter_network');
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

  function bucketKey(pct) {
    for (const [floor, key] of PROGRESS_BUCKETS) {
      if (pct >= floor) return key;
    }
    return 'progress_starting';
  }
})();
