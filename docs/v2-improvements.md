# v2 Frontend — Improvement Proposals

> **Saved 2026-05-16.** A companion design document to the rebuilt `web/v2/` SPA.
> The interactive prototype lives at `v2-improvements.html` in the design project.
> Twelve proposals, plus a version switcher between the legacy `/` UI and the
> new `/v2/` UI, persisted in `localStorage` under `mtd.uiPref`.

---

## خلاصه فارسی

پروژهٔ شما در شرایط فعلی پایهٔ خوبی دارد: چیدمان سه‌ستونهٔ smch.ir-مانند،
نمایش پیشرفت واقعی، کارت خلاصهٔ اجرا، بایگانی خطاها. این سند دوازده پیشنهاد
برای تبدیل v2 به ابزار روزانهٔ کاربران ارائه می‌دهد. ترتیب پیشنهادها بر مبنای
نسبت **تأثیر به تلاش** است؛ سه پیشنهاد اول از همه ارزشمندترند.

علاوه بر آن، طراحی یک **کلید سوئیچ بین v1 و v2** که در حافظهٔ مرورگر ذخیره
می‌شود و در بازدید بعدی همان نسخه را باز می‌کند، در §0 توضیح داده شده است.
سه گونهٔ پیشنهادی (Pill / FAB / Dropdown) معرفی شده‌اند، و نوع **Pill** به‌عنوان
گزینهٔ پیشنهادی معرفی می‌شود. کد کامل آماده برای چسباندن در §3 آمده.

---

## §0 — Version switcher

A two-state toggle that lets a user pick which UI they prefer; the choice is
persisted to `localStorage` and applied as a redirect on subsequent visits.

### Behaviour spec

1. On every page load, **before paint**, read `localStorage.mtd.uiPref`.
   - `'v1'` and currently on `/v2/*` → `location.replace('/')`
   - `'v2'` and currently on `/` → `location.replace('/v2/')`
   - missing → no redirect (user lands wherever the link took them)
2. The toggle in the header reads the **current URL** for its initial state,
   not the preference — so a deliberate visit to the other version always
   shows the right toggle state.
3. Clicking the other side: write the new pref and navigate to that URL.
4. Provide a "Clear preference" affordance somewhere (Display Preferences
   dialog is a good home) so a user can return to per-visit default.

### Three shapes considered

| Shape | Pros | Cons | Verdict |
|---|---|---|---|
| **A · Header pill** (recommended) | Always visible, one-click flip, low visual weight | Two visible states cost a bit of header real estate | **Ship this** |
| B · Floating dock pill | Out of the way, can grow into a small dock later | Lower discoverability, occludes content on mobile | Defer |
| C · Brand-name dropdown | Highest scalability for future versions | Two-click interaction; menu feels heavy for two items | Use when ≥ 3 versions exist |

### Drop-in code (option A)

**Step 1 — Redirect shim** (`<head>` of both `index.ejs` and `web/v2/index.html`):

```html
<script>
  (function () {
    const pref = localStorage.getItem('mtd.uiPref'); // 'v1' | 'v2' | null
    const onV2 = location.pathname.startsWith('/v2');
    if (pref === 'v1' && onV2)  location.replace('/');
    if (pref === 'v2' && !onV2) location.replace('/v2/');
  })();
</script>
```

**Step 2 — Toggle markup** (header nav, both pages):

```html
<div class="ui-switch" id="uiSwitch" role="group" aria-label="Choose UI version">
  <span class="ui-switch-knob" aria-hidden="true"></span>
  <button type="button" data-go="v1">Classic</button>
  <button type="button" data-go="v2">Modern</button>
</div>
```

**Step 3 — Wiring** (inline script, near end of body):

```html
<script>
  (function () {
    const sw = document.getElementById('uiSwitch');
    if (!sw) return;
    const here = location.pathname.startsWith('/v2') ? 'v2' : 'v1';
    sw.dataset.on = here;
    sw.querySelectorAll('button').forEach(function (b) {
      b.classList.toggle('is-on', b.dataset.go === here);
      b.addEventListener('click', function () {
        const go = b.dataset.go;
        localStorage.setItem('mtd.uiPref', go);
        location.assign(go === 'v2' ? '/v2/' : '/');
      });
    });
  })();
</script>
```

