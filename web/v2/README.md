# Document Translator — v2 frontend

A Claude-inspired single-page UI that talks to the existing
`local_launcher.py` (or the production `server.js`) without changing any
backend behaviour. The legacy `index.ejs` continues to live at `/`.

> Stack: HTML + Tailwind CDN + Alpine.js. **No build step required.**

---

## Features

- Drag-and-drop, click-to-pick, or batch upload (max 2 files, 50 MB each).
- Sequential translation with a real progress bar fed by the existing
  `PROGRESS:N` markers in the launcher.
- 36-hour server-side cache for OpenAI API translations
  (sha256 of the file bytes + target language + engine + AI model).
  A cache hit shows a "cached" badge next to each download.
- Download links for every output the backend produces:
  `_PER_TranslatePolish.docx`, `_PER_Double.docx`, `_PER_Classic.docx`.
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
| `web/v2/index.html` | Main page. Tailwind CDN + Alpine.js + Vazirmatn/Inter from Google Fonts. |
| `web/v2/app.js`     | Alpine factory `docTranslator()` — upload, polling, cache-hit display, theme, newsletter. |
| `web/v2/styles.css` | CSS variables for the Claude-inspired warm palette + dark-theme override + Vazirmatn polish. |
| `subscribers.txt`   | (created on demand) one email per line, UTF-8. |
| `run_local_launcher_v2.bat` | Windows launcher that opens v2 in your browser. |

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

- Uploaded `.docx` files are kept on the server for **up to 36 hours**
  (cache TTL) for OpenAI API engines. After that they are permanently
  deleted by the launcher's cleanup thread.
- The newsletter list is plain text in `subscribers.txt`. Keep it out of
  any public repo branch — `.gitignore` already excludes it.
- No telemetry. No analytics. No third-party JS beyond the Tailwind +
  Alpine.js + Google Fonts CDN requests.
