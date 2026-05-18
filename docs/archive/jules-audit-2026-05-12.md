# Jules audit — 2026-05-12

External audit report at `C:/Users/Owner/Downloads/00 Translation Files/
audit-from-Jules -2026-05-12.md` (read-only). 13 findings. Disposition
below.

## Applied (this session)

| # | Finding | Fix |
|---|---------|-----|
| A2 | Command injection in `open_app_docx_file` — `subprocess.Popen(["start", "", out_path], shell=True)` parses through cmd, so a malicious docx filename with `&`, `|`, `^`, `(`, `)`, or quotes could execute attacker commands when the user clicks "Open file". | Replaced the Windows branch with `os.startfile(out_path)`. macOS / Linux paths already used `Popen([list])` without shell=True, no change. |
| A10 | Polish "refined N lines" log counts lines processed, not lines actually changed — produced misleading green logs on F8 runs where zero lines changed. | Polisher now computes `_lines_modified` by diffing `fa_lines` vs `polished_lines` and surfaces both counts. The `last_call_data` dict carries both `lines_processed` and `lines_modified`. Logs the polish-effectiveness warning when `lines_modified / lines_processed < 2 %` on jobs with ≥20 lines (F6 / F8 visibility). |

## Confirmed open (in `debug-2026-05-11-night.md`)

| # | Finding | Status |
|---|---------|--------|
| A8 | F5 reconciler convergence (Jules suggests +1 attempt + temperature variation) | Open. The A14 retry-policy fix from the Codex audit already covers the API-error class of failures; the model-format class still needs the attempt/temperature lever. Defer for the next prompt iteration. |
| A9 | F6 polish sensitivity (Jules points at `<CONSERVATISM_GATE>` in `polish_PER.txt`) | Open. The A10 fix above surfaces the issue at runtime; the prompt-side fix is a quality decision that belongs in the prompt-bazsi rewrite pass the user wants later. |
| A10 (Jules) | F8 reporting mismatch | This audit's A10 fix addresses the reporting half — the log now shows real modified count. The cell-write / redistribution audit Codex suggested for the root cause is still open. |

## Rejected — verified false / not actionable as stated

| # | Finding | Why |
|---|---------|-----|
| A6 | "XSS risk in v2 announcements at `app.js:672`". | False positive. Line 672 is `ul.innerHTML = ''` inside `clearResults()` — assignment of empty string to clear the list before rebuilding. The actual list items are then built with `document.createElement` + `textContent`. Same false positive that the Antigravity audit raised earlier (resolved in `docs/codex-audit-2026-05-12.md`). The Codex audit's separate, real concern (URL scheme validation) was already addressed (A9 there). |
| A3 | "Cache-hostile prompt prefixes" — `f"Lines to translate: {n}\n\n..."` at the start of every user message. | Misleading impact claim. The system prompt is already byte-identical across calls (the comment at `polisher.py:192` records this was deliberately fixed). What gets cached is the system prefix; the user-message body always differs per document regardless of where `{n}` sits. Moving `{n}` to the end would not extend any meaningful shared prefix. Skip. |

## Deferred — bigger architectural work

| # | Finding | Why deferred |
|---|---------|--------------|
| A1 | `cli.py` 4,364 lines | Duplicated by Codex A10 and Antigravity A1; deliberate roadmap item. |
| A4 | `_sync_globals_from_ctx` fragility | Same migration as A1. Each function that gets threaded with `ctx` is one less call to this bridge. |
| A5 | Parallel-array `DocxCtx` anti-pattern | Replacing with `SubtitleRow` objects is a full L-effort refactor that touches every reader and writer. The current `source_columns_snapshot` already protects against the most dangerous misalignment (source column drift). |
| A7 | `except Exception: pass` in CLI init | Some of these are intentional (fetch online config in offline mode, optional version-checker). A surgical pass is needed, not a sweep. |
| A11 | `_send_file` blocking read | Low impact in practice — downloads are infrequent and small. Async refactor of the launcher is out of scope. |
| A12 | `os.environ["PATH"]` global modification (line 758) | The PATH is extended only with the script folder so undetected_chromedriver can find its bundled binaries. Subprocess inheritance is the intended behaviour; no secret leaks. Cosmetic. |
| A13 | Failure-archive path traversal via job_id | job_id is a server-side UUID. Already defended; defensive note only. |

## Score

A2 was a genuine critical that prior audits missed — Jules earned its place by catching the `shell=True` pattern. A10 was a real reliability gap (F8 reporting) and Jules's fix recommendation was right.

But Jules also repeated the same `innerHTML=''` XSS misread that Antigravity made, and overstated the cache impact of `{n}` at the prompt prefix. The other findings duplicate Codex / debug log known items.

Reading score: 15/20. Useful catch on A2 + A10. The two XSS / cache calls erode trust; for an audit at this depth I expect at least a glance at the surrounding code before raising a finding.

Three independent audits in twelve hours now agree the project is sound at the operational level; the open architectural item (cli.py monolith) is the next big lever.
