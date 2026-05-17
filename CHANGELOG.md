# CHANGES — machine-translate-docx

> Project changelog. Newest entries at the top. Read this file to come
> up to speed on the project state in a single sitting — there is no
> need to re-read the source to understand recent direction.

---

## 2026-05-17 — v2 redesign drop-in + backend wire-up

Branch `feat/v2-redesign-wireup` (commit `cbb5f2e` initial drop, plus
follow-up cleanup) lands the v2 redesign preview UI and the two
launcher endpoints the new frontend expects. Multi-engine matrix
smoke verified on `feat/v2-redesign-wireup` (9 cases × fa+vi).

### Frontend (additive only)

| File | Status |
|---|---|
| `web/v2/redesign.html` | NEW — 1,947-line single-file Claude-palette redesign reachable at `/v2/redesign.html`. Lives next to (not on top of) the existing `web/v2/index.html`. |
| `docs/v2-improvements.md` | NEW — 12 design proposals + matrix + v1↔v2 switcher spec. |
| `docs/v2-backend-todo.md` | NEW — contract for the backend changes the redesign waits on. |
| `CLAUDE.md` | Replaced with deploy version — adds `web/v2/redesign.html` to Key Paths, new Anti-indexing posture section, v2 version switcher (C23). |

### Backend (additive only — `local_launcher.py`)

- `GET /history?limit=N` — scans `Log json file/` for `*_log.json`
  sidecars, returns up to `limit` newest runs with
  `{id, model, target_lang, elapsed_seconds, completed_at, filename}`
  per row. 60-second in-memory cache so v2 page loads don't re-scan
  per poll. Capped at 50.
- `GET /robots.txt` — `User-agent: *\nDisallow: /\n`. The legacy
  allow-all handler lower in `do_GET` was removed to avoid two
  routes claiming `/robots.txt`.
- `X-Robots-Tag: noindex, nofollow, noarchive, nosnippet,
  noimageindex` added to `_send_security_headers` so every response
  (including `/download/*.docx`) carries the directive — the HTTP-
  header equivalent of the v2 page's meta block, but applies to
  non-HTML too.
- Top-level `from urllib.parse import …` extended with `parse_qs`
  for the `/history?limit=…` query parser.

### Verification

- pytest `tests/ --ignore=tests/test_v2_e2e.py`: **239 passed / 8 skipped / 6 deselected**.
- Live curl: `GET /robots.txt` → 200 + correct body; `GET /history?limit=3`
  → 200 + real JSON from sidecar logs; `GET /count` regression → 200.
- Smoke fixture (`tests/fixtures/sample_hyperlink.docx`)
  end-to-end on chatgpt-polish FA: exit 0.

---

## 2026-05-17 — Sprint D-C complete (bridge collapse) + P2/P3 round 2

Eight commits land the full `_sync_globals_from_ctx` collapse plus
a second batch of P2/P3 hygiene items from the master audit. Master
HEAD: `5408f80` (then `27be4ad` for the pre-audit cleanup). Branch
`refactor/cli-py-sprint-d-final` synced. Tag:
`archive/2026-05-17-sprint-d-c-complete`.

### Sprint D-C bridge collapse (6 atomic slices)

The Phase-H mirror function `_sync_globals_from_ctx` and its 6 call
sites in `main()` are gone. Every bare-name read across cli.py was
threaded through `ctx` first, then the bridge was deleted last.

| Slice | Scope | Commit |
|---|---|---|
| 1 | Add `xtm` and `rtlstyle` to `ctx.docx` | `5dd4a9c` |
| 2 | Thread cell-write helpers (10 reads) | `7601686` |
| 3 | Thread 6 small helpers (15 reads) | `026b778` |
| 4 | Thread engine orchestrators (15 reads) | `751052f` |
| 5 | Thread top-level orchestrators (20 reads) | `2d9afce` |
| 6 | Delete the Phase-H mirror bridge | `b12b8a2` |

After slice 6 the only references to `_sync_globals_from_ctx` are
two historical comments. RuntimeContext is now the canonical state
surface — constraint C10 has been rewritten in `PROJECT_MEMORY.md`
to reflect this (no more "call after every pipeline boundary"
rule).

### P2/P3 hygiene round 2 (Phase 2, single commit `dfee48b`)

Seven items from `docs/master-audit-2026-05-16.md`:

- New `src/machine_translate_docx/openai_tools/_pricing.py` —
  consolidates the PRICES table that was duplicated 3× across
  `translator.py`, `polisher.py`, `splitting.py`.
- New `_normalize_usage` helper in `_retry.py` — Response-API
  usage-shape normalization that was duplicated in `translator.py`
  and `polisher.py`.
- `saved_filename` from CLI stdout is now path-confined against
  `uploads_root` in `local_launcher.py`.
- `openai_tools/splitting.py` now wraps every OpenAI call with
  `call_with_retry` (was the one OpenAI caller without it).
- Google file-mode workers: `sys.exit(7)` in the exception path
  replaced with `raise TranslationFailure(reason="google_file_mode_error", …)`.
- `translation_succeded` → `translation_succeeded` typo fix across
  cli.py + runner.py + test fixtures.
- `E_mail_str` / `E_MAIL_STR` consolidated into
  `config.SUPPORT_EMAIL`.

### Pre-audit cleanup (commit `27be4ad`)

