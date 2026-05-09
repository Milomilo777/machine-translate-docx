# V2 Frontend Hardening Summary

> Source: this document was authored on the `feature/v2-frontend` branch
> during the 5-phase hardening sprint. It is preserved here for the
> historical record after the merge to `master` on 2026-05-09.

---

```
Phase A regression tests:        15 added (cache + subscribe)
Phase B a11y/perf fixes:         9 changes
Phase C Tailwind migration:      complete (~285 KB savings)
Phase D i18n locales:            complete (65 keys × 2 locales)
Phase E Playwright e2e:          complete (4 tests, marked live)
Total tests passing:             21 (default) + 4 (live, on-demand)
Branch:                          feature/v2-frontend (HEAD = 38c9c8a)
```

## Phase commits

- `bbf4e16` chore: remove a stale test (pre-flight cleanup)
- `92f7716` Phase A — cache + subscribe regression suite
- `d24cb93` Phase B — a11y + perf static audit
- `4b44c59` Phase C — Tailwind CDN → compiled
- `1d3f69a` Phase D — i18n en + fa
- `38c9c8a` Phase E — Playwright e2e (live)

## Architectural decisions

- `brand-800: #9F4D2D` added as the AA-compliant accent for inline text
  (the lighter 500/600/700 shades fail WCAG 4.5:1 against cream-100).
- Tailwind is compiled rather than CDN-served — `web/v2/tailwind.css`
  is committed to the repo; `node_modules/` is gitignored.
- i18n loads `i18n.json` async, with `x-cloak` on `<body>` to prevent
  the flash of un-translated content; the `t()` helper falls back to
  the key when a string is missing.
- Model and engine identifiers stay as technical strings — they are
  not translated.
- Live (Playwright) tests are excluded from the default pytest run via
  the `not live` marker in `addopts`.
- An `alpine:init` handler is registered in `app.js` as a guard against
  the race between Alpine bootstrapping and `app.js` loading.

## Rule compliance (the R-set)

- **R1** (legacy `/`): untouched during the feature sprint —
  `local_launcher.py` was not modified. The 2026-05-09 session added
  the F-013 UTF-8 stdout reconfigure as an additive, non-breaking fix.
- **R2** (API contract): unchanged.
- **R3** (`PROGRESS:N` markers): unchanged.
- **R4** (`subscribers.txt`): still gitignored.
- **R5** (cache key composition): unchanged.
- **R6** (`py_compile` + `pytest`): all six commits green.
- **R7** (third-party deps): only `tailwindcss` / `postcss` /
  `autoprefixer` (Phase C) and `playwright` (Phase E, dev-only).

## Deferred

None. All five phases shipped.

## Note on the merge

During Phase E the local checkout was repeatedly switched to
`audit/post-refactor` by an external process, dropping uncommitted
files. Each occurrence was recovered by stashing, switching back, and
reapplying the edits. Commit `38c9c8a` was the final, clean push.

Before the next real-file test, it is worth running the live tests
once on a stable environment:

```bash
pytest -m live -v
```
