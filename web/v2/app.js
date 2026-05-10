/* ──────────────────────────────────────────────────────────────────────────
   SMTV Document Translator — v2 client (plain JS, 2026-05-09)
   No framework. Every interactive behaviour is wired with
   addEventListener so the page survives a missing CDN, a slow network,
   or a runtime error in any other layer.

   Backend endpoints (shared with /index.ejs):
      POST /upload      → multipart: file + sourceLanguage + targetLanguage
                          + translationEngine + aiModel + splitTranslate?
                          → { ok, jobId, cacheHit }
      GET  /status/:id  → { status, progress, filename, filename2,
                            filename3, error }
      GET  /download/<name> → docx bytes
      POST /subscribe   → JSON { email } → { ok, message }
   ────────────────────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  const POLL_INTERVAL_MS = 4000;
  const MAX_WAIT_MS      = 40 * 60 * 1000;   // 40 min per file
  const MAX_FILES        = 2;
  const MAX_FILE_BYTES   = 50 * 1024 * 1024; // 50 MB

  const LS = {
    source: 'v2.savedSourceLang',
    target: 'v2.savedTargetLang',
    theme:  'v2.theme',
  };

  function lsGet(k, def) { try { return localStorage.getItem(k) ?? def; } catch (_) { return def; } }
  function lsSet(k, v)   { try { localStorage.setItem(k, v); } catch (_) {} }

  // ── Mutable state ─────────────────────────────────────────────────────────
  const state = {
    files: [],
    running: false,
    currentJobIndex: 0,
    progress: 0,
  };

  // ── DOM lookup helper — defers until the element actually exists.
  function $(id) { return document.getElementById(id); }

  // ── Boot ──────────────────────────────────────────────────────────────────
  function boot() {
    restoreTheme();
    restoreLanguages();
    syncEngineUI();
    syncSplitMethodUI();
    syncTargetEngineCascade();
    wireDropZone();
    wireFormControls();
    wireTranslateButton();
    wireNewsletter();
    wireThemeButton();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // ── Theme ────────────────────────────────────────────────────────────────
  function restoreTheme() {
    const t = lsGet(LS.theme, 'light');
    document.documentElement.setAttribute('data-theme', t);
    paintThemeIcons(t);
  }
  function paintThemeIcons(theme) {
    const light = $('themeIconLight');
    const dark  = $('themeIconDark');
    if (!light || !dark) return;
    light.classList.toggle('hidden', theme === 'dark');
    dark .classList.toggle('hidden', theme !== 'dark');
  }
  function wireThemeButton() {
    const btn = $('themeBtn');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme') || 'light';
      const next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      lsSet(LS.theme, next);
      paintThemeIcons(next);
    });
  }

  // ── Language defaults ────────────────────────────────────────────────────
  function restoreLanguages() {
    const src = $('sourceLanguage');
    const tgt = $('targetLanguage');
    if (src) src.value = lsGet(LS.source, 'en');
    if (tgt) tgt.value = lsGet(LS.target, 'fa');
  }

  // When the user picks a target language, default the engine to the
  // best fit if the current selection makes no sense any more.
  function syncTargetEngineCascade() {
    const tgt = $('targetLanguage');
    const eng = $('engine');
    if (!tgt || !eng) return;
    const onChange = () => {
      lsSet(LS.target, tgt.value);
      // If the user just picked Persian, prefer chatgpt-polish; otherwise
      // if the current engine is the Persian-only one, fall back to
      // DeepL → Google.
      if (tgt.value === 'fa' && eng.value !== 'chatgpt-polish' && eng.value !== 'chatgpt') {
        eng.value = 'chatgpt-polish';
      } else if (tgt.value !== 'fa' && eng.value === 'chatgpt-polish') {
        eng.value = 'deepl';
      }
      syncEngineUI();
      syncSplitMethodUI();
    };
    tgt.addEventListener('change', onChange);
    const src = $('sourceLanguage');
    if (src) src.addEventListener('change', () => lsSet(LS.source, src.value));
    eng.addEventListener('change', syncEngineUI);
  }

  // Toggle the AI-model field's visibility based on the chosen engine.
  function syncEngineUI() {
    const eng = $('engine');
    const aim = $('aiModelField');
    if (!eng || !aim) return;
    const showModel = (eng.value === 'chatgpt' || eng.value === 'chatgpt-polish');
    aim.classList.toggle('hidden', !showModel);
  }

  // Hide the Persian Double Lines option whenever the target language is
  // not Persian, and reset the dropdown if it was the active selection.
  // When target switches back to Persian, the option becomes visible and
  // is auto-selected as the default Split Method.
  function syncSplitMethodUI() {
    const tgt = $('targetLanguage');
    const sel = $('splitEngine');
    if (!tgt || !sel) return;
    const pdl = sel.querySelector('option[value="persian_double_lines"]');
    if (!pdl) return;
    if (tgt.value === 'fa') {
      pdl.hidden = false;
      pdl.disabled = false;
      sel.value = 'persian_double_lines';
    } else {
      if (sel.value === 'persian_double_lines') sel.value = 'basic';
      pdl.hidden = true;
      pdl.disabled = true;
    }
  }

  // ── Drop zone + file input ───────────────────────────────────────────────
  function wireDropZone() {
    const zone  = $('dropZone');
    const input = $('fileInput');
    if (!zone || !input) return;

    // Click anywhere on the zone (except on the input itself) → open dialog.
    zone.addEventListener('click', (e) => {
      if (e.target === input) return;
      input.click();
    });
    zone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        input.click();
      }
    });

    // Drag-and-drop visual feedback + file capture.
    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('drag-active');
    });
    zone.addEventListener('dragleave', () => {
      zone.classList.remove('drag-active');
    });
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('drag-active');
      const list = e.dataTransfer ? Array.from(e.dataTransfer.files) : [];
      acceptFiles(list);
    });

    input.addEventListener('change', () => {
      acceptFiles(Array.from(input.files || []));
      input.value = ''; // allow re-selecting the same file
    });
  }

  function acceptFiles(list) {
    clearError();
    for (const f of list) {
      if (state.files.length >= MAX_FILES) break;
      if (!f.name.toLowerCase().endsWith('.docx')) {
        showError(`Skipped "${f.name}" — only .docx files are accepted.`);
        continue;
      }
      if (f.size > MAX_FILE_BYTES) {
        showError(`Skipped "${f.name}" — file is larger than 50 MB.`);
        continue;
      }
      state.files.push(f);
    }
    renderFileList();
    updateActionRow();
  }

  function renderFileList() {
    const ul = $('fileList');
    if (!ul) return;
    ul.innerHTML = '';
    state.files.forEach((f, idx) => {
      const li = document.createElement('li');
      li.className = 'file-row';
      li.innerHTML = `
        <span class="file-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M14 3v5h5M6 3h8l5 5v13H6V3z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
          </svg>
        </span>
        <span class="file-name"></span>
        <span class="file-size tabular"></span>
        <button type="button" class="file-remove" aria-label="Remove file">✕</button>
      `;
      li.querySelector('.file-name').textContent = f.name;
      li.querySelector('.file-size').textContent = formatBytes(f.size);
      li.querySelector('.file-remove').addEventListener('click', () => {
        state.files.splice(idx, 1);
        renderFileList();
        updateActionRow();
      });
      ul.appendChild(li);
    });
    ul.classList.toggle('hidden', state.files.length === 0);
  }

  function updateActionRow() {
    const btn  = $('translateBtn');
    const note = $('fileSelectedNote');
    if (btn) btn.disabled = state.files.length === 0 || state.running;
    if (note) {
      if (!state.files.length) { note.classList.add('hidden'); note.textContent = ''; }
      else if (state.files.length === 1) { note.classList.remove('hidden'); note.textContent = '1 file selected'; }
      else                                { note.classList.remove('hidden'); note.textContent = '2 files queued (max)'; }
    }
  }

  // ── Form change persistence ─────────────────────────────────────────────
  function wireFormControls() { /* persistence handled in syncTargetEngineCascade */ }

  // ── Translate button ─────────────────────────────────────────────────────
  function wireTranslateButton() {
    const btn = $('translateBtn');
    if (!btn) return;
    btn.disabled = true;
    btn.addEventListener('click', () => { void runTranslation(); });
  }

  async function runTranslation() {
    if (!state.files.length || state.running) return;
    state.running = true;
    showRunningButton(true);
    clearError();
    clearResults();
    setProgress(0, 'Starting…');
    showProgress(true);

    try {
      for (let i = 0; i < state.files.length; i++) {
        state.currentJobIndex = i;
        updateProgressJob();
        setProgress(0, 'Uploading…');
        await translateOne(state.files[i]);
      }
    } catch (e) {
      showError((e && e.message) ? e.message : 'Unknown error');
    } finally {
      state.running = false;
      showRunningButton(false);
      showProgress(false);
      updateActionRow();
    }
  }

  async function translateOne(file) {
    const fd = new FormData();
    fd.append('file', file, file.name);
    fd.append('sourceLanguage',    $('sourceLanguage').value);
    fd.append('targetLanguage',    $('targetLanguage').value);
    fd.append('translationEngine', $('engine').value);
    const eng = $('engine').value;
    if (eng === 'chatgpt' || eng === 'chatgpt-polish') {
      fd.append('aiModel', $('aiModel').value);
    }
    const splitSelectEl = $('splitEngine');
    const splitVal = splitSelectEl ? splitSelectEl.value : 'basic';
    // Persian Double Lines is a post-translate step: it pairs with any
    // engine, so toggling splitTranslate here covers chatgpt-polish too.
    if (eng === 'google' || eng === 'deepl' || splitVal === 'persian_double_lines') {
      fd.append('splitTranslate', 'true');
    }
    if (splitVal && splitVal !== 'basic') {
      fd.append('splitEngine', splitVal);
    }

    const upRes = await fetch('/upload', { method: 'POST', body: fd });
    if (!upRes.ok) throw new Error(`Upload failed (HTTP ${upRes.status})`);
    const upData = await upRes.json();
    if (!upData.ok) throw new Error(upData.comment || 'Upload rejected');

    const wasCached = !!upData.cacheHit;
    if (wasCached) setProgress(100, 'Cached — instant download');

    const status = await pollStatus(upData.jobId);
    pushResults(status, wasCached);
  }

  async function pollStatus(jobId) {
    const start = Date.now();
    while (Date.now() - start < MAX_WAIT_MS) {
      await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
      let res;
      try { res = await fetch('/status/' + encodeURIComponent(jobId)); }
      catch (_) { continue; }
      if (!res.ok) continue;
      const data = await res.json();
      if (typeof data.progress === 'number') setProgress(data.progress, bucketLabel(data.progress));
      if (data.status === 'done')  return data;
      if (data.status === 'error') throw new Error(data.error || 'Translation failed');
    }
    throw new Error('Timed out waiting for the backend');
  }

  function bucketLabel(pct) {
    if (pct >= 100) return 'Finalising…';
    if (pct >=  90) return 'Saving output…';
    if (pct >=  75) return 'Aligning subtitles…';
    if (pct >=  65) return 'Polishing translation…';
    if (pct >=  30) return 'Translating…';
    if (pct >=  15) return 'Sending to backend…';
    if (pct >=  10) return 'Backend started…';
    if (pct >=   5) return 'Queued…';
    return 'Starting…';
  }

  // ── DOM mutations: progress, error, results ─────────────────────────────
  function setProgress(pct, label) {
    state.progress = pct;
    const fill  = $('progressFill');
    const pctEl = $('progressPct');
    const lbl   = $('progressLabel');
    const blbl  = $('btnRunningLabel');
    if (fill)  fill.style.width = pct + '%';
    if (pctEl) pctEl.textContent = pct + '%';
    if (lbl)   lbl.textContent   = label;
    if (blbl)  blbl.textContent  = label;
  }

  function showProgress(on) {
    const box = $('progressBox');
    if (box) box.classList.toggle('hidden', !on);
  }

  function updateProgressJob() {
    const el = $('progressJob');
    if (!el) return;
    const idx = state.currentJobIndex + 1;
    const total = state.files.length;
    const name = state.files[state.currentJobIndex] ? state.files[state.currentJobIndex].name : '';
    el.textContent = `Job ${idx} of ${total} · ${name}`;
  }

  function showRunningButton(on) {
    const idle = $('btnIdle');
    const run  = $('btnRunning');
    const btn  = $('translateBtn');
    if (idle) idle.classList.toggle('hidden',  on);
    if (run)  run.classList.toggle('hidden', !on);
    if (btn)  btn.disabled = on || state.files.length === 0;
  }

  function showError(msg) {
    const box = $('errorBox');
    const txt = $('errorText');
    if (txt) txt.textContent = msg;
    if (box) box.classList.remove('hidden');
  }
  function clearError() {
    const box = $('errorBox');
    const txt = $('errorText');
    if (txt) txt.textContent = '';
    if (box) box.classList.add('hidden');
  }

  function clearResults() {
    const ul = $('resultsList');
    if (!ul) return;
    ul.innerHTML = '';
    ul.classList.add('hidden');
  }

  function pushResults(status, wasCached) {
    const ul = $('resultsList');
    if (!ul) return;
    const add = (filename, suffix) => {
      if (!filename) return;
      const display = stripPrefix(filename);
      const li = document.createElement('li');
      li.className = 'result-row';
      li.innerHTML = `
        <span class="result-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M14 3v5h5M6 3h8l5 5v13H6V3z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
          </svg>
        </span>
        <span class="result-label"></span>
        <a class="result-link"></a>
      `;
      li.querySelector('.result-label').textContent = `${display} — ${suffix}` + (wasCached ? '  (cached)' : '');
      const a = li.querySelector('.result-link');
      a.href = '/download/' + encodeURIComponent(filename);
      a.setAttribute('download', display);
      a.textContent = 'Download';
      ul.appendChild(li);
    };
    add(status.filename,  'translated');
    add(status.filename2, 'aligner double');
    add(status.filename3, 'classic split');
    if (ul.children.length) ul.classList.remove('hidden');
  }

  // ── Newsletter ───────────────────────────────────────────────────────────
  function wireNewsletter() {
    const form = $('newsletterForm');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = $('newsletterEmail');
      const btn   = $('newsletterBtn');
      const msg   = $('newsletterMsg');
      const email = (input.value || '').trim();
      if (!email) return;
      if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }
      try {
        const res  = await fetch('/subscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });
        const data = await res.json().catch(() => ({}));
        const ok = !!data.ok;
        if (msg) {
          msg.textContent = ok
            ? (data.message === 'already subscribed' ? 'You are already on the list.' : 'Welcome! You will hear from us only on major releases.')
            : (data.message || 'Subscription failed. Please try again.');
          msg.classList.toggle('msg-ok',  ok);
          msg.classList.toggle('msg-err', !ok);
          msg.classList.remove('hidden');
        }
        if (ok && input) input.value = '';
      } catch (_) {
        if (msg) {
          msg.textContent = 'Network error. Please try again.';
          msg.classList.add('msg-err');
          msg.classList.remove('msg-ok');
          msg.classList.remove('hidden');
        }
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Subscribe'; }
      }
    });
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  function stripPrefix(name) { return name.replace(/^\d{10,}-/, ''); }
  function formatBytes(n) {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  }
})();
