# Document Translator — v2 frontend

A Claude-inspired single-page UI that talks to the existing
`local_launcher.py` (or the production `server.js`) without changing any
backend behaviour. The legacy `index.ejs` continues to live at `/`.

> Stack: plain HTML + a single hand-written `styles.css` + plain JS in
> `app.js`. Tailwind compile is preserved for forward-compat (`tailwind.css`)
> but every visible class is also defined in `styles.css` so a missing
> build step never blanks the page.

> 2026-05-11 rebuild: layout went from a two-column form/sidebar split
> to a three-column **announcements | translator + stories | info**
> grid that mimics the smch.ir homepage pattern, recoloured with the
> Anthropic / Claude warm palette (cream + clay-orange). Content for
> the announcements panel and the stories grid is now read from
> `web/v2/content.json` — edit that file alone to push a new
> announcement; no HTML / JS change required.

> 2026-05-09 rewrite: i18n.json is no longer loaded at runtime — all UI
> copy is inline English in `index.html` for resilience (the previous
> async fetch could leave the page blank if it raced with Alpine init).
> The `i18n.json` file is preserved for future re-introduction, but
> nothing imports it today.

## Editing announcements / stories

Open [`content.json`](./content.json). Two arrays:

```jsonc
{
  "announcements": [
    { "date": "2026-05-11", "title": "...", "body": "Plain text — no markdown" }
  ],
  "stories": [
    { "title": "...", "summary": "...", "badge": "Tip", "link": "https://..." }
  ]
}
```

The page falls back gracefully when the file is missing or malformed
(announcements panel shows "No announcements yet."; stories section
hides itself entirely). Empty fields are skipped per item.

## Persian / Arabic / Hebrew RTL

`<html dir="rtl">` flips automatically when either the Source or Target
language is `fa`, `ar`, `he`, or `ur`. The announcement card's accent
border swaps from left to right; selects flip arrow position; the
stories grid stays left-aligned (cards are language-neutral).

---

## Features

- Drag-and-drop, click-to-pick, or batch upload (max 2 files, 50 MB each).
- Sequential translation with a real progress bar fed by the existing
  `PROGRESS:N` markers in the launcher.
- 5-day server-side cache for OpenAI API translations
  (sha256 of the file bytes + target language + engine + AI model + split method).
  A cache hit shows a "cached" badge next to each download.
- Download links for every output the backend produces:
  `_PER_Polish.docx`, `_PER_Polish_Double_Lines.docx`, `_chatGPT.docx`,
  `_Google.docx`, etc. (engine suffix per `docx_io/save.engine_suffix`).
- Newsletter signup that writes to `subscribers.txt` in the project root.
- Light / dark theme toggle (Claude-style warm cream by day,
  warm dark by night). Persisted in `localStorage`.
- Mobile-responsive (tested down to 360 px).
- RTL switch when target language is Persian or Arabic.
- Works with keyboard navigation and screen readers.

---

## Local run (Windows)

Double-click **`run_local_launcher_v2.bat`** in the project root. It will:

1. Find `E:\Python311\python.exe` (or fall back to PATH).
2. Start the Python launcher with `--no-browser`.
3. Open `http://127.0.0.1:3000/v2/` in your default browser.

The legacy UI is still available at `http://127.0.0.1:3000/`.

---

## Local run (Linux / macOS)

```bash
python3 local_launcher.py --no-browser
# in another terminal/tab
xdg-open http://127.0.0.1:3000/v2/    # Linux
open     http://127.0.0.1:3000/v2/    # macOS
```

---

## Deploying to production

The v2 frontend is a static bundle of three files under `web/v2/`. There
are two recommended ways to host it:

### Option 1 — same Python launcher serves it (simplest)

Already done. The launcher's `do_GET` handler now serves
`/v2`, `/v2/`, and `/v2/<asset>` from this directory. Just deploy the
project as before and the new UI is live.

### Option 2 — static CDN + same backend on a server

If you want the frontend on a CDN (Cloudflare Pages, Netlify, GitHub Pages,
etc.) while the backend stays on a Linux box, do this:

1. Copy `web/v2/index.html`, `app.js`, `styles.css` to the static host.
2. In `app.js`, change the four backend URLs from relative
   (`/upload`, `/status/`, `/download/`, `/subscribe`) to your absolute
   backend origin, e.g. `https://api.example.com/upload`.
3. On the backend, enable CORS for the frontend origin. The current
   launcher does NOT send CORS headers — add them by editing the four
   `_send_json` / `_send_file` helpers in `local_launcher.py` to also
   emit:
       `Access-Control-Allow-Origin: https://your-frontend.example.com`
       `Access-Control-Allow-Methods: GET, POST, OPTIONS`
       `Access-Control-Allow-Headers: Content-Type`
   Then handle `OPTIONS` requests with a 204.

For a single-server deployment (Option 1), no CORS work is needed.

---

## File map

| File | Role |
|------|------|
| `web/v2/index.html` | Main page. Compiled Tailwind + Alpine.js CDN + Vazirmatn/Inter Google Fonts. |
| `web/v2/app.js`     | Alpine factory `docTranslator()` — upload, polling, cache-hit display, theme, newsletter. |
| `web/v2/styles.css` | Theme tokens + dark-mode override + Vazirmatn polish + `.sr-only`. |
| `web/v2/tailwind.css` | Compiled output — minified utilities + base + components. **Committed.** |
| `web/v2/src/tailwind.css` | Tailwind source (3 directives: `@tailwind base/components/utilities`). |
| `web/v2/tailwind.config.js` | Palette + fonts + radii + shadows. Source of truth. |
| `web/v2/package.json` | npm scripts: `build:css` (one-shot), `watch:css` (rebuild on edit). |
| `subscribers.txt`   | (created on demand) one email per line, UTF-8. |
| `run_local_launcher_v2.bat` | Windows launcher that opens v2 in your browser. |

---

## Building the Tailwind CSS

```bash
cd web/v2
npm install        # only needed once, or after upgrading deps
npm run build:css  # regenerate tailwind.css (minified, ~14 KB)

# during active development:
npm run watch:css  # rebuild on every save to index.html / app.js
```

Whenever you add a new Tailwind utility class to `index.html` or `app.js`,
run `build:css` (or keep `watch:css` running) and commit the regenerated
`web/v2/tailwind.css`. The file is part of the repo so the v2 page works
without Node at runtime.

---

## Backend endpoints used by v2

All are already provided by `local_launcher.py`. None of them require
v2-specific changes on the legacy UI side.

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/v2/`            | Serves `web/v2/index.html` |
| GET    | `/v2/<asset>`     | Serves `app.js`, `styles.css`, fonts, etc. |
| POST   | `/upload`         | Same as legacy. Now returns `{ok, jobId, cacheHit}`. |
| GET    | `/status/:jobId`  | Same as legacy. Returns `progress` field too. |
| GET    | `/download/<name>`| Same as legacy. |
| POST   | `/subscribe`      | Body: `{"email": "..."}` → `{ok, message}`. Writes to `subscribers.txt`. |

---

## Privacy notes

- Uploaded `.docx` files are kept on the server for **up to 5 days**
  (cache TTL) for OpenAI API engines. After that they are permanently
  deleted by the launcher's cleanup thread.
- The newsletter list is plain text in `subscribers.txt`. Keep it out of
  any public repo branch — `.gitignore` already excludes it.
- No telemetry. No analytics. The only third-party network requests are
  Alpine.js (jsdelivr CDN) and Google Fonts. Tailwind is now compiled
  locally — no longer fetched from `cdn.tailwindcss.com`.
