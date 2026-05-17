# Backend TODO — endpoints v2 needs

> Tracker for backend changes required to make the v2 redesign
> (`v2-redesign.html` / `web/v2/index.html`) work end-to-end.
> Created 2026-05-16. Items are listed in priority order; each one
> describes the contract the frontend already expects.

---

## Already wired (no work needed)

These endpoints exist in `local_launcher.py` today and the v2 frontend
already calls them:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/upload` | Submit a translation job (multipart form). Returns `{ok, jobId, cacheHit?}`. |
| `GET`  | `/status/:jobId` | Poll job. Returns `{status, progress, filename?, error?}`. |
| `GET`  | `/download/:filename` | Download a finished docx. |
| `POST` | `/cancel/:jobId` | Cancel a running job. |
| `GET`  | `/count` | Lifetime counter — `{count: 12847}`. |
| `GET`  | `/robotscount` | Current concurrency — `{count: {all: 3, ...}}`. |
| `POST` | `/subscribe` | Newsletter signup — body `{email}`. |

---

## TODO #1 — `GET /history?limit=N` _(blocks: Recent runs panel)_

The right-sidebar **Recent runs** panel currently shows 10 static mock
entries. The frontend already tries to fetch `/history?limit=10` on
load and re-renders the panel if the endpoint responds; if it 404s the
static fallback stays visible.

### Contract the frontend expects

`GET /history?limit=10`

```jsonc
{
  "runs": [
    {
      "id":               "20260516-1422-ab3c",   // string, opaque
      "model":            "gpt-5.5",              // engine name OR OpenAI model id
      "target_lang":      "fa",                   // ISO-639-1 code (lowercase)
      "elapsed_seconds":  71,                     // number (float ok)
      "completed_at":     "2026-05-16T14:23:42Z", // ISO-8601 UTC
      "filename":         "ep-73-broadcast_PER_Polish.docx"  // optional
    },
    // … up to `limit` items, newest first
  ]
}
```

Frontend tolerance:
- Missing fields render as `—`.
- `target_lang` falls back to `dest_lang` if the launcher prefers that key.
- `model` falls back to `engine` if absent.
- Time ago is computed client-side from `completed_at`.

### Suggested implementation

The launcher already writes a `_log.json` sidecar next to each output
docx. The cheapest path:

1. **Index lookup.** Scan the runtime output directory for `*_log.json`
   files modified in the last N days (default 30). Sort by mtime
   descending. Take the first `limit`.

2. **Parse minimum fields.** For each sidecar:
   ```python
   {
     "id": log["run_info"]["job_id"],
     "model": log["run_info"]["model"] or log["summary"]["model"],
     "target_lang": log["run_info"]["dest_lang"],
     "elapsed_seconds": log["summary"]["elapsed_total_seconds"],
     "completed_at": log["run_info"]["completed_at_iso"],
     "filename": basename(sidecar_path).replace("_log.json", ".docx")
   }
   ```

3. **Cache it.** Cache the result in-memory for ~60 s — this endpoint
   will be hit on every v2 page load.

4. **Where to put the code.** Add a `do_GET` branch in
   `local_launcher.py` next to `/count`:
   ```python
   elif self.path.startswith("/history"):
       q = urllib.parse.urlparse(self.path).query
       params = urllib.parse.parse_qs(q)
       limit = int(params.get("limit", ["10"])[0])
       limit = max(1, min(50, limit))
       runs = _load_recent_runs(limit)
       self._send_json({"runs": runs})
   ```

   `_load_recent_runs(limit)` is the new helper — implementable in
   ~40 lines.

### Optional refinements (not required for v0)

- Filter `?source_ip=…` so the per-user flag is meaningful (today the
  Recent runs panel shows the **viewer's** flag against runs from any
  user; that's an honest representation but a bit confusing).
- Include `cache_hit` boolean so the frontend can show a small `cached`
  badge on the row.

---

## TODO #2 — Server-side anti-indexing _(complements meta tags)_

The v2 page already ships a strong **client-side** robots block (every
major crawler's `<meta name="…">` directive, plus referrer-policy +
no-cache headers). But meta tags are advisory — well-behaved crawlers
honour them; aggressive scrapers ignore them. The launcher should add
**server-side** reinforcement:

### 2a. Serve `/robots.txt`

```
User-agent: *
Disallow: /
```

In `local_launcher.py`'s `do_GET`, next to the other static routes:

```python
elif self.path == "/robots.txt":
    self._send_text("User-agent: *\nDisallow: /\n", ctype="text/plain")
```

### 2b. Emit `X-Robots-Tag` on every response

This is the HTTP-header equivalent of the meta tag and applies even to
non-HTML responses (e.g. `/download/<file>`):

```python
self.send_header("X-Robots-Tag",
                 "noindex, nofollow, noarchive, nosnippet, noimageindex")
```

Add it inside `_set_default_headers` (or wherever the launcher centralises
response headers) so every endpoint inherits it.

### 2c. Optional — IP-allowlist / basic-auth gate

If the tool is for a single team, a one-line bind to `127.0.0.1` (already
the default for local dev) plus an SSH tunnel or VPN is the strongest
guarantee — no public surface at all. If a public URL is required, a
minimal `Authorization: Basic` check in the launcher rejects bots without
credentials before any meta tag is evaluated.

---

## TODO #3 — _(no blockers right now)_

Everything else the v2 frontend uses works today.
The streaming token preview (`/status/:jobId` over SSE) is in
[`docs/v2-improvements.md` §02](./v2-improvements.md#02--live-token-stream-on-chatgpt-polish)
as a stretch goal; until then, polling is fine.

---

## Frontend already does its part

The relevant block in `v2-redesign.html` (search for `loadHistory`):

```js
(async function loadHistory() {
  try {
    const r = await fetch('/history?limit=10');
    if (!r.ok) return;
    const data = await r.json();
    if (!Array.isArray(data.runs) || data.runs.length === 0) return;
    // … re-render the list with elapsed + target_lang …
  } catch (_) { /* keep static mock */ }
})();
```

So **the moment** `GET /history` ships in `local_launcher.py`, the v2
page will start showing real runs without any frontend change.

— end —
