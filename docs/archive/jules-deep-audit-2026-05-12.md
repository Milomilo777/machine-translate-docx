# Jules deep audit — 2026-05-12

Source branch: `origin/audit-jules-2026-05-12-4244030856483517826`.
Audit file as Jules wrote it: `audit-from-Jules -2026-05-12.md` on that
branch. 8 deep-pass findings (B1–B8) on top of A1–A7 already processed
in `docs/jules-audit-2026-05-12.md`.

## Disposition

| # | Finding | Status | Why |
|---|---------|--------|-----|
| B1 | _sync_globals_from_ctx whitelist incomplete | **deferred** | Same as Antigravity-deep B1; L-effort architecture refactor scheduled for the migration sprint. |
| B2 | Dead functions `getDownLoadedFileNameFirefox`, `join_from_lines` | **fixed** | Both removed from `cli.py`. `grep` confirmed zero call sites. |
| B3 | Prompts < 1 024 token static prefix → cache-cold | **rejected (stale)** | Jules read a pre-phase-1 snapshot. Current sizes: translate_PER ≈ 2 000 tok + 1 648 tok shared SMTV block = 3 648 effective tokens. polish_PER ≈ 3 000 tok + shared = 4 640. Both well over the 1 024 threshold Jules quoted. |
| B4 | `_send_zip_for_job` blocking `read_bytes()` | **rejected (stale)** | The endpoint is RETIRED — it always returns 410 GONE, never calls `read_bytes()`. Jules read the old implementation. |
| B5 | atexit cleanup depends on `_ctx` being built | **fixed** | New `_spawned_driver_pids: set` plus `_track_spawned_driver()` records every driver PID immediately on spawn. The atexit hook now also `SIGTERM`s any PID that didn't end up wired into `_ctx` — covers the "crashed during init" case. |
| B6 | Aligner silently drops every row if pre-first-group skips | **fixed** | `align()` now raises `ValueError` if the source table has translatable rows but `_parse_groups` produced zero groups. No more blank-docx writes on parser regressions. |
| B7 | CSP missing on launcher | **already fixed** | Closed in commit `f06a67c` (Antigravity-deep B14, 2026-05-13). `_send_security_headers()` is wired into every response path. |
| B8 | Batch files hard-code absolute paths | **deferred** | Same as Antigravity-deep B19; workflow hygiene, not blocking. |

## Rejected with notes

**B3 (cache-cold prompts).** Jules's report quotes `~300 tokens` for `translate_PER.txt` and `~450 tokens` for `polish_PER.txt`. The branch Jules read from is `audit-jules-2026-05-12-4244030856483517826` (forked off master at commit `6d8fec2`). That snapshot already contained the phase-1 prompt rewrite committed in `fa8fa4a` (visible in its `git log`), so the small-prompt reading is unsupported by what's on disk in that branch. Likely Jules truncated the file in its own scan window. The actual chars-to-tokens ratio of the phase-1 prompts is recorded in `docs/prompt-rewrite-2026-05-12.md`. No action.

**B4 (blocking `_send_zip_for_job`).** The function exists in `local_launcher.py:962-…` but only as a stub that returns `HTTPStatus.GONE` (410). The retire note is right above it (`local_launcher.py:963-969`). No `read_bytes()` runs on the live path. No action.

## Cross-references

- Antigravity-deep B7 / Jules-deep B5 / Codex audit findings → all addressed in this branch or in the audit-light follow-up of 2026-05-13.
- The Persian `_normalize_fa` script-script normalisation (Antigravity-deep B15) and the launcher security headers (B14) close every web-facing item Jules raised.

## Score

Jules's deep pass is **partially stale** — it didn't see the phase-1 prompt rewrite or the `_send_zip_for_job` retirement. The two genuinely new findings B2 (dead functions) and B5 (atexit fragility) are real and fixable. B6 (aligner empty-group assert) is a good defensive addition. The rest overlap with what Antigravity-deep already covered.

Net useful findings from Jules deep pass: 3 (B2, B5, B6), all S–M effort, applied in this commit.

Reading score: 14 / 20. The stale-snapshot issue is the main weakness.