**Step 4 — Styles** (Claude warm palette — paste into `web/v2/styles.css` and the
equivalent stylesheet for the legacy UI):

```css
.ui-switch {
  display: inline-flex; position: relative;
  background: #faf9f5;
  border: 1px solid #e6dfd8; border-radius: 9999px;
  padding: 3px;
}
.ui-switch button {
  position: relative; z-index: 1;
  background: transparent; border: none; cursor: pointer;
  padding: 7px 16px; border-radius: 9999px;
  font: 500 13px/1 Inter, sans-serif;
  color: #6c6a64;
  transition: color 120ms;
}
.ui-switch button.is-on { color: #ffffff; }
.ui-switch-knob {
  position: absolute; top: 3px; bottom: 3px; left: 3px;
  width: calc(50% - 3px);
  background: #cc785c;
  border-radius: 9999px;
  transition: transform 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
.ui-switch[data-on="v2"] .ui-switch-knob { transform: translateX(100%); }
```

---

## §1 — Twelve proposals

Ordered roughly by priority. Impact and effort are estimates; numbers are not strict.

### 01 · In-page bilingual preview before download · _impact: high · effort: medium_

After a successful run, render the translated paragraphs **inline** alongside
the source rows (RTL-aware for Persian/Arabic/Hebrew/Urdu). Users find problems
before they download. The polish layer already preserves row identity in the
sidecar JSON — surface it.

- Frontend: a tab/accordion on the run-summary card with a two-column reader.
- Backend: a new endpoint `GET /preview/:jobId` that streams the rendered
  paragraphs (or reads them from the docx server-side and returns JSON).

### 02 · Live token stream on chatgpt-polish · _impact: high · effort: high_

Stream partial output via SSE on `/status/:jobId` instead of polling for
`PROGRESS:N`. Users see Persian text appearing in real time, same perceived-speed
trick ChatGPT itself uses. Keeps users on the page during 40–90 s runs.

- Backend: swap polling for Server-Sent Events; emit tokens as the OpenAI SDK
  yields them.
- Frontend: replace the progress bar with (or augment it by) a dark "terminal"
  card that shows the latest 200 chars.

### 03 · Saved presets — one-click recall · _impact: high · effort: low · frontend only_

Most users run two or three combinations. Save the full form state (source,
target, engine, AI model, split method, CPL value) under a user-chosen name
in `localStorage`. Render the three most-recent presets as outlined cards
next to the engine select.

- Storage key: `mtd.presets` → array of `{ id, name, fields, lastUsed }`.
- Default seeds: "TV Persian", "Fast EN→FR", "Long docs (mini)".

### 04 · Command palette · ⌘K · _impact: medium · effort: low · frontend only_

A fuzzy palette that operates the existing form. Type `deepl fr` → engine
+ target language set, focus moves to upload. Type `history` → opens recent
runs panel. Type `polish 50` → bumps CPL slider to 50. No new backend.

- A 200-line plain-JS implementation. Don't pull in a library.
- Bind `Cmd+K` / `Ctrl+K`. Esc closes.

### 05 · Glossary editor — make the TM visible · _impact: high · effort: medium_

The codebase already has `xlsx_translation_memory/` but the page never shows
it. A modal with a two-column editable table (source / target, plus add /
delete) unlocks domain-specific terminology without leaving the browser —
critical for broadcast subtitle work where terms must be consistent.

- Backend: `GET /glossary` returns the current xlsx as JSON; `POST /glossary`
  accepts an updated array and rewrites the xlsx. Atomic write + backup.
- Frontend: modal with virtual scrolling if > 500 rows.

### 06 · Engine comparison — run two, pick one · _impact: medium · effort: high_

A "Compare" mode that runs DeepL + OpenAI on the same docx in parallel and
shows the first three rows of each side-by-side. User picks the winner; the
other is cached for 24 h.

- Cost: doubles per-call spend; gate behind a checkbox + cost-estimate warning.
- Best for short marketing docs, not 200-row scripts.

### 07 · Failure inbox in the sidebar · _impact: medium · effort: low_

