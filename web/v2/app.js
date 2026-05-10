/* ──────────────────────────────────────────────────────────────────────────
   SMTV Document Translator — v2 client (plain JS, 2026-05-09)
   No framework. Every interactive behaviour is wired with
   addEventListener so the page survives a missing CDN, a slow network,
   or a runtime error in any other layer.

   Backend endpoints (shared with /index.ejs):
      POST /upload      → multipart: file + sourceLanguage + targetLanguage
                          + translationEngine + aiModel + splitTranslate?
                          → { ok, jobId, cacheHit }
      GET  /status/:id  → { status, progress, filename, error }
      Cache-hit response also carries { cacheHit: true,
                                        splitterOnly: bool }
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
    source:    'v2.savedSourceLang',
    target:    'v2.savedTargetLang',
    theme:     'v2.theme',
    sessionCost: 'v2.sessionCostUsd',  // U-4 (2026-05-11 audit)
  };

  function lsGet(k, def) { try { return localStorage.getItem(k) ?? def; } catch (_) { return def; } }
  function lsSet(k, v)   { try { localStorage.setItem(k, v); } catch (_) {} }

  // ── Mutable state ─────────────────────────────────────────────────────────
  const state = {
    files: [],
    running: false,
    currentJobIndex: 0,
    progress: 0,
    currentJobId: null,    // U-1 (2026-05-11 audit) — for /cancel/<id>
    pricing: null,         // U-2 — populated from /pricing on boot
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
    syncDocumentDir();
    wireDropZone();
    wireFormControls();
    wireTranslateButton();
    wireCancelButton();      // U-1
    wireNewsletter();
    wireThemeButton();
    wireOfflineBanner();     // U-5
    paintFooterBuild();
    paintFooterCost();       // U-4
    void loadAndRenderContent();
    void loadPricing();      // U-2
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
      syncDocumentDir();
    };
    tgt.addEventListener('change', onChange);
    const src = $('sourceLanguage');
    if (src) src.addEventListener('change', () => {
      lsSet(LS.source, src.value);
      syncDocumentDir();
    });
    eng.addEventListener('change', syncEngineUI);
  }

  // Set <html dir="rtl"> when the source OR target language is RTL so the
  // Persian / Arabic / Hebrew side gets correct alignment + Vazirmatn font
  // without dragging the entire UI rightward (the form labels stay LTR
  // because the language picker is *English* — switching the whole page
  // just because the target is FA was confusing during testing).
  // Heuristic: if EITHER side is RTL, lean RTL. Saves the user from having
  // to toggle by hand.
  function syncDocumentDir() {
    const RTL = new Set(['fa', 'ar', 'he', 'ur']);
    const src = $('sourceLanguage');
    const tgt = $('targetLanguage');
    const wantRTL =
      (src && RTL.has((src.value || '').toLowerCase())) ||
      (tgt && RTL.has((tgt.value || '').toLowerCase()));
    document.documentElement.setAttribute('dir', wantRTL ? 'rtl' : 'ltr');
  }

  // Toggle the AI-model field's visibility based on the chosen engine.
  function syncEngineUI() {
    const eng = $('engine');
    const aim = $('aiModelField');
    if (!eng || !aim) return;
    const showModel = (eng.value === 'chatgpt' || eng.value === 'chatgpt-polish');
    aim.classList.toggle('hidden', !showModel);
    paintCostEstimate();   // U-2: engine change can flip estimator on/off
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
    paintCostEstimate();   // U-2
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
  function wireFormControls() {
    // U-2: re-paint the cost estimate whenever the AI model changes too.
    const aim = $('aiModel');
    if (aim) aim.addEventListener('change', paintCostEstimate);
  }

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
      // F-2: surface the structured reason token alongside the message.
      showError((e && e.message) ? e.message : 'Unknown error', (e && e.reason) || '');
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

    state.currentJobId = upData.jobId;     // U-1: needed by Cancel
    showCancelButton(true);

    const wasCached    = !!upData.cacheHit;
    const splitterOnly = !!upData.splitterOnly;
    if (wasCached) {
      // Phase 12 banner: distinguish "cache hit, splitter applied" from
      // "cache hit, identical output". Only the splitter case implies
      // that the user just re-ran with a different Split Method.
      setProgress(100, splitterOnly
        ? 'Translated text reused from cache; only the split was redone'
        : 'Cached — instant download');
    }

    let status;
    try {
      status = await pollStatus(upData.jobId);
    } finally {
      state.currentJobId = null;
      showCancelButton(false);
    }
    pushResults(status, wasCached, splitterOnly);

    // U-4: pull the sidecar cost (chatgpt-polish only) and add to session total.
    if (status && status.filename) {
      void accumulateSidecarCost(status.filename);
    }
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
      if (data.status === 'done')      return data;
      if (data.status === 'cancelled') throw new Error('Cancelled by user');
      if (data.status === 'error') {
        // F-2 (2026-05-11 audit): backend's `error` field carries
        // `<reason>: <message>` when the run hit a structured failure
        // (B-001 / [FAIL] line). Split off the leading token so we can
        // surface it as a category badge in the UI.
        const raw = data.error || 'Translation failed';
        const m = /^([a-z][a-z0-9_]+):\s+(.*)$/i.exec(raw);
        const err = new Error(m ? m[2] : raw);
        if (m) err.reason = m[1];
        throw err;
      }
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

  function showError(msg, reason) {
    const box    = $('errorBox');
    const txt    = $('errorText');
    const badge  = $('errorReason');
    if (txt)   txt.textContent = msg;
    if (badge) {
      if (reason) {
        badge.textContent = reason;
        badge.classList.remove('hidden');
      } else {
        badge.textContent = '';
        badge.classList.add('hidden');
      }
    }
    if (box) box.classList.remove('hidden');
  }
  function clearError() {
    const box   = $('errorBox');
    const txt   = $('errorText');
    const badge = $('errorReason');
    if (txt) txt.textContent = '';
    if (badge) { badge.textContent = ''; badge.classList.add('hidden'); }
    if (box) box.classList.add('hidden');
  }

  function clearResults() {
    const ul = $('resultsList');
    if (!ul) return;
    ul.innerHTML = '';
    ul.classList.add('hidden');
  }

  function pushResults(status, wasCached, splitterOnly) {
    const ul = $('resultsList');
    if (!ul) return;
    const tag = splitterOnly
      ? '  (cached — splitter only)'
      : (wasCached ? '  (cached)' : '');
    const add = (filename, suffix) => {
      if (!filename) return;
      const display = stripPrefix(filename);
      const li = document.createElement('li');
      li.className = 'result-row';
      const iconSpan = document.createElement('span');
      iconSpan.className = 'result-icon';
      iconSpan.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M14 3v5h5M6 3h8l5 5v13H6V3z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';
      const lbl = document.createElement('span');
      lbl.className = 'result-label';
      lbl.textContent = `${display} — ${suffix}${tag}`;
      const a = document.createElement('a');
      a.className = 'result-link';
      a.href = '/download/' + encodeURIComponent(filename);
      a.setAttribute('download', display);
      a.textContent = 'Download';
      li.appendChild(iconSpan);
      li.appendChild(lbl);
      li.appendChild(a);
      ul.appendChild(li);
    };
    add(status.filename, 'translated');

    // U-3 (2026-05-11 audit): chatgpt-polish runs always emit a JSON
    // sidecar at <docx_stem>_log.json next to the .docx. Surface a
    // download link for it whenever the pair travels together.
    if (status && status.filename && /\.docx$/i.test(status.filename)) {
      const sidecar = status.filename.replace(/\.docx$/i, '_log.json');
      // We don't pre-flight HEAD it; if the sidecar doesn't exist the
      // browser shows a 404 in the download dialog. This is cheaper
      // than an extra round-trip and the link is visually muted to
      // signal it's optional.
      const li = document.createElement('li');
      li.className = 'result-row result-row--secondary';
      const iconSpan = document.createElement('span');
      iconSpan.className = 'result-icon';
      iconSpan.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 8h6M9 12h6M9 16h4M14 3v5h5M6 3h8l5 5v13H6V3z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>';
      const lbl = document.createElement('span');
      lbl.className = 'result-label';
      lbl.textContent = 'Run log (tokens + cost)';
      const a = document.createElement('a');
      a.className = 'result-link';
      a.href = '/download/' + encodeURIComponent(sidecar);
      a.setAttribute('download', stripPrefix(sidecar));
      a.textContent = 'Download log JSON';
      li.appendChild(iconSpan);
      li.appendChild(lbl);
      li.appendChild(a);
      ul.appendChild(li);
    }

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

  // ── Content (announcements + stories from /v2/content.json) ────────────
  //
  // The page degrades gracefully when content.json is unreachable (offline
  // mode, dev-time syntax error, 404). Empty content blocks just hide the
  // surrounding section instead of rendering a broken card.
  async function loadAndRenderContent() {
    let payload = null;
    try {
      const res = await fetch('/v2/content.json', { cache: 'no-store' });
      if (res.ok) payload = await res.json();
    } catch (_) { /* offline / parse error — fall through to empty render */ }
    payload = payload && typeof payload === 'object' ? payload : {};
    renderAnnouncements(Array.isArray(payload.announcements) ? payload.announcements : []);
    renderStories(Array.isArray(payload.stories) ? payload.stories : []);
  }

  function renderAnnouncements(items) {
    const ol = $('announcementsList');
    if (!ol) return;
    ol.innerHTML = '';
    if (!items.length) {
      const li = document.createElement('li');
      li.className = 'announce-empty';
      li.textContent = 'No announcements yet.';
      ol.appendChild(li);
      return;
    }
    for (const a of items) {
      const li = document.createElement('li');
      li.className = 'announce-item';
      // Build the three pieces explicitly so anything in the JSON that
      // isn't a string is silently rendered as empty — defensive against
      // editor mistakes in content.json.
      const dateEl = document.createElement('span');
      dateEl.className = 'announce-date tabular';
      dateEl.textContent = String(a.date || '');
      const titleEl = document.createElement('h3');
      titleEl.className = 'announce-title';
      titleEl.textContent = String(a.title || '');
      const bodyEl = document.createElement('p');
      bodyEl.className = 'announce-body';
      bodyEl.textContent = String(a.body || '');
      if (dateEl.textContent)  li.appendChild(dateEl);
      if (titleEl.textContent) li.appendChild(titleEl);
      if (bodyEl.textContent)  li.appendChild(bodyEl);
      ol.appendChild(li);
    }
  }

  function renderStories(items) {
    const grid = $('storiesGrid');
    if (!grid) return;
    grid.innerHTML = '';
    // Hide the surrounding section when there's nothing to show — the
    // header would dangle awkwardly.
    const section = grid.closest('.stories-section');
    if (!items.length) {
      if (section) section.classList.add('hidden');
      return;
    }
    if (section) section.classList.remove('hidden');
    for (const s of items) {
      const card = document.createElement('article');
      card.className = 'story-card';
      if (s.badge) {
        const b = document.createElement('span');
        b.className = 'story-badge';
        b.textContent = String(s.badge);
        card.appendChild(b);
      }
      if (s.title) {
        const h = document.createElement('h3');
        h.className = 'story-title';
        h.textContent = String(s.title);
        card.appendChild(h);
      }
      if (s.summary) {
        const p = document.createElement('p');
        p.className = 'story-summary';
        p.textContent = String(s.summary);
        card.appendChild(p);
      }
      if (s.link) {
        const a = document.createElement('a');
        a.className = 'story-link';
        a.href = String(s.link);
        a.target = '_blank';
        a.rel = 'noopener';
        a.textContent = 'Read more →';
        card.appendChild(a);
      }
      grid.appendChild(card);
    }
  }

  // ── Footer build line — small, harmless, gives a release-watcher a
  // visible signal that they're on the right deploy. The build slug is
  // injected at deploy time from a meta tag if present; otherwise we
  // show today's UTC date so a stale tab is obvious.
  function paintFooterBuild() {
    const el = $('footerBuild');
    if (!el) return;
    const slug = (document.querySelector('meta[name="build-slug"]') || {}).content || '';
    const today = new Date().toISOString().slice(0, 10);
    el.textContent = slug ? `build ${slug}` : `build ${today}`;
  }

  // ── Cancel button (U-1 2026-05-11 audit) ────────────────────────────────
  function wireCancelButton() {
    const btn = $('cancelBtn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      if (!state.currentJobId) return;
      btn.disabled = true;
      try {
        await fetch('/cancel/' + encodeURIComponent(state.currentJobId), { method: 'POST' });
      } catch (_) { /* the poll loop will surface the cancelled status */ }
    });
  }
  function showCancelButton(on) {
    const btn = $('cancelBtn');
    if (!btn) return;
    btn.classList.toggle('hidden', !on);
    btn.disabled = !on;
  }

  // ── Offline banner (U-5 2026-05-11) ─────────────────────────────────────
  function wireOfflineBanner() {
    const update = () => {
      const banner = $('offlineBanner');
      if (!banner) return;
      banner.classList.toggle('hidden', !!navigator.onLine);
    };
    update();
    window.addEventListener('online',  update);
    window.addEventListener('offline', update);
  }

  // ── Pricing fetch + cost estimate (U-2 2026-05-11) ──────────────────────
  async function loadPricing() {
    try {
      const res = await fetch('/pricing', { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      if (data && Array.isArray(data.models)) {
        state.pricing = data.models;
        paintCostEstimate();
      }
    } catch (_) { /* offline / endpoint missing — silent */ }
  }

  function paintCostEstimate() {
    const el = $('costEstimate');
    if (!el) return;
    if (!state.pricing || !state.pricing.length) {
      el.classList.add('hidden');
      return;
    }
    const eng = $('engine');
    const aim = $('aiModel');
    if (!eng || !aim) return;
    const usesOpenAI = (eng.value === 'chatgpt' || eng.value === 'chatgpt-polish');
    if (!usesOpenAI || state.files.length === 0) {
      el.classList.add('hidden');
      return;
    }
    const model = state.pricing.find(m => m.id === aim.value);
    if (!model) { el.classList.add('hidden'); return; }
    // Rough cost estimate: 1 token ≈ 4 chars; size is in bytes. The
    // chatgpt-polish path makes two calls (translate + polish) so the
    // input is read twice. Output tokens are roughly source × 1.0 for
    // most languages; ZWNJ-heavy Persian skews higher but we keep the
    // estimate conservative by assuming output_tokens ≈ input_tokens.
    const totalBytes = state.files.reduce((acc, f) => acc + f.size, 0);
    const inputTokens = Math.round(totalBytes / 4);
    const calls       = (eng.value === 'chatgpt-polish') ? 2 : 1;
    const inputCost   = (inputTokens / 1_000_000) * model.input  * calls;
    const outputCost  = (inputTokens / 1_000_000) * model.output * calls;
    const total = inputCost + outputCost;
    // Cache hits could cut the bill ~10× — note that on the badge.
    el.textContent = `Estimated cost: ~$${total.toFixed(3)} (cache hits ≈ $${(total * 0.18).toFixed(3)})`;
    el.classList.remove('hidden');
  }

  // ── Session-cost accumulator (U-4 2026-05-11) ───────────────────────────
  async function accumulateSidecarCost(docxFilename) {
    if (!docxFilename || !/\.docx$/i.test(docxFilename)) return;
    const sidecar = docxFilename.replace(/\.docx$/i, '_log.json');
    let log = null;
    try {
      const res = await fetch('/download/' + encodeURIComponent(sidecar), { cache: 'no-store' });
      if (!res.ok) return;
      log = await res.json();
    } catch (_) { return; }
    const dollars = log && log.summary && typeof log.summary.total_cost_usd === 'number'
      ? log.summary.total_cost_usd : 0;
    if (!dollars) return;
    const prev = parseFloat(lsGet(LS.sessionCost, '0')) || 0;
    const next = prev + dollars;
    lsSet(LS.sessionCost, String(next));
    paintFooterCost();
  }

  function paintFooterCost() {
    const el = $('footerCost');
    if (!el) return;
    const total = parseFloat(lsGet(LS.sessionCost, '0')) || 0;
    el.textContent = total > 0 ? `· session: $${total.toFixed(3)}` : '';
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  function stripPrefix(name) { return name.replace(/^\d{10,}-/, ''); }
  function formatBytes(n) {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  }
})();