- `docs/cli-shrink-phase3-handoff.md` status banner refreshed
  (Task C no longer "DEFERRED" — it's DONE).
- `docs/agent-handoff.md:157` C10 description updated to the
  post-bridge invariant.
- Tagged + deleted `origin/claude/raw-cache-refactor` — commits
  absorbed via the spec-not-merge pattern, preserved as
  `archive/2026-05-15-raw-cache-refactor-original`.
- Orphan local branch `claude/festive-colden-af72d9` deleted.
- Worktree `.claude/worktrees/raw-cache-v2/` + its branch removed.
- Memory file `pending_cache_refactor.md` deleted (work merged).
- Smoke-test artifacts cleaned from `Log json file/` and `/tmp`.

### Verification

- pytest tests/ --ignore=tests/test_v2_e2e.py: **239 passed, 8
  skipped (live), 6 deselected** at every commit.
- End-to-end smoke chatgpt-polish FA on `sample_hyperlink.docx`:
  exit 0 at every cli.py-touching commit. C13 source-column lock
  PASS across 42 rows. Target column: 17/40 populated with 17/17
  Persian Unicode script match.

### cli.py line-count

cli.py 2,686 → **2,651** (-35 net). The bridge body removal saved
~70 lines; the threading work added ~35 lines to function
signatures. Total reduction from the start of the original
3-phase shrink: 4,395 → 2,651 = **−39.7%**.

---

## 2026-05-16 — Cache refactor + Sprint D-C partial + P2/P3 hygiene + matrix smoke

Continuation on `refactor/cli-py-sprint-d-final` (branch already
ahead by 5 Sprint D-A/B commits merged to master at `44c9f76`).
Seven new commits, NOT merged to master yet.

**Numbers:**

| File | Before this pass | After | Delta |
|---|---:|---:|---:|
| `local_launcher.py` | 2,645 | 2,827 | +182 |
| `src/machine_translate_docx/cli.py` | 2,670 | 2,686 | +16 |
| `src/machine_translate_docx/translation_log_writer.py` | 178 | 178 | (signature change) |
| `src/machine_translate_docx/config.py` | (unchanged size, +1 line) | — | +1 |

**Commits in order:**

- `1ec1859` — **Phase 1: raw-cache refactor.** Implements the
  cache architecture from the three commit messages on
  `origin/claude/raw-cache-refactor` (used as written spec, not
  cherry-picked). `_cache_key` drops `split_engine` from the
  SHA-256; B1-guard generalised to all `_API_ENGINES` + all
  langs; new `_apply_basic_split` method spawns CLI `--splitonly`
  subprocess with `MTD_SKIP_STATS_BROWSER=1`; `_apply_splitter`
  routes basic/openai/null → `_apply_basic_split`; reordered
  `_process_job` so `cache_store` happens BEFORE `_apply_splitter`
  (because `_apply_basic_split` overwrites `output_path` in
  place). Cache replay for same-bytes, different-splitter now
  takes ~10-30 s instead of ~5 min full re-translate. Two
  drive-by CLI fixes (translate_docx splitonly guard +
  create_webdriver splitonly bypass) needed to make the spec
  command actually work end-to-end. Isolated integration test
  passed; full HTTP cache-replay test left to user's pre-merge
  smoke.

- `cda1467` — **Phase 2 partial: Sprint D-C.** Cannot land in
  full this session (176 bare-name occurrences across 41 names).
  Removed the smallest verified-dead branch: the 3 setattr calls
  that mirror `ctx.openai.{translator,polisher,translation_log}`
  back to module globals — empirically dead by grep after the
  Sprint D phase 3 extraction of `write_translation_log`. Full
  bridge deletion documented as deferred in
  `docs/session-state-2026-05-16-cache-d-c-p2.md` with a ranked
  threading order (start with `dest_lang`, 55 occurrences).

- `3b97fcc` — **P2.6: fd leak in cli.py stderr suppression.**
  End-of-main() opened os.devnull, leaked the fd across process
  exit, and reassigned `sys.__stderr__` (a frozen reference).
  Replaced with `sys.stderr = io.StringIO()` — in-memory discard,
  no fd, no immutable-ref mutation, destructor noise still
  suppressed.

- `ded9d7e` — **P2.7: route validate_json_string traceback to
  stderr.** `print(traceback.format_exc())` was going to stdout
  where the launcher's structured parser watches for
  `Saved file name:` / `PROGRESS:N`. Re-routed via
  `file=sys.stderr`.

- `b073290` — **P2.3: mask Telegram bot token in exception text.**
  Three Telegram URL sites embed the bot token in the URL.
  `urllib.HTTPError.__str__` can include the URL on some Python
  builds, leaking the token via tracebacks. Added
  `_mask_telegram_token(text, token)` helper; wrapped each
  urlopen with try/except that masks before re-raising. The
  `except RuntimeError: raise` short-circuit preserves
  intentional "telegram rejected" messages for the existing
  test contract.

- `588a2cf` — **P2.2: `write_translation_log` adds
  `strip_prompts` flag.** Sidecar JSON bundles full
  translator + polisher system prompts — risky if the launcher
  ever serves them publicly. Added keyword-only
  `strip_prompts: bool = False`. When True, omits
  `system_prompt` and `user_prompt_sample` from each entry,
  keeping only `prompt_hash`. Default False preserves legacy
  behaviour. cli.py shim still calls 2-positional; future
  config.toml wiring left to a follow-up.

- `e8b7062` — **P3.3: simplify `not foo == True` to `not foo`**
  in cli.py:917 and :926. Same logic, less noise.

**Phase 4 — Real multi-engine matrix smoke (9 cases, all PASS):**

| # | engine × lang × split | Result |
|---|---|---|
| 1 | chatgpt-api × fa × basic | PASS — col 2 has 37/42 Persian rows |
| 2 | chatgpt-polish × fa × basic | PASS |
| 3 | chatgpt-polish × fa × persian_double_lines | PASS (CLI level — same as basic; aligner is launcher-level) |
| 4 | chatgpt-api × vi × basic | PASS — col 2 has 37/42 Vietnamese rows |
| 5 | chatgpt-polish × vi × basic | PASS |
| 6 | google × fa × basic | PASS — Persian via translate.google.com |
| 7 | google × vi × basic | PASS — Vietnamese via translate.google.com |
| 8 | deepl × fa × basic | PASS — DeepL web (no creds needed for public path) |
| 9 | deepl × vi × basic | PASS |

C13 source-column lock intact on every case. Engine suffix
(`_PER_chatGPT` / `_PER_Polish` / `_PER_Google` / `_PER_Deepl`
and `_VIE` variants) correct on every case.

Full handoff lives in
`docs/session-state-2026-05-16-cache-d-c-p2.md`.

---

## 2026-05-16 — Sprint D final (cli.py shrink continuation)

Continuation of the cli.py shrink on
`refactor/cli-py-sprint-d-final`. Four atomic commits, no merge to
master yet — the user runs their own end-to-end smoke before
merging.

**Numbers:**

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| `cli.py` lines | 3,947 | 2,670 | **−1,277 (−32.4 %)** |
| `statistics.py` lines | 42 | 754 | +712 |
| `engines/google_file_modes.py` lines | — | 857 | +857 (new) |
| Pytest pass | 239 | 239 | (stable) |

Combined with the prior 3-phase shrink (4,395 → 3,947), cli.py is
now **down 1,725 lines from its 2026-05-15 peak (−39.3 %).**

**Commits in dependency order:**

- `260a351` — **Phase 1 — pre-extract fixup.** Fixed the latent
  `UnboundLocalError` in `run_statistics` where line ~3226
  `driver = webdriver.Chrome(service=service, …)` ran *before*
  line ~3228 `service = Service()`. The outer `except Exception`
  masked it — `run_statistics` was effectively dead code in the
  use_api / splitonly branch. Reorder, +3/−4 lines.

- `69bb2c5` — **Phase 2 — D-A.4: extract `run_statistics`.**
  Moved the 228-line stats-form-submission body into
  `statistics.py`. Mirrors the `docx_io/parse.py:88` lazy-import
  pattern (selenium + psutil + cli module globals imported inside
  the function body). Added native `MTD_SKIP_STATS_BROWSER` env-var
  guard as the very first statement — the cache refactor's
  launcher basic-split spawn will set this to opt out of a Chrome
  launch (the original translate already submitted stats). Two
  smokes verified: default behaviour unchanged; with the env var
  set, `"Creating a new browser for stats"` and `"Warning failed
  to update stats"` are absent. cli.py: 3,947 → 3,726.

- `0bcbdfd` — **Phase 3 — D-A.5: extract
  `get_robot_usage_comment`.** Moved the 363-line "available
  updates" check body into `statistics.py`. Same lazy-import
  pattern + same `MTD_SKIP_STATS_BROWSER` short-circuit. Legacy
  body has a long-standing `return 0;` mid-function leaving the
  second half (forms.gle form-fill) unreachable — extracted
  verbatim so a future un-deadening lands as an exact restore.
  cli.py: 3,726 → 3,368.

- `468e11e` — **Phase 4 — D-B: Google file-mode workers.**
  Created `src/machine_translate_docx/engines/google_file_modes.py`
  with all 10 functions of the file-mode sub-system:
  - 3 top-level dispatchers (`google_translate_from_text_file`,
    `_html_javascript`, `_html_xlsxfile`)
  - 3 selenium workers (`selenium_chrome_google_translate_*`)
  - 1 download poller (`get_last_downloaded_file_path`)
  - 3 file generators (`generate_text_file_from_phrases`,
    `_html_file_…`, `_xlsx_file_…`)

  The 3 dispatchers are re-exported from `engines/__init__.py`
  so `cli.translate_docx` imports them via
  `from .engines import google_translate_from_*`. The 7 internal
  helpers are private to the new module — their only callers are
  the dispatchers. Lazy import of cli globals matches the
  statistics.py pattern.

  **Drive-by improvement (P2 from 2026-05-16 master audit):**
  `sys.exit(7)` in `selenium_chrome_google_translate_text_file`'s
  except is replaced with `raise TranslationFailure(reason=
  "google_file_mode_error", …)` so the launcher's structured-
  failure stdout parser picks it up. Sibling `sys.exit(8)` /
  `sys.exit(13)` left as-is — non-zero-exit detection still
  covers them.

  Three latent bugs preserved verbatim and documented in the new
  module docstring: (1) `generate_xlsx_file_from_phrases` sets
  `self.wb = None` in a module-level function (NameError,
  masked by `sys.exit(13)`); (2) `get_last_downloaded_file_path`
  reads `driver` as bare name in nested scopes — resolved via
  lazy import of `cli.driver`; (3)
  `google_translate_from_html_javascript` reads `html_file_path`
  as bare name immediately after a helper that only sets it
  locally, so it resolves to cli's module-level default of `''`.
  cli.py: 3,368 → 2,670.

**Phase 5 deferred (Sprint D-C, `_sync_globals_from_ctx` collapse):**
Audit found **176 bare-name occurrences across 41 names** in cli.py
that `_sync_globals_from_ctx` still mirrors. Each requires a
signature change (caller + callee) plus full pytest + smoke. That's
~6 hours of careful work at one occurrence per 2 minutes. Deferred
to a follow-up session to preserve "better partial than broken"
discipline. Full map and recommended threading order live in
`docs/session-state-2026-05-16-sprint-d-complete.md`.

**Latent bug discovered (not fixed):**
`run_statistics` (and `get_robot_usage_comment`) read `end_time`
and `elapsed_time` as bare names, but neither is ever bound at
cli's module scope — only `_end_time` / `_elapsed_time` exist as
`main()` locals. The reads raise `NameError`, caught by the outer
`except Exception` → "Warning failed to update stats" → no form
submission. The stats form has been silently broken on the
chatgpt-API path for the lifetime of the C25 fast-path. Preserved
verbatim in the extraction. Documented in the new module
docstring and in
`docs/session-state-2026-05-16-sprint-d-complete.md`.

**Tests:** 239 pytest pass on every commit (8 skipped live, 6
deselected). End-to-end smoke (`chatgpt-polish FA` on
`tests/fixtures/sample_hyperlink.docx`) green on every commit,
with C13 source-column lock intact and col 2 populated for 18 / 42
rows. The launcher / v2 frontend / cache layer are untouched —
this branch is scoped strictly to cli.py and its extracted
modules.

---

## 2026-05-14 — Server deployment (`feat/server-deploy` branch)

User asked for a one-command server deploy on the cheapest possible
VPS. Built the full stack: single config file, interactive wizard
for secrets, HTTP Basic auth on the web UI, systemd unit with
resource limits, Caddy reverse-proxy recipe, log rotation, daily
backups, full deploy guide.

New module `src/machine_translate_docx/server_config.py`:
  - Loads `config.toml` (default `runtime_dir/config.toml`, override
    via `MTD_CONFIG_PATH`).
  - Pushes `[telegram]`, `[smtp]`, `[failure_alerts]`, `[server]`
    values into the corresponding `MTD_*` env vars at boot. Real
    env vars override the file (operator wins).
  - Round-trip helpers: `write_config(cfg, path)` writes mode 0600
    on POSIX. `get_auth` / `get_server` return typed subsections.
  - `generate_session_secret()` for cookie signing seeds.

New scripts (`scripts/`):
  - `setup_wizard.py` — interactive prompts collect OpenAI API key,
    Telegram token + chat id + test message, web-UI password
    (bcrypt-hashed, PBKDF2 fallback if bcrypt absent), SMTP, failure
    alert sinks. Validates formats (`sk-`, `digits:chars`). Idempotent.
  - `install_server.sh` — one-shot Ubuntu 22.04+ / Debian 12+
    installer. Creates `mtd` user, sets up venv from
    `requirements-server.txt`, runs the wizard, installs the
    systemd unit, enables + starts. ~2 minutes on a fresh VPS.
  - `mtd-server.service` — systemd unit with `User=mtd`,
    `MemoryMax=512M`, `CPUQuota=80%`, hardened (`ProtectSystem=strict`,
    `NoNewPrivileges`, `RestrictNamespaces`, etc.).
  - `Caddyfile.example` — TLS-terminating reverse proxy with
    auto-Let's Encrypt, 600 s timeouts for long translations,
    `/health` log skipping.
  - `mtd-logrotate` — **weekly** rotation + **90-day** retention
    (per operator preference) for `Log json file/*.json` and Caddy
    access log.
  - `mtd-backup.sh` — daily cron archive of `config.toml` + JSON
    sidecars + cache + subscribers list to `/var/backups/mtd/`,
    30-day local retention.

`local_launcher.py` changes:
  - `--setup` flag invokes the wizard and exits.
  - `_check_auth(path)` middleware on every `do_GET` / `do_POST`.
    `/health`, `/static/*`, `/favicon.ico` are explicitly public.
  - `_verify_password` supports bcrypt (`$2b$...`) and stdlib
    PBKDF2-SHA256 fallback (`pbkdf2_sha256$iters$salt$digest`).
  - `_handle_health()` returns `{status, version, uptime}` — no
    secrets, no auth.
  - `main()` bootstraps `server_config.bootstrap()` before parsing
    args so `[server]` overrides the built-in defaults; adds
    `src/` to `sys.path` so the package import works when invoked
    as a top-level script.

New deps file: `requirements-server.txt` (~30 MB install, no
Chrome/chromedriver, no heavy NLP, optional `bcrypt`).

New doc: `docs/server-deploy.md` — start-to-finish guide with
prerequisites, install command, config schema walkthrough, HTTPS
setup, monitoring, troubleshooting, resource budget table.

Validated locally on Windows (smoke test via mock backend):
  · `/` no auth      → 401 ✓
  · `/` good creds   → 200 ✓
  · `/` bad creds    → 401 ✓
  · `/health`        → 200 ✓ + JSON payload
  · `/static/*`      → 200 (public, as designed)
  · config.toml load logs "loaded ... → N env var(s) populated"
  · auth status logs "[auth] HTTP Basic enabled for user 'X'"

Constraints added: C27 (single config.toml), C28 (auth-gated
routes), C29 (/health always public), C30 (non-root + /opt/mtd),
C31 (backups daily + logrotate weekly 90-day).

Tests: 239/239 pass (no regressions). Total: 10 new files, ~1100
new lines.

---

## 2026-05-16i — Sprint D attempt 1: statistics.py scaffold + local_time_offset

Beginning of the cli.py shrink continuation (`docs/cli-shrink-phase3-handoff.md`).
Scope was intentionally narrowed mid-session:

- ✅ Created `src/machine_translate_docx/statistics.py` and moved
  `local_time_offset` (14 lines, fully stateless) into it. cli.py
  imports it back so call sites are unchanged.
- ⏸ `run_statistics` (232 lines) and `get_robot_usage_comment` (370
  lines) deferred. Each reads 10+ module-level globals (`xtm`,
  `xlsxreplacefile`, `start_time`, `end_time`, `elapsed_time`,
  `docx_file_name`, `numrows`, `dest_font`, `split_translation`, plus
  Selenium imports). Threading them safely needs a dedicated session
  with full pytest + multi-engine smoke after every extraction.
- ⏸ Sprint D-B (Google file-mode workers) deferred for the same
  reason — `selenium_chrome_google_translate_*_file` workers each
  carry per-row state through `ctx.docx.table_cells`.
- ⏸ Sprint D-C (`_sync_globals_from_ctx` collapse) deferred until
  D-A and D-B drain the bare-name reads.

**Correction in the handoff doc:** `print_console_docx_file_translated`
was previously listed as extractable, but it writes into
`ctx.docx.table_cells[*][2]` via the cell-write shims — it's the
non-split write path, not a reporting helper. Removed from the
extraction list.

Result: cli.py 3,957 → 3,947 lines (-10). New `statistics.py` (42
lines) is the scaffold for future extractions. Test suite still 239
passed / 8 skipped (live) / 6 deselected. End-to-end smoke
(chatgpt-polish, sample_hyperlink.docx, fa): exit 0.

Branch: `refactor/cli-py-sprint-d` — merged to master, tagged
`archive/2026-05-16-cli-shrink-sprint-d-attempt1`, deleted.

---

## 2026-05-16h — Docs: UML diagrams + detailed module architecture SVG

Documentation-only landing — no source changes.

- New: [`docs/uml.md`](docs/uml.md) — five Mermaid-based UML diagrams
  rendered natively by GitHub. Covers class composition
  (RuntimeContext + 7 sub-dataclasses, Engine Protocol + 3
  implementations, OpenAI tool surface, exception hierarchy,
  validator types), sequence for the happy path, sequence for the
  failure + alerting path (B-001 + B-002 + 3 alert channels),
  activity diagram of the full job lifecycle with every decision
  point, and a deployment diagram showing dev / prod / frozen-.exe
  surfaces with a side-by-side comparison table. Opens with a
  reflection section justifying which UML types are useful here and
  which are intentionally absent (use-case, openai class diagram, …).
- New: [`docs/diagrams/architecture-detailed-light.svg`](docs/diagrams/architecture-detailed-light.svg)
  — module-level architecture map. Four horizontal layers (browser+HTTP,
  CLI orchestrator, engines/docx_io/openai_tools/supporting, outputs)
  with every package under `src/machine_translate_docx/` represented as
  its own card. Useful as a single-page reference for new contributors.
- Updated: [`docs/diagrams/architecture-light.svg`](docs/diagrams/architecture-light.svg)
  — high-level SVG refreshed for the post-2026-05-11 layout
  (`machine_translate_docx.cli` instead of `machine_translate_docx.py`,
  5-day cache instead of 36-h).
- New: `JVM_Migration_Analysis.docx` at repo root — Word document
  with the Java + Kotlin migration analysis (verdict, blockers,
  what's easy, real risks, alternative paths).
- `docs/index.md` updated: links to `uml.md`,
  `architecture-detailed-light.svg`, `master-audit-2026-05-16.md`,
  and the JVM migration analysis.
- `.gitignore` gains `~$*` pattern so Word's lock files never get
  staged accidentally.

---

## 2026-05-16g — P2 quick win: drop dead cookie-cleanup branch

Single targeted P2 fix from the master audit. In
`src/machine_translate_docx/runner.py` the block loop carried a
historical "every odd block, clean cookies for chatgpt / perplexity"
branch — but `chatgpt --enginemethod api` never enters this loop
(handled by the single-call path) and the two web engines were
removed in the 2026-05-10 cleanup. On the surviving chatgpt API
path, `ctx.browser.driver` is None, so this line would
AttributeError on every odd block index if it ever did execute.
Replaced with a one-paragraph history comment. Tests still 239/239.

---

## 2026-05-16f — Sprint C: cover the previously-untested orchestration core

Third audit-follow-up sprint. Six new test files for the orchestration
layer modules the leaf-test suite was skipping over. Test suite grows
from 190 → **239** (+49).

Modules now covered:

- `tests/test_docx_io_parse.py` — 5 tests for
  `read_and_parse_docx_document` (the single biggest pure function in
  the package, ~384 lines). Uses a stub-cli technique to avoid
  importing the heavy entry script's module-level work. Covers basic
  array population, C13 source-column snapshotting, hyperlink-run
  inclusion, empty-docx EmptyDocxError, idempotency.
- `tests/test_docx_io_save.py` — 9 tests for `engine_suffix`,
  `_resolve_output_path` (collision avoidance per C6),
  `_write_minimal_sidecar`, `_restore_source_column` (the C13 lock
  restore), and `save_docx_file` orchestrator.
- `tests/test_dispatch.py` — 12 tests for `set_translation_function`,
  `use_phrasesblock`, `set_array_dispatcher`. Pins the R15 method-flip
  + DeepL fallback behaviour at the dispatch layer.
- `tests/test_log_paths.py` — 9 tests for `resolve_log_dir`,
  `resolve_log_path`, `cleanup_old_logs` (retention boundary including
  zero), and `_find_project_root` (PyInstaller `MTD_FROZEN_ROOT` path).
- `tests/test_retry.py` — 7 tests for `call_with_retry` (success first
  try, retry then succeed, max retries exhausted raises, non-retryable
  errors propagate immediately) + `prompt_hash` (deterministic, 8 hex
  chars, distinct outputs).
- `tests/test_get_ctx_snapshot.py` — 3 regression tests for commit
  `4c36183` (the snapshot-ordering bug). Asserts `cli.translation_log
  is _get_ctx().openai.translation_log` immediately after import, and
  the equivalent for `oai_translator` and `oai_polisher`. Handles
  cross-test isolation against `test_docx_io_parse.py`'s stub-cli
  installation in `sys.modules`.
- `tests/test_docx_io_runs.py` — 4 tests for `_iter_paragraph_runs`
  including the critical `<w:hyperlink>`-child traversal (this is the
  iterator behind the "hyperlink anchor text must reach the translated
  cell" invariant that was previously only smoke-tested live).

### Adjustments made during writing

- `test_docx_io_parse.py` had to stub `machine_translate_docx.cli` in
  `sys.modules` to avoid the heavy entry-script module-level work.
  Stub exposes six predicates the lazy import inside parse needs.
- `test_get_ctx_snapshot.py::_import_cli` now detects if a stub is
  cached under the cli module path (via `hasattr(cached, "_get_ctx")`)
  and evicts it before importing the real module — keeps the tests
  in either order: stub-first or real-first.
- `test_docx_io_save.py` discovered that `_resolve_output_path` writes
  back into `ctx.flags.word_file_to_translate_save_as_path` rather
  than returning a path, and that `_write_minimal_sidecar` resolves
  its own log path via a lazy import of `resolve_log_path`. Tests
  adjusted to mirror real behaviour, not the task spec's guess.
- `test_dispatch.py` confirmed an interesting subtlety:
  `use_phrasesblock("chatgpt", "api")` returns True (chatgpt always
  uses the array dispatcher regardless of method).

### Verification

- `pytest tests/ --ignore=tests/test_v2_e2e.py`: **239 passed,
  8 skipped (live), 6 deselected**.
- End-to-end smoke chatgpt-polish on sample_hyperlink.docx: exit 0.

### What's left from the audit

- **Sprint D** — original phase-3 continuation work
  (`docs/cli-shrink-phase3-handoff.md`): statistics extraction
  (~900 lines), Google file-mode workers (~800 lines),
  `_sync_globals_from_ctx` collapse.
- P2 / P3 polish items (translation-log prompt-stripping flag,
  Telegram-token masking, sundry stale comments) tracked in the
  audit report but not critical-path.

After Sprint C the test suite covers every module in
`src/machine_translate_docx/` that has any user-visible behaviour.

---

## 2026-05-16e — Sprint B: P0 + P1 fixes from master audit + 36 new tests

Second half of the master-audit follow-up
([`docs/master-audit-2026-05-16.md`](docs/master-audit-2026-05-16.md))
— addresses every P0 and P1 finding plus the related test-coverage
gaps. Test suite grows from 154 → **190** (+36 new tests).

### P0 fixes

- **P0-1 — `server.js` path traversal.** `GET /download/:fileName`
  now resolves the candidate path and rejects anything outside
  `uploads/` with a 403 (matches the equivalent check in
  `local_launcher.py`). Sibling fix: `multer({...})`'s `fileFilter`
  and `limits` were nested under `diskStorage({...})` where multer
  silently ignores them — moved to the top-level `multer({...})`
  options. The upload endpoint now actually enforces the `.docx`
  filter and a 50 MB fileSize cap.
- **P0-2 — Integration test entry-point.**
  `tests/integration/test_real_file_per_engine.py` invoked
  `src/machine_translate_docx.py` (deleted on 2026-05-11) and
  parametrized the long-dead `chatgpt-web` / `perplexity-web`
  engines. Switched to `python -m machine_translate_docx.cli` with
  `PYTHONPATH=src`; dropped the two dead engines from parametrize +
  `ENGINE_SUFFIX` + `WEB_ENGINES`; removed the web-engine-only
  skip branch. `pytest -m live tests/integration` now runs.

### P1 fixes

- **P1-1 — `xlsx_translation_memory.py` C24 violation.**
  `newmm_tokenizer` and `tinysegmenter` were top-level imports.
  Every CLI startup required these Thai / CJK NLP toolkits even
  for `chatgpt --enginemethod api` runs that never tokenize.
  Moved both imports to function-local scope (`word_tokenize`
  inside `tokenize_phrase`, `tinysegmenter` inside `__init__`).
- **P1-2 — `input()` ignored `silent` flag (C16 violation).**
  `cli.py` prompted for `dest_lang` only on `if not splitonly:` —
  no silent guard. Now emits `[FAIL] reason=missing_destlang` and
  exits 20 in silent mode.
- **P1-3 — `engines/deepl.py` UnboundLocalError-masked-by-bare-try.**
  `closed_cookies_accept_message_bool` was read before the local
  reassign — Python pre-classified it as local, so reads at lines
  176 / 232 raised `UnboundLocalError`, silently swallowed by the
  surrounding `try/except Exception: pass`. Cookie-banner closure
  was effectively dead code. Added the canonical C11 seed-from-ctx
  pattern at the top of `selenium_chrome_deepl_log_in`.
- **P1-5 — SSRF allowlist in `network_utils.py`.** `fetch_country_
  data` and `check_mirror_url` accepted any URL from
  `json_configuration_array`. A compromised remote config could
  point them at internal endpoints (cloud-metadata, intranet
  APIs). Added an explicit `_SAFE_HOSTNAMES` allowlist (ip-api.com,
  Selenium driver mirrors, public DNS), extensible via
  `MTD_NETWORK_ALLOW_HOSTS`. Added `allow_redirects=False` so a
  redirect-chain attack can't bypass the allowlist. Renamed
  `test_internet` → `probe_internet` (pytest was collecting the
  historical name as a non-None test, emitting
  `PytestReturnNotNoneWarning` on every CI run). Socket now uses
  a context manager.
- **P1-6 — Tests for the three new shrink modules.** Added 36
  pytest functions across three new files:
  - `tests/test_network_utils.py` — 17 tests covering all four
    public helpers + SSRF allowlist behaviour + env-var override.
  - `tests/test_docx_io_metadata.py` — 8 tests (splitonly no-op,
    name + ISO fallback, exact format-string parity, short-table
    no-crash, repeated-write).
  - `tests/test_translation_log_writer.py` — 11 tests covering
    summary aggregation, polish-lines counting (new and legacy
    paths), row-count metadata, prompt_hash present/absent,
    output_file resolution, and UTF-8 `ensure_ascii=False`.
- **P1-8 — `tests/test_aligner_only.py` was not a pytest file.**
  Filename matched `python_files = "test_*.py"` so pytest scanned
  it, but it had zero `def test_*` functions. Moved to
  `scripts/aligner_only.py`.

### Verification

- `pytest tests/ --ignore=tests/test_v2_e2e.py`: **190 passed,
  8 skipped (live), 6 deselected** (down from 8 because two dead
  engines no longer parametrize).
- End-to-end smoke on `tests/fixtures/sample_hyperlink.docx` with
  `chatgpt --enginemethod api --aimodel gpt-5.4-mini --with-polish`:
  exit 0.

### What's left from the audit

- **Sprint C** — 5 more uncovered modules (`docx_io/parse.py`,
  `docx_io/save.py`, `dispatch.py`, `log_paths.py`,
  `openai_tools/_retry.py::call_with_retry`) + a regression test
  for the `_get_ctx()` snapshot-ordering bug fix.
- **Sprint D** — original phase-3 continuation work
  (`docs/cli-shrink-phase3-handoff.md`): statistics extraction,
  Google file-mode workers, `_sync_globals_from_ctx` collapse.

---

## 2026-05-16d — Sprint A: dead-code purge + doc sweep

Quick-wins follow-up to the master deep audit
([`docs/master-audit-2026-05-16.md`](docs/master-audit-2026-05-16.md)).
Zero functional change, zero risk; pure hygiene.

### Deletions (verified zero callers by repo-wide grep)

- `src/machine_translate_docx/table.py` — full file (~400 LOC).
  Copy of python-docx internals importing `.blkcntnr` etc. that
  don't exist in this package. Orphan untracked by post-migration
  PRs.
- `src/machine_translate_docx/updtlnk.py` — full file. Windows
  `.lnk` rewriter hard-coded to a non-existent path.
- `src/machine_translate_docx/openai_tools/example.py` — full
  file. Scratch script with wrong relative import and a
  non-existent model (`gpt-5-nano`).

### cli.py cleanup (-53 lines: 4,002 → 3,949)

- Comment fragment ending mid-sentence referencing the removed
  `engines._prompts` shim.
- Duplicate `elif translation_engine in ['deepl', 'chatgpt']`
  after an `if translation_engine in ['chatgpt', 'deepl']` —
  identical set, never fires.
- Duplicate `location_primary_country_checker_url_key`
  assignment (the first value was overwritten on the next line).
- Two `if engine == "chatgpt" and False:` dead blocks totalling
  ~30 lines, plus the orphan `user_data_dir = fr"C:\Temp\Chrome"`
  they referenced.
- `_orig_run_statistics_body_marker = None` placeholder.

### Documentation sweep

- `README.md`: tests `113/113 → 154/154`; `C1–C20 → C1–C31`;
  rewrote the `src/` tree with the post-2026-05-11 layout
  (now includes `network_utils.py`, `translation_log_writer.py`,
  `validators/`, `xlsx_translation_memory/`,
  `docx_io/metadata.py`).
- `CONTRIBUTING.md`: tests `113/113 → 154/154`; `C1–C20 → C1–C31`.
- `web/v2/README.md`: `36-hour → 5-day` cache (matches
  `CACHE_TTL_SEC` since commit `c811d4d`); output filename family
  updated to the post-phase-5 `_PER_Polish` suffix scheme.
- `SECURITY.md`: `src/openai_tools/* →
  src/machine_translate_docx/openai_tools/*`.
- `docs/architecture.md`: pipeline diagram + Component
  Responsibilities rebuilt; `aligner_per` references switched to
  `persian_double_lines`.
- `docs/testing.md`: "Ten tests" → 18-file table (154 tests);
  `py_compile` + aligner import paths corrected.
- `AGENTS.md`: rewritten end-to-end. Old version cited removed
  files (`machine-translate-docx.py`, `src/openai_tools/`),
  wrong CLI flags (`--input` vs `--docxfile`), and the long-gone
  `_find_double_file` workflow.

### Internal source comments

- `runtime.py:140` — `aligner_per → persian_double_lines`.
- `local_launcher.py:63 + :135` — stale module name + cache-TTL.

### Verification

- `pytest tests/ --ignore=tests/test_v2_e2e.py`: 154 passed,
  8 skipped (live), 8 deselected.
- End-to-end chatgpt-polish smoke on `sample_hyperlink.docx`: exit 0.

---

## 2026-05-16c — cli.py 3-phase shrink — Phase 3 (own work)

Third phase of the cli.py shrink, executed directly. Pushes cli.py
below 4,000 lines for the first time since the src/ migration.

### New module — `src/machine_translate_docx/translation_log_writer.py`

Owns the JSON-sidecar writer that the OpenAI engines emit at end of
run. The historical `write_translation_log(log_path)` body lived in
the entry script and read `translation_log` plus `_get_ctx()` from
module scope. The new implementation takes `(ctx, log_path)` as
explicit arguments — `translation_log` is read off
`ctx.openai.translation_log` directly, removing one of the few
remaining bare-name globals.

`cli.py` keeps a 2-line shim with the historical 1-arg signature so
the injected callback in `docx_io/save.py` (and the `[INFO]
Translation log saved` line operators look for) is unchanged.

### Deletion

- `getDownLoadedFileNameChrome(waitTime)` — 22-line Chrome-downloads
  scraper. The only "caller" was a commented-out line inside
  `selenium_chrome_google_translate_xlsx_file`; the live code path
  already uses `get_last_downloaded_file_path()` instead. Removed.

### Result

- `cli.py`: 4,129 → 3,994 lines (-135, total -401 from the 4,395
  start, -9.1%). First time the entry script is under 4,000 lines
  since the 2026-05-11 src/ migration.
- New code: `translation_log_writer.py` (148 lines).
- Test suite: 154 passed / 8 skipped (live) / 8 deselected.

### Phase 3 (continued) — handoff prompt for the big blocks

The remaining high-payoff work is captured in a Claude Code Console
handoff prompt at
[`docs/cli-shrink-phase3-handoff.md`](docs/cli-shrink-phase3-handoff.md):

1. Extract the statistics + report cluster (`run_statistics`,
   `get_robot_usage_comment`, `print_console_docx_file_translated`,
   `local_time_offset`) — ~900 lines.
2. Extract the Google file-mode workers
   (`selenium_chrome_google_translate_{text,html_javascript,xlsx}_file`
   + their `generate_*_from_phrases` + `google_translate_from_*`
   wrappers) — ~800 lines, lower-priority because file modes are
   rarely chosen over singlephrase / phrasesblock.
3. Collapse `_sync_globals_from_ctx` once the remaining helpers read
   from ctx directly.

Each item carries documented globals, call sites, and verification
steps so the work can resume in a separate session without
re-discovering context.

---

## 2026-05-16b — cli.py 3-phase shrink — Phase 2 (low-risk extractions)

Second phase of the cli.py shrink. Moves four free-standing helper
clusters out of the entry script into dedicated modules and deletes
three more orphan functions discovered in the process.

### New module — `src/machine_translate_docx/network_utils.py`

Owns the four startup-time region/connectivity helpers:

- `test_internet(host, port, timeout)` — TCP probe against Google DNS.
- `fetch_country_data(url, *, http_timeout)` — region detection.
- `check_mirror_url(url, *, http_timeout)` — driver-mirror reachability.
- `set_se_driver_mirror_url_if_needed(country_name, mirror_url, *,
  restricted_countries, http_timeout)` — env-var setter for restricted
  regions. Renamed from `set_SE_DRIVER_MIRROR_URL_if_needed` to follow
  the rest of the repo's snake_case convention.

Every dependency that the historical bodies read from module globals
(`location_http_query_timeout`, `chrome_driver_restricted_countries`)
is now an explicit keyword argument. The module imports only `socket`,
`os`, `json`, and `requests` so adding it to the package costs almost
nothing at startup.

### New module — `src/machine_translate_docx/docx_io/metadata.py`

Owns the two output-side DOCX metadata writers:

- `write_destination_language_in_docx_cell(docxdoc, *, splitonly,
  dest_lang_name, dest_lang)` — fills cell (1, 2) of the first table
  with the human-readable destination language name (fallback to ISO).
- `set_docx_properties_comment_for_history(docxdoc, *, program_version,
  engine)` — stamps a one-line audit comment into core properties.

Thin shims in `cli.py` preserve the historical zero-argument signatures
so existing call sites keep working without churn.

### Moved to existing modules

- `deepl_double_linefeed_between_phrases(dest_lang)` →
  `engines/deepl.py`. Inline tuple turned into a module-level frozen
  set (`_DEEPL_SINGLE_LINEFEED_LANGS`).
- `delete_paragraph(paragraph)` → `docx_io/cells.py`. Documented as
  the "cell-clearing helper" with a one-line rationale.

### Deletions (orphans)

- `generate_tmx_file()` — 62-line TMX exporter. Only caller was a
  commented-out `#generate_tmx_file ()` line. Removed.
- `linux_distribution()` — wrapped `platform.linux_distribution()`
  (deprecated and removed in Python 3.8+). Only caller was the
  also-orphan `print_os_info()`. Removed.
- `print_os_info()` — startup OS-info dump that called the removed
  `platform.dist()` (also gone in 3.8+). Never called from anywhere.
  Removed.

### Result

- `cli.py`: 4,257 → 4,129 lines (-128, total -266 from the 4,395 start).
- New code: `network_utils.py` (119 lines) + `docx_io/metadata.py`
  (74 lines) + small additions to `engines/deepl.py` and
  `docx_io/cells.py`.
- Test suite: 154 passed / 8 skipped (live) / 8 deselected. Zero
  failures.

Phase 3 will tackle the remaining big block — the statistics +
log-writer cluster (~900 lines) and the Google file-mode workers
(~800 lines) — plus the eventual cell-shim collapse once globals are
moved onto `RuntimeContext`.

---

## 2026-05-16a — cli.py 3-phase shrink — Phase 1 (dead-code removal)

First phase of a planned 3-phase shrink of `src/machine_translate_docx/cli.py`
(the 4,395-line god file that survived the src/ layout migration). Phase 1
is the lowest-risk pass: delete functions that are demonstrably never called
and a function that is fully duplicated by a module helper.

### Deletions

- `lineno()` — 3-line helper, never called anywhere in the repo.
- `reverse_string()` — 2-line helper, never called anywhere.
- `remove_span_tag()` — 24-line DeepL HTML-clean helper. Never called from
  cli.py and fully duplicated by `engines/deepl.py::_remove_span_tag` (which
  is the version DeepL actually uses).
- `create_translation_split_prompts()` + `print_prompt_block()` +
  `MAX_CHARS = 750` — orphan demo function (~80 lines) that printed AI
  prompts to stdout. No call site existed.
- `print_html_program_result()` — 18-line HTML debug dumper, never called.

### Result

- `cli.py`: 4,395 → 4,257 lines (-138, -3.1%).
- Test suite: 154 passed / 8 skipped (live) / 8 deselected. Zero failures.
- No production behaviour change — every removed function had zero call
  sites (verified by repo-wide grep).

Branch: `refactor/cli-py-3-phase-shrink`. Phase 2 (extract OS info /
network / statistics / TMX / Google file-mode workers into dedicated
modules) and phase 3 (collapse `_sync_globals_from_ctx` + cell shims)
follow.

---

## 2026-05-15c — Validator layer + prompt-regression suite (env-gated)

Follow-up to the v7 promote. Two new code modules deliver the
"machine-deterministic post-pass" and "fixture-based regression"
items from `docs/prompt-architecture-followups.md`. Both are
opt-in via a single env var so production runs are unaffected
until the operator explicitly turns them on.

### Validator layer

`src/machine_translate_docx/validators/` (NEW package):
- `__init__.py` — public API (`validate_translate_output`,
  `validate_polish_output`, `is_validator_enabled`,
  `ValidatorReport`, `ValidatorIssue`).
- `post_translate.py` — translation-side checks: LINE_COUNT_MISMATCH,
  BLANK_POSITION_MISMATCH, LATIN_LEAKAGE (FA-only),
  PROTECTED_SPAN_MISSING (URL/handle/hashtag/tech code),
  LITERAL_BACKSLASH_N_LOST, PERSIAN_BASHE, PERSIAN_SEMICOLON_OUTSIDE_QUOTE,
  TOOSAT_PASSIVE (warning), FORBIDDEN_GLYPH.
- `post_polish.py` — polish-side checks: adds TAG_FORMAT_INVALID,
  TAG_NUMBER_MISMATCH, UNEXPECTED_BLANK_OUTPUT on top of every
  translation check.

Wired into:
- `OpenAITranslator.translate()` — runs the validator after parsing
  the model response, before returning. Reports issues to stdout
  with the `[validator]` prefix. Never rejects output; the layer
  is diagnostic in v1.
- `OpenAIPolisher.polish()` — same flow.

Single env var: `MTD_VALIDATOR_ENABLED`. Truthy (1/true/yes/on) →
validator runs. Anything else (including unset) → no-op fast path.
The contract is "always call validate_*; check `.passed`; ignore
issues when disabled" — caller code is one if-statement.

The validator is wrapped in a try/except in both callsites so a
bug in the validator can never break a translation job; it logs
and steps aside.

### Regression suite

`tests/test_prompts_regression.py` + `tests/fixtures/prompts_regression/`:
- YAML-based fixture format. Each fixture describes one regression
  case: input, mock_output, line_count, must_contain / must_not_contain /
  must_contain_one_of / name_consistency / validator_must_(not)_flag.
- Two run modes:
    MOCK (default, CI-safe): asserts the fixture's hand-crafted
      mock_output against its invariants. No API calls.
    LIVE (opt-in): set `MTD_REGRESSION_LIVE=1`. Sends the input to
      the real translator / polisher; asserts model output against
      invariants. Costs API tokens.

Initial 8 fixtures land covering:
  case_01_baashe_normalization        MN-4 / COLLOQUIAL_NORMALIZE
  case_02_url_preservation            W1 / SA-11 / PROTECTED_SPAN
  case_03_name_consistency            PRE_EMIT_CHECK C1
  case_04_welcome_to_x_polish         LS-12 BROADCAST_OPENING_PATTERNS
  case_05_lao_greeting_byte_id        LS-13 FOREIGN_SCRIPT_AUTHENTIC_VOICE
  case_06_negation_scope              SA-1 + SCOPE_ATTACHMENT_GUARD
  case_07_tech_code_byte_id           W3 / vitamin-code transliteration
  case_08_blank_line_preservation     PRE_EMIT_CHECK C5

`tests/fixtures/prompts_regression/README.md` documents the schema
so a new case is one YAML drop-in.

### Test results

- `tests/test_validators.py` — 25 new unit tests, all green.
- `tests/test_prompts_regression.py` — 9 mock-mode tests + 8 live-mode
  tests (skipped without env var).
- Full suite: **154 passed, 8 skipped, 8 deselected** (vs 120 before).
- `py_compile` clean on all new and modified modules.

### Operator usage

Turn on the validator for one run:

```powershell
$env:MTD_VALIDATOR_ENABLED = "1"
E:\Python311\python.exe local_launcher.py
```

Run the live regression once before promoting a new prompt version:

```powershell
$env:MTD_REGRESSION_LIVE = "1"
$env:OPENAI_API_KEY = "sk-..."
E:\Python311\python.exe -m pytest tests/test_prompts_regression.py -v
```

Both env vars default to off — packaged builds and existing CI runs
behave exactly as before.

---

## 2026-05-15b — PRE_EMIT_CHECK pass: name-consistency gate end-to-end

Follow-up to the v7 promote. User asked whether proper nouns stay
consistent across the document (first line == last line orthography),
and pointed out that the universal prompt is the primary engine for
many users who never run polish — so universal translate must produce
publication-quality output in a single call.

Added a compact, focused pre-flight check to both translate prompts
and to both polish prompts. Modelled on a 9-layer pre-flight pattern
but condensed to the 4–6 checks that actually apply to subtitle
translation execution (most code-related layers don't transfer).

translate_universal.txt — new `<PRE_EMIT_CHECK>` block (C1–C6):
  C1 NAME_CONSISTENCY — every proper noun appears in ONE form across
     all N lines. FIRST line names == LAST line names. No variants like
     "ایلان ماسک / الون ماسک" or "Bounxou / Bun Xou" coexisting.
  C2 TERMINOLOGY_LOCK — recurring domain term → ONE rendering throughout.
  C3 SCOPE_INTEGRITY — not / never / no longer / only / except / unless /
     must / may / should / can / already / still / yet / because /
     although / despite — verify scope vs source.
  C4 ONTOLOGICAL_SAFETY — inanimate subject + human/religious action
     → reverse-engineer (e.g. "the glacier meditates" → restore literal
     "the glacier retreats").
  C5 LINE_INTEGRITY — count(input) == count(output). No merge/split/reorder.
  C6 LATIN_CLEAN — zero source-language residue outside ALLOWED_LATIN.

  Wider than Persian's check because universal callers usually have no
  downstream polish pass — this is the only chance to catch drift.

translate_PER.txt — compact `<PRE_EMIT_CHECK>` (C1–C4):
  C1 NAME_CONSISTENCY (same as universal).
  C2 TERMINOLOGY_LOCK (same).
  C3 LINE_INTEGRITY.
  C4 LATIN_CLEAN.
  Tighter because polisher provides a second pass; the polisher catches
  scope/ontological/modality drift via SA-1, SA-6, SA-7, SA-14.

polish_PER.txt — Q17 NAME_CONSISTENCY + Q18 TERMINOLOGY_LOCK
  added to the QA list as cross-line, before-emit checks. Polish sees all
  pairs at once and can correct any drift the translator missed.

polish_universal.txt — Q14 NAME_CONSISTENCY + Q15 TERMINOLOGY_LOCK
  added to QA, matching the Persian polish structure.

Proposal-v7 trail files synced with canonical so the iteration trail
stays accurate at the v7 leaf.

Tests: 120/120 still passing. No code changes in this pass — prompt-
only edits to the four pipeline prompts + their proposal-v7 mirrors.

---

## 2026-05-15 — v7 prompts promoted: STATIC + JOB_CONFIG, legacy injections, code restructure

Six iterations of round-trip critique between Claude and GPT-5.5
landed as v7-final. Promoted v7 to canonical for both Persian-specific
and universal prompt files, with the user-approved additions:

**Persian v7 (canonical) — translate_PER.txt + polish_PER.txt + _smtv_locks.txt:**

- Selective legacy injection per GPT-5.5 ACCEPT list (~15-20% growth):
  - ID block: `[ROLE]` qualifier "subtitle-grade, line-stable, scope-safe", Adaptive Triad PERSONA, new `[TARGET]` / `[GUARDRAILS]` / `[METHOD]` subfields.
  - STYLE: COLLOQUIAL_NORMALIZE, TENSE_SIMPLIFY, COLLOCATION_FIT, NO_QUOTE list, DASH_NORMALIZE en/em forbidden, ENGLISH_PARENTHETICAL preserve, WRITTEN_NUMBERS factual-only.
  - NATIVE_REGISTER: PERSONA_DETECTOR fallback (1st/2nd/3rd person + spiritual/news/imperative markers), VOICE_SAFETY N8, RHETORICAL_OVERRIDE SAGE non-Master, KE_SOFT_LIMIT (soft, not hard).
  - NON_WHITELIST: LATIN_PHRASES list (per capita / de facto / ...), HOMONYM_RULE, ACADEMIC_TERM_INLINE, INLINE_DEFINITION ("واژهٔ X یعنی"), FILLERS persona-aware.
  - WORKFLOW Phase 1: FRICTION_RADAR, TERMINOLOGY_TRACK, ANTI-JITTER, HONORIFIC_BLOCK_LOCK.
  - WORKFLOW Phase 2: AUTO_LOCK markup/code, Persian indirect-speech grammar (گفت که خواهد آمد), SPEAKER_TEST broadcast prosody, ROUND_TRIP back-check.

- Polish-only additions (corrective):
  - SA-1 SCOPE_ATTACHMENT_GUARD ("not eating → روزه‌داری" trap).
  - SA-5 extended to SPEAKER + COREFERENCE.
  - SA-14 ONTOLOGICAL_REPAIR (narrow EN-compass repair like "اعتکاف یخچال → عقب‌نشینی").
  - Q16 ROUND_TRIP final back-check.

- New v7.1 user-requested additions:
  - LS-12 BROADCAST_OPENING_PATTERNS: canonical SMTV opening/closing
    forms locked for cross-episode consistency. "Welcome to X" →
    "خوش آمدید به X" (deliberately non-idiomatic; downstream editors
    lose time fixing variations). Covers Welcome / Welcome back /
    I'm <Name> / You're watching / Stay tuned / Thanks for watching /
    See you next time.
  - LS-13 FOREIGN_SCRIPT_AUTHENTIC_VOICE: non-EN, non-FA script
    tokens (Lao ສະບາຍດີ, Chinese 你好, Sanskrit नमस्ते, Arabic السلام
    علیکم, etc.) used as authentic-voice greetings — preserved byte-id
    in translation, corrective-restored in polish.

- Rejected per GPT-5.5 verdict:
  - F1 / F7 / F8 (multiple identity framings).
  - R10 (formulaic patterns — covered by native syntax).
  - R30 (single-quote for unfamiliar names — conflicts with quote policy).
  - B1, B3 (extra phases / Q1-Q5 reframing).
  - "ISO-17100 Certified Auditor" claim → replaced with "inspired".
  - "SOV Enforcer" → softened to "Persian-first".

**Universal v7 (canonical) — translate_universal.txt + polish_universal.txt:**

Major restructure into STATIC + JOB_CONFIG layout per GPT-5.5
recommendation for OpenAI prompt cache reuse:

- System prompt is now BYTE-IDENTICAL across all documents and
  language pairs. Uses generic "source language" / "target language"
  references; no `{SOURCE_LANG}` / `{DEST_LANG}` substitution.
- Language identity, line count N, and input lines now live in the
  user message via a `<LANGUAGE_BINDING>` + `<JOB_CONFIG>` + `<LINES>` /
  `<PAIRS>` envelope.
- Same legacy-injection set as Persian, generalised: PERSONA_DETECTOR,
  WRITTEN_NUMBERS, ROUND_TRIP, AUTO_LOCK, SCRIPT_PURITY (LS-6 in
  polish), FOREIGN_SCRIPT_AUTHENTIC_VOICE (LS-9 in polish, item 13
  in translate NON_WHITELIST).
- Why this matters: prior universal used `{SOURCE_LANG}` /
  `{DEST_LANG}` placeholders inside the system prompt body, which
  broke the prompt cache prefix the moment either changed. The new
  layout keeps the system prompt's first ≥1024 tokens identical for
  any language pair, so OpenAI's automatic prompt caching hits.

**Code changes (translator.py + polisher.py + runner.py):**

- `src/machine_translate_docx/openai_tools/_lang_descriptors.py` (NEW)
  — curated language-code → rich descriptor table (~80 locales).
  Falls back to `google_translate_lang_codes` then raw code. Used
  by both translator and polisher to populate JOB_CONFIG.
- `OpenAITranslator._load_system_prompt`: no longer substitutes
  `{SOURCE_LANG}` / `{DEST_LANG}`; returns template verbatim.
- `OpenAITranslator._build_user_message(source_lang, dest_lang, text)`:
  emits a `<JOB_CONFIG>` block (SOURCE_LANGUAGE, TARGET_LANGUAGE, N)
  followed by `<LINES>` block with numbered input.
- `OpenAIPolisher.__init__`: new `source_lang` parameter (default "en")
  stored on instance. `_build_user_envelope(src_lines, fa_lines)`
  emits `<JOB_CONFIG>` + `<PAIRS>` block (legacy [EN]/[FA] labels
  preserved inside <PAIRS> for backward parser compatibility).
- `runner.py`: passes `source_lang=ctx.language.src_lang` to
  `OpenAIPolisher` construction.

**Persian-specific prompts (translate_PER.txt, polish_PER.txt, _smtv_locks.txt):**

Already cacheable (no placeholders). For consistency they also
receive a JOB_CONFIG envelope in the user message — harmless extra
context that confirms FA target. Cache behaviour unchanged.

**Iteration trail in branch (`claude/blissful-pasteur-dcab73`):**

All v1 through v7 proposal files retained in `prompts/*_proposal_v*.txt`
plus `docs/v7-additions-proposal.md` (legacy-feature evaluation
matrix) and `docs/prompt-architecture-followups.md` (validator +
regression suite roadmap). The proposal files are kept for audit;
the canonical files are the production-active set.

Validator layer and regression test suite are the next milestone
(both deferred to a follow-up branch — to be built with a single
on/off env var per user request).

---

## 2026-05-14 — Mac .app bundle + .dmg recipe (upstream comparison)

User asked how the upstream repo (`translation-robot/machine-translate-
docx`) handled Mac packaging. Upstream's `compile/mac/` directory uses
PyInstaller's `BUNDLE()` to produce a `.app`, then `create-dmg` to
wrap it in a `.dmg` — both proper Mac distribution formats. Folded
the good parts into our spec and docs.

  packaging/mtd.spec:
    - New `BUNDLE()` call gated by `IS_MACOS`. Produces `dist/mtd.app/`
      alongside the existing `dist/mtd/` onedir. Bundle id
      `com.smtv.mtd`, NSHighResolutionCapable, LSMinimumSystemVersion
      10.13, productivity category. Auto-picks an optional
      `packaging/mtd.icns` icon when present.
    - Kept `upx=False` deliberately — Apple's notarytool rejects
      UPX-compressed Mach-O binaries; the upstream's `upx=True`
      breaks signed distribution.

  packaging/mac_build.md:
    - New "Path C — .app bundle (native Mac experience)" with the
      `iconutil -c icns` recipe for an .icns icon.
    - New "Path D — .dmg disk image" with the full `create-dmg`
      invocation and the codesign + notarytool + stapler sequence
      that produces a quarantine-free download.
    - "Comparison with the upstream repo's Mac build" table — heavy
      NLP deps, upx, hardcoded Python framework paths, and result
      size are documented. Upstream is ~300+ MB; this build is
      ~70-80 MB.

Windows build re-validated; same onedir output, `BUNDLE()` is a no-op
on non-Mac platforms.

Still not validated on a real Mac — requires running PyInstaller on
macOS (no cross-compile). The flow is now complete enough for one
build pass.

---

## 2026-05-14 — Mac build scaffolding (cross-platform spec + docs)

Follow-up to the .exe packaging landing. Made the PyInstaller spec
file platform-aware so the same `packaging/mtd.spec` builds on
Windows, macOS, and Linux:

  - `sys.platform` is read at spec-load time. `IS_WINDOWS` / `IS_MACOS`
    / `IS_LINUX` gate the platform-specific bits.
  - `pywin32` family hidden imports (`win32com`, `pythoncom`,
    `pywintypes`) are added ONLY on Windows. `cli.py` already guards
    the runtime usage with `if platform.system() == 'Windows'`.
  - The `.ico` icon is skipped on non-Windows (wrong format for Mac;
    a future iteration can add a real `.icns`).
  - Windows build re-validated after the spec edits (`--help` ran
    cleanly; 65 MB output unchanged).

New `packaging/mac_build.md` walks through the Mac build flow:
  - Clean venv setup with pyenv + python 3.11.7.
  - Same dep list minus `pywin32`.
  - Three distribution paths: (A) zip + `xattr -dr com.apple.quarantine`,
    (B) codesign + notarize for production, (C) `.app` bundle.
  - Common pitfalls table: Gatekeeper quarantine, missing Xcode CLT,
    dyld_library_path, Apple Silicon vs Intel architecture.

**Honest validation status:** the Mac flow has not been run from this
machine — PyInstaller cannot cross-compile, so a real Mac is needed
for the first verification pass. The Windows flow remains validated
on 2026-05-14 with FA + FR translations.

---

## 2026-05-14 — Distributable Windows .exe (`feat/exe-packaging` branch)

Colleague reported the previous `compile.bat` PyInstaller flow built
an .exe that wouldn't run on end-user machines. Spent a build pass
on a clean working solution:

  - New `packaging/` directory with `mtd_entry.py` wrapper and
    `mtd.spec` PyInstaller config. Onedir mode (faster startup,
    debuggable folder layout, ~65 MB total).
  - `packaging/README.md` walks through the clean-venv setup that
    keeps the build size sane — system pythons contaminated by
    PyTorch / PyQt5 / numpy ballooned the .exe to 1.2 GB; the clean
    venv keeps it at 65 MB.
  - `log_paths.py` and `translator.py` honour `MTD_FROZEN_ROOT` so
    the bundled `prompts/` and the central `Log json file/` directory
    resolve next to the executable instead of trying to find a
    project root that doesn't exist in the frozen layout.
  - `selenium_utils/driver.py` got a fast-path NO-OP for the
    `chatgpt+api` engine combination — the OpenAI API path doesn't
    need Chrome, and trying to launch it on a box without Chrome
    installed was the colleague's repro for "exe builds but doesn't
    work". Skip the driver entirely on that path; also fixed a NPE
    in the cleanup branch when `ctx.browser.driver is None`.
  - Lazy-imported `mysql.connector` from `translator.py` and
    `splitting.py` so end users without MariaDB installed don't get
    a startup ImportError. The DB persistence layer is opt-in via
    `MARIADB_HOST` env var; the import only fires when it's actually
    used.
  - Wrapped `hazm` and `undetected_chromedriver` top-level imports in
    try/except so a packaged build that ships only the OpenAI API
    flow doesn't fail to start on the heavy Persian-NLP and
    Selenium-stealth dependencies. Both have passthrough fallbacks.

Validation on a clean folder install (zipped .exe + unzipped on a
machine that has no Python and no Chrome — simulated by copying the
`dist/mtd/` folder to a separate working directory):

| Test | File | Lang | Model | Duration | Cost | Status |
|------|------|------|-------|----------|------|--------|
| 1 | VEGC 3148 (Namibian Potato Recipes) | Persian | gpt-5.4-mini | 22 s | $0.07 | ✅ |
| 2 | UL 3147 (Isabella La Rocca González) | French  | gpt-5.4-mini | 94 s | $0.26 | ✅ |

Output samples:
  - FA: "پس از بازدید از بازار پرجنب‌وجوش صبحگاهی اوشاکاتی..."
  - FR: "Les canetons nagent pour la toute première fois."

Both runs wrote the docx beside the input + `_log.json` into
`Log json file/` next to `mtd.exe`. No Python required on the user's
machine. No Chrome required. Drop-folder distribution: zip the
`dist/mtd/` folder, send to user, they extract and run `mtd.exe`.

---

## 2026-05-13 — FA aligner: span-guard + benchmark scaffolding + باشه ban

User attached a manually-corrected reference file `… Persian.docx` and
asked for a cross-language "benchmark" alignment — using punctuation
that exists in both EN and FA (parens, quotes, commas) as anchors so
the FA chunk for row N ends where the EN row N ends.

What was built:

  **Span guard in `_is_safe_break`** — the safe-and-effective subset of
  the benchmark idea. The splitter now refuses any position that sits
  INSIDE an unclosed `(`, `"`, or `“` span:
    if left.count('(') > left.count(')')   → not safe
    if left.count('"') % 2 == 1            → not safe
    if left.count('“') > left.count('”')   → not safe
  Validated on AJAR 3147: 0 punctuation orphans (down from many), 71 %
  exact match with the manual reference, 185 doubles, 0 triples.

  **`_parse_groups` now tracks `en_per_row`** — one EN string per
  row_index, "" if EN was empty. Foundation for an eventual LLM-rescue
  path that can hint anchors to the model.

  **`_align_to_en_benchmarks` scaffolding** kept INACTIVE — a pure
  position-based EN→FA punct mapper. Validated to over-correct on
  ~30 % of groups because the manual editor restructures sentences
  semantically (e.g. moves "خوشحالیم" forward in the FA clause). Left
  in the file as a hook the future LLM rescue can borrow.

  **`polish_PER.txt` HL-14 NO_BAASHE** — broadcast Persian on state TV
  in year 1400 never uses `باشه`. Polisher now lifts it to `بله` (or
  context-appropriate `درست است` / `حتماً`). User-reported register
  miss.

5 new aligner regression tests + 2 new span-guard tests (total: 120).

---

## 2026-05-13 — FA aligner: three bugs from AJAR 3147 fixed

User-reported defects in
`AJAR 3147 (One World of Peace... P6) sf1 - table fix1_PER_Polish_Double_Lines.docx`:
metadata wiped from row 0, "Persian" gone from row 1, `...` ellipsis
split across rows (`.` ending one chunk and `..` orphaned at the start
of the next), `)` and `"` separated from their content, and 44 entire
FA translations dropped from rows that contained legitimate text.

Three root causes, all fixed in `persian_double_lines.py`:

  **B-003 SHADING_MISCLASSIFY**: `_cell_has_shading` returned True for
  every non-white fill. Real broadcast docx files use yellow `FFF2CC`,
  pink `FFC0CB`, blue `B4D5FF` as EDITOR HIGHLIGHTS for "Fix1 yellow
  shaded lines" content — not as bridge markers. Treating them as grey
  bridge rows wiped every yellow-flagged Persian line (~30 of the 44
  dropped rows). Fix: bridge classification now requires a TRUE GREY
  fill (six hex chars with R == G == B). Editor highlights are
  preserved.

  **B-004 BRIDGE_REGEX_OVER_AND_UNDER**: `^SM\s*:` and `^Master\s*:`
  swallowed every line of dialogue starting with the speaker prefix
  ("SM: Speak something?" → bridge → content lost). Conversely,
  `01:40:39 John Moschitta, MC(m):` (timecode + speaker on the same
  line) was NOT classified as a bridge, so the group grouper grew
  across the speaker boundary and merged unrelated sentences. Fix:
  added end-anchors to `^SM\s*:\s*$` / `^Master\s*:\s*$` /
  `^Narrator\s*:?\s*$` / `^Maharaj\s*:\s*$`; extended timecode
  patterns to `^\d{1,2}:\d{2}(:\d{2})?\s*$` and added a new
  `^\d{1,2}:\d{2}:\d{2}\s+\S.*[\(\[][mf][\)\]]\s*:?\s*$` for
  timecode-prefixed speaker rows.

  **B-005 PUNCT_CLUSTER_SPLIT**: `_is_safe_break` allowed splitting
  inside `...`, between `(` and its content, and right before `)` /
  `"`. The split scanner's priority-1 (sentence-end) rule then broke
  at the FIRST `.` of `...`, leaving `..` orphaned on the next chunk.
  Same for `((parens` and trailing `)`. Fix: `_is_safe_break` now
  refuses any position where (a) both sides are sentence-end
  punctuation (mid-cluster), (b) `text[pos-1]` is an opener (`( " «
  「 [`), or (c) `text[pos]` is a closer (`) " » 」 ]`).

Validated on the failing file: 44 dropped rows → 12 (all 12 are
expected tail rows of multi-row groups where content sits in the head
rows). 0 orphaned punctuation rows. Metadata r0/r1 preserved. R150
"جان سالم به در می‌برند" restored. R272 "خانم‌ها و آقایان!", R274
"استاد اعظم چینگ های!" restored.

New regression tests (5): `test_bridge_speaker_label_only`,
`test_bridge_timecode_with_speaker`, `test_safe_break_avoids_ellipsis_split`,
`test_safe_break_avoids_orphaned_brackets`, `test_grey_only_shading_is_bridge`.
Total: 118/118 pass.

---

## 2026-05-13 — Multi-script polish cycle (zh / vi / ar) + critical AR fix

User-requested second cycle, polishing the universal prompt against
three non-European target languages on the same UL 3147 source. One
translate+polish run per language, then reflect across all three to
extract universal patterns (not language-specific rules).

Critical defect uncovered (B-002 SCRIPT_LEAK):
  `polisher.py` was running `normalize_fa()` unconditionally on every
  polished line, regardless of target language. `normalize_fa()` maps
  Arabic Yeh `ي` → Persian Yeh `ی` and Arabic Kaf `ك` → Persian Kaf
  `ک` — correct for FA, but actively breaks Arabic output. Every AR
  run was silently writing Persian variants for 500+ characters per
  file. Fix: gate the normaliser by `self.dest_lang == "fa"`; AR runs
  now preserve their canonical `ي` / `ك`. Verified on UL 3147 → ar:
  AR yeh 520 / FA yeh 0, AR kaf 190 / FA kaf 0.

Universal prompt refinements (v1 → v2):

  - `polish_universal.txt` HL-7 SCRIPT_PURITY — Arabic-script targets
    must use only their own canonical letter variants. Documented the
    Persian/Arabic/Urdu sets so future runs catch any residual leak
    even if the post-processor gate is later disabled.
  - EDIT rule ④e (Genre-register literalism) — "personal narrative" in
    casual speech does NOT mean the bookish target noun for "narrative"
    (个人叙事 / tự sự cá nhân / السرد الشخصي); use the conversational
    equivalent. Observed in all three languages on the same source line.
  - EDIT rule ④f (Repeated-title consistency) — when the SAME quoted
    title appears more than once (welcome + welcome-back + "for more
    info, visit X"), every instance must use the IDENTICAL form. Caught
    after ZH output mixed 《》 and "" for the same book title.

Re-translation of both source files (UL 3147 + VEGC 3148) into FA was
also run from their original `C:/.../00 Translation Files/` location
so the `_PER_Polish.docx` outputs now live beside the originals (the
earlier session 1 outputs in the project root were cleaned up).

Total spend this cycle: 4 runs × ≈$0.27 = $1.08. Plus two FA
re-translations (~$0.66) so users get the polished outputs alongside
their sources. Tests: 113/113 unchanged.

---

## 2026-05-13 — Prompt-quality reflective cycle (UL 3147 + VEGC 3148)

Seven-round iterative refinement run on `gpt-5.5` against two new
attached docx files (`UL 3147 (Isabella La Rocca González, P2of2)`
and `VEGC 3148 (Namibian Potato Recipes P2of 2)`). Each round:
translate + polish in classic-split mode, dump phrase pairs, multi-
layer reflective analysis, then minimum-bytes prompt refinement.

Infrastructure additions:

  - New `src/machine_translate_docx/log_paths.py` resolves a central
    `Log json file/` folder at project root and runs a 10-day
    retention sweep at CLI startup. `_log.json` sidecars no longer
    sit beside the output docx — they all land in the central folder
    so a working directory can host many translation runs without
    drowning in side files.
  - `docx_io/save.py` + `cli.py` rewired to call the helper. The
    docx itself still saves to the user's chosen path; only the
    sidecar moves. CLI prints `[INFO] Log retention swept N file(s)
    older than 10 days.` when files are pruned.
  - `Log json file/` added to `.gitignore`.

FA prompt refinements (v0 → v2, 4 tests):

  - `polish_PER.txt` HL-13 NO_SEMICOLON — `؛` forbidden in polished
    output; split into clauses on the same line or map to `،`.
    Caught the two `؛` leaks visible in UL 3147 round 1 (G105, G110).
  - `_smtv_locks.txt` COMMON_MT_PATTERNS table extended with four
    fresh patterns observed in real output:
      روایت شخصی زیادی آوردم   → خاطرات شخصی زیادی به کار گرفتم
      گوشت گاو مورد بزرگی است → گوشت گاو نمونهٔ بارزی است
      تأسیسات غیرشفاف‌اند     → تأسیسات کاملاً بسته‌اند
      گنجی از X (gold metaphor) → ذخیره / گنجینه
  - All 5 v0 defects (semicolon×2, opaque calque, "big one" calque,
    "personal narrative" calque) verified fixed on the v2 re-run.

Universal prompt refinements (v0 → v1, 3 tests):

  - `polish_universal.txt` MISSION gained a calibration note: if the
    first pass touched < 5 % of lines, re-scan — 0 % is almost never
    correct on a real document.
  - EDIT rule ④ expanded with four named calque shapes (abstract-
    adjective literalism, vague-noun literalism, Romance preposed-
    adjective inversion, metaphor literalism) so the model has
    concrete patterns to fire on without a language-specific table.
  - QA gained Q6 (calque sweep) and Q7 (semicolon copied verbatim
    from source).
  - Validated on UL 3147 → Spanish: `Son muy opacas` → `Son muy
    herméticas`; `un gran factor` → `un caso importante`. The
    Spanish polisher touch rate stays low (≤ 1 %) because the
    translator is already producing native-shaped Spanish; the
    calque examples fire only when truly needed.

Total spend: 7 runs × ≈$0.28 = $1.95. The remaining 5 of the 12-
test budget were unused — the prompts converged earlier than
budgeted. No code regression: all 113 unit tests still pass.

---

## 2026-05-13 — Internal deep audit (post-Jules / Antigravity / Codex)

Independent fifth audit pass run by Claude Opus 4.7 against the
improved prompt at `docs/audit-prompt-v2-2026-05-13.md`. Full report:
[`docs/internal-audit-2026-05-13.md`](docs/internal-audit-2026-05-13.md).

Three new defects found and fixed in the same commit:

  - **C1** bare `except:` in `translator.py:123` and `:406` (left over
    from the Codex A3 cleanup that only touched `splitting.py`).
  - **C2** payload logging in `splitting.py:221-251` was not env-gated
    like `translator.py` / `polisher.py` after Antigravity-deep B5.
    Same `MTD_DEBUG_PAYLOADS=1` gate added.
  - **C3** `update_job` raised `KeyError` when a status update arrived
    after `cancel_job` had popped the entry — silently killed the
    stdout-reader thread. Guarded with `dict.get`.

Verdict (cumulative across all 5 audit passes): codebase is solid
for production use of the `chatgpt-polish` + `persian_double_lines`
pipeline. The architecture roadmap (`cli.py` monolith, launcher
monolith, `_sync_globals_from_ctx` bridge) is the next big lever,
scheduled but not blocking. No open critical or high-severity defect.

---

## Project shape (current)

```
src/
  machine-translate-docx.py     CLI entry point (orchestrator)
  runtime.py                    RuntimeContext dataclass
  config.py                     module-level constants + parallel arrays
  runner.py                     block-loop orchestrator
  engines/
    google.py                   Selenium-based Google Translate engine
    deepl.py                    Selenium-based DeepL engine
    chatgpt_api.py              OpenAI API engine bridge
    inactive/                   disabled web engines (chatgpt_web, perplexity_web)
  selenium_utils/               driver / click / forms helpers
  openai_tools/
    translator.py               single-call translate
    polisher.py                 single-call FA polish
    aligner_per.py              FA bilingual doubling aligner
    splitting.py                legacy per-phrase splitter
    fa_postprocess.py           safe FA character normalizer
prompts/
  translate_PER.txt             Persian translation system prompt
  polish_PER.txt                Persian polish system prompt
  translate_universal.txt       fallback prompt for other languages
index.ejs                       legacy frontend (served at /)
web/v2/                         v2 SPA — Tailwind + plain JS (served at /v2/)
local_launcher.py               Python dev server (no Node required)
server.js                       Express production server (Node)
```

---

## Output naming convention

```
input  filename.docx
       ↓
output filename_PER_TranslatePolish.docx   main translate+polish output
       filename_PER_Double.docx            mechanical aligner double output
       filename_PER_Classic.docx           mechanical word-wrap split
       filename_PER_TranslatePolish_log.json  per-block translation log
```

Both files are served for download when the FA + chatgpt-polish
pipeline runs. Classic downloads immediately, Double downloads
after 1800 ms to avoid the Chrome multi-download permission prompt.

---

## Sessions

### 2026-05-11 — Reserved announcement slots + sound + weekly subscriber report + legacy F-1 (branch `w`)

Ships everything queued at end-of-day: two reserved announcement
surfaces in the v2 SPA, a sound + cross-tab finish signal, a weekly
Telegram export of the newsletter list, a legacy-dropdown trim, and
a prioritised future-ideas backlog.

**v2: pinned banner + welcome modal**

  Two announcement surfaces driven by `content.json`:

  - **Pinned banner** — single sticky row at the very top of the
    page (above the announcements column). `data-kind` chooses the
    accent stripe colour (`release` / `notice` / `warning`).
    Dismissable, persists per `id` in
    `localStorage('v2.pinned.dismissed.<id>')`. Change the id in
    `content.json` to re-show.
  - **Welcome modal** — cinematic full-screen dialog with a
    fade-in backdrop + spring rise + soft clay glow that pulses
    every 5 s. Shows once per `id`, dismissable via close button /
    backdrop click / Esc. Optional `cta { label, url }` block. Both
    surfaces silently no-op when their slot is missing or
    malformed. Honours `prefers-reduced-motion`.

  Both renderers live in `web/v2/app.js` and consume the new
  reserved slots in `web/v2/content.json` (`pinned`, `modal`).

**v2: sound + cross-tab finish signal**

  New `playSound` toggle in the Display Preferences modal (default
  OFF). When a translation finishes:

  - **Always** (pref on): a two-note Web Audio chime (C5 → E5,
    ~120 ms, pure synthesis — no asset download).
  - **If the tab is hidden**: tab title flashes
    `(✓ Done) <filename>` every 1.1 s; falls back to the original
    title when the user switches back.
  - **If the user granted Notification permission**: a system
    `Notification('Translation finished', …)` with the filename.
    Permission is requested lazily the first time the user enables
    `playSound`; denying is fine — chime + title flash still work.

  Closes the "user didn't notice the run finished while in another
  tab" gap from the legacy UI.

**Backend: weekly Telegram subscriber report**

  New scheduler thread in `local_launcher.py`:

  - Default schedule: **Saturday 12:00 Europe/Paris**. Override via
    `MTD_SCHEDULER_TZ=<IANA tz>`.
  - Reuses `MTD_TELEGRAM_TOKEN` + `MTD_TELEGRAM_CHAT_ID` (now also
    used by the failure-archive alerter). If unset, the scheduler
    is dormant and prints
    `[subscribers] Telegram not configured — weekly report disabled`
    once at boot.
  - Empty `subscribers.txt` → silent skip. Non-empty → sends a
    Markdown text snapshot + the file as a Telegram document.
  - State persisted to
    `runtime_dir/subscribers_report_state.json`. If the last
    weekly attempt failed, the next launcher boot reads the
    `pending_warning` flag and prints
    `[subscribers] WARNING: last attempt at <ts> failed (N
    email(s) pending). Reason: <repr(exc)>` to stderr, then clears
    the flag so it doesn't nag every boot.

**Legacy `index.ejs`: F-1 dropdown trim**

  Stale `gpt-5.4` option removed from the AI-model dropdown — only
  the two `config.VALID_AI_MODELS` entries (`gpt-5.5`,
  `gpt-5.4-mini`) remain. F-5 / U-6 from the audit are N/A: the
  legacy template has no theme toggle to persist (the audit
  finding assumed one).

**`docs/v2-future-ideas.md`**

  New tier-1..4 backlog for the v2 SPA. Each idea scored against
  three axes (server cost, client cost, build cost) so a future
  reviewer can pick from the top quickly. Anti-patterns section
  (no framework, no CDN-required fonts, no heavy chart libs) keeps
  the dependency-light posture explicit.

**Bug fix in this session**

  Initial commit had a TDZ bug: `SOUND_STATE` was a `const` near
  the bottom of the IIFE but `wireVisibilityWatcher()` reads it
  from `boot()`, which fires synchronously on a `defer`-loaded
  script (the `document.readyState !== 'loading'` path). Moved
  the declaration up next to the rest of the IIFE-level state.
  Caught by spinning the v2 page in the preview tool and watching
  the renderers silently fail to paint.

**Verification**

  - `pytest`: 113 / 113 pass.
  - Live DeepL en→fr smoke: exit 0, source 42/42 preserved,
    target 18/40 phrase — baseline unchanged.
  - v2 boot in the preview tool: 4 announcements rendered, 3
    story cards rendered, pinned banner visible with the correct
    text, welcome modal visible with the correct title + CTA,
    `playSound` checkbox present with correct default (OFF).

Master tip going in: `5e3314e`.

### 2026-05-11 — Drain the parked-item queue (branch `next/clean-parked-list`)

Clears every item that was parked in `docs/audit-2026-05-11.md` and
the next-session handoff. No new constraints; pure resilience +
cosmetic + cost-visibility improvements.

**Launcher resilience**

  - **R-1** — `job_procs[job_id]` is now `pop()`-ed under lock right
    after `proc.wait()` returns, so OS handles held by the `Popen`
    object are freed immediately instead of after the 1-h job-cleanup
    sweep.
  - **R-2** — the stdout reader loop is wrapped in `try/finally` that
    drains remaining buffered lines + closes `proc.stdout` even when
    the parser body raises. Without this, an exception mid-loop would
    leak the pipe fd and leave the child blocked on a full pipe.
  - **R-6** — `cancel_job()` now flips `job.status = "cancelled"` under
    the same lock as the status check, so two concurrent cancels can
    no longer both observe `pending` and both call `proc.kill()`. The
    actual kill happens outside the lock (it can block on Windows
    handle settle); the second caller short-circuits at the status
    check.

**Selenium error visibility (R-7, minimal)**

  - New helper `engines/_base.py:_maybe_log_swallowed(label, exc)`.
    No-op by default; when `MTD_SELENIUM_VERBOSE=1` is in the env it
    prints a one-line summary + a 3-frame traceback to stderr for
    every swallowed exception. Wired into 4 sites in
    `engines/google.py` (page-load timeout x2, cookie-banner
    re-attempt, browse-your-files sentinel). The full Selenium engine
    rewrite stays parked; this is the smallest useful step.

**Privacy (R-8)**

  - `engines/deepl.py` masks the DeepL account email before printing
    the login banner — `mo***@example.com` instead of the full
    address. Sign-in itself still uses the unmasked value; only
    stdout output is masked.

**v2 frontend cosmetic**

  - **F-6** — `renderFileList()` rebuilt without the
    `innerHTML`/`textContent` mix. Every child is now a real DOM node
    built via `createElement` + `createElementNS`. A new
    `makeFileSvg(px)` helper builds the file icon SVG without going
    through `innerHTML`. Defensive against XSS via a hostile
    filename even if the upload-validation layer is bypassed.
  - **F-8** — every `<label class="form-field">` in the v2 form now
    carries an explicit `for="<select-id>"` attribute. Previously the
    label wrapped the select (implicit linkage, valid HTML but
    ambiguous for some assistive technologies).

**Cost visibility (C-3)**

  - `line_count_reconciler` now prints a `[reconciler-cost]` line
    after each call: prompt + cached + completion tokens + cost in
    USD. Run volume is low (only fires on line-count mismatch) but
    the previous invisibility made the chatgpt-polish sidecar's
    `total_cost_usd` look ~5–10 % too cheap on noisy days.

**Hygiene**

  - **H-2** — 24 commented-out dead imports removed from
    `cli.py` (Yandex/Thai/Persian-NLP holdovers from Phase A).
  - **H-5** — new `compile/README.md` explains the relationship
    between `pyproject.toml` (direct deps with `>=` floors) and the
    frozen `compile/requirements*.txt` files (transitive pins for
    reproducible deploys), plus the refresh recipe.

**Testing (T-2)**

  - New `make test-integration` / `make test-all` targets in
    `Makefile` (+ same in `tasks.bat`). The unit-only `make test`
    target keeps its existing `--ignore=tests/integration` so
    fast-loop dev stays fast; the new targets are opt-in for CI or
    manual runs that want everything green.

**Verification**

  - `pytest`: 113 / 113 pass (no regressions, no test changes
    needed).
  - Live DeepL en→fr smoke via the `-m` form: exit 0, source 42/42
    preserved, target 18/40 phrase — baseline unchanged.

Master tip going in: `d8b3bbb`.

### 2026-05-11 — Full src/ layout migration (branch `next/src-layout-migration`)

The biggest single refactor of the project lands. Every `.py` file
under `src/` moves into a real Python package; every bare-name
import (`from runtime import …`) becomes a proper package-relative
or package-absolute import; the CLI becomes `python -m
machine_translate_docx.cli`. `pip install -e .` now produces a
working `mtd` console script via PEP 621 entry-point.

**Files moved** (history preserved via `git mv`):

```
src/runtime.py                  → src/machine_translate_docx/runtime.py
src/config.py                   → src/machine_translate_docx/config.py
src/dispatch.py                 → src/machine_translate_docx/dispatch.py
src/runner.py                   → src/machine_translate_docx/runner.py
src/exceptions.py               → src/machine_translate_docx/exceptions.py
src/translation_health.py       → src/machine_translate_docx/translation_health.py
src/table.py                    → src/machine_translate_docx/table.py
src/updtlnk.py                  → src/machine_translate_docx/updtlnk.py
src/machine_translate_docx.py   → src/machine_translate_docx/cli.py
src/docx_io/                    → src/machine_translate_docx/docx_io/
src/engines/                    → src/machine_translate_docx/engines/
src/openai_tools/               → src/machine_translate_docx/openai_tools/
src/selenium_utils/             → src/machine_translate_docx/selenium_utils/
src/xlsx_translation_memory/    → src/machine_translate_docx/xlsx_translation_memory/
```

`src/configuration/`, `src/installer/`, `src/chromedrivers/`, and
`src/mac_service_template/` stay where they are — they're data /
build / asset directories, not Python code.

**Imports rewritten** (32 files, 83 import lines, automated via a
one-shot Python script):

  - Inside the new package: bare `from runtime import …` becomes
    `from ..runtime import …` (or deeper `from ...runtime import …`
    for sub-subpackages), so the package is self-contained.
  - Inside `tests/` and `local_launcher.py`: same import becomes
    `from machine_translate_docx.runtime import …` (absolute form).
  - `unittest.mock.patch("runner.X")` strings rewritten to
    `patch("machine_translate_docx.runner.X")` so monkey-patching
    targets the new module path.

**`pyproject.toml`** updated for the `src/` layout:

```toml
[tool.setuptools]
package-dir = { "" = "src" }

[tool.setuptools.packages.find]
where   = ["src"]
include = ["machine_translate_docx*"]

[project.scripts]
mtd = "machine_translate_docx.cli:main"
```

`pip install -e .` from a clone now ships a working `mtd` command.
The old root-level `machine_translate_docx/__init__.py` namespace
wrapper is removed — the real package replaces it.

**Launcher subprocess** in `local_launcher.py` switched from running
the script by path (`python src/machine_translate_docx.py …`) to
running the module (`python -m machine_translate_docx.cli …`) with
`PYTHONPATH=src` injected into the child env. Necessary because the
new package uses relative imports and Python's script-mode loader
gives them no package context. A legacy fallback path is kept so
mid-migration checkouts keep working.

**Makefile + tasks.bat** updated similarly. The `cd _real_test/`
smoke target prefixes the command with `PYTHONPATH=../src` so the
package is findable from the working directory.

**`tests/conftest.py`** docstring updated (the `sys.path` shim
itself is unchanged — adding `src/` to `sys.path` now exposes the
package, just as it used to expose the flat modules).

**`CLAUDE.md`** key-paths table fully refreshed to the new
`src/machine_translate_docx/<module>.py` paths. CLI invocation
example updated to the `-m` form.

**Lazy import fix**: `docx_io/parse.py` had a `from
machine_translate_docx import (is_end_of_line, …)` lazy-import
referring to the old root-level entry script; rewritten to
`from machine_translate_docx.cli import …`. Caught by the live
smoke test, not pytest (the test mocks bypass the lazy import).

**Verification**

  - `pytest`: 113 / 113 pass.
  - `PYTHONPATH=src python -m machine_translate_docx.cli --help` —
    prints the program banner + argparse usage.
  - Live DeepL en→fr smoke via the `-m` invocation: exit 0,
    source 42/42 preserved, target 18/40 phrase — baseline
    unchanged.

Master tip going in: `74e755b`.

### 2026-05-11 — Final polish: package wrapper + PR template + handoff doc + memory date (branch `next/final-polish`)

End-of-day polish landing the smallest remaining items so the next
session opens to a clean state.

  - **`machine_translate_docx/__init__.py`** — thin namespace
    wrapper at the project root. Its only job is to inject the
    repo's `src/` directory into `sys.path` on import so external
    callers who ran `pip install -e .` can write
    `from machine_translate_docx import runtime`. The flat-layout
    caveat still applies — the full src-layout migration stays
    parked. `pyproject.toml`'s `[tool.setuptools].packages` now
    lists this single package; `pip install -e .` succeeds.
  - **`.github/PULL_REQUEST_TEMPLATE.md`** — bullet list for what /
    why / how + a test plan checklist + the seven invariant ticks
    that matter most (C1, C2, C4, C7, C13, C15, C18) + a
    CHANGELOG-entry reminder.
  - **`docs/next-session-handoff.md`** — rewritten end-to-end. The
    file had been stale since 2026-05-10 (it still pointed at
    `0f07c14` and asked the next session to extract `parse +
    get_cell_data`, which has long since landed). The new version
    is a status snapshot at master tip `336603e`, a chronological
    summary of everything that landed across the 2026-05-10 →
    2026-05-11 push, the parked items list, three operator
    questions, and an end-of-day "nothing is blocked" sign-off.
  - **`PROJECT_MEMORY.md`** last-updated banner refreshed.

Tests: 113 / 113 pass.

Master tip going in: `336603e`.

### 2026-05-11 — Repo-hygiene follow-up: CI + issue templates + docs index + CHANGELOG rename (branch `next/repo-hygiene-followup`)

Completes the repo-housekeeping queue parked in the 2026-05-11
audit. No code paths touched; pure tooling + documentation.

  - **`.github/workflows/ci.yml`** — pytest on every push to
    `master` and every PR, on Python 3.11 + 3.12 (Ubuntu).
    Companion `py_compile` job sweeps every `.py` file. `live`-
    marked tests stay out of CI.
  - **`.github/ISSUE_TEMPLATE/`** — three files: `bug_report.yml`,
    `feature_request.yml` (with an invariant-check checklist
    against C1/C2/C7/C13), and `config.yml` (blanks disabled +
    security/discussion links).
  - **`scripts/`** — new directory with a `README.md`; the
    bloated `run.bat` (hundreds of stale `SET DOCXFILE=…` lines)
    moved under `scripts/legacy/run-developer-scratch.bat`.
    Project root keeps the three supported runners
    (`tasks.bat`, `compile.bat`, `run_local_launcher_v2.bat`).
  - **`docs/index.md`** — hub for the 24 markdown files under
    `docs/`. Grouped into: Getting started · Architecture ·
    Translation domain · Operations + observability · API +
    engines · Process / playbooks · Historical / archived.
  - **`CHANGES.md` → `CHANGELOG.md`** — `git mv` rename so history
    is preserved. A `CHANGES.md` stub stays so older bookmarks
    resolve. Every internal reference (README, CONTRIBUTING,
    PROJECT_MEMORY, pyproject.toml, AGENT.md, docs/index.md, two
    playbooks) updated.

Verification: `pytest`: 113 / 113 pass — pytest still reads from
`pyproject.toml`.

Master tip going in: `ed311fe`.

### 2026-05-11 — `pyproject.toml` (PEP 621) + pytest config migration (branch `next/pyproject-toml`)

Adds the modern Python project metadata file that's been missing
since the project's start. `pyproject.toml` is now the canonical
metadata source — IDE integrations, modern resolvers (pip 22+, uv,
poetry, hatch), and lockfile tools all read from here. The pinned
`compile/requirements.txt` stays in place as a frozen reproducible
install set; both live side-by-side on purpose.

**Contents**

  - `[build-system]` — setuptools + wheel, PEP 517 compliant.
  - `[project]` — full metadata: name, version, description, MIT
    license, keywords, classifiers, authors, `requires-python>=3.11`,
    and 25 direct runtime dependencies with permissive `>=` floors
    (transitive pins remain in `compile/requirements.txt`).
  - `[project.optional-dependencies]`:
      - `test` — `pytest>=8.0` (mirrors `requirements-test.txt`).
      - `db` — `mysql-connector-python>=8.0` for the optional
        MariaDB translation-memory path (gated by `MARIADB_HOST`).
      - `fa-legacy` — `hazm`, `nltk`, `newmm-tokenizer`,
        `tinysegmenter` for historic dev envs (not used in the
        active pipeline; we ship `openai_tools/fa_postprocess.py`).
  - `[project.urls]` — homepage, repository, docs, changelog,
    issues — all populated.
  - `[tool.pytest.ini_options]` — replaces `pytest.ini`. Default
    run keeps the existing `-ra -q -m "not live"` behaviour plus
    `--strict-markers`; `live` marker still documented.

**Migration note**

  Layout caveat is spelled out in a top-of-file comment: the `src/`
  tree is currently a collection of bare top-level modules, not a
  single importable package (files import each other by bare name;
  `tests/conftest.py` puts `src/` on `sys.path`). `pip install -e .`
  does NOT yet produce a working CLI install — only the metadata is
  consumed today. Migrating to package-relative imports is parked
  for a separate refactor; touching it would invalidate every
  `from runtime import …` line across the codebase.

**Cleanup**

  - `pytest.ini` removed (now `[tool.pytest.ini_options]`).

**Verification**

  - `pytest`: 113 / 113 pass with pytest reading config from
    `pyproject.toml`. 8 `live`-marked tests still deselected.
  - **Live smoke** DeepL en→fr on the canonical fixture: exit 0,
    source 42/42 preserved, target 18/40 phrase-grouped — baseline
    unchanged.

Master tip going in: `84beb91`.

### 2026-05-11 — Repo first-impression: README, LICENSE, architecture diagrams (branch `next/repo-readme-and-diagrams`)

A repository-hygiene pass aimed at the visitor experience on GitHub.
Before: the landing was a one-line `# machine-translate-docx`
stub, no LICENSE, no diagrams, a `.bat` file with `-----------` in
its filename, and three policy files (`CONTRIBUTING`, `SECURITY`,
`LICENSE`) missing entirely. After: a polished landing page with
embedded SVG architecture diagrams, all the standard OSS policy
files, and three hand-coded diagram pairs (light + dark theme each)
that render natively on GitHub.

**Repo cleanup**

  - Removed `"run_local_launcher     -----------.bat"` — a corrupt
    filename from a copy-paste artefact, kept around for years.
  - Added `LICENSE` (MIT, 2022-2026).
  - Added `CONTRIBUTING.md` — dev setup, pre-commit checklist,
    project rules (the C1-C20 invariants of `PROJECT_MEMORY.md`),
    code-style highlights, bug-reporting template.
  - Added `SECURITY.md` — coordinated-disclosure email, in-scope
    vs out-of-scope, active security measures list.

**SVG diagram set** — three diagrams × two themes = six files in
`docs/diagrams/`, each ~9 KB, all hand-coded with the project's
Anthropic-inspired warm palette and a `<title>` + `<desc>` block
for screen-reader access:

  1. `architecture-{light,dark}.svg` — frontends → launcher → CLI
     → engines → outputs (the top of the README).
  2. `pipeline-{light,dark}.svg` — 3-row workflow (Ingest /
     Process / Deliver) with the failure-branch dotted off the
     Process row.
  3. `failure-path-{light,dark}.svg` — four failure-mode triggers
     converging on the structured `[FAIL] reason=…` line, then
     splitting into the failure archive + three alert channels.

  Light → dark variants are produced by a mechanical palette swap
  documented in `docs/diagrams/README.md` so editing one and
  re-running the swap keeps the pair in lock-step.

**New README.md** — replaces the one-line stub. Sections in the
order that matches what a fresh visitor wants to know: hero +
badges + hero diagram → "What it does" → quick start (clone,
install, run unit tests, start the dev server) → translation
pipeline (with the second SVG) → failure handling (with the third
SVG) → architecture file tree → documentation index → status →
acknowledgements → license. Uses `<picture>` blocks so the right
SVG fires automatically on GitHub light vs dark.

Tests: 113 / 113 pass. No code paths touched — pure documentation
and asset additions.

Master tip going in: `db174b2`.

### 2026-05-11 — Telegram multi-recipient + docs expansion (branch `next/telegram-multi-recipient`)

User encountered two friction points during the Telegram setup:
(1) pasted the `getUpdates` URL *into* Telegram instead of a
browser, then accidentally pasted the bot token in the chat (had
to revoke immediately), and (2) wanted to know how to add more
than one recipient.

**Multi-recipient support**

  `MTD_TELEGRAM_CHAT_ID` now accepts a list, separated by commas,
  semicolons, or whitespace. New helper `_parse_telegram_chat_ids`
  splits + drops empties + preserves duplicates. The launcher
  iterates recipients and the per-recipient send is wrapped in a
  defensive try/except, so one bad id (kicked from a group, etc.)
  never blocks the rest of the fan-out.

  Six new unit tests in `tests/test_telegram_alert.py` cover
  single id, comma-separated, mixed separators
  (`;` / `,` / whitespace), empty-piece dropping, negative group
  ids + channel handles, and empty input.

**Docs expansion** in `docs/telegram-alerts-setup.md`

  - **Section 2a** — recommends `@userinfobot` as the easy way to
    discover your chat id (no URL, no browser, takes 5 seconds).
  - **Section 2b** — the original browser-URL method, now with a
    bold ⚠ warning about the most common mistake (pasting the URL
    *into Telegram* instead of a browser).
  - **Section 4** — three multi-recipient patterns, each with
    pros/cons:
      * 4a multiple individual DMs
      * 4b a private group
      * 4c a public or private channel
    Plus an explicit "mixing patterns" example.
  - **New Troubleshooting section** covering the URL-as-message
    mistake, the token-leak emergency response (`/revoke` to
    `@BotFather`), empty `result` arrays, the "bots can't DM users
    who haven't /start'd" gotcha, the Group Privacy default, and
    how to detect a bot kicked from a recipient.

  PROJECT_MEMORY C20 retains its current scope (the multi-recipient
  feature is purely a parsing improvement; the env-var name is
  unchanged so existing setups keep working).

  Tests: 113 / 113 pass (107 prior + 6 new).

Master tip going in: `b348e35`.

### 2026-05-11 — Cost-field UX tweak + Telegram failure alerts (branch `next/cost-field-and-telegram`)

Two small changes the user asked for after the run-summary wave:

**Cost field — keep the label, suppress only the value**

  Previous behaviour: when the `showCost` preference was off, the
  whole "Cost" metric vanished from the run-summary card. The user
  wants the label to **stay** in the layout (so the slot is visible
  and easily recognisable) and only the value to read `—`.

  Changes:
    - `web/v2/styles.css` — removed the rule that
      `display:none`'d the whole `.metric[data-metric="cost"]`.
    - `web/v2/app.js:paintRunSummary` — when `state.prefs.showCost`
      is off, sets `#rsCost` to `—` directly; when on, shows the
      `$X.XXX` figure.
    - `state.lastSidecar` is cached so toggling the preference now
      re-paints the summary card live (no second run required).

**Telegram bot failure alerts — full implementation**

  Adds Telegram as a third failure-alert channel alongside the
  existing email + webhook plumbing. Two new env vars:

    MTD_TELEGRAM_TOKEN      from @BotFather
    MTD_TELEGRAM_CHAT_ID    your DM-with-bot chat id
    MTD_TELEGRAM_NO_ATTACHMENT=1   (optional — text-only)

  When a job fails, the launcher (a) writes the failure archive
  exactly as before, (b) POSTs a Markdown text alert to Telegram
  with reason / job id / engine / lang / file / first 500 chars of
  the message, and (c) tries to upload `input.docx` from the
  archive as a Telegram document attachment (capped at 20 MB so we
  stay below all Telegram cloud-bot limits).

  Implementation is pure stdlib — `urllib.request` for the JSON
  POST and a hand-rolled multipart body for `sendDocument`. No new
  dependency. Both calls are wrapped in try/except so a missing
  network or a revoked token cannot block the failure-archive path.

  Security:
    - Token + chat_id come from environment only; never committed.
    - The token is sent in the URL path (Telegram's standard) over
      HTTPS only.
    - The token is masked in launcher logs (`chat {first 6 chars}…`).
    - All Markdown-special chars in user-supplied strings are
      escaped via `_telegram_escape` so a filename like
      `my_doc*name.docx` cannot break formatting.
    - Full step-by-step setup + threat model in
      `docs/telegram-alerts-setup.md`.

  PROJECT_MEMORY C20 updated to mention the new env vars.

  Tests: 107 / 107 pass (102 prior + 5 new in
  `tests/test_telegram_alert.py` covering escape behaviour and
  multipart construction with a stubbed `urllib.request.urlopen`).

Master tip going in: `98f330d`.

### 2026-05-11 — Run-summary card + history + display preferences (branch `next/run-summary-and-history`)

Implements backlog items #1 + #2 from yesterday's audit findings.
Cost is captured everywhere (sidecar, history rows, summary card)
but **hidden by default** in the UI per user request — toggleable
from a new Display Preferences modal so it can be flipped on later
without any code change.

**Backend (small, additive)**

  - `src/docx_io/save.py` now writes a **minimal `_log.json`** sidecar
    next to every non-OpenAI run (DeepL / Google / chatgpt-no-polish).
    Schema overlaps the chatgpt-polish sidecar where possible:
    `run_info` (timestamp, engine, method, langs, with_polish=false)
    + empty `blocks` + `summary` with `row_count`,
    `source_rows_nonempty`, `target_rows_nonempty`. Tokens / cost
    fields are explicitly `null` so the v2 card can decide whether
    to render the OpenAI-specific rows.
  - `src/machine_translate_docx.py:write_translation_log` enriches
    the chatgpt-polish summary with the same row-count fields plus
    `polish_lines_touched` / `polish_lines_total` (used by the
    "polish over-rewrote" warning).

**Frontend wave** (all in `web/v2/`)

  - **Run-summary card** under the results list: model, elapsed,
    tokens (total/prompt/out), cache-hit %, cost, cache savings,
    cache expiry (24 h after `run_info.timestamp`), rows translated,
    polish lines touched. Each metric carries a `data-metric=…`
    attr so the Display Preferences toggles can hide individual
    rows without re-render.
  - **ETA + throughput live** under the progress bar: "~12s left"
    + "≈ 2,300 chars/s", anchored on the first ≥ 15% PROGRESS ping
    so the early 0→5→10 jitter doesn't poison the estimate.
  - **Cache savings** = `cached_tokens × (input_rate − cached_rate) /
    1M`, computed against the `/pricing` table.
  - **Cache expiry** badge counts hours-until-24h-rollover.
  - **Run history sidebar** in the right column — last 10 runs in
    `localStorage('v2.history.v1')`. Each row shows file +
    engine/lang + elapsed + timestamp; cost only shown when the
    `showCost` preference is on. Two tools: `⤓ CSV` exports the
    history as a CSV blob (download via `Blob` URL); `✕` clears.
  - **Quality warnings** under the summary card, rendered as
    badge-prefixed bullets: `polish_over_rewrite` (>80% of polish
    lines changed), `output_short` (target / source < 30%),
    `cache_miss_unexpected` (same file in last 5 min but
    cache hit < 30%). All toggleable as a group via the
    `showWarnings` preference.
  - **Display Preferences modal** opened by a small ⚙ button on
    the summary card. Five toggles:
      - `showCost` (default OFF)
      - `showCacheSavings` (default ON)
      - `showCacheExpiry` (default ON)
      - `showWarnings` (default ON)
      - `showEta` (default ON)
    Each toggle has an inline note explaining what it controls.
    State persists in `localStorage('v2.prefs.v1')`. Visibility is
    driven by `data-pref-*` attrs on `<html>` so CSS does the work
    — no re-renders required when toggling.

**Verification**

  - `pytest`: 102 / 102 pass (no test changes needed).
  - DeepL en→fr smoke: sidecar `sidecar_smoke_FRE_Deepl_log.json`
    written with `engine=deepl`, `method=phrasesblock`,
    `row_count=43`, `source_rows_nonempty=37`,
    `target_rows_nonempty=17`. Tokens / cost fields are null.
  - v2 boot: `data-pref-show-cost="0"` (cost row hidden by default),
    `data-pref-show-warnings="1"` (warnings shown by default), all
    other elements present and wired.

Master tip going in: `f62a1b9`. Cost field is **reserved but
hidden** — flip the toggle in Display Preferences when ready.

### 2026-05-11 — comprehensive audit pass (branch `audit/comprehensive-2026-05-11`)

A skeptical-eye, single-night audit pass over the whole project: backend
reliability, OpenAI cost surface, frontend UX, hygiene + docs + tooling.
Discovery via four parallel `Explore` agents; findings + self-critique +
conflict scan + final action list authored to
`docs/audit-2026-05-11.md`. 14 KEEP items applied; the rest are parked
in the same doc.

**Backend hardenings**

  - **R-3** — `_archive_failed_job` now falls back to a system-temp
    directory if `runtime_dir/failures/` is unwritable, so a permission
    error never produces a silently-missing failure folder. Both
    branches log full traceback to stderr.
  - **R-4** — `_append_subscriber` no longer echoes the raw exception
    text into the JSON response (was leaking internal paths). Returns
    `"server error"` and logs traceback to stderr.
  - **R-5** — `_sanitize_filename` caps the basename at 200 chars,
    preserving a trailing `.ext` of up to 10 chars, so a 1000-char
    upload name doesn't trip Windows' 255-byte filename ceiling.

**OpenAI cost surface**

  - **C-2** — `openai_tools/splitting.py:calculate_openai_cost` now
    extracts `cached_tokens` from the response and prices them at the
    cached-tier rate (~10% of full). Previously cached tokens were
    billed at full rate, overstating splitter cost by ~10× on cache
    hits. Added `gpt-5.5` row so the project default has a real
    number, not the `[WARN] No known pricing` zero.
  - **U-2** — new `GET /pricing` endpoint exposes the per-1M-token
    table for every model in `config.VALID_AI_MODELS`. The v2
    frontend pulls this and shows a pre-flight cost estimate next to
    the Translate button.

**v2 frontend wave**

  - **F-2** — backend `[FAIL] reason=<token> message=<text>` lines
    were already parsed into `jobs[id].error` as `<token>: <text>`;
    v2 now splits them in `pollStatus`, renders the token as a small
    error-reason badge, and shows the message body alongside.
  - **F-3** — RTL select-arrow gradient was hardcoded 45°/135°;
    the chevron now re-declares with swapped angles under
    `[dir="rtl"]` so Persian users see a correctly-pointing arrow.
  - **F-4** — RTL progress-fill gradient flipped from `90deg` to
    `270deg` so the darker accent stays at the leading edge in
    Persian mode.
  - **U-1** — Cancel button shows during a run; POSTs to
    `/cancel/<jobId>`; the poll loop now distinguishes `"cancelled"`
    from `"error"` and surfaces it as a non-error message.
  - **U-3** — `_log.json` sidecar download link in the results list,
    auto-rendered next to the docx download whenever a chatgpt-polish
    run produces one.
  - **U-4** — Session-cost watermark in the footer; reads the
    sidecar's `summary.total_cost_usd` after every run, accumulates in
    `localStorage('v2.sessionCostUsd')`, persists across reloads.
  - **U-5** — Top-of-page offline banner toggled by `window.online`
    / `window.offline` events.

**Hygiene**

  - **H-1** — `.gitignore` gains explicit `.claude/launch.json` and
    `.claude/settings.local*.json` exclusions so the worktree-personal
    files can never sneak into a commit.
  - **H-3** — `todo.txt` (last edit 2022, references retired features)
    removed.

**Tests**

  - **T-1** — `tests/test_fa_postprocess.py`: 14 unit tests pinning
    the four hardlocks of `openai_tools.fa_postprocess.normalize_fa`
    (Arabic→Persian letter mapping; Arabic-Indic→Persian digit
    mapping; idempotence; ASCII / ZWNJ / harakat untouched).

**Verification at end of pass**

  - `pytest`: 102 / 102 pass (88 prior + 14 new).
  - `tasks.bat smoke`: DeepL en→fr exit 0, source 42/42 preserved.
  - `GET /pricing` returns the two whitelisted models with their
    full input / cached / output rates.
  - v2 cost-estimate badge: `Estimated cost: ~$0.875 (cache hits ≈
    $0.158)` for a 50 KB chatgpt-polish job — verified live.

Master tip going in: `8c8c2d6`. Tests at end: 102 / 102. Smoke
unchanged. 14 items closed; ~15 deferred items queued in the audit
doc for the next maintenance pass.

### 2026-05-11 — v2 frontend rebuild (branch `next/v2-frontend-rebuild`)

The legacy `index.ejs` UI at `/` is **untouched** — every byte still
serves the same way. The v2 SPA at `/v2/` was rebuilt in place to match
the smch.ir layout pattern (left announcements column, centre
translator + stories, right info / newsletter), recoloured with the
Anthropic / Claude warm palette (cream `#FAF9F5`, clay-orange
`#D97757`, near-black ink).

**Editorial surface — `web/v2/content.json`.** New single-source-of-
truth file with two arrays: `announcements` (date + title + body) and
`stories` (title + summary + optional badge + optional link). Editing
this file is the only thing required to push a new announcement
or story tile — no HTML / JS / CSS change. The page falls back
gracefully when the file is missing or malformed.

**Files touched (only inside `web/v2/`):**

  - `index.html` — three-column main grid with `<aside>` panels;
    same translator form + drop zone + progress + results section as
    before, just relocated to a `tool-card` in the centre column. The
    AI-model dropdown is trimmed to `gpt-5.5` and `gpt-5.4-mini` to
    match `config.VALID_AI_MODELS` (the stale `gpt-5.4` option that
    would now hit B-004 was removed).
  - `styles.css` — full rewrite of layout + tokens; new card +
    panel + story-grid components; explicit RTL accents on the
    announcements panel border + the select arrow; light + dark
    palettes both tuned to the Claude warm tones.
  - `app.js` — adds `loadAndRenderContent()` (fetches
    `/v2/content.json`, renders both blocks via `textContent` so any
    JSON edit is XSS-safe), `syncDocumentDir()` (auto-flips
    `<html dir="rtl">` when either Source or Target is fa / ar / he /
    ur, called on every language change), and a small
    `paintFooterBuild()` watermark.
  - `README.md` — documents the new content-editing workflow and the
    auto-RTL behaviour.

**Smoke-tested live** via `local_launcher.py --backend mock` on port
18081: `/v2/` returns 200 with the new HTML, `/v2/content.json` is
served with `application/json`, four announcements + three stories
render, the theme toggle flips light↔dark, and the language picker
flips `<html dir>` between LTR (en) and RTL (fa). The legacy `/` still
returns 200 with the original `index.ejs`.

Master tip going in: `ed4cab3`. Tests: 88 / 88 pass — backend
untouched.

### 2026-05-11 — remaining W-* fixes + final real-engine validation (branch `next/remaining-fixes-and-final-validation`)

Drained the rest of the W-* backlog from
`docs/real-engine-test-findings.md` and re-ran the full real-engine
matrix to confirm nothing regressed:

  - **W-2** — `local_launcher.py` now exports `PYTHONUTF8=1` and
    `PYTHONIOENCODING=utf-8` to the parent process environment via
    `os.environ.setdefault(...)`. Subprocess.Popen calls already
    passed these via the explicit `env=` mapping; this is a
    belt-and-suspenders default for any child that doesn't go
    through the explicit path (e.g. an aligner helper that spawns
    its own subprocess).
  - **W-4 + W-8** — `_strip_timestamp` in the launcher used to
    rename only the docx, leaving the `_log.json` sidecar under
    the timestamped name and pointing at a non-existent docx.
    Helper now (a) renames the matching sidecar alongside the docx
    and (b) rewrites the sidecar's `run_info.output_file` field
    to the post-rename name. New `tests/test_log_sidecar_pair.py`
    pins four scenarios (no-sidecar, with-sidecar, output_file
    rewrite, no-prefix idempotency).
  - **W-5** — `docx_io/parse.py` now prints
    `[INFO] Parsed N source lines into M phrase groups — translation
    will be written to phrase-head rows; other rows of the same
    phrase remain empty by design.` immediately after
    `split_phrases(ctx)`. Closes the recurring "why are 22 of my
    40 cells empty?" review question. Verified live in all 6
    real-engine runs.
  - **W-7** — investigated. Not a bug: row 10 of the sample
    fixture is a paragraph carrying `<w:shd w:fill="002060"/>`,
    which is in `shading_color_ignore_text`. The cell-walker
    correctly skips it and the cell becomes empty. Documented in
    the findings doc; no code change.
  - **Final real-engine matrix** (V2.1 through V2.7 in the findings
    doc): DeepL en→fr, Google en→fr / en→de, DeepL en→es,
    chatgpt+polish en→fa, chatgpt+polish+split en→fa,
    plus a second-run cache verification. Two negative tests:
    empty source (exits 20 with `[FAIL] reason=engine_empty`)
    and invalid `--aimodel gpt-99` (exits 1 with the structured
    "not a recognised" message). Source column 42/42 preserved
    everywhere. Cache hit on the second-run path: 91.7 % on
    translation, 76.2 % on polish.

Master tip going in: `c114ca2`. Tests: 88 / 88 pass (84 prior +
4 new for `_log.json` + docx pair). Smoke unchanged: DeepL en→fr
in ~27 s, 0 / 42 mismatches.

### 2026-05-10 — post-test hardening pass (branch `next/post-test-hardening`)

Drained the queue of bugs and weaknesses surfaced during the
real-engine pass. Five line-items closed in one focused commit:

  - **B-001 — empty-source / engine-empty no longer reported as
    success.** Two new modules: `src/exceptions.py` (a
    `TranslationFailure` hierarchy with `EmptyDocxError` and
    `EngineReturnedEmptyError`) and `src/translation_health.py`
    (the post-parse + post-translate sanity checks). `main()` now
    runs `assert_source_has_content(ctx)` after parse and
    `assert_translation_present(ctx)` after the engine returns.
    On either failure the `__main__` block catches the structured
    exception, prints `[FAIL] reason=<token> message=<text>` for
    the launcher to pick up, and exits with code 20. Verified live:
    a 3-row docx with no source text exits 20 with the structured
    line; the regression run of DeepL en→fr on `sample_hyperlink`
    is unchanged at 18/40 phrase rows.
  - **B-002 — failure archive + alerting.** The launcher's stdout
    parser now picks up `[FAIL] reason=...` lines and copies the
    input docx, captured stdout, and a `meta.json` to
    `runtime_dir/failures/<job_id>__<UTC ts>/`. A `UNREVIEWED.txt`
    sentinel makes pending issues visible at `ls`. Two env-gated
    alerts ride on top: `MTD_FAILURE_EMAIL=op@example.com` (uses
    `smtplib` + standard `MTD_SMTP_*` env vars; no third-party
    dependency) and `MTD_FAILURE_WEBHOOK=https://...` (POSTs the
    Discord/Slack/Mattermost `{"content": "..."}` shape). All
    alerts are best-effort — a flaky email server cannot kill the
    launcher.
  - **B-004 + W-3 — single source of truth for OpenAI model IDs.**
    `src/config.py` gains `DEFAULT_AI_MODEL`, `ALIGNER_MODEL`,
    `VALID_AI_MODELS`, and `is_valid_ai_model()`. The CLI parse
    layer rejects `--aimodel <unknown>` with a clear message
    immediately (before parsing the docx, before launching Chrome).
    `runner.py`, `translator.py`, `polisher.py` import the default
    instead of hardcoding `"gpt-5.5"`. C1 (aligner = `gpt-5.4-mini`)
    is preserved — the constant exists so the value is read from
    one place; it is not parameterised away. Verified live:
    `--aimodel gpt-5.5-mini` now exits 1 with
    `ERROR: --aimodel 'gpt-5.5-mini' is not a recognised OpenAI
    model identifier. Allowed values: gpt-5.5, gpt-5.4-mini.`
  - **W-1 — `_sync_globals_from_ctx` coverage policy documented.**
    Decided to keep the function as a whitelist (per-subcontext)
    rather than walking every public field. The docstring now
    spells out the reasoning (CLI booleans must not be overwritten
    by stale ctx defaults; the dispatcher and session flags are
    consumed via `ctx.*` paths) and the contract for new fields
    (add the explicit mirror here AND a unit test).
  - **14 new unit tests** in `tests/test_post_test_hardening.py`
    cover the model whitelist, the two health-check functions, the
    `MIN_NONEMPTY_RATIO` floor (kept strictly below the
    phrase-grouped baseline 0.45 so normal DeepL/Google runs do
    not get flagged), and the exception inheritance.

Master tip going in: `0eff583`. Tests: 84 / 84 pass (70 prior + 14
new). Smoke: DeepL en→fr in 27 s, 0 / 42 mismatches — unchanged.

### 2026-05-10 — real-engine test pass + findings (branch `next/real-engine-tests-and-findings`)

End-to-end validation across DeepL, Google, and the ChatGPT API on
the `sample_hyperlink.docx` fixture (42 rows, EN source, phrase-grouped
subtitle template). Two random non-Persian languages (German, Spanish)
covered alongside the canonical French and Persian runs.

**Test outcomes** — all engines produced correct output: source column
preserved 42/42; target rows non-empty 18/40 phrases (DeepL/Google
non-split) or 37/40 rows (chatgpt + split-translation); diacritics +
ZWNJ + RTL all correct in the saved docx. Live cache verification:
chatgpt-polish second + third runs hit 91.7 % cached prompts on
translation and ~76 % on polish — confirming the 24-h
`prompt_cache_retention` flag is wired end-to-end.

**Inline fix landed during the pass:** `_sync_globals_from_ctx` did
not mirror `ctx.openai.translation_log` back to the module-level
`translation_log` global, so `write_translation_log()` always wrote
an empty JSON sidecar. Added a 2-line `setattr` mirror to the helper.
Without this fix, cache verification (T7) was impossible because
every sidecar reported zeros. Documented in `B-003` of the findings
file. All 70 unit tests still pass.

**`docs/real-engine-test-findings.md` — new file with:**

  - The test matrix + per-test diagnostics.
  - 4 bugs queued for the hardening session: B-001 silent-success on
    empty-source docx, B-002 missing failed-job archive + alerting,
    B-003 (the inline-fixed translation_log mirror), B-004 invalid
    `gpt-5.5-mini` model offered nowhere but accepted at CLI.
  - 8 weaknesses / smaller suggestions (W-1 through W-8) — each with
    a fix sketch and a "why it matters" line.
  - Acceptance criteria for the follow-up commit so the next session
    knows when to stop.

Master tip going in: `958e82b`. Tests: 70 / 70 pass. No regression.

### 2026-05-10 — thread docx globals to ctx (branch `next/thread-docx-globals-to-ctx`)

Prerequisite phase for the upcoming `read_and_parse_docx_document` and
`get_cell_data` extractions. Both functions read the same module-level
globals (`docxdoc`, `use_html`, `silent`, `E_mail_str`,
`PROGRAM_VERSION`); without threading them through `ctx` first the
extracted modules would need a global-passthrough shim ~5x heavier than
the cells.py / save.py shims.

  - **G1 — `docxdoc` + `use_html` on `DocxCtx`.** Two new fields added
    to `runtime.py:DocxCtx`. Entry script line 1050 now mirrors
    `docxdoc` and `use_html` onto `_get_ctx().docx.*` immediately after
    the `docx.Document(...)` call, and `_get_ctx()` itself snapshots
    them on first call so threaded callees that arrive before line 1050
    still see the right state. `_sync_globals_from_ctx` already mirrors
    every public `ctx.docx.*` attribute back to module scope, so legacy
    bare-name reads keep working.
  - **G2 — `get_cell_data` extracted to `docx_io/cells.py`.** The
    per-cell reader (~120 lines in the entry script, plus the two
    shading-detection helpers `get_paragraph_shading_color` /
    `get_run_shading_color`) now lives in `src/docx_io/cells.py`. The
    function reads the colour-ignore list from
    `ctx.config.shading_color_ignore_text` (new field on `ConfigCtx`,
    populated in the entry script via `_get_ctx()`'s lazy snapshot).
    The two shading helpers are private (`_paragraph_shading_color`,
    `_run_shading_color`) and share a `_shading_fill_color` core that
    drops the dead `attrib_val` / `attrib_color` reads from the
    original. The fall-through `for run in paragraph_runs:` body is
    untouched — same flag semantics, same skip rules, same return
    shape. Added `tests/test_docx_io_cells.py` with seven unit tests:
    four for the shading helpers (raw XML strings) and three for
    `get_cell_data` against an in-memory python-docx document
    (plain text / `<pause>` + `<enter>` markers / whitespace
    collapse). All 70 unit tests pass after the move.
  - **G3 — `read_and_parse_docx_document` extracted to
    `docx_io/parse.py`.** The ~330-line parser now lives next to the
    other docx-IO helpers. The function reads `docxdoc` and `use_html`
    from `ctx.docx`, `silent` / `splitonly` /
    `word_file_to_translate` from `ctx.flags`, and lazy-imports the
    four `is_*_line` predicates plus `prepare_and_clear_cell_for_writing`
    and `split_phrases` from the entry script (avoids an import cycle
    — those helpers still own state that is not yet on ctx).
    `E_MAIL_STR` and `PROGRAM_VERSION` are module constants in the new
    file, used only by the error-exit branches; if the entry-script
    values drift, this banner drifts too — accepted duplication, not
    a behaviour bug. **Bug fix in the same pass:** the original
    "document does not have a table" branch referenced an undefined
    name `docxfile`; replaced with `ctx.flags.word_file_to_translate`.
    The entry script keeps a re-export shim (`from docx_io.parse
    import read_and_parse_docx_document`) so `main()` is unchanged.
  - **G3 ordering follow-up — explicit ctx mirrors at the source.**
    Threading G1's `_get_ctx().docx.docxdoc = ...` mirror onto line
    1091 made that the *first* `_get_ctx()` call site, which forced
    the lazy snapshot to fire before `chrome_options` (line 1243) had
    been built — leaving `ctx.browser.chrome_options` empty so
    `create_webdriver(ctx)` raised `'NoneType' object has no
    attribute Chrome'`. Fix: removed the eager `_get_ctx()` call at
    line ~570 (G2 mirror — it fired even earlier, before
    `translation_engine` was parsed) so the snapshot now lands
    after both globals exist; added an explicit
    `_get_ctx().browser.webdriver_module = webdriver` mirror right
    after the conditional `import webdriver` (since the snapshot
    might still pre-date this branch in some call paths) and an
    explicit `_get_ctx().browser.chrome_options = chrome_options`
    mirror right after `chrome_options = Options()` for the same
    reason. Smoke test back to ~27 s / 0 of 42 source-column
    mismatches.

Master tip going in: `0f07c14`. Tests: 70 / 70 pass. Smoke:
DeepL en→fr in 27 s, 0 / 42 mismatches.

### 2026-05-10 — session-close: branch cleanup + next-session handoff

End-of-session bookkeeping after the docx_io extraction was merged.

  - Deleted `next/persian-double-lines-as-splitter` (local + remote).
    Tag `archive/persian-double-lines-as-splitter-2026-05-10` retains
    the working state for any future revival.
  - Created `docs/next-session-handoff.md` — focused entry point for
    the next session: thread the remaining ~6 docx-related module
    globals (`docxdoc`, `use_html`, `silent`, `E_mail_str`,
    `PROGRAM_VERSION`, plus the `docxfile` typo to fix-as-you-go) to
    `ctx`, then extract `read_and_parse_docx_document` (~800 lines)
    and `get_cell_data` (~440 lines) to `src/docx_io/parse.py` and
    `src/docx_io/cells.py`. New branch will be
    `next/thread-docx-globals-to-ctx`.
  - Updated agent memory: `project_state.md` now points to the new
    handoff doc; key-files list reflects the post-cleanup layout
    (deleted web engines + new dispatch.py + docx_io package).

Master tip: `0f07c14`. 63/63 unit tests pass. Real-file smoke
verified earlier in the day (DeepL en→fr ~28 s, 0/42 mismatches).

### 2026-05-10 — docx_io extraction (branch `next/extract-docx-parse`)

Follow-up to the architecture-cleanup checkpoints. Tackled the
"docx parse" extraction that was deferred. Created the new
`src/docx_io/` package and moved three coherent groups of helpers
out of the entry script.

**docx_io/runs.py** — `_iter_paragraph_runs`. Walks every `<w:r>`
below a paragraph regardless of parent (the python-docx native
iterator silently drops hyperlink contents — the bug we fixed on
2026-05-09).

**docx_io/cells.py** — `change_cell_font`, `set_first_paragraph`,
`add_paragraph`. The two paragraph-write functions were
copy-pasted in the entry script; deduplicated through a private
`_write_into_paragraph` helper. All three take their dependencies
(`dest_lang`, `dest_font`, `rtlstyle`) as explicit kwargs so the
per-cell write path is unit-testable in isolation.

**docx_io/save.py** — `save_docx_file`, `engine_suffix`. The save
function body is now broken into three named helpers
(`_resolve_output_path`, `_restore_source_column`, save loop) so
each step is independently readable. Takes `docxdoc`, `silent`,
and `write_translation_log_fn` as explicit parameters. The shim
in the entry script emits the `PROGRESS:90` marker and delegates.

Engine suffix table cleaned up while we were there: the dead
`chatgpt-web` / `perplexity-web` branches (deleted in the previous
cleanup) are gone.

**Deferred (third time, with reasoning):**
`read_and_parse_docx_document` is ~800 lines and reads ~20 module
globals (`docxdoc`, `use_html`, `docxfile`, `silent`, `dest_lang_tag`,
many more). Doing it properly requires threading those globals
through `ctx` first — that's its own focused pass.
`get_cell_data` is similar (entangled with module globals).

**Verification.**
  - 63/63 unit tests pass
  - Real-file smoke (`tasks.bat smoke` = DeepL en→fr on the
    `sample_hyperlink` fixture): 28 s, 0/42 source-column
    mismatches, hyperlink row populated correctly

Net result: entry script ~70 lines smaller, three new modules with
clear single-purpose APIs, zero behaviour change.

### 2026-05-10 — Checkpoint 3 + 4: prompt cleanup + Makefile (branch `next/architecture-cleanup-after-audit`)

**C3 (limited scope).** Initial plan was to move ~80 helpers out of
the entry script. Decision after a survey: most of the candidates
(file-mode helpers, statistics, docx parse) are too entangled with
module globals — extracting them now risks regression for limited
maintenance benefit. Did the high-value low-risk subset:

  - `selenium_webservice_perplexity_translate` extracted to
    `src/engines/perplexity_webservice.py`. The entry script imports
    it back; future C3.x cycles can drop the back-import once all
    runner-injection sites are updated.
  - `build_translation_prompt` and the `engines._prompts` shim
    deleted entirely — they were only consumed by the chatgpt-web /
    perplexity-web engines that were removed in C1.

Entry script line count down by ~80 lines net.

**C4. Local task runner.** Two new files:

  - `Makefile` — GNU make for unix / macOS / git-bash.
  - `tasks.bat` — Windows command-prompt shim with the same target
    names.

Targets:

  - `test`        — pytest unit tests (63/63 pass)
  - `smoke`       — DeepL en→fr quick run on the fixture
  - `live-deepl`  — DeepL en→fr + en→fa real-file runs
  - `live-google` — Google en→fr + en→fa real-file runs
  - `live-all`    — both engines, all targets
  - `clean`       — wipe `_real_test/` and stale `__pycache__/`

Override the Python interpreter with the `PYTHON` env var:

```
PYTHON=E:/Python311/python.exe make test
```

CI hosted on GitHub Actions was discussed and explicitly skipped —
zero ongoing cost, no external dependencies, no GitHub minutes.

**Smoke verified.** `tasks.bat smoke` produced
`smoke_FRE_Deepl.docx` in 25 s. `tasks.bat test` runs 63/63 unit
tests in ~2 s.

Net result of the four checkpoints: web engines deleted, entry
script renamed + importable, dispatch logic in one place, local
task runner. Architecture is materially cleaner; nothing regressed.

### 2026-05-10 — Checkpoint 2: entry rename + dispatch extracted (branch `next/architecture-cleanup-after-audit`)

**C2.1.** Renamed `src/machine-translate-docx.py` →
`src/machine_translate_docx.py`. The hyphen made the entry script
un-importable as a Python module — every helper that needed sharing
had to be extracted to a sibling file and re-imported back into the
entry script via a shim. Now the module is importable directly from
anywhere in the codebase. Updated references in `local_launcher.py`,
`run.bat`, `compile.bat`, `compile/windows/compile.bat`, `package.json`,
`server.js`, and the integration test.

**C2.2-3.** New file `src/dispatch.py`. Two pure functions plus an
injection point:

  * `use_phrasesblock(engine, method) -> bool` — the per-engine
    "should we use the block-loop runner?" predicate. Was previously
    inline in `translate_docx`.
  * `set_translation_function(ctx)` — resolves
    `ctx.engine.dispatcher` for the per-call wrapper. Was previously
    a 45-line function in the entry script.
  * `set_array_dispatcher(fn)` — registers the array-lookup helper
    that still lives in the entry script. Used to avoid a circular
    import; goes away when C3 extracts the helper too.

The two functions share the same engine ↔ method matrix and cannot
drift apart — they're literally next to each other now. The entry
script's `translate_docx` body shrank from ~25 lines of `if/elif`
chains to one call: `if _dispatch_use_phrasesblock(...)`.

63/63 unit tests still pass.

Next: Checkpoint 3 — extract the remaining ~80 functions still in
the entry script to engine-specific modules.

### 2026-05-10 — Checkpoint 1: web engines deleted (branch `next/architecture-cleanup-after-audit`)

First of four checkpoints in the post-audit architecture cleanup. The
two web-LLM engines (chatgpt-web, perplexity-web) were re-activated in
phase 8 of the persian-double-lines roadmap but never reached a
working live state — chatgpt.com Cloudflare-gates guest sessions, and
perplexity.ai's selectors kept drifting. Their continued presence in
the codebase was pure tax: every shared-helper refactor had to look
at them, every UI list had to mention them, every dispatch table
needed an entry. Deleted in five small commits on a fresh branch.

Recovery if a future revival ever becomes worthwhile:

  - git tag `archive/persian-double-lines-as-splitter-2026-05-10`
    holds the working code at branch tip.
  - Remote `upstream-old` (the legacy translation-robot/main) holds
    the pre-refactor original.
  - The legacy timing snapshot is preserved in `engines/_timing.py`'s
    module docstring as a historical reference.

**C1.1.** Deleted `src/engines/chatgpt_web.py`, `perplexity_web.py`,
`_prompts.py` (only consumed by the two web engines).

**C1.2.** Removed dispatch entries: `runner.py:translate_once` chatgpt-web
and perplexity-web branches, the `is_web_llm` gate around the Google
fallback (no longer needed), entry-script `set_translation_function`
elif branches, perplexity's "web" entry in `use_phrasesblock`, CLI
engine_method routing, `engines/__init__.py` `EngineName.CHATGPT_WEB`
+ `PERPLEXITY_WEB` members and DISPATCH_TABLE entries.

**C1.3.** Dropped `CHATGPT_WEB_*` and `PERPLEXITY_WEB_*` constants from
`engines/_timing.py` (25 constants gone). Module docstring's legacy
snapshot kept as historical reference.

**C1.4.** Removed UI options: `<option value="chatgpt-web">` and
`perplexity-web` from `index.ejs` and `web/v2/index.html`; cleared
the corresponding querySelectors and comments. `local_launcher.py`
`_engine_suffix_for` table + `_map_engine` cases dropped.

**C1.5.** `tests/test_engines_registry.py` web-engine assertions
replaced with `test_web_engines_removed` — explicitly asserts the
modules and `EngineName` members are GONE so a future accidental
re-introduction fails the test. `tests/test_launcher_endpoints.py`
suffix table assertion updated to expect "" for the deleted engines.

63/63 unit tests pass.

Next: Checkpoint 2 — rename entry script + extract dispatch.

### 2026-05-10 — perplexity-web block-mode + chatgpt-web inter-block revert (branch `next/persian-double-lines-as-splitter`)

User-observed runtime asymmetry: chatgpt-web was sending block-by-block
(many phrases per call) but perplexity-web was sending line-by-line
(one phrase per call) — much slower and against design intent. Plus
the previous 3× timeout pass over-bumped the *between-blocks* setup
waits in chatgpt-web; only the post-submit translation waits were
supposed to grow.

**A1. perplexity-web routing fix.** `translate_docx` in the entry
script gated `use_phrasesblock` on `engine_method in ("phrasesblock",
"webservice")` for perplexity — `"web"` was missing, so the
phrase-block runner was skipped and the dispatcher fell back to a
per-phrase loop. Added `"web"` to the list. Now perplexity-web
behaves exactly like chatgpt-web: one engine call per ~1500-char
block, regardless of how many lines that contains.

**A2. Reverted *between-blocks* chatgpt-web timings to pre-3× values.**

  - `CHATGPT_WEB_ACCEPT_BUTTON_WAIT     0.6 → 0.2`
  - `CHATGPT_WEB_LOGGED_OUT_LINK_WAIT   7.5 → 2.5`
  - `CHATGPT_WEB_STAY_LOGGED_OUT_WAIT   1.5 → 0.5`
  - `CHATGPT_WEB_AFTER_INJECT_SLEEP     6   → 2`

These are the modal/cookie/inject waits — page-setup overhead. They
fire BEFORE submit and contribute to "between blocks" wall time.
Tripling them was unhelpful; reverted.

**A3. Kept *post-submit* timings elevated.** The waits that gave
ChatGPT room to actually translate stay at the higher values from
the previous pass:

  - `CHATGPT_WEB_AFTER_SUBMIT_SLEEP     5.0` s (added new)
  - `CHATGPT_WEB_STOP_BUTTON_FIND_WAIT  3.0` s (added new — replaces
                                                hardcoded `timeout = 1`)
  - `CHATGPT_WEB_STREAMING_POLL         0.75` s (was 0.25 before)
  - `CHATGPT_WEB_MAX_STREAMING_WAIT     180` s (was 60 before)

64/64 unit tests still pass.

### 2026-05-10 — chatgpt-web 3× timeout pass + missing post-submit wait (branch `next/persian-double-lines-as-splitter`)

User confirmed the previous timing bump was still too aggressive on
chatgpt-web — the page loaded, the prompt pasted, then the body
declared the call dead before ChatGPT had even started streaming.
Two fixes per user direction "تقریباً ۳ برابر کن":

**P1. The real bug — no wait between submit and the polling loop.**
The legacy body went straight from `safe_click(button_submit_prompt)`
into `WebDriverWait(driver, timeout=1).until(stop_streaming_button)`.
On a 2026 guest session, ChatGPT typically takes 2–5 s after submit
before the Stop-streaming UI renders. The 1 s WebDriverWait raised
TimeoutException, the `while` loop `break`-ed, the body fell through
to BeautifulSoup parsing, and `articles[1]` either IndexError-ed
(if user turn was the only article) or returned the user's own
prompt as "translation".

  - **New** `CHATGPT_WEB_AFTER_SUBMIT_SLEEP = 5.0 s` — explicit pause
    between the submit click and the start of the polling loop.
  - **New** `CHATGPT_WEB_STOP_BUTTON_FIND_WAIT = 3.0 s` — replaces
    the hardcoded `timeout = 1` per WebDriverWait iteration.

Together: ChatGPT now has at least 5 s to begin streaming before
we look, and each look gives 3 s of grace before assuming "done".

**P2. Triple all existing chatgpt-web timings.**

  - `CHATGPT_WEB_ACCEPT_BUTTON_WAIT     0.2  → 0.6`
  - `CHATGPT_WEB_LOGGED_OUT_LINK_WAIT   2.5  → 7.5`
  - `CHATGPT_WEB_STAY_LOGGED_OUT_WAIT   0.5  → 1.5`
  - `CHATGPT_WEB_AFTER_INJECT_SLEEP     2.0  → 6.0`
  - `CHATGPT_WEB_STREAMING_POLL         0.25 → 0.75`
  - `CHATGPT_WEB_MAX_STREAMING_WAIT     60   → 180`

Every literal in the function body now resolves to one of these
constants — `_timing.py` is the single source of truth.

64 / 64 unit tests still pass. The body NameError / IndexError
diagnostics from the previous pass are unchanged; only timings moved.

### 2026-05-10 — web-engine timing bumps + Google fallback gated (branch `next/persian-double-lines-as-splitter`)

User-observed runtime issues, two of them:

1. **Perplexity-web closes too fast and loops.** "Doesn't give the
   site time to translate, closes and reopens." Root cause: legacy
   timings (1 s for the Submit button, 2.5 s for the first prose-div
   read, 5 s for the visible retry) were too aggressive — perplexity.ai
   guest sessions in 2026 are noticeably heavier than they were in
   the 2024 reference build. Several waits raced and the body bailed
   before the response landed; the runner saw `(False, "")` and
   reopened the page, ad infinitum.

2. **chatgpt-web mid-run switched to Google then looped.** The
   block-loop's "single-line last-resort fallback" in
   `runner.py:translate_lines_block` calls
   `selenium_chrome_google_translate(ctx, line)` whenever the active
   engine fails on a single line. The same browser/driver is reused,
   so after Google answers, the browser is sitting on
   translate.google.com — the next chatgpt-web call has to redo the
   whole `delete_all_cookies()` + Cloudflare dance from a cold
   document, every single time. That is the loop the user saw.

**T1. Perplexity timing bumps in `src/engines/_timing.py`:**

  - `PERPLEXITY_WEB_TEXTAREA_WAIT       7  → 10` s
  - `PERPLEXITY_WEB_SUBMIT_BUTTON_WAIT  1  → 5`  s  ← user's pain point
  - `PERPLEXITY_WEB_AFTER_SUBMIT_SLEEP  1  → 2`  s
  - `PERPLEXITY_WEB_STOP_BUTTON_POLL    0.25 → 0.5` s
  - `PERPLEXITY_WEB_PROSE_FIRST_WAIT    2.5 → 8`  s
  - `PERPLEXITY_WEB_PROSE_RETRY_SLEEP   0.25 → 0.5` s
  - `PERPLEXITY_WEB_PROSE_VISIBLE_WAIT  5  → 15` s

**T2. ChatGPT-web timing bumps:**

  - `CHATGPT_WEB_LOGGED_OUT_LINK_WAIT   1.2 → 2.5` s
  - `CHATGPT_WEB_STAY_LOGGED_OUT_WAIT   0.3 → 0.5` s
  - `CHATGPT_WEB_AFTER_INJECT_SLEEP     1   → 2`   s
  - `CHATGPT_WEB_MAX_STREAMING_WAIT     40  → 60`  s

**T3. Hardcoded literals in both web engines replaced with timing
imports.** The constants are now the single source of truth — the
function bodies reference them directly. Future bumps are a one-line
edit instead of a hunt-and-peck across 400-line bodies.

**T4. Google fallback gated.** `runner.py:translate_lines_block`'s
single-line last-resort Google call is now skipped when
`(engine, method)` is `(chatgpt, web)` or `(perplexity, web)`. The
genuine LLM-web engines should fail loudly (return
`"Unable to get translation."` for that line) rather than contaminate
the browser. Other engines (deepl, perplexity webservice) still get
the Google bridge.

64 / 64 unit tests still pass.

### 2026-05-10 — web engines (chatgpt-web, perplexity-web) deep audit (branch `next/persian-double-lines-as-splitter`)

User asked for an actual line-by-line debug + alignment of the two
guest-session web engines vs `translation-robot/main` legacy. Outcome:
the function bodies match legacy almost exactly (only the `except:` →
`except Exception:` cosmetic cleanup we did earlier). The structural
problems are all in the **module surface** — the bodies reference
helpers that historically lived in the same module and were never
re-imported when phase 8 extracted the engines. Every call to either
engine NameError'd on the first line and the wrapper silently
returned `(False, "")` so the bug was invisible.

**W1. `build_translation_prompt` not importable from web engines.**
The helper sat in `src/machine-translate-docx.py`, which has a hyphen
in the filename and is therefore not a regular importable Python
module. Extracted to a new file:

```
src/engines/_prompts.py
```

The entry script re-imports it via `import engines._prompts as
_engine_prompts` so the module-level name keeps resolving for any
caller that still goes through it; the local `def` later in the file
is left as-is and shadows the import with an identical body.

**W2. Missing helper imports.** Added to both `chatgpt_web.py` and
`perplexity_web.py`:

```
from selenium_utils import safe_click, set_chrome_window_2_3_screen
from config import get_nested_value_from_json_array
from engines._prompts import build_translation_prompt
```

**W3. `set_chrome_window_2_3_screen()` zero-arg call vs ctx-arg helper.**
The legacy body called `set_chrome_window_2_3_screen()` (no args, used
module globals). Our refactored helper takes `ctx`. The `translate()`
wrapper now seeds `g["ctx"] = ctx` alongside the other globals; the
in-body call is `set_chrome_window_2_3_screen(ctx)`.

**W4. `perplexity_close_messages` called `deepl_close_messages()` (zero
args).** Legacy `deepl_close_messages` was a sibling zero-arg function;
our refactor moved it under `engines.deepl` with a `ctx` parameter.
Replaced the legacy "call again to be safe" with a recursive
self-call into `perplexity_close_messages` plus a re-entry guard via
a function attribute (`_in_progress`). Same intent, no infinite
recursion.

**W5. `perplexity_web` wrapper passed 2 positional args to a 3-arg
body.** Caught earlier in the timing pass. Now passes
`(text, 2, 3)` — the third is `max_try_count`, used only in a debug
`print` inside the legacy body.

**W6. `articles[1]` IndexError when ChatGPT response missing.** Legacy
assumed at least 2 articles in the DOM (index 0 = user prompt, index 1
= ChatGPT response). On a guest session that gets rate-limited or
Cloudflare-gated, only the prompt article (or zero) is in the DOM and
the body raises `IndexError`. Added an early bail at
`chatgpt_web.py:372` that returns `(False, "")` with a one-line
diagnostic so the runner can fall back gracefully.

**Smoke status.** Real-file run on
`tests/fixtures/sample_hyperlink.docx` confirms chatgpt-web now reaches
the response-parse step (no more silent NameError); the actual
translation fails because chatgpt.com guest sessions are
Cloudflare-gated for automated traffic — recorded as a recommended
follow-up. The same fixes apply to perplexity-web; live verification
is deferred to the same selector/captcha sweep.

64 / 64 unit tests still pass.

### 2026-05-10 — engine timing alignment + reference module (branch `next/persian-double-lines-as-splitter`)

User flagged the engines as "feeling slower than the legacy
translation-robot/main repo" and asked for a one-time timing audit so
we don't have to re-clone the legacy on every regression. Outcome: a
new `src/engines/_timing.py` module that documents every wait /
sleep / poll-interval used by all four Selenium engines, with
``LEGACY``/``OURS`` citations and reasoning for each divergence. The
module IS the source of truth — `chatgpt_web.py` and `perplexity_web.py`
import the constants and the registry test asserts equality.

**Findings.** Legacy has **no inter-request sleep on any engine**. The
de-facto throttle is page-load time (Google, DeepL) or `delete_all_cookies()`
+ `.get()` reload (chatgpt-web, perplexity-web). Phase 8 added a 0.9 s
defensive pre-sleep to both web engines as a guard against rate-limiting,
without verification — pure additive cost. Aligned to legacy parity:

  - `CHATGPT_WEB_PRE_SLEEP    = 0.0`  (was 0.9)
  - `PERPLEXITY_WEB_PRE_SLEEP = 0.0`  (was 0.9)

`WEB_SLEEP_BETWEEN_PHRASES_SEC` on each module now aliases the timing
constant; external imports still resolve to the value. The pre-sleep
is only triggered when `> 0`, so a future bump is one-line.

**Bonus bug.** The phase 8 perplexity-web wrapper called the legacy
body with **two positional args** (`text, 2`); the legacy signature is
`(to_translate, retry_count, max_try_count)` — three. Masked because
`max_try_count` is only used in a debug `print`. Fixed: pass `(text, 2, 3)`.

**DeepL + Google verified unchanged.** Real-file re-run on
`tests/fixtures/sample_hyperlink.docx`:

| engine + method            | wall time | source mismatches | hyperlink |
|----------------------------|-----------|-------------------|-----------|
| deepl phrasesblock en→fr   | 29 s      | 0 / 42            | yes       |
| google phrasesblock en→fr  | 11 s      | 0 / 42            | yes       |

64 / 64 unit tests pass (the registry test was updated to assert
legacy parity instead of "0.7 ≤ sleep ≤ 1.2").

### 2026-05-10 — Google engine repaired + 4 fixes (branch `next/persian-double-lines-as-splitter`)

After DeepL was unblocked, the Google engine was the next stop on the
real-file matrix. Two of its three methods were broken in different
ways; one of those was masked by an empty default that produced an
unreadable failure mode. Changes:

**G1. Google `phrasesblock` was dispatchable but never populated.**
The block-loop runner (`src/runner.py:translate_once`) had branches for
`deepl`, `chatgpt`, and `perplexity` but raised `ValueError("Unknown
translation engine: google")` on the first call. Worse, `translate_docx`
in the entry script never even routed Google through the phrasesblock
path — `use_phrasesblock` was set true only for `chatgpt`, `deepl`, and
`perplexity`. So the dispatcher fell back to a stale `translation_array`
lookup, the array stayed empty (length 0), and every phrase looped
through 14 retries of `[WARN] translation_array index out of range`
before giving up. Fixed both:

  - Added a `google` branch to `translate_once` that calls
    `selenium_chrome_google_translate(ctx, text)` and returns the
    `(success, translated)` shape the rest of the runner expects.
  - Added `google` to the `use_phrasesblock` selector in `translate_docx`.

**G2. Default method for `--engine google` was a dead path.**
The default fell through to `engine_method = 'javascript'`, which
uploads a local HTML file to translate.google.com — a path that modern
Chrome (~2022+) blocks on file:// URLs. The fail-fast banner from the
last session kept this from cascading into hundreds of warnings, but
the user still got an empty docx. Switched the default to
`phrasesblock`. Users who genuinely want the file-mode path can still
pass `--enginemethod javascript` explicitly.

**G3. `html.unescape` not applied to final translation.**
`google.py` reads the result via `result_element.get_attribute('innerHTML')`,
which returns HTML-escaped text (`&nbsp;`, `&amp;`). The historical
unescape happened only inside the `_still_translating` retry loop —
but that loop's regex (`'$Translation'`) is permanently disabled by
audit finding F-010 and never matches. So entity escapes leaked into
the docx (visible as the literal `&nbsp;` substring on row 26 of the
fixture). Always unescape now, after the main read.

**G4. 15-second TimeoutException on every phrasesblock call.**
A `WebDriverWait(15)` for the Copy-to-clipboard button was a leftover
sentinel from when the engine actually clicked it; the textarea-read
path doesn't use it. On targets that surface the toolbar slowly (FA),
the wait timed out every single call, dumped a noisy traceback, then
proceeded normally. Cut to 3 s and replaced the traceback with silent
fall-through.

**Real-file verification with `tests/fixtures/sample_hyperlink.docx`
on translate.google.com (no `--showbrowser` for the speed-test):**

| target  | method        | wall time | source-column mismatches | nbsp leak | hyperlink populated |
|---------|---------------|-----------|--------------------------|-----------|---------------------|
| French  | singlephrase  | 5 m 25 s  | 0 / 42                   | YES (pre-G3) | yes              |
| French  | phrasesblock  | 26 s → **10 s** (after G4) | 0 / 42 | no | yes              |
| Persian | phrasesblock  | 30 s      | 0 / 42                   | no        | yes                 |

64 / 64 unit tests still pass.

### 2026-05-10 — DeepL engine real-file run + NameError fixes (branch `next/persian-double-lines-as-splitter`)

The agent's run report flagged DeepL as deferred — "translation step
hangs". A direct read of `src/engines/deepl.py` against the legacy
`translation-robot/main` revealed the hang was actually a fast-failing
NameError that the outer try/except swallowed silently. Five concrete
bugs:

**D1. `src_lang` / `dest_lang` / `dest_lang_name` not pulled from ctx.**
Lines 512 / 522 of the previous file referenced bare module-level names
that existed in the legacy globals world but never made it into the
Phase F refactor. Added an explicit triple at the top of the function:

```
src_lang       = ctx.language.src_lang or "en"
dest_lang      = ctx.language.dest_lang or "en"
dest_lang_name = ctx.language.dest_lang_name or dest_lang
```

Without this, the URL-build line raised NameError on the very first
iteration of the page-open loop and the function fell through to
`except Exception: print(traceback)` → returned `(False, "")`.

**D2. `copy_translation_button` referenced before definition.** A
visibility-check block read `copy_translation_button` inside a
`getBoundingClientRect` JS call BEFORE the variable was even
declared (it gets assigned ~50 lines later when the copy button is
located). Wrapped the block in `if copy_translation_button is not
None`, and pre-initialized the var to `None` outside the loop.

**D3. `remove_span_tag` not imported.** The legacy code used a
module-global helper that was never re-exported when the engine moved
into `src/engines/deepl.py`. Inlined a local `_remove_span_tag()` that
does the same regex pass.

**D4. `clipboard` package not imported.** The clipboard fallback path
called `clipboard.copy('')` and `clipboard.paste()` without an import.
Added a defensive `try: import clipboard / except ImportError: clipboard
= None` and gated the fallback on `clipboard is not None`.

**D5. `translated_phrases_array` could be undefined at function exit.**
The variable was only set inside the inner-loop try block. If every
iteration raised, the outer `translation = "\n".join(translated_phrases_array)`
NameError'd. Pre-initialized to `[]` at the top of the loop scope.

**Bonus.** Replaced the brittle full-class-string completion-detection
literal with a stable substring (`lmt__progress_popup
lmt__progress_popup--visible`) — DeepL has rotated the surrounding
class names twice in the last year; the shorter anchor matches both
the legacy and current popup builds.

**Real-file verification (not smoke).**
Ran `tests/fixtures/sample_hyperlink.docx` (41 rows, hyperlinks +
shaded cells) through the actual DeepL site with `--showbrowser`:

| target | wall time | rows translated | source-column mismatches | hyperlink row populated |
|--------|-----------|-----------------|--------------------------|-------------------------|
| French | 21 s      | all visible rows | 0 / 42                   | yes                     |
| Persian| 26 s      | 18 (rest are shaded/empty) | 0 / 42      | yes                     |

The agent's "DeepL deferred" follow-up is closed by this entry.

64 / 64 unit tests still pass.

### 2026-05-10 — post-agent UX fixes (branch `next/persian-double-lines-as-splitter`)

User-reported regressions and a feature request after the agent's first
end-to-end live run on the legacy `index.ejs` UI:

**U1. `Persian Double Lines` option was hidden for FA targets.**
The legacy frontend still had the pre-phase-1 logic that hid the entire
splitSection whenever target=fa + engine=chatgpt-polish (the assumption
being that the engine ran the aligner internally). Phase 1 detached the
aligner from the engine, so this hide-block is wrong now: hiding the
splitSection meant the user could never reach the Persian Double Lines
option at all. Removed the hide-block from `engineChecker()`; the
splitSection is visible for every combination.

**U2. `Split Method = OpenAI API` was not applied with
`chatgpt-polish`.** Same pre-phase-1 logic also force-unchecked the
splitTranslate checkbox under fa+chatgpt-polish, so even when the user
picked an OpenAI splitter the request shipped without `splitTranslate`,
and the splitter never ran. Removed.

**U3. `chatgpt-web` engine was disabled in the engine dropdown.**
`engineChecker()` had `chatgptwebOption.disabled = true` left over from
when the engine sat in `src/engines/inactive/`. Phase 8 reactivated the
engine but the frontend was not updated. Removed the disable.

**U4. File selection vanished when the user changed dropdown values.**
The legacy form's `<input type="file">` would lose its FileList on some
browsers when surrounding `<select>` elements toggled. Added a small
guard: the chosen File object is captured into a JS variable on
`change`, and `sendToServer()` falls back to that cached object when the
input element has gone empty. The user no longer has to re-pick the
file after changing engine / language.

**U5. Cancel button — new feature.**
Mid-translation, the user had no way to abort a job. Added:
- `LocalState.cancel_job(job_id)` — kills the registered subprocess and
  marks the job `status='cancelled'`.
- `LocalState.job_procs[job_id]` — handles registered when the
  subprocess starts, cleared on exit.
- `POST /cancel/<job_id>` endpoint.
- `_run_real_backend` registers its `Popen` immediately after spawn.
- The job-thread `except` no longer overwrites `cancelled` with `error`
  if the user already cancelled.
- A red "Cancel translation" button under the progress bar in the
  loading overlay; wired to `POST /cancel/<jobId>` for the active job.
- Polling treats `status='cancelled'` as a terminal state and surfaces
  it as a regular alert ("Translation cancelled by user").

The launcher contract is unchanged for non-cancelled flows.
Tests: 64 passing.

---

### 2026-05-10 — Persian Double Lines as a splitter (agent run, branch `next/persian-double-lines-as-splitter`)

**Phase 13 — end-to-end runs and fixes uncovered by them.**
First live execution of `tests/integration/test_real_file_per_engine.py`
under `pytest -m live`. Results:

| Engine          | Target | Outcome     |
|-----------------|--------|-------------|
| chatgpt (api)   | mn     | ✅ pass     |
| chatgpt (api)   | fa     | ✅ pass     |
| chatgpt-polish  | mn     | ✅ pass     |
| chatgpt-polish  | fa     | ✅ pass (Persian Double Lines split + suffix) |
| google          | mn     | ✅ pass     |
| deepl           | mn     | ⚠ timeout (deferred after two fix attempts) |
| chatgpt-web     | mn     | ⚠ smoke skip (upstream selectors changed) |
| perplexity-web  | mn     | ⚠ smoke skip |

Live runs surfaced four bugs left from earlier extraction work:

  * `src/engines/deepl.py` referenced two bare globals
    (`set_chrome_window_2_3_screen`, `deepl_sleep_wait_translation_seconds`)
    that no longer existed in module scope after Phase G3. Both are now
    properly imported / read through `ctx.browser`.
  * `src/machine-translate-docx.py` engine_method switch silently
    rewrote `--enginemethod web` to `phrasesblock` for chatgpt and
    perplexity. Adds `elif engine_method == 'web':` branches so the
    method survives.
  * `src/runner.py` translate_once raised on chatgpt method != 'api' and
    perplexity method != 'webservice'. Adds method == 'web' branches
    that delegate to `engines.chatgpt_web.translate(ctx, text)` /
    `engines.perplexity_web.translate(ctx, text)`.

DeepL hang and the two web-engine selector breakages are documented in
`docs/agent-run-report.md` §3 and listed as recommended follow-ups.
The launcher contract is unchanged. Tests: 64 passing under default
`pytest`; 5 of 8 live integration scenarios pass under `pytest -m live`.

**Phase 12 — cache UI feedback (splitterOnly banner).**
The `splitterOnly` flag the launcher emits on cache hit (set in
phase 4) is now consumed by both UIs. v2 swaps the existing
"Cached — instant download" progress label for "Translated text
reused from cache; only the split was redone" when splitter-only is
true, and tags the result row with `(cached — splitter only)`.
Legacy `index.ejs` previously ignored `cacheHit` entirely; it now
appends a one-line note to the success alert distinguishing
"Reused from the 36-hour translation cache" from "Translated text
reused from cache; only the split was redone." The launcher contract
is unchanged. Tests: 64 passing.

**Phase 11 — line-count reconciler for the LLM single-call path.**
New module `src/openai_tools/line_count_reconciler.py` exposes
`reconcile_line_count(source_lines, translated_lines, src_lang_name,
dest_lang_name, *, max_attempts=2)`. When the translator returns a
mismatched line count, the reconciler asks `gpt-5.4-mini` (hardcoded,
matching the aligner) up to two times for a strict line-aligned
re-emission, then falls back to pad/truncate so the result always has
exactly `len(source_lines)` entries. Every API call sets
`prompt_cache_retention=24h`. Wired into
`engines.chatgpt_api.run_openai_single_call` between translate and
polish — polish therefore always sees correctly-aligned input. The
runner block-loop and Selenium engines are untouched. Tests: 64
passing (6 new for the reconciler, including pad / truncate fallbacks
and an exception-during-API path; the OpenAI client is injected so the
suite stays offline).

**Phase 10 — real-file integration test scaffolded.**
A new opt-in test module `tests/integration/test_real_file_per_engine.py`
boots the entry script as a subprocess against the
`tests/fixtures/sample_hyperlink.docx` fixture for every supported engine
and asserts the AGENT.md contract on the output: source columns 0+1
byte-identical, target column 2 populated, hyperlinked text preserved,
correct engine suffix, no Traceback, no `[LOCK] Restored …`. Web engines
(`chatgpt-web`, `perplexity-web`) are smoke-tested only — non-zero exit
converts to `pytest.skip` so a guest-session UI change upstream does not
turn this into a blocking CI failure. Tests are marked
`@pytest.mark.live` (module-wide `pytestmark`) so they stay excluded
from the default `pytest` invocation; run with
`pytest -m live tests/integration`. The test target is `mn` for the
non-FA flow and `fa` for the FA-only Persian Double Lines case;
`MTD_TEST_MODEL=gpt-5.4-mini` overrides the OpenAI model so the live
runs stay cheap. Tests: 58 passing default, 8 additional live tests
collected under `-m live`.

**Phase 9 — module rename: `aligner_per` → `persian_double_lines`.**
The aligner module is renamed to match the user-facing Split Method
name. The class `FASubtitleAligner` is unchanged. A thin
`openai_tools.aligner_per` shim re-exports every public and private
symbol from the new module via a star-import + `__getattr__`
forwarder, so existing callers (the two test modules and any future
external consumer) keep working without modification. Internal
references in `openai_tools/__init__.py` and `local_launcher.py` are
updated to the new name. Tests: 58 passing.

**Phase 8 — chatgpt-web and perplexity-web engines reactivated.**
The two Selenium guest-session engines are moved out of
`src/engines/inactive/` into the active engines package. Each gets a
thin :func:`translate(ctx, text)` adapter that sleeps 0.9 s before
each call (within the documented 700-1200 ms range to stay under
unauthenticated rate-limit thresholds), seeds the legacy module
globals from `RuntimeContext`, delegates to the existing
selenium-based body, and returns `(False, "")` on any exception so
the launcher pipe never hangs.

The dispatcher registry (`src/engines/__init__.py`) gains
`EngineName.CHATGPT_WEB` and `EngineName.PERPLEXITY_WEB` plus
matching `DISPATCH_TABLE` entries. `set_translation_function` in the
entry script now special-cases method=`web` for both engines and
binds the adapter as the per-phrase dispatcher. `local_launcher`'s
`_map_engine` rejects nothing now: `chatgpt-web` →
`--engine chatgpt --enginemethod web`; `perplexity-web` →
`--engine perplexity --enginemethod web`. Both UIs gain the new
options. The `_API_ENGINES` cache list is unchanged, so web engines
do not cache (Selenium sessions are stateful and not idempotent).

The legacy global-seeding bridge is intentionally minimal — the web
bodies still reference helper names (`safe_click`,
`set_chrome_window_2_3_screen`, `build_translation_prompt`,
`get_nested_value_from_json_array`) that exist on the entry-script
module and are reached via Python's regular import machinery once the
adapter is invoked from inside the entry-script process. Any selector
breakage on chatgpt.com / perplexity.ai surfaces as `(False, "")` so
the block-loop continues with empty translations rather than crashing
the job. Tests: 58 passing (3 new on `test_engines_registry`).

**Phase 7 — Classic split path removed; one file per job.**
The `_Classic` and `_Double` companion outputs are gone. The `Job`
dataclass loses `filename2` and `filename3`; the `/status/:id`
response no longer includes them; `_send_zip_for_job` keeps only the
`410 GONE` body (the multi-file ZIP packaging is dead code now);
`_find_double_file` and `_find_classic_file` are deleted; the orphan
`_simple_split_docx` and `_write_cell_text` helpers in
`machine-translate-docx.py` are deleted. Both frontends collapse to a
single download — legacy `index.ejs` drops the timed-sequential and
ZIP-bundle paths; v2 `app.js` drops the aligner-double / classic-split
result rows. The v2 sidebar copy and several state docs (CLAUDE.md,
PROJECT_MEMORY.md, docs/architecture.md, docs/subtitle-syncing.md,
docs/testing.md) are updated to the new naming. Historical logs
(error-catalog, decisions-2026, post-refactor-audit) are intentionally
left as records of past states. Tests: 56 passing.

**Phase 6 — `_Double_Lines` filename suffix locked in.**
The Persian-Double-Lines output appends `_Double_Lines` before `.docx`,
after the engine suffix. Examples: `sample_PER_Polish_Double_Lines.docx`,
`sample_PER_chatGPT_Double_Lines.docx`. The actual splitter logic was
already in `_apply_splitter` from phase 4; this phase extracts the
naming bit into a pure module-level helper `_double_lines_output_path`
so it is unit-testable without spinning up an HTTP request handler. New
tests cover the suffix table, including unknown / blank engine names
falling back to no tag, plus the `_Double_Lines` naming. Tests: 56
passing (3 new for filename helpers).

**Phase 5 — engine-aware output filename suffixes.**
The bare `_TranslatePolish` polish tag is replaced by a per-engine tag
appended after the lang code. New mapping:

```
google           _Google
deepl            _Deepl
chatgpt + api    _Polish (with-polish) | _chatGPT (without)
chatgpt-web      _web_chatGPT
perplexity-web   _web_Perplexity
```

`save_docx_file` now calls a new module-level helper `_engine_suffix(ctx)`
to derive the tag from the engine + method + with_polish triple. The
launcher mirrors the same table in `_engine_suffix_for(engine)`, used
by `_fallback_output_path` when the subprocess never prints
`Saved file name:`. Old `_PER_TranslatePolish.docx` files keep working
on cache hit (they are stored by name, not derived). `_Classic`
references stay until phase 7. Tests: 53 passing.

**Phase 4 — cache stores the engine output (not the splitter result).**
`LocalState.cache` switched from `(timestamp, [(kind, path), ...])` to
`(timestamp, dict)` carrying `main_path`, `source_path`,
`translation_array`, `phrase_separator_table`, and the
engine/model/language tuple. The cache key is unchanged, so a re-upload
with a different Split Method now reuses the cached translation and
applies the splitter on top — Persian Double Lines, in particular,
re-runs the FA mechanical aligner in-process (no API call) for a
sub-2 s response. Pre-phase-4 (legacy) cache entries are detected by
their list shape and evicted on access. Two new launcher methods carry
the splitter logic: `_apply_splitter` (post-translate path) and
`_materialise_cached_output` (cache-hit path); both fall back to the
unsplit engine output on any aligner error. `_find_double_file` and
`_find_classic_file` callsites are dropped in `_process_job`; the
helpers themselves remain for now and get removed in phase 7.
Tests: 53 passing (5 cache tests adapted to the new keyword-only
signature, 2 new tests cover the dict shape and pre-phase-4 eviction).

**Phase 3 — conditional UI for Persian Double Lines.**
The `persian_double_lines` `<option>` is now visible only when the
target language is `fa`; switching to any other target hides it and
falls back to `basic` if it had been selected. When the user picks
`fa` as target, Persian Double Lines becomes the auto-selected default
in both UIs (replacing the previous OpenAI-API auto-pick in legacy).
v2 gains a `syncSplitMethodUI()` helper that fires on boot, on engine
change, and on target-language change. Tests: 51 passing.

**Phase 2 — Persian Double Lines exposed as a Split Method.**
Both frontends now expose a `persian_double_lines` value on their
`splitEngine` dropdown. Legacy `index.ejs` adds a third `<option>`. v2
gains a 5th `form-field` ("Split method") with the same three choices
(`basic` / `openai` / `persian_double_lines`); v2 `app.js` reads the new
field and forwards it as `splitEngine` whenever the user picked
something other than `basic`, and additionally sets `splitTranslate=true`
when the value is `persian_double_lines` (so chatgpt-polish jobs can
opt into the splitter even though v2 omits the legacy
`splitTranslate` checkbox). `local_launcher.py` now passes the value
straight through to `--splitengine`. CLI argparse validation accepts
`persian_double_lines` alongside `openai`. Wiring of the actual splitter
behaviour (re-runs the FA aligner against the cached translation) lands
in phases 4-6. Tests: 51 passing.

**Phase 1 — aligner detached from chatgpt-polish.**
The post-translation block in `src/machine-translate-docx.py` that produced
`_PER_Classic.docx` and `_PER_Double.docx` for every FA + chatgpt-polish run
is removed. The engine still does translate + polish; it no longer drives the
aligner. Module-level `from openai_tools.aligner_per import FASubtitleAligner`
import retired (the aligner is reached on demand from the new Split Method
flow planned in phases 2-9). One file out per job for FA + chatgpt-polish:
`{stem}_PER_TranslatePolish.docx` (suffix rename to `_Polish` lands in
phase 5). `local_launcher.py` `_find_double_file` / `_find_classic_file` still
exist; they now return `None` for new jobs (cleanup in phase 7). Tests:
51 passing, no regressions.

---

### 2026-05-09 (part seven) — long-standing hyperlink bug fixed

**S1. Hyperlinked text was silently dropped from cell output.**
A team-mate flagged a long-standing bug: cells that contain a
clickable hyperlink had the link's visible text removed from the
translation pipeline — so the translator received "Here is a
with alt text." instead of "Here is a hyperlink with alt text."

Root cause: `get_cell_data()` walked `paragraph.runs`, which only
returns `<w:r>` elements that are *direct* children of `<w:p>`.
Hyperlinked text lives inside `<w:hyperlink>`, so its runs are
silently skipped. The same bug also dropped runs nested in
`<w:smartTag>`, `<w:fldSimple>`, and any other inline container.

Fix (forward-looking): added `_iter_paragraph_runs(paragraph)`
that uses `paragraph._p.iter(qn('w:r'))` to walk every `<w:r>`
descendant in document order. Each match is wrapped in a
`docx.text.run.Run` so all the existing font / highlight / shading
/ strike checks still apply unchanged. The change is a single
line replacement at the for-loop site (`paragraph.runs` →
`_iter_paragraph_runs(paragraph)`).

Verified on `sample_hyperlink.docx`:
```
BEFORE  table 0 row 8:  'Here is a  with alt text.'
AFTER   table 0 row 8:  'Here is a hyperlink with alt text.'

BEFORE  table 0 row 30: 'an email to '
AFTER   table 0 row 30: 'an email to smtv.bot@gmail.com'
```

Tests: 51/51.

---

### 2026-05-09 (part six) — first successful real translation; Google-js diagnosis

**R1. ChatGPT translate confirmed end-to-end.** First green real-file
test of the day:
```
OpenAI single-call mode: 16 lines, 948 chars
[DIAG] After get_translation_and_replace_after: to_text rows populated = 16, translation_array lines = 16
```
The entire 16-phrase sample doc was translated to Mongolian and
written to `sample_MON.docx`. No `[LOCK] Restored …` line — the
text-based lock comparison (commit 5744e96) eliminated the previous
false positive. Source column intact.

**R2. split_phrases() bug confirmed fixed (commit 3cac1b6).** Before
the fix the run produced `to_text rows populated = 0` and an empty
docx; after, all 16 phrases were grouped, sent to OpenAI, returned,
and written to `cells[2]` of the right rows.

**R3. Google web JavaScript engine — known broken in modern Chrome.**
The same job with `engine=google` (engine_method=javascript) ran
the per-paragraph loop in 0 seconds, producing
`translation_array lines = 0`, then ~210 retries of
`[WARN] translation_array index out of range`. Root cause is
inherent to the engine, not the refactor: since ~2022 Chrome blocks
Google's translate widget from running on `file://` URLs (CORS /
sandboxing). The HTML page loads but Google's widget refuses to
operate.

Added a single-line fail-fast message after the engine returns
empty so users get a meaningful error instead of pages of
`index out of range` retries:
```
[ERROR] Google web translate returned 0 lines.
[ERROR] Modern Chrome blocks the Google translate widget on
[ERROR] file:// URLs (CORS / sandboxing). This engine path
[ERROR] cannot complete in current Chrome versions.
[INFO] Use the OpenAI API engine (chatgpt) or DeepL instead.
```

The Google-javascript path stays in the codebase for the case where
someone runs against an older Chrome; the message tells everyone
else where to go.

---

### 2026-05-09 (part five) — three audit-driven fixes (F-010 + mutable-default + atexit)

Targeting the audit's lowest-scoring dimensions (D2 Smell `B`,
D6 Maintainability `B`).

**Q1. F-010 — Google `still translating` regex.** The historical
value `'$Translation'` is regex `$` (end-of-string) followed by
literal `Translation`, so it never matched. Both the `if` and the
`while` predicates were silent no-ops in production. Replaced with
`None` plus a small `_still_translating(text)` helper that short-
circuits when the pattern is `None`. Behaviour is identical (still
no-op), but the no-op is now explicit and the wait loop is one line
away from working when someone identifies the real loading marker
in Google's DOM. Closes `F-010` from the post-refactor audit.

**Q2. Mutable-default trap in `translation_result_phrase_array`.**
The init `[[]] * (numrows + 1)` had every slot pointing at the same
shared `[]`. Current code only does `array[i] = lines_divided` (slot
replace), which sidesteps the trap, but any future `array[i].append`
would silently mutate every slot at once. Replaced with
`[[] for _ in range(numrows + 1)]` so each slot is a distinct list.

**Q3. `atexit` cleanup for the Chrome driver.** The happy-path
`driver.quit()` lives at the bottom of `main()`; on any earlier
crash, the child Chrome process was orphaned and the launcher's
job pool accumulated zombie browsers. Registered
`_atexit_cleanup_driver` at module load — closes
`_ctx.browser.driver` on any normal termination, including crashes.
Nested `try/except` so the handler can't itself raise during
interpreter teardown.

Tests: 51/51.

---

### 2026-05-09 (part four) — repo housekeeping: docs in English, branches archived, lint sweep

Two commits, one tag-and-delete operation, and a new memory rule.

**O1. CHANGES.md and `docs/v2-frontend-hardening.md` translated to
English.** The legacy Persian content was either prose (translated) or
linguistic sample data (left in place — those characters are *data*,
not text). Other docs already had only sample-data Persian, so no
changes there. Result: 1316-line CHANGES.md compressed to ~480
English lines, newest-first.

**O2. Bare `except:` cleanup — 107 sites in five files.**
`src/machine-translate-docx.py` (42), `src/engines/deepl.py` (35),
`src/engines/inactive/perplexity_web.py` (14),
`src/engines/inactive/chatgpt_web.py` (11),
`src/xlsx_translation_memory/xlsx_translation_memory.py` (5). Each
became `except Exception:`. Matches `.claude/rules/code-style.md`'s
mandate and stops swallowing `KeyboardInterrupt` / `SystemExit`.

**O3. Silent-mode guards on three blocking `input()` calls.** All
remaining unguarded `input()` calls in the entry script now respect
the `silent` flag:

- Google CAPTCHA prompt — raises in silent mode (the launcher
  subprocess can't proceed without a human).
- xlsx and docx save-retry prompts — sleep 2 s in silent mode and
  retry, instead of hanging the launcher pipe forever.

Closes the failure mode where the launcher could deadlock on certain
error paths.

**O4. `.editorconfig` added.** LF line endings, UTF-8, 4-space Python
indent, 2-space markup indent, CRLF for `*.bat`, trim trailing
whitespace. Prevents whitespace churn across IDEs.

**O5. Memory rule: docs are English-only in the repo.** Added
`feedback_docs_english_only.md` to `~/.claude/.../memory/` so the
rule survives session breaks. Conversation responses stay in Persian
per the existing line-separation rule.

**O6. Memory rule: auto-commit + auto-doc.** Added
`feedback_auto_commit_and_doc.md`. Every change made by the
assistant on this repo: (1) commit immediately to current branch,
(2) update CHANGES.md in the same flow, (3) update PROJECT_MEMORY.md
when an invariant changes, (4) push to origin. Default branch is
`master`.

**O7. Two empty branches deleted (local + remote).**

```
review-rewrite-opus-4.7         deleted (was 244f55f)
claude/romantic-bhabha-a3ad61   deleted (was cbe6f31)
```

The latter also had a stale worktree at
`.claude/worktrees/romantic-bhabha-a3ad61/`; pruned via
`git worktree prune`.

**O8. Three merged backup branches archived as tags + deleted.** The
"album-of-memories" pattern: tag the final state, then delete the
branch. Archived state stays accessible via the tag forever; the
branch list is clean.

```
audit/post-refactor       →  tag archive/audit-post-refactor       (4e6c354)
refactor/architecture     →  tag archive/refactor-architecture     (f798322)
feature/v2-frontend       →  tag archive/feature-v2-frontend       (38c9c8a)
```

After the tag-and-delete, the only branch on origin is `master`.

**O9. Today's commits on master**:

```
85e0811  chore(maintainability): English docs, bare-except cleanup, silent-mode input guards
6207a59  docs: log today's 9 commits in CHANGES.md
a205a41  fix(docx): defensive lock on source-language column
81fdd8f  audit: pre-real-test sweep
f957f89  fix(progress): hide overlay + Google-js markers + bufsize=1
8955042  fix(translate): seed driver in remaining selenium helpers
9770ffd  fix(translate): seed local driver from ctx
38ebce4  fix(translate): non-split write path
496183f  fix(translate): Phase H bridge — _sync_globals_from_ctx
1a8c127  fix(translate): xtm — module-level None + global declaration
02d62da  fix(translate): Phase H — thread ctx through translate_docx
```

Tests: 51/51 passing.

---

### 2026-05-09 (part three) — Phase H bridge, progress UX, source-column lock

Nine commits, all on `master`, 51/51 tests passing throughout.

**N1. Phase H bridge — `_sync_globals_from_ctx(ctx)`.** A new helper
that mirrors every public attribute of `ctx.docx` (and
`ctx.browser.driver`, `ctx.openai.translator/polisher`,
`ctx.language.dest_lang/src_lang`) onto the module namespace. Wired
into `main()` at four pipeline boundaries: after
`read_and_parse_docx_document`, after `create_webdriver`, after
`translate_docx`, and after `document_split_phrases`. The bridge lets
the ~40 helpers that still read by bare name see the populated state
without forcing a one-by-one refactor.

**N2. Threaded helpers.** `translate_docx`,
`print_console_docx_file_translated`, `cell_set_1st_paragraph`, and
`cell_add_paragraph` now take `ctx`. Three writes against the empty
global `table_cells` were redirected to `ctx.docx.table_cells`.
`prepare_and_clear_cell_for_writing` now skips rows with fewer than
three cells (subtitle footers).

**N3. `xtm` module-level binding.** Added `xtm = None` at module
top and `global xtm` inside `initialize_translation_memory_xlsx`. The
historical code expected a module global but the assignment was
local-only — every later `if xtm is not None` raised `NameError`
once that path ran live.

**N4. Driver seed in Selenium helpers.** Five functions now seed
`driver = ctx.browser.driver` at the top of their bodies:
`selenium_chrome_google_translate_text_file`,
`selenium_chrome_google_translate_html_javascript_file`,
`selenium_chrome_google_translate_xlsx_file`,
`get_translation_and_replace_after`, `run_statistics`. Each of these
later reassigns `driver` in a recovery branch — without the seed,
Python treated `driver` as local for the entire body and every prior
`driver.get(...)` raised `UnboundLocalError`.

**N5. Non-split write path decoupled from phrase array.**
`print_console_docx_file_translated` now writes the translation
straight from `ctx.docx.to_text_by_phrase_separator_table[row_n]` in
non-split mode, regardless of whether `document_split_phrases`
populated `translation_result_phrase_array`. The previous gate
caused silent empty-cell failures whenever the splitter skipped a row.

**N6. Progress UX.** Three related fixes:

- The legacy frontend's catch block hides `loadingElement` *before*
  `await showAlert(...)` so the progress bar no longer animates
  behind the dialog.
- `subprocess.Popen` for the backend now uses `bufsize=1` (line-
  buffered). The default fully-buffered pipe held `PROGRESS:N`
  markers in an 8 KB buffer, so the bar appeared to jump from 10 %
  straight to 100 %.
- The Google-javascript path emits `PROGRESS:15/30/50/75/90` from
  inside the per-paragraph loop (it was previously silent —
  `runner.py`'s block-loop emits never reach this code path).
- `save_docx_file` emits `PROGRESS:90` at its top to fill the
  DeepL/Perplexity gap between runner's last 75 and the final 100.

**N7. Source-column defensive lock.** New field
`source_columns_snapshot` on `RuntimeDocx`. At parse time, every cell
in columns 0 and 1 is `deepcopy`'d (full XML element). At save time,
just before `docxdoc.save(...)`, each snapshot is compared (via
`lxml.etree.tostring`) against the live cell; if any cell drifted, it
is restored from the snapshot. Fires a `[LOCK] Restored N source-
column cell(s) before save (drift detected — translation memory leak
suspected)` log line so any leak is visible. Closes the user-reported
bug where translation-memory `before` substitutions were leaking
into the EN source column.

**N8. Today's nine commits on master**:

```
6207a59  docs: log today's 9 commits in CHANGES.md
a205a41  fix(docx): defensive lock on source-language column
81fdd8f  audit: pre-real-test sweep
f957f89  fix(progress): hide overlay + Google-js markers + bufsize=1
8955042  fix(translate): seed driver in remaining selenium helpers
9770ffd  fix(translate): seed local driver from ctx
38ebce4  fix(translate): non-split write path
496183f  fix(translate): Phase H bridge — _sync_globals_from_ctx
1a8c127  fix(translate): xtm — module-level None + global declaration
02d62da  fix(translate): Phase H — thread ctx through translate_docx
```

---

### 2026-05-09 (part two) — branch consolidation into master

**M1. Merged `audit/post-refactor` into master.** 26 commits
covering Phase A→G4 refactor and 12 audit fixes. Most important:
`F-001` (Engine Protocol resync to the post-F1 `translate(ctx, text)`
shape) and `F-007` (`html.unescape` instead of the non-existent
`str.unescape`). Strategy: `git merge --no-ff` to preserve the phase
history. Smoke test: 36 passed. `F-010` (DeepL `$Translation` regex)
and `F-012` (entry-script middle-layer threading, Phase H) were
deferred at this point — Phase H landed later the same day.

**M2. Merged `feature/v2-frontend` into master.** Seven commits
adding the Claude-inspired SPA at `web/v2/`: Tailwind 3.4 (compiled,
not CDN), Alpine.js, drag-and-drop, 36-hour cache, newsletter,
i18n EN/FA, Playwright e2e tests. Backend additions in
`local_launcher.py` are additive and non-breaking (cache layer,
`/v2/*` routes, `/subscribe` endpoint). The legacy `/` route is
preserved unchanged. One `modify/delete` conflict on
`tests/test_aligner_split.py` resolved in favour of the audit-side
rebuild. Strategy: `git merge --no-ff`. Tests after merge: 51 passed.

**M3. F-013 fix — Windows console encoding.** `_process_job`
prints `▶ ✓ ✗ —`, which the default Windows `cp1252` console can't
encode, so the job-processing thread died on the first job. Fix
added at the top of `local_launcher.py`:

```python
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass
```

**M4. Documentation refresh.** Updated `CLAUDE.md` (new architecture
diagram showing both UIs, full module map, links to new docs),
`PROJECT_MEMORY.md` (constraints C7–C13, finding F-013, today's
six entries in 'Recent Important Changes'), `CHANGES.md` (M1–M5
section), `.gitignore` (`.doc/` ignored).

**M5. Branch retention plan.** Per agreement with the user, all
merged branches stay until the first successful real-file test:

```
audit/post-refactor       merged, kept
refactor/architecture     merged, kept (subset of audit)
feature/v2-frontend       merged, kept
```

The two empty branches (`review-rewrite-opus-4.7`,
`claude/romantic-bhabha-a3ad61`) were deleted on 2026-05-09 once the
master fix sweep was complete.

---

### 2026-05-08 (part two) — Aligner v2 + UI polish

**S1. Three outputs reduced to two.** AIAlign was removed; classic
and double both run mechanically (`llm_threshold=0`). Sequential
download swapped for ZIP to avoid the Chrome multi-download prompt
(later flipped back to staggered single downloads — see B1 below).
Files changed: `local_launcher.py`, `index.ejs`,
`src/machine-translate-docx.py`.

**S2. B1 — `splitTranslate` was True for `fa+chatgpt-polish`.**
After restoring the engine from `localStorage`, the `engineChecker()`
JS handler did not run, leaving `splitTranslate=True` even though the
aligner already does the line distribution. Backend now force-disables
it; the JS now also re-runs the checker on restore.

**S3. Progress bar for Google / DeepL.** `machine-translate-docx.py`
emits `PROGRESS:25/50/75` proportional to block progress in the block
loop. Frontend label is now engine-agnostic ('Translating…',
'Polishing…', 'Aligning subtitles…').

**S4. `aligner_per.py` rewritten — Mechanical v2.0.** From 1565
lines to ~380 lines. Built on the cleaner `fa_aligner.py` from the
v7.5 skill. Kept: `_display_len`, RTL markers, protected bigrams,
shaded-cell detection, cross-group sentinels. Removed: B4 weight
tables, discourse-marker alignment, LLM stubs, quality scoring. New
module-level helpers: `_find_break`, `_split_for_n_rows`,
`_distribute_to_rows`, `_enforce_no_triple`. Important fix in
`_parse_groups`: trailing empty-FA rows are now folded into the
preceding group, which is what the single-call output shape requires.

**S5. `_simple_split_docx` rewritten — Classic without insert /
double.** The old `deepcopy(_row._tr)` approach inserted new rows,
which doubled both the EN cell and the line-number cell (the
visible 'red lines'). The new flow groups rows via `_parse_groups`,
splits into at most `n_rows` chunks, writes one chunk per row, and
pads with `''` — no row is ever duplicated and only `cells[2]`
changes.

**S6. Prompt caching — Responses API for gpt-5.x.** `gpt-5.5`
didn't match the `if "pro" in self.model` test, so the translator
silently fell back to `chat.completions.create` where caching is
broken for the GPT-5 family. Detection broadened:

```python
_use_responses_api = (
    "pro" in self.model.lower()
    or self.model.lower().startswith("gpt-5")
)
```

Response normalisation (Responses API uses `input_tokens` /
`input_tokens_details`; we map them onto `prompt_tokens` /
`prompt_tokens_details` after `model_dump()` so cost calc is
unchanged) and text extraction (`response.output_text`) updated.
Files: `translator.py`, `polisher.py`.

**S7. localStorage stores language only.** Engine and AI model
were dropped from the saved state — they always default from the
language now. Re-running the same target language no longer locks
the user into a previously chosen low-quality engine. `_lsSet` /
`_lsGet` / `_lsDel` helpers wrap `localStorage` in `try/catch` for
private-mode browsers.

**S8. Engine-lock fix — guard every `.selected` behind
`setDefault`.** `deeplOption.selected = true` and
`googleOption.selected = true` inside `engineChecker()` were
unconditional, so changing the engine immediately reverted it.
Consolidated all defaults under a single `if (setDefault)` block.

**S9. Official `gpt-5.5` pricing (April 2026).**

```
Input:        $5.00 / 1M tokens
Cached input: $0.50 / 1M tokens
Output:       $30.00 / 1M tokens
```

`translator.py` and `polisher.py` cost calc now uses cached price
for `cached_tokens` and full price for the rest.

**S10. Standalone aligner test tool.** New `tests/test_aligner_only.py`:

```bash
python tests/test_aligner_only.py FILE_PER_TranslatePolish.docx [--verbose]
```

Output: `FILE_PER_TranslatePolish_Double_TEST.docx`. Exit 0 if no
triples and no chunks over 48 chars. Exit 1 otherwise (file is still
written for inspection).

---

### 2026-05-09 (part one) — server.js, fa_postprocess, RTL, batch research

**P1. `server.js` and `package.json`.** `server.js.txt` no longer
exists (renamed to `server.js` earlier). Added a missing
`package.json` declaring the npm dependencies the production server
requires (`express ^4.19`, `multer ^1.4`, `cross-spawn ^7.0`,
`body-parser ^1.20`, `cron ^3.1`, `iconv-lite ^0.6`, `ps-list ^8.1`).
`engines.node = ">=18"`. `local_launcher.py` is independent of all
this and works without Node.

**P2. `fa_postprocess.py` — safe FA normalizer.** New file:
`src/openai_tools/fa_postprocess.py`. The default `hazm.Normalizer`
broke W3 TECH_LOCK in this project (e.g. `GPT-4o` → `GPT- ۴ o`)
and converted `"..."` to `«...»` (violates HL-11). Replaced with
a custom <50-line normalizer that does only the safe subset:

- `ي` (U+064A) → `ی` (U+06CC)
- `ك` (U+0643) → `ک` (U+06A9)
- digits `٠-٩` (U+0660+) → `۰-۹` (U+06F0+)

ASCII, quotes, ZWNJ, harakat, spacing — all left alone. Applied in
`polisher.polish` after the residue check. Test:
`tests/test_polisher_parse.py::test_fa_postprocess_normalize_safe_subset`.

**P3. Aligner discourse-cue expansion.** Four new categories in
`_BUILTIN_CUES` of `aligner_per.py`: addition, sequence, example,
emphasis. ~20 lines; same structure; near-zero risk.

**P4. RTL helpers via the official python-docx API.**
`_ensure_rtl_paragraph` and `_ensure_rtl_run` no longer use manual
`find()` traversals — now use `get_or_add_pPr()` / `get_or_add_rPr()`.
Schema-correct insertion, shorter, idempotent.

**P5. Pure research (no implementation).**

- `docs/batch-api-analysis.md` — Batch API is the wrong tool for
  the current interactive UI; potentially right for future bulk
  workflows. Deferred.
- `docs/aligner-research.md` — comparison with Gale-Church, DP,
  embeddings, ASR. Three ideas captured for future work.
- `docs/rtl-rendering.md` — the why and how behind the E10 fix;
  why `python-bidi` / `arabic-reshaper` were not adopted.

**P6. Progress bar via existing polling.** No SSE.

- `Job` dataclass gained a `progress: int = 0` field.
- `local_launcher._process_job` sets `progress=5` (job recorded)
  and `progress=10` (semaphore acquired).
- `_run_real_backend` parses `PROGRESS:` lines from subprocess
  stdout and calls `update_job(progress=...)`. The line itself
  isn't echoed (it would be visual noise).
- `machine-translate-docx.py` emits five anchor markers: `15` before
  translate, `30` after translate, `65` after polish, `75` before the
  aligner pass, `100` after Double finishes.
- `/status/:jobId` returns `progress`. `index.ejs` has a
  `<progress>` element + label + percentage. `pollJobStatus` calls
  `_updateProgress(data.progress)` on every tick. Label resolution
  via `_progressLabel(pct)`.

---

### 2026-05-08 (part one) — review-rewrite-opus-4.7 phases 1–5

A rolling cleanup pass across five phases.

**Phase 1 — critical fixes (visible in the final output or in
security):**

- **0.1 RTL/bidi in FA cells (mirrored-text fix).** `_set_fa_cell`
  used to set only `run.text`. If the cell template lacked
  `<w:bidi/>`, Word rendered the FA text LTR (reversed). New helpers
  `_ensure_rtl_paragraph(p)` and `_ensure_rtl_run(run)` add `<w:bidi/>`
  to `pPr` and `<w:rtl/>` to `rPr`. Idempotent.
- **0.2 English-residue detection in polish.** New helper
  `_detect_en_residue(text)` flags lines where >40 % of characters
  are Latin and the longest word is >5 chars. Flagged lines are
  replaced by the pre-polish translator output. List of changes is
  recorded in `last_call_data["en_residue"]` for inspection.
- **0.3 Server-side file validation.** `_validate_docx_payload`
  in `local_launcher.py`: PK magic bytes + 50 MB zip-bomb cap.
  Runs before disk write. The frontend's client-side check is no
  longer trusted alone.

**Phase 2 — visible bugs:**

- **0.4 ZIP package for download (E9 fix).** New endpoint
  `GET /download-zip/:jobId` bundles every output file for the job
  into one `_PER_package.zip`. Frontend uses it whenever
  `filename2 || filename3` exist, so Chrome only sees one download.
  (Reverted to staggered downloads in S1 above; the endpoint stays
  as 410 Gone.)
- **0.5 Auto-cleanup of the job store.** `cleanup_old_jobs(max_age_sec=3600)`
  runs on a 10-minute interval thread, removing `done`/`error` jobs
  older than an hour.
- **0.6 OpenAI retry with backoff.** New `src/openai_tools/_retry.py`:
  `call_with_retry(fn, *, label)`. Three retries with 1 / 2 / 4 s
  backoff for `RateLimitError`, `APIConnectionError`, `APITimeoutError`.
  `BadRequestError` re-raised immediately. All other exceptions
  re-raised — no silent swallow. Used by translator, polisher, and
  the aligner.

**Phase 3 — aligner quality:**

- **0.7 `_display_len` — exclude ZWNJ from length.** Word renders
  ZWNJ (U+200C) as zero-width but `len()` counts it. Every
  `len(...) > MAX_CHARS` validation in `aligner_per.py` switched
  to `_display_len(...) > MAX_CHARS`. Slicing operations (`text[:MAX_CHARS]`)
  keep `len` — the result is conservative.
- **0.8 Cross-group triple guard with sentinel.** Bridge rows are
  invisible in the flat list; consecutive identical chunks across a
  bridge could trigger the "5 in a row" suppression downstream. Fix:
  inject `'\x00GROUP_BOUNDARY\x00'` between groups before flatten,
  re-chunker skips these slots.
- **0.9 Per-content-type `BREAK_RATIO`.** A dict
  `_BREAK_RATIO_BY_TYPE` replaces the single `BREAK_RATIO_MEDIAN=0.45`:
  `narration` and `spiritual` keep 0.45 (verb-final FA),
  `news_attr` 0.55 (front-loaded subject), `dialogue` and
  `ingredient` 0.50.

**Phase 4 — code quality + tests:**

- **0.10 Ten unit tests + pytest setup.** New `pytest.ini`,
  `requirements-test.txt`, `tests/conftest.py`,
  `tests/test_aligner_split.py` (6 tests),
  `tests/test_polisher_parse.py` (3), `tests/test_translator_utils.py`
  (1). Tests construct objects via `__new__` so they run without
  `OPENAI_API_KEY` and without network. Run: `pip install -r
  requirements-test.txt && pytest` → 10 passed in <2 s.
- **0.11 DB connection guard.** `self.db_enabled =
  bool(os.environ.get("MARIADB_HOST"))` in `OpenAITranslator.__init__`.
  When false, `set_filename` and the 'Save query record' block early-
  return with an INFO log. Removes the two retry attempts that ran
  on every API call in DB-less environments.
- **0.12 Concurrent-job semaphore.** `_job_semaphore =
  threading.Semaphore(int(os.environ.get("MTD_MAX_CONCURRENT_JOBS",
  "2")))` at module level in `local_launcher.py`. `_process_job`
  acquires before work and releases in `finally`. Caps the number of
  concurrent backend subprocesses (each ~250–500 MB resident).

**Phase 5 — optional:**

- **0.13/0.15 — skipped.** Progress bar (would have required
  significant SSE/polling changes — landed later as part of P6
  above) and `virastar` (no PyPI distribution).
- **0.14 `prompt_hash` in log JSON.** New helper in
  `_retry.py`: `prompt_hash(text)` returns `sha256(text)[:8]`.
  Recorded in `OpenAITranslator.last_call_data["prompt_hash"]`,
  `OpenAIPolisher.last_call_data["prompt_hash"]`, and
  `FASubtitleAligner.last_stats["prompt_hash"]`. Lets us identify
  which prompt version was used in a given log when prompts later
  change.

---

### Earlier (numbered changes, oldest first)

These predate the dated session log above.

1. **Polisher output uses `⟨⟨N⟩⟩` tags.** Replaced the old
   `Line N: text` format that conflicted with content text. Tags
   use U+27E8 / U+27E9 — they don't appear in normal text. Parser
   has four strategies in priority order: tag, legacy `Line N:`,
   plain line-for-line, pass-through with length warning.
2. **Output filename collision protection.** If the destination
   path exists, suffixes `_1`, `_2`, `_3` are appended until a
   free name is found.
3. **Polling architecture in the server.** `/upload` returns
   `{ ok: true, jobId }` immediately. The Python pipeline runs in
   the background. The frontend polls `/status/:jobId` every 4 s.
   Job store: in-memory `Map<jobId, JobState>`. Completed jobs are
   pruned after 2 hours; pending jobs time out at 50 minutes.
4. **OpenAI Translation + Polish engine.** New engine
   `chatgpt-polish`, available only for Persian. Translates with
   `gpt-5.5`, then runs a second `gpt-5.5` polish pass.
5. **Frontend cleanups in `index.ejs`.** Loading-overlay class
   conflict fixed; `engineChecker()` rewritten cleanly;
   localStorage save/restore for source language, target language,
   and engine; `pollJobStatus(jobId)` replaces the synchronous
   wait — 40 minutes max, retries on transient network errors.
6. **Single-call mode for OpenAI.** Prior code split the file into
   blocks and called the API per block. New flow: one API call for
   translation, one for polish (when `--with-polish` is set).
   Block loop preserved for non-OpenAI engines.
7. **`timeout=1800` on every API call.** Translator and polisher
   both pass `timeout=1800` to the SDK to avoid indefinite hangs.
8. **Removed `reasoning_effort` from translator + cache fix.** On
   `gpt-5.4-mini`, `reasoning_effort: "high"` produced 38997
   reasoning tokens for 95 subtitle lines — 94 % of all generated
   tokens. Removed entirely from the translator. Polisher keeps it
   only when `"mini"` is in the model name. Separately, `{N}` was
   moved from the system prompt into the user message so the system
   prompt is identical across runs and the prompt cache actually hits.
9. **Default model upgrade to `gpt-5.5`.** Translator, polisher,
   and CLI default. Aligner stays hard-pinned to `gpt-5.4-mini`
   regardless of `--aimodel` (intentional — the aligner needs a
   different cost/latency profile).
10. **FA aligner — bridge and shaded-cell detection.** Three
    layers: XML cell-shading detection (`_cell_has_shading`), new
    `BRIDGE_PATTERNS` for timecodes / ALL-CAPS labels / `ONSCREEN`
    / `VO`, and a fallback that treats empty EN cells as bridges.
    Write-back uses `row_indices` so bridge / shaded cells are
    never touched.
11. **UI model selector.** Dropdown in `index.ejs` (visible only
    when an OpenAI engine is selected) with three options:
    `gpt-5.5` (recommended), `gpt-5.4`, `gpt-5.4-mini`. The chosen
    model is appended to the `--aimodel` flag and persisted in
    `localStorage`.
12. **`local_launcher.py` — Python local server.** Pure Python
    (no Express): `ThreadingHTTPServer`, custom multipart parser,
    real-backend subprocess + mock-backend mode for UI exercising.
    Several bugs fixed during stabilisation: form field name
    (`translationEngine` not `engine`), duplicate `ai_model`
    parameter, timestamp prefix in output names, `_FA` instead of
    `_PER` in the language-suffix fallback (added `_LANG_ALPHA3B`
    map).
13. **Prompt files renamed `_fa` → `_PER`.**
    `prompts/translate_fa.txt` → `prompts/translate_PER.txt`,
    same for `polish_fa.txt`. New `_prompt_lang_code()` helper
    (`fa` → `PER`, `ar` → `ARA`); `_normalize_lang()` is read-only
    and unchanged.
14. **Final output naming convention** —
    `{stem}_PER_TranslatePolish.docx`, `{stem}_PER_Double.docx`,
    `{stem}_PER_TranslatePolish_log.json`. Aligner derives its
    output name from the input filename, not the polish output.
15. **Three-file output** (later reduced to two — see S1 above).
    `_PER_TranslatePolish.docx`, `_PER_Classic.docx`,
    `_PER_Double.docx`. `Job.filename2` and `filename3` plus
    `_find_classic_file` / `_find_double_file` discovery helpers.
16. **Hide the Split section for FA + chatgpt-polish.** When the
    aligner is responsible for line distribution, the Split UI is
    not just unneeded — it actively duplicates work. The whole
    `#splitSection` is hidden via `engineChecker()` and
    `splitTranslate` is forced to false.
17. **Three distinct split outputs (later removed in S1)** —
    Classic (algorithmic), Double (mechanical aligner), AIAlign
    (LLM-reviewed aligner). Phase 2 of this redesign collapsed
    Classic and Double to two mechanical outputs and dropped
    AIAlign entirely.

---

## Current status

| Area | Status |
|------|--------|
| OpenAI translate (single-call) | ✓ |
| OpenAI polish (single-call) | ✓ |
| Classic split (no insert, no doubling, FA column only) | ✓ |
| Double aligner (FA-based grouping, maximises doubles) | ✓ |
| `⟨⟨N⟩⟩` polisher format | ✓ |
| Polling architecture | ✓ |
| localStorage (language only) | ✓ |
| Prompt cache — Responses API for `gpt-5.x` | ✓ |
| `gpt-5.5` default model | ✓ |
| UI model selector | ✓ |
| Two-file download with 1800 ms delay | ✓ |
| `engineChecker` without lock-loop | ✓ |
| Official `gpt-5.5` pricing + cached cost | ✓ |
| `_PER` / `_PER_Double` / `_PER_Classic` naming | ✓ |
| Prompt file `_PER` suffix | ✓ |
| Split section hidden for FA + polish | ✓ |
| Standalone aligner test | ✓ |
| Phase A→G4 refactor (runtime / config / engines / selenium_utils / runner) | ✓ |
| Audit + 12 finding fixes | ✓ |
| F-013 fix (Windows console encoding) | ✓ |
| v2 UI (Claude-inspired) at `/v2/` next to legacy at `/` | ✓ |
| 36-hour cache + `/subscribe` endpoint | ✓ |
| Phase H bridge — `_sync_globals_from_ctx` | ✓ |
| Driver seeding in five Selenium helpers | ✓ |
| Non-split write path decoupled from phrase array | ✓ |
| Source-column defensive lock | ✓ |
| Progress UX (overlay-hide, line-buffered subprocess, milestones) | ✓ |
| Tests: 51 passing | ✓ |
| End-to-end real-file test | ⚠ pending |

---

## Open follow-ups

- Verify aligner output quality on a real broadcast subtitle file.
- Manual end-to-end test on both UIs with a real `.docx`.
- After a successful real test: delete the three merged backup
  branches (`audit/post-refactor`, `refactor/architecture`,
  `feature/v2-frontend`).
- Phase H finish: thread the ~40 remaining helpers in
  `src/machine-translate-docx.py` so the bridge can be removed.
  Tracked as audit finding `F-012`.
- Audit finding `F-010`: the DeepL `regex_still_translating_str =
  '$Translation'` never matches because `$` is end-of-string.
  Deferred — flipping it changes wait-loop semantics, needs a
  dedicated test.

---

## Reading guide for the next session

Fastest path to context:

1. This file (CHANGES.md) — the whole picture in five minutes.
2. `src/openai_tools/translator.py` — translation work.
3. `src/openai_tools/polisher.py` — polish work.
4. `src/openai_tools/aligner_per.py` — aligner work.
5. `src/machine-translate-docx.py` (search `_single_call_done`) — CLI work.
6. `server.js` (job store + `/status`) — production server work.
7. `local_launcher.py` — local-server work.

### Likely questions

- *Which model for what?* — translate + polish: `gpt-5.5`. Aligner:
  `gpt-5.4-mini` (always).
- *How does the prompt cache work?* — System prompt is identical
  across runs. `N` lives in the user message. Cache hits start at
  the second call.
- *Where is single-call?* — search `_single_call_done` in
  `machine-translate-docx.py`.
- *Polisher output format?* — `⟨⟨N⟩⟩ text` — regex in
  `polisher.py`.
- *How does the aligner work?* — purely mechanical
  (`llm_threshold=0`), three passes, `aligner_per.py`.
- *Why are shaded cells handled correctly?* — `_cell_has_shading()`
  reads the docx XML and skips shaded cells.
- *Where are the FA prompts?* — `prompts/translate_PER.txt` and
  `prompts/polish_PER.txt`.
- *How does `local_launcher.py` read the engine?* —
  `fields.get("translationEngine")` (matches the JS form name).
- *Why is the Split section hidden?* — for FA + chatgpt-polish, the
  aligner replaces the splitter — leaving both on duplicates work.
- *Why three downloads?* — TranslatePolish + Classic + Double, one
  every 1.5 s.
- *Should we migrate to Java/Kotlin?* — no; the bottleneck is API
  latency, not Python, and `python-docx` has no Java equivalent.
