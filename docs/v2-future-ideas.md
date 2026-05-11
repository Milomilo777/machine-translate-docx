# v2 frontend — future ideas

> A prioritised backlog of low-cost / high-value tweaks for the v2 SPA.
> Every idea is scored against three axes:
>
>   - **Server cost**: how much extra CPU / memory / disk / network
>     the launcher takes on. We're on a small box — anything more than
>     "trivial" should be a hard sell.
>   - **Client cost**: bytes shipped to the browser + JS / CSS runtime.
>     The v2 SPA is plain JS today (no React / Vue / Alpine); we keep
>     it that way.
>   - **Build cost**: how much engineering time to ship it.
>
> Picked the warm Anthropic Claude palette as the visual baseline
> (cream `#FAF9F5`, clay `#D97757`, near-black ink). Anything that
> needs custom artwork should reuse the existing colour tokens.
>
> Updated 2026-05-11.

---

## Tier 1 — small + obvious wins (do these first)

| Idea | Server | Client | Build | Notes |
|---|---|---|---|---|
| **Tab-title progress** ("(45 %) SMTV Translate") | 0 | trivial JS | ~15 min | Update `document.title` from the same poll that drives the progress bar. Already half-built via the cross-tab "done" flash. |
| **Auto-detect source lang from filename** | 0 | <100 B JS | ~30 min | If the upload is named `sample_fa.docx` / `doc-french.docx` / `*_PER.docx`, pre-select the matching source. The existing `_LANG_ALPHA3B` table is the input. |
| **Per-file remembered prefs** | 0 | localStorage | ~45 min | Key `v2.fileprefs.<basename>` → `{engine, src, dst, model}`. Restore on next upload of the same basename. |
| **Toast pattern for transient confirmations** | 0 | ~40 lines CSS + JS | ~1 h | "File added", "Cache hit", "Copied to clipboard" should not use the heavy error-box. Tiny right-bottom toasts that fade out. |
| **Keyboard shortcuts** (Esc, `?` help, Ctrl+Enter to translate, Space to focus drop-zone) | 0 | ~30 lines JS | ~45 min | Plus a small `?` modal that lists them. |
| **Cached-vs-fresh badge** on the Run summary card | 0 | <50 B CSS + JS | ~15 min | We already track `wasCached` — surface it as a coloured pill instead of the appended `  (cached)` text. |

## Tier 2 — nice-to-have, no infrastructure cost

| Idea | Server | Client | Build |
|---|---|---|---|
| **Drag-resize of side panels** | 0 | ~80 lines JS + CSS-custom-property | ~2 h |
| **CSV export augmentation** (session-summary, not just history) | 0 | already shipping CSV; +20 lines | ~30 min |
| **Mini sparkline of last-10 runs' tokens** | 0 | hand-rolled SVG, ~60 lines | ~1.5 h |
| **Drag-and-drop reorder of queued files** | 0 | ~60 lines JS | ~1 h |
| **`prefers-reduced-motion` audit** + per-component opt-out | 0 | already partially honoured; tighten | ~45 min |
| **Inline help "?" on each form field** | 0 | <500 B CSS + 1 line per field | ~1 h |
| **Side-by-side bilingual preview** of a saved docx in-browser | 0 | parses docx with `mammoth`-equivalent or just shows row-by-row from the sidecar | ~3 h (no new dep — read the existing JSON + render an HTML table) |

## Tier 3 — needs a small backend touch

| Idea | Server | Build |
|---|---|---|
| **Per-session running token meter** in the footer (not just $) | one extra row in the sidecar `summary` (already shipped) | ~30 min frontend only |
| **"Cancel + retry with different engine" button** on the Run summary card | reuse `/cancel/<id>` then re-POST | ~1.5 h frontend; backend already has the surface |
| **Compare two runs side-by-side** | one new endpoint that returns two sidecars in a wrapper, OR pure frontend if we already keep them in localStorage | ~3 h |
| **Pre-flight estimate calibration** | record actual token usage per language pair → multiply estimate next time | ~2 h, ~200 LoC backend |

## Tier 4 — bigger wins worth considering later

| Idea | Cost | Why |
|---|---|---|
| **WebSocket-based progress** instead of 4 s polling | medium server (one socket per job; pool needed) | Sub-second progress updates, no polling overhead. Worth it only when concurrent-job count grows. |
| **Browser-side docx preview** before upload | client-only (use `mammoth.js` or roll a thin reader) | Lets the user confirm they're about to translate the right table. ~200 KB JS download though. |
| **Localisable UI** (en / fa) | client-only, but every string needs a key | The v2 SPA is English-only today; a 200-string i18n.json would expand into a maintenance surface. Defer until there's a non-English user asking for it. |

## Anti-patterns to avoid

- **Adding any framework** (React / Vue / Svelte / Alpine). The v2 SPA
  is plain JS for a reason — every framework adds a ~50–150 KB
  baseline plus a new failure mode. Stay vanilla.
- **Server-pushed events** (SSE / WebSocket) for the simple progress
  bar. The 4 s poll is cheaper than an open socket on our small box.
- **Heavy chart libraries** (Chart.js, D3). Hand-rolled SVG sparklines
  are ~60 lines of code and ship 0 KB.
- **Tailwind regeneration as a runtime step.** The compiled
  `tailwind.css` is committed; only re-run the build on palette
  changes.
- **CDN-served fonts as a hard dependency.** The page already
  degrades gracefully when Google Fonts is unreachable; do not
  introduce a CDN-only component without a stdlib fallback.

## How to keep adding ideas

When a new idea surfaces during a session, append it under the
matching tier with the three-axis cost scoring above. If the cost
table is fuzzy ("medium client"), say so — the next reviewer will
sharpen it.