The launcher already writes `runtime_dir/failures/<job_id>__<utc-ts>/` with the
input docx + stdout + meta.json. The v2 page never surfaces them. Add a
small "Recent failures" panel in the right sidebar listing the last 5 with
the structured `reason` token and a **Retry with same settings** button.

- Backend: new `GET /failures` returns a list of `{ id, ts, reason, file }`.
- Frontend: a clone of the existing History card, restyled with the warning
  hairline.

### 08 · First-run guided tour · _impact: medium · effort: low · frontend only_

Three highlighted spots, one-time. Drop-zone → Persian Double Lines option →
Run-summary card. Dismissible, never replayed, stored as `mtd.toured = true`.
The three-column layout is rich; without a tour, half of it goes unnoticed.

### 09 · Multi-file queue with drag-to-reorder · _impact: medium · effort: medium_

Lift the 2-file cap to 5–10 with a visible queue: each row shows file name,
engine, progress bar, grip handle. Reorder while idle, watch progress while
running. The simplest version doesn't need parallelism — visibility alone
wins. Persists across reload so a refresh doesn't lose the queue.

### 10 · Mobile bottom-sheet for the action row · _impact: medium · effort: low_

Below 720 px the Translate button + progress scroll out of view as the user
reads announcements. A sticky bottom sheet with the primary action one tap
away — small grab-handle to expand into the full run-summary. Pure CSS.

### 11 · Email/Telegram on success, not just failure · _impact: medium · effort: low_

Failure alerts already exist. A symmetric success path — "Done. Download: …"
via the same Telegram bot or SMTP — lets users start a 90-second polish run,
close the laptop, and get pinged on their phone. A single checkbox in
Display Preferences turns it on per-session.

- Reuse: `MTD_TELEGRAM_TOKEN` / `MTD_TELEGRAM_CHAT_ID` from the failure path.
- New env: `MTD_NOTIFY_ON_SUCCESS` (defaults to off).

### 12 · "Why this output?" — explainable polish · _impact: medium · effort: medium_

When polish over-rewrites (already a quality warning), let the user expand
each affected row to see: engine output · polished output · which
`fa_postprocess` rules fired. Two reasons: editors learn to trust the model,
and you build a free dataset of disputed lines for prompt tuning.

The sidecar JSON already carries enough to render this; no new compute.

---

## §2 — Impact vs effort

```
          high impact
              ▲
              │   02 ●          01 ●
              │
              │   06 ●          05 ●  03 ●
              │
              │   12 ●          07 ●  04 ●
              │                 09 ●
              │                 10 ●  08 ●  11 ●
              │
              └───────────────────────────► high effort
          low impact
```

**Quadrant guide.** Top-right is high-impact, high-effort — schedule those
in roadmap form. Top-left is high-impact, low-effort — **ship these next.**
Bottom-right is low-impact, high-effort — skip unless they unlock something
else.

**Recommended starting set** (one-week scope):

1. **03** Saved presets — 4 h frontend.
2. **07** Failure inbox — 4 h backend + 4 h frontend.
3. **08** First-run tour — 4 h frontend.
4. **§0** Version switcher — 1 h.

That's ~17 hours of work for four shippable wins.

---

## §3 — Open questions for the team

- **Glossary write authority.** If anyone with the URL can `POST /glossary`,
  one accidental edit clobbers it. Do we add a token, gate it to localhost,
  or accept the risk for a single-team tool?
- **Streaming compatibility.** The Express server (`server.js`) handles SSE
  trivially; the stdlib launcher's `BaseHTTPRequestHandler` is harder. Worth
  the lift?
- **Compare mode billing.** Two parallel OpenAI calls on the same fixture
  doubles cost. Should the cost estimate display a 2× warning when Compare
  is on?
- **Mobile audience.** The README claims "tested down to 360 px" — what
  fraction of real traffic is mobile? If < 10 %, propose **10** drops down
  the list.

---

## Caveats

- All cost / token / latency numbers are inherited from current
  `local_launcher.py` and `_log.json` schemas — verify before quoting them
  in any external doc.
- The Anthropic-style warm palette (`#FAF9F5` / `#CC785C`) is a stand-in for
  whatever brand language SMTV wants long-term; if you have a brand, replace
  the variables in `styles.css`.

— end —
