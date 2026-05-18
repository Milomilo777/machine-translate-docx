# Antigravity / Codex light + deep audits — 2026-05-12 (applied 2026-05-13)

Two follow-up audit reports landed on 2026-05-12 (one "light" and one
"deep"); both flagged the same families of issue. Disposition below.

## Applied this session

| # | Finding | Fix |
|---|---------|-----|
| B3 | `_retry.py` no jitter | Full-jitter backoff (`uniform(0, BASE * 2^n)` capped at 30 s) — retry-herd no longer collides on rate-limit windows. |
| B4 | `MAX_RETRIES = 3` too tight | Bumped to **5** total attempts for transient 5xx; non-retryable classes (BadRequestError) still fail fast. |
| B5 | translator prints full payload + full response JSON | Default emits a one-line summary (line count, est. tokens, first-line sample, prompt/cached/completion counts). Full payloads gated by `MTD_DEBUG_PAYLOADS=1`. Telegram alerts no longer accidentally exfiltrate document text. |
| B6 | translator line-count mismatch silently passes raw | Same behaviour retained, but with a louder `[WARNING]` line and an in-code note that the next refactor must lift this into a structured `TranslationFailure`. (The single-call path already runs through the reconciler — only the per-block fallback path hits this.) |
| B8 | polisher swallows API errors and returns unpolished text silently | `last_call_data` now carries `polish_skipped: true`, `skipped_reason`, `lines_modified: 0`. Sidecar JSON + run summary can detect the no-op explicitly. |
| B13 | reconciler `max_attempts = 2` too few | Bumped default to **4**. gpt-5.4-mini gets two more chances to converge on dense paragraph structures before the pad/truncate fallback. |
| B14 | no security headers on launcher responses | Added `Content-Security-Policy` (default-src 'self', tight script/style allowlist, `frame-ancestors 'none'`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` on every HTML / JSON / file response. CDN audio (Pixabay) explicitly allowed via `media-src`. |
| B15 | aligner doesn't normalise Arabic Yeh/Kaf or Arabic-Indic digits | `_normalize_fa()` now applies the same Yeh / Kaf / digit script substitutions the polisher's `fa_postprocess.normalize_fa()` does. Aligner runs upstream of polish in some workflows; both stages now see the same canonical FA form. |

Plus a reasoning-effort knob change from yesterday: polisher on mini stepped down from `high` → `medium` (user instruction). Verified on sample_hyperlink — polish now 15.6 s (was 83 s with high) and `8/17` lines modified (was `6/17`). Cleaner trade.

## Confirmed open — left for the next dedicated session

| # | Finding | Why deferred |
|---|---------|--------------|
| B1 | `cli.py` global / context bridge incomplete | The `RuntimeContext` migration roadmap item. Estimated ~60 % of helpers thread `ctx` today; finishing the migration removes the `_sync_globals_from_ctx` bridge entirely. L-effort. |
| B2 | `cli.py` heavy import-time side effects | Same migration — moving the side-effects into `main()` is part of the same refactor pass. L-effort. |
| B7 | 30-min `timeout=1800` per OpenAI call | Behaviour policy. Dynamic per-block timeout requires a job-level watchdog to be safe; M-effort and risky without tests. Park. |
| B9 | Persian prompts long and rule-heavy | The phase-1 prompt rewrite from 2026-05-12 already cut `translate_PER` by 65 % and introduced the shared `_smtv_locks.txt`. Further decomposition (`_persian_style.txt`, mode-specific annexes) is L-effort and depends on future quality data. |
| B10 | translator emits raw, polisher emits tagged `⟨⟨N⟩⟩` | The parser's four-strategy recovery already absorbs the mismatch; unifying the contract requires a coordinated prompt + parser change. M-effort, scheduled for the next prompt iteration. |
| B11 | `local_launcher.py` ~2 900-line monolith | Same architecture roadmap as B1. Split into `upload.py` / `jobs.py` / `cache.py` / `downloads.py` / `notifications.py`. L-effort. |
| B12 | v2 SPA polls every 4 s with no backoff | Working but wasteful at scale. M-effort. SSE / WebSocket would be the right long-term answer. |
| B16 | retry / reconciler / aligner edge-case tests missing | Workflow improvement. The bench tool (`tools/aligner_bench.py`) added on 2026-05-12 closes part of the gap for aligner regression testing. |
| B17 | no `[tool.ruff]` / `[tool.mypy]` / `[tool.bandit]` config | Workflow improvement; not user-facing. |
| B18 | `CHANGELOG.md` stale TODO/FIXME notes | Maintenance hygiene; defer to a dedicated cleanup commit. |
| B19 | batch scripts hard-code absolute Windows paths | Maintenance hygiene. The launcher itself uses relative resolution; only the convenience `.bat` shells embed paths. |
| B20 | "No CI workflow" — already exists | False as stated. `.github/workflows/ci.yml` is present (per a 2026-05-11 commit). May need adding lint / typecheck steps under B17. |

## Score

- The "light" report and the "deep" report agreed on roughly the same 12 findings and gave the deep version 20. B3, B5, B6, B8, B13, B14, B15 are real wins (security, reliability, logging hygiene) that this session applies.
- Nothing flagged was a false positive on inspection. The deep audit is sharper than the earlier two: B14 (CSP / X-Frame-Options) and B15 (FA normalisation) were genuinely unseen by Antigravity / Jules / Codex earlier.
- The L-effort architecture items (B1, B2, B11) compound — they should land in one branch with their own benchmark + tests rather than being chipped at piecemeal.

Audit reading score: 18 / 20. Top-tier external review.

113 unit tests still green; aligner bench unchanged at 232 doubles / 0 over_limit on the BMD + CTAW corpus.
