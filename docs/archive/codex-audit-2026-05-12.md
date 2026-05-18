# Codex 5.5 audit — 2026-05-12

External audit report at `C:/Users/Owner/Desktop/machine-translate-docx-audit/
audit-from-Codex 5.5-2026-05-12.md` (read-only, did not touch code). 15
findings. This file tracks the disposition — applied vs. deferred vs.
rejected — and links each fix to its commit.

## Applied (this session)

| # | Finding | Fix |
|---|---------|-----|
| A1 | `/download/<name>` path traversal | `local_launcher.py: _send_file` resolves the path and requires `relative_to(uploads_dir.resolve())`; rejects symlink escapes |
| A2 | `_strip_timestamp` deletes fresh output | Now walks the same `_1`, `_2` collision suffix the CLI uses; never overwrites |
| A3 | Aligner failure looked successful | `docx_io/save.py` no longer catches aligner exceptions — they propagate to the CLI `[FAIL]` handler |
| A7 | `/upload` reads body before any cap | Added `_MAX_DOCX_COMPRESSED` (20 MB) precheck against `Content-Length`; reject 413 before reading. Also added DOCX shape check (`[Content_Types].xml` + `word/document.xml` required) |
| A8 | DeepL credentials only from tracked JSON | `MTD_DEEPL_EMAIL` / `MTD_DEEPL_PASSWORD` / `MTD_DEEPL_ENABLED` env vars take precedence; `.gitignore` now excludes `configuration.local.json` + `*secret*` / `*credentials*` under `src/configuration/` |
| A9 | v2 SPA href accepts any scheme | Added `safeHref()` helper; allows `http(s):` and relative paths only; rejects `javascript:` / `data:` / unknown schemes |
| A12 | Aligner can save over-limit chunks | `docx_io/save.py` raises `TranslationFailure(reason="aligner_over_limit")` when `stats["over_limit"] > 0` |
| A14 | Reconciler bypasses shared retry | `line_count_reconciler.py` now wraps the OpenAI call in `call_with_retry()`. Transient 5xx get exponential backoff instead of being treated as a model-format failure |

Plus the user-requested side-feature: **legacy frontend now has a 0..100 slider for the aligner LLM threshold** wired end-to-end (form → `local_launcher.py` → CLI `--alignerllmthreshold` → `ctx.flags.aligner_llm_threshold` → `FASubtitleAligner(llm_threshold=...)`). The aligner itself still ignores the value — the wire is ready for the future hybrid mode. Note in the UI tells the user that 0 = pure mechanical and 100 = model-driven.

## Confirmed open (already documented in `debug-2026-05-11-night.md`)

| # | Finding | Status |
|---|---------|--------|
| A4 | F5 — reconciler pads/truncates after failed repair | Still open. A14 reduces the API-error surface but does not fix the format-failure path. |
| A5 | F6 — weak polish is only diagnostic | Still open. Surfacing `polish_lines_touched < threshold` as a sidecar warning is a follow-up. |
| A6 | F8 — no-change polish is not actionable | Still open. Needs a unit test of `run_openai_single_call` → `get_translation_and_replace_after` → cell write to find the gap. |

## Deferred — bigger work, ticket later

| # | Finding | Why deferred |
|---|---------|--------------|
| A10 | `cli.py` is still 4,355 lines | This is the architecture-refactor roadmap item; deferred deliberately. |
| A11 | Splitter responsibilities duplicated CLI vs. launcher | One-function unification is the right move but requires aligning two divergent paths; ~half-day, scheduled for the next refactor pass. |
| A13 | ZWNJ-aware length inconsistent inside the aligner | Audit needed of every `_display_len` vs `len()` site in `persian_double_lines.py`. Lower priority since broadcast over-limit (A12) is now a hard fail; the next over-limit incident will pinpoint the worst offender. |
| A15 | No lint / typing / JS check in CI | Workflow improvement; not user-facing. Add Ruff + `node --check` in a separate PR. |

## Rejected

None — every finding was at least a real issue or a meaningful concern. A6 (XSS) from the earlier Antigravity audit was wrong, but Codex 5.5's report did not repeat it.

## Score

Codex 5.5 found seven HIGH+ findings that were genuinely impactful, three of them (A1, A2, A7) outright security/data-integrity holes that nobody had spotted in the prior session. The two architecture findings (A10, A11) duplicated existing roadmap items; the F4/F5/F6 confirmations matched the debug log. Overall a much sharper audit than Antigravity's — fewer hallucinated paths, no XSS false positive, more security focus. Reading score: 19/20.
