# PROJECT_MEMORY.md — Machine Translate DOCX

Committed team memory. Keep it concise — no raw logs, no long discussion.
Summary + link to `docs/` for depth.

Last updated: 2026-05-16 (master `HEAD`). Same-day landings since the previous bump: **cli.py 3-phase shrink** (4,395 → 3,994 lines, -9.1%). Phase 1 deleted six dead functions discovered by repo-wide grep (`lineno`, `reverse_string`, `remove_span_tag`, `create_translation_split_prompts` + `print_prompt_block`, `print_html_program_result`). Phase 2 extracted four startup helpers into a new `network_utils.py` (`test_internet`, `fetch_country_data`, `check_mirror_url`, `set_se_driver_mirror_url_if_needed` — renamed from mixed-case), the two output-side metadata writers into a new `docx_io/metadata.py` (`write_destination_language_in_docx_cell`, `set_docx_properties_comment_for_history`), moved `deepl_double_linefeed_between_phrases` into `engines/deepl.py` and `delete_paragraph` into `docx_io/cells.py`, and deleted three more orphans (`generate_tmx_file`, `linux_distribution`, `print_os_info`). Phase 3 extracted `write_translation_log` into a new `translation_log_writer.py` (now takes `(ctx, log_path)` explicitly, reads off `ctx.openai.translation_log`), deleted `getDownLoadedFileNameChrome`, and fixed a subtle pre-existing snapshot-ordering bug: `oai_translator` / `oai_polisher` / `translation_log` were declared AFTER the first runtime `_get_ctx()` call at line ~1062, so the snapshot caught `NameError` and `ctx.openai.translation_log` stayed at the dataclass empty `{}` default. Move the three names above the snapshot line so identity is brokered correctly from import time onward; `_sync_globals_from_ctx` was already repairing the divergence on its first call in `main()`, so behaviour in production was unchanged. Remaining big-payoff blocks (statistics cluster ~900 lines, Google file-mode workers ~800 lines, `_sync_globals_from_ctx` collapse) deferred to `docs/cli-shrink-phase3-handoff.md`. Tests: 154/154; six-way parallel smoke (chatgpt-api / chatgpt-polish / google × fa / fr) all passed.

---

## Active Constraints (never violate)

| # | Constraint | Why |
|---|-----------|-----|
| C1 | Aligner model is always `gpt-5.4-mini` — hardcoded | User preference; do not parameterize further |
| C2 | Do NOT add `reasoning_effort` to translator | Caused 94 % reasoning token overhead in testing |
| C3 | `_normalize_lang()` is read-only | Side effects elsewhere; use `_prompt_lang_code()` for prompt lookup only |
| C4 | Every OpenAI API call must set `extra_body={"prompt_cache_retention": "24h"}` | Cost reduction |
| C5 | Output filenames never get a timestamp prefix | Stripped by `_strip_timestamp()` in `local_launcher.py` |
| C6 | File collisions get `_1`, `_2` suffix — never silent overwrite | Data safety |
| C7 | BOTH frontends (legacy `/` and v2 `/v2/`) must remain functional | User keeps both as choices |
| C8 | `local_launcher.py` read-only list relaxed — F-013 (UTF-8 stdout), v2 routes, line-buffered subprocess all landed | Originally read-only; necessary fixes have been documented |
| C9 | `subprocess.Popen` for the backend MUST use `bufsize=1` | Without line-buffering, PROGRESS:N markers stall in the pipe and the UI bar jumps from 10 % to 100 % |
| C10 | **`RuntimeContext` is the sole canonical state surface for cli.py helpers.** Every function body must read pipeline state from `ctx.<sub>.<field>` — never by bare module-global name. Module-level globals at the top of `cli.py` remain authoritative only for argparse-time CLI inputs (snapshotted into `ctx` by `_get_ctx()`) and one-shot import-time setup (`rtlstyle`, `docxdoc`, `xtm`). The Phase-H mirror function `_sync_globals_from_ctx` was deleted on 2026-05-16 in Sprint D-C slice 6 once every bare-name read was threaded through ctx | Sprint D-C (2026-05-16) — replaced the older Phase-H "mirror after each pipeline step" pattern |
| C11 | New Selenium helpers must seed `driver = ctx.browser.driver` at the top if they later reassign `driver` | Otherwise Python treats `driver` as local for the entire body and every prior read raises UnboundLocalError |
| C12 | Legacy frontend error path: hide `loadingElement` BEFORE `await showAlert(...)` | Otherwise the progress overlay keeps animating behind the dialog while the user reads the error message |
| C13 | **Source language column is frozen.** Columns 0 + 1 of the input docx are deepcopy-snapshotted at parse time; `save_docx_file` restores any drift before the docx is written. No engine, helper, or future code path may modify the source side — the lock catches leaks regardless of cause | Translation-memory `before` replacements, alignment helpers, or any future bug must never bleed into the source-language column |
| C14 | **All committed `.md` files are English.** The repo is English-only; Persian belongs to the conversation, never to a commit. Linguistic sample data (FA characters demonstrating split rules) is fine inside code fences | Multi-tool / multi-author readability |
| C15 | **No `bare except:` in this codebase.** Always `except Exception:` (or a more specific class). Bare except hides `KeyboardInterrupt` and `SystemExit` and is a long-standing project rule from `.claude/rules/code-style.md` | Cleaned up 2026-05-09: 107 sites in 5 files |
| C16 | **`input()` must respect the `silent` flag.** Any blocking prompt in the entry script needs an `if not silent:` guard, with a non-interactive fallback (sleep+retry, or raise) for the silent branch. The launcher subprocess passes `--silent` and cannot answer a prompt | Cleaned up 2026-05-09: three remaining unguarded prompts now sleep+retry or raise |
| C17 | **Three merged backup branches were archived as `archive/*` tags and deleted on 2026-05-09.** Branch list on origin is now `master` only. Use `git show archive/<name>` to inspect any historical branch state | Branch list hygiene + permanent backup via tag |
| C18 | **OpenAI model ids are validated against `config.VALID_AI_MODELS`.** The single source of truth for model identifiers; CLI rejects unknown values; aligner stays `ALIGNER_MODEL = "gpt-5.4-mini"` (not parameterisable, just centralised). Reject `--aimodel <unknown>` at parse time, do not let it travel to the API call | B-004 (2026-05-10) — typoed `gpt-5.5-mini` used to fail mid-run with a 400 BadRequestError after Chrome had already launched |
| C19 | **Empty / no-translation runs exit non-zero with `[FAIL] reason=...`.** `assert_source_has_content(ctx)` after parse and `assert_translation_present(ctx)` after engine return raise `TranslationFailure` subclasses. The `__main__` block catches them, prints `[FAIL] reason=<token> message=<text>` for the launcher to parse, and `sys.exit(20)`. Never let the user think a no-op run succeeded | B-001 (2026-05-10) |
| C20 | **Failures are archived to `runtime_dir/failures/<job_id>__<ts>/`.** Launcher copies the input docx, stdout, meta.json, and an `UNREVIEWED.txt` sentinel into the folder on any non-zero backend exit. Optional alerting via `MTD_FAILURE_EMAIL` (smtplib), `MTD_FAILURE_WEBHOOK` (Discord/Slack shape), or `MTD_TELEGRAM_TOKEN` + `MTD_TELEGRAM_CHAT_ID` (Telegram bot — text alert always, optional 20 MB docx attachment unless `MTD_TELEGRAM_NO_ATTACHMENT=1`). All best-effort — never let alerting failures kill the launcher | B-002 (2026-05-10) + Telegram (2026-05-11) |
| C21 | **v2 announcement surfaces are driven by `web/v2/content.json`.** Four slots: `pinned` (single sticky banner at the very top of the page), `modal` (one-time welcome dialog per id), `announcements` (left-column list), `stories` (centre-column tile grid). `pinned.id` and `modal.id` drive dismissal persistence (`localStorage('v2.pinned.dismissed.<id>')` / `localStorage('v2.modal.dismissed.<id>')`); changing the id re-shows the surface to every visitor. Slots may be `null` or absent → silently skipped. **Never paint announcement content from any source other than content.json** — operators rely on a single edit point | 2026-05-11 |
| C22 | **Weekly newsletter export.** When `MTD_TELEGRAM_TOKEN` + `MTD_TELEGRAM_CHAT_ID` are configured, every Saturday at 12:00 in `MTD_SCHEDULER_TZ` (default `Europe/Paris`) the launcher uploads `subscribers.txt` as a Telegram document. Empty file → silent skip. Failure → `runtime_dir/subscribers_report_state.json` records `pending_warning: true`; the next launcher boot prints one stderr line surfacing it then clears the flag. Token unset → scheduler is dormant and the boot prints `[subscribers] Telegram not configured` once. Do not move the schedule to a more-frequent interval without operator sign-off | 2026-05-11 |
| C23 | **Branch lifecycle: test → commit → push → merge to master ASAP → tag `archive/*` → delete.** Never delete a branch (local or remote) without first creating a retroactive lightweight or annotated tag at its tip under `archive/<purpose>-<YYYY-MM-DD>` and pushing the tag to origin. This keeps the tree clean while preserving every historical tip. The only exception is a branch that carries zero unique commits relative to master (a pure copy) — those can be deleted without a tag. The user explicitly invoked this rule on 2026-05-12 after noticing the overnight branch had been deleted without a tag; the tag was added retroactively as `archive/2026-05-11-overnight-fixes` | 2026-05-12 |
| C24 | **No top-level imports of optional / heavy dependencies in `cli.py`, `translator.py`, `splitting.py`.** `mysql.connector`, `hazm`, `undetected_chromedriver` are lazy-loaded (function-local imports or try/except with a passthrough fallback) so a packaged build (PyInstaller .exe shipped to a user with no DB, no NLP toolkit, no Chrome) boots successfully. Future heavy deps follow the same rule | 2026-05-14 (feat/exe-packaging) |
| C25 | **`create_webdriver(ctx)` is a NO-OP when `ctx.engine.engine == 'chatgpt' and ctx.engine.method == 'api'`.** The OpenAI API path is pure HTTP — it never needs a browser. Skipping Chrome saves ~6 s of startup latency and lets the CLI run on Chrome-less machines. Companion guard: the cleanup branch in `cli.py:main()` only calls `ctx.browser.driver.close()` when the driver is not None | 2026-05-14 (feat/exe-packaging) |
| C26 | **`MTD_FROZEN_ROOT` env var resolves runtime paths next to the .exe in a packaged build.** PyInstaller's `mtd_entry.py` wrapper sets it to `Path(sys.executable).parent`. `log_paths._find_project_root` honours it for the central `Log json file/` directory; `_find_prompts_dir` honours it for an override prompts directory (the wrapper also auto-falls-back to `sys._MEIPASS/prompts` for the bundled set). In non-frozen development runs the env var is empty and the existing src-tree finder is used | 2026-05-14 (feat/exe-packaging) |
| C27 | **Server deployment: single `config.toml` is the source of truth.** `src/machine_translate_docx/server_config.py` reads a TOML file (default `runtime_dir/config.toml`, override `MTD_CONFIG_PATH`) and pushes its `[telegram]` / `[smtp]` / `[failure_alerts]` / `[server]` keys into the corresponding `MTD_*` env vars at launcher boot. A real env var still wins over the file (operator overrides). Auth credentials (`[auth]` username + bcrypt-or-PBKDF2 password hash) and the OpenAI API key (`[openai]`) live in the same file. Wizard at `scripts/setup_wizard.py` writes the file with mode `0600` on POSIX. Never re-introduce scattered env-var-only configuration | 2026-05-14 (feat/server-deploy) |
| C28 | **HTTP Basic auth gates every launcher route except the explicitly-public set.** `_PUBLIC_PATHS = {"/health", "/favicon.ico"}` and `_PUBLIC_PREFIXES = ("/static/",)` are the ONLY paths that bypass auth. When `config.toml`'s `[auth]` section is empty the launcher runs unauthenticated (workstation / .exe mode unchanged); when populated the launcher returns 401 + `WWW-Authenticate` on unauthenticated requests. Don't add a new public path without explicitly extending those sets | 2026-05-14 (feat/server-deploy) |
| C29 | **`/health` returns 200 with `{status,version,uptime}` and is always public.** Used by Caddy heartbeat + UptimeRobot. Don't add secrets (config values, user counts, env vars) to the payload — it leaks them to anyone who scans port 80 | 2026-05-14 (feat/server-deploy) |
| C30 | **Server install path uses `/opt/mtd/` with non-root `mtd` user.** `scripts/install_server.sh` enforces this; `scripts/mtd-server.service` runs `User=mtd` with `MemoryMax=512M`, `CPUQuota=80%`, and `ProtectSystem=strict`. Don't run the launcher as root | 2026-05-14 (feat/server-deploy) |
| C31 | **Backups daily, log rotation weekly with 90-day retention.** Per operator preference set 2026-05-14: `scripts/mtd-backup.sh` runs from cron at 03:30 UTC and writes `/var/backups/mtd/mtd-YYYY-MM-DD.tgz` with 30-day local retention. `scripts/mtd-logrotate` rotates `Log json file/*.json` + `/var/log/caddy/mtd.access.log` weekly and keeps 90 weeks. Off-box backup is best-effort (uncomment `rsync` or `aws s3` line in mtd-backup.sh) | 2026-05-14 (feat/server-deploy) |
| C27 | **Prompts are byte-identical across calls; language identity lives in the user message.** Both `translate_universal.txt` / `polish_universal.txt` (and the Persian-specific files) MUST NOT contain `{SOURCE_LANG}` / `{DEST_LANG}` / `{N}` template placeholders. `OpenAITranslator._load_system_prompt` returns the template verbatim. The per-job language pair and line count are supplied in the user message via a `<JOB_CONFIG>` envelope, immediately followed by `<LINES>` (translator) or `<PAIRS>` (polisher). This is the precondition for OpenAI's automatic prompt caching, which needs the first ≥1024 tokens of the prefix to match byte-for-byte across calls — without this layout, the cache prefix breaks the moment source-language or target-language changes | 2026-05-15 (v7 promote) |
| C28 | **`OpenAIPolisher` requires `source_lang` at construction.** The polisher emits a JOB_CONFIG envelope listing both source and target language. `runner.py` passes `source_lang=ctx.language.src_lang or "en"`; never instantiate the polisher without it in new call sites. Constructor signature: `OpenAIPolisher(model, dest_lang, source_lang="en", prompt_path=None)` — `source_lang` defaults so legacy callers don't break, but the default loses the language pair in the JOB_CONFIG | 2026-05-15 (v7 promote) |
| C29 | **Language descriptors come from `openai_tools/_lang_descriptors.py`.** Rich locale → descriptor table (~80 entries, e.g. `fa` → `"Persian / فارسی, Iran, modern standard written Persian"`). Callers use `lang_descriptor(code)`; fallback chain: curated table → bare primary subtag in curated table → `config.google_translate_lang_codes` → raw code. Add new locales to the curated table, never inline | 2026-05-15 (v7 promote) |
| C30 | **`LS-12 BROADCAST_OPENING_PATTERNS` is intentionally non-idiomatic Persian.** "Welcome to X" → "خوش آمدید به X" (NOT "به X خوش آمدید"). The deliberate canonical form locks cross-episode consistency for SMTV broadcasts — most programmes re-use the same opening/closing templates and downstream subtitle editors lose time fixing variations. Do NOT "fix" the rule to a more idiomatic Persian form on a code-style review; consult the user before any change to these canonical patterns | 2026-05-15 (v7 promote) |
| C31 | **`LS-13 FOREIGN_SCRIPT_AUTHENTIC_VOICE` keeps non-source, non-target script tokens byte-identical.** Lao ສະບາຍດີ, Chinese 你好, Sanskrit नमस्ते, etc. used as authentic-voice greetings — translator keeps them verbatim, polisher restores them if translator erred. The transliteration in parens "(Sabaidee)" is also byte-id. Only the framing sentence (`In my native Lao, that means, "..."`) and the English meaning inside the trailing quote get translated | 2026-05-15 (v7 promote) |

---

## Key Architectural Decisions

See [`docs/decisions-2026.md`](docs/decisions-2026.md) for full log.

| Decision | Chosen approach |
|----------|----------------|
| Translation pipeline | Single-call (whole file in one API call), not block-by-block |
| Polish pipeline | Single-call, separate from translation |
| Aligner Classic | `FASubtitleAligner`; `llm_threshold=0`; fully mechanical; no API calls |
| Aligner Double | `FASubtitleAligner`; `llm_threshold=0`; fully mechanical; no API calls |
| Three-file output | TranslatePolish + Classic + Double; sequential browser downloads 0/1500/3000 ms |
| Split section visibility | Hidden when Persian + chatgpt-polish (aligner handles distribution) |
| Frontend–backend comms | Polling: POST `/upload` → jobId → GET `/status/:id` every 4 s |
| Job store | In-memory dict in `local_launcher.py`; one `filename` per job (phase 7 collapsed multi-file output to one); no persistence |
| Lang code convention | ISO 639-2/B in filenames; `_LANG_ALPHA3B` dict in `local_launcher.py` |
| Prompt file naming | `{action}_{LANG_CODE}.txt` — e.g., `translate_PER.txt`, `polish_PER.txt` |
| Java/Kotlin migration | Not recommended — API latency is bottleneck; python-docx has no Java equivalent |

---

## Important Terminology

| Term | Meaning |
|------|---------|
| `_PER_Polish` | Output of chatgpt-polish (translate + polish; phase 5 renamed from `_PER_TranslatePolish`) |
| `_Double_Lines` | Suffix appended when Persian Double Lines Split Method is selected (phase 6) |
| `Persian Double Lines` | Split Method that runs the FA mechanical aligner over the engine's translated docx (default for FA target) |
| `chatgpt-polish` | Engine name for translate + polish (no longer runs the aligner since phase 1) |
| `bridge row` | Table row to skip in aligner (timecodes, speaker tags, empty FA) |
| `llm_threshold` | Groups with score *below* this go to LLM. Currently 0 = all mechanical |
| `splitSection` | HTML wrapper div for Split controls — hidden for Persian+chatgpt-polish |
| `_normalize_lang()` | Internal lang normalizer — read-only |
| `_prompt_lang_code()` | Maps normalized lang to prompt filename suffix (e.g. `fa` → `PER`) |
| single-call mode | Entire file translated in one API request (vs. block-by-block) |

---

## Known Recurring Issues

See [`docs/error-catalog.md`](docs/error-catalog.md) for full list.

| ID | Issue | Status |
|----|-------|--------|
| E1 | Splitter fallback model was `gpt-5_5-2026-04-23` (underscore) → 404 error | **Fixed** 2026-05-07 |
| E2 | `engineSelector` TDZ crash in `index.ejs` when `engineChecker()` called before declaration | **Fixed** |
| E3 | Output filename had timestamp prefix from upload (`1778036666789-file.docx`) | **Fixed** via `_strip_timestamp()` |
| E4 | `_PER_Double.docx` created on disk but never served for download | **Fixed** via `_find_double_file()` + `filename2` in job |
| E5 | Polisher `⟨⟨N⟩⟩` tag parser — 4 fallback strategies needed | **Active** — works, monitor edge cases |
| E6 | `splitting.py` `cached_tokens: 0` — prompt cache not applied | **Fixed** 2026-05-07 |
| E8 | Split Method (OpenAI API) conflicted with Aligner — massive redundant API calls | **Fixed** 2026-05-08 — Split section hidden for Persian+chatgpt-polish |
| E9 | Only 1 of 3 files downloaded — Chrome blocks multiple file downloads without permission | **Mitigated** — delays increased to 1500/3000ms; user must Allow once in Chrome |
| E10 | Persian text rendered mirrored/reversed in Word — `<w:bidi/>` / `<w:rtl/>` missing on rebuilt cells | **Fixed** 2026-05-08 (Phase 1) — `_ensure_rtl_paragraph` + `_ensure_rtl_run` in `aligner_per.py` |
| E11 | Polisher could return source English verbatim → English residue rows in final FA output | **Fixed** 2026-05-08 (Phase 1) — `_detect_en_residue` falls back to translator output, logs flagged indices |
| E12 | `local_launcher.py` accepted any payload as DOCX (client-side magic bytes only) | **Fixed** 2026-05-08 (Phase 1) — `_validate_docx_payload` (PK header + 50 MB zip-bomb cap) before disk write |
| E13 | Multi-file download blocked by Chrome — required user click "Allow" | **Fixed** 2026-05-08 (Phase 2) — single `/download-zip/:jobId` endpoint bundles all outputs |
| E14 | Job store grew unbounded across long sessions | **Fixed** 2026-05-08 (Phase 2) — `start_cleanup_thread` prunes finished jobs >1 h old every 10 min |
| E15 | Transient OpenAI errors (rate-limit, network) caused full pipeline fail | **Fixed** 2026-05-08 (Phase 2) — shared `call_with_retry` helper with 3 attempts and exponential backoff |
| F-001 | `engines/_base.py` Engine Protocol declared pre-F1 `(self, source_text, src_lang_name, dest_lang_name)` shape; mismatch with `(ctx, text)` callers | **Fixed** 2026-05-08 — Protocol rewritten to post-F1 shape |
| F-007 | `engines/google.py` called non-existent `str.unescape` method (would `AttributeError`) | **Fixed** 2026-05-08 — `html.unescape` instead |
| F-010 | `engines/deepl.py` `regex_still_translating_str = '$Translation'` — `$` is end-of-string, never matches | **Deferred** — flipping changes wait-loop semantics; needs dedicated session |
| F-012 | ~44 entry-script functions in `src/machine-translate-docx.py` still read module-level globals; F1.6 only threaded `main()` + leaves | **Deferred (Phase H)** — out of audit's trivial-fix budget |
| F-013 | `local_launcher.py` `_process_job` printed `▶ ✓ ✗ —` → `UnicodeEncodeError` on Windows `cp1252` console | **Fixed** 2026-05-09 — `sys.stdout.reconfigure(encoding="utf-8")` at startup |

---

## Recent Important Changes (last 30 days)

| Date | Change |
|------|--------|
| 2026-05-16 | **Cache refactor + Sprint D-C partial + P2/P3 hygiene + matrix smoke** (`refactor/cli-py-sprint-d-final` second pass, 7 commits, NOT merged to master yet). Phase 1: raw-cache refactor in `local_launcher.py` — `_cache_key` drops `split_engine`, B1-guard generalised to all `_API_ENGINES` + all langs, new `_apply_basic_split` method routes basic/openai/null splits through a CLI `--splitonly` subprocess with `MTD_SKIP_STATS_BROWSER=1`, reordered `_process_job` so cache_store runs BEFORE `_apply_splitter`. Cache replay for same-bytes + different-splitter: ~10-30 s (was ~5 min full re-translate). Two drive-by CLI fixes (translate_docx splitonly guard, create_webdriver splitonly bypass) made the spec command end-to-end-functional. Phase 2 partial: removed 3 verified-dead `setattr` calls from `_sync_globals_from_ctx` (OpenAI handles after `write_translation_log` extraction); full bridge deletion deferred (176 occurrences in 41 names — ~6 h focused work). Phase 3: 4 P2 + 1 P3 cleanups (fd leak fix, traceback to stderr, Telegram token masking, `strip_prompts` flag in translation_log_writer, `not foo == True` simplification). Phase 4: real multi-engine matrix smoke — 9/9 cases PASS (chatgpt-api / chatgpt-polish / google / deepl × fa / vi, all with valid translations, C13 intact, correct engine suffix). Full handoff in `docs/session-state-2026-05-16-cache-d-c-p2.md`. |
| 2026-05-16 | **Sprint D final — cli.py shrink continuation** (`refactor/cli-py-sprint-d-final`, 4 commits, NOT merged to master yet). cli.py 3,947 → 2,670 lines (-1,277, -32.4 %). Combined with the prior 3-phase shrink, cli.py is down 1,725 lines from its 2026-05-15 peak (-39.3 %). Commits: `260a351` (Phase 1 pre-extract fixup — `service = Service()` ordering in `run_statistics`), `69bb2c5` (Phase 2 D-A.4 — `run_statistics` → `statistics.py` with native `MTD_SKIP_STATS_BROWSER` env-var guard), `0bcbdfd` (Phase 3 D-A.5 — `get_robot_usage_comment` → `statistics.py`), `468e11e` (Phase 4 D-B — 10 Google file-mode functions → new `engines/google_file_modes.py`, 3 dispatchers re-exported via `engines/__init__.py`; `sys.exit(7)` → `raise TranslationFailure(reason="google_file_mode_error")` per P2 audit). Phase 5 (`_sync_globals_from_ctx` collapse) **DEFERRED** — audit found 176 bare-name occurrences across 41 mirrored names; deferred to a follow-up session for safety per "better partial than broken" discipline. Full handoff in `docs/session-state-2026-05-16-sprint-d-complete.md`. Tests: 239 pytest pass on every commit; smoke `chatgpt-polish FA` green with C13 cols 0+1 byte-identical. Latent bug surfaced (not fixed): `end_time` / `elapsed_time` bare-name reads in `run_statistics` / `get_robot_usage_comment` raise `NameError` (caught by outer except) — the stats form has been silently broken on the chatgpt-API path for the lifetime of C25; preserved verbatim. |
| 2026-05-16 | **cli.py 3-phase shrink** (`refactor/cli-py-3-phase-shrink`, 5 commits). cli.py 4,395 → 3,994 lines (-401, -9.1%). New modules: `network_utils.py`, `docx_io/metadata.py`, `translation_log_writer.py`. Functions moved into existing modules: `deepl_double_linefeed_between_phrases` (deepl.py), `delete_paragraph` (cells.py). Nine orphan functions deleted (`lineno`, `reverse_string`, `remove_span_tag`, `create_translation_split_prompts` + `print_prompt_block`, `print_html_program_result`, `generate_tmx_file`, `linux_distribution`, `print_os_info`, `getDownLoadedFileNameChrome`). Bonus: fixed pre-existing snapshot-ordering bug where `oai_translator` / `oai_polisher` / `translation_log` were declared AFTER the first runtime `_get_ctx()` call (benign in production thanks to `_sync_globals_from_ctx`, but identity probes now pass from import time). Verified: 154 pytest pass; six-way parallel smoke test (chatgpt-api / chatgpt-polish / google × fa / fr) all green. Remaining work captured in [`docs/cli-shrink-phase3-handoff.md`](docs/cli-shrink-phase3-handoff.md). |
| 2026-05-09 | **Repo housekeeping** — three merged backup branches archived as `archive/*` tags then deleted (`audit/post-refactor`, `refactor/architecture`, `feature/v2-frontend`); two empty branches (`review-rewrite-opus-4.7`, `claude/romantic-bhabha-a3ad61`) deleted local + remote. Origin now has master only. |
| 2026-05-09 | **English-only docs** — `CHANGELOG.md` rewritten in English (1316 → ~480 lines, newest-first); `docs/v2-frontend-hardening.md` translated. Memory rule `feedback_docs_english_only.md` added. |
| 2026-05-09 | **Maintainability sweep** — 107 bare `except:` → `except Exception:` across 5 files; three unguarded `input()` calls now respect `silent` flag (CAPTCHA prompt raises in silent, save retries sleep+retry); `.editorconfig` added (LF, UTF-8, indents per filetype). |
| 2026-05-09 | **Auto-commit + auto-doc rule** — memory rule `feedback_auto_commit_and_doc.md`: every change → commit current branch + CHANGELOG.md update + push, in the same flow. Default branch is master. |
| 2026-05-09 | **Phase H bridge — `_sync_globals_from_ctx`:** mirrors `ctx.docx.*` (and `ctx.browser.driver`, `ctx.openai.translator/polisher`, `dest_lang`, `src_lang`) onto the module so the ~40 helpers that still read by bare name see populated state. Wired into main() at four pipeline boundaries (after read, after create_webdriver, after translate_docx, after document_split_phrases). Adds `xtm = None` module-level + `global xtm` declaration in `initialize_translation_memory_xlsx`. |
| 2026-05-09 | **Phase H — selenium driver seeds:** five Selenium-touching helpers now seed `driver = ctx.browser.driver` at the top so reassign branches don't trigger UnboundLocalError on prior reads (`selenium_chrome_google_translate_text_file/html_javascript_file/xlsx_file`, `get_translation_and_replace_after`, `run_statistics`). Reassign sites mirror the new handle back to `ctx.browser.driver`. |
| 2026-05-09 | **Phase H — non-split write path decoupled:** `print_console_docx_file_translated` now writes the translated cell whenever `ctx.docx.to_text_by_phrase_separator_table[row_n]` is non-empty, regardless of `translation_result_phrase_array` shape. Closed the silent failure mode where an empty `phrase_array` (because document_split_phrases skipped the row) left the cell unwritten. |
| 2026-05-09 | **Phase H — translate_docx + cell helpers threaded:** `translate_docx`, `cell_set_1st_paragraph`, `cell_add_paragraph`, `print_console_docx_file_translated` now take `ctx`. Three writes that hit the empty global `table_cells` are redirected to `ctx.docx.table_cells`. |
| 2026-05-09 | **Phase H — `docxfile_table_number_of_phrases` increment threaded:** `generate_html_file_from_phrases_for_google_translate_javascript` now uses `ctx.docx.docxfile_table_number_of_phrases += 1` instead of the bare-name read-then-write that would `UnboundLocalError`. |
| 2026-05-09 | **Progress UX fixes:** loading overlay hidden BEFORE `showAlert(...)` so error dialogs no longer have the bar animating behind them. PROGRESS:15/30/50/75/90 markers added to the Google-javascript paragraph loop (previously 10→100 jump). PROGRESS:90 emitted at the start of `save_docx_file` to fill the gap for DeepL/Perplexity engines that finish at runner's PROGRESS:75 and otherwise jump straight to 100. `subprocess.Popen` for the backend now uses `bufsize=1` (line-buffered) so PROGRESS markers reach the launcher in real time. |
| 2026-05-09 | **Master consolidation:** merged `audit/post-refactor` (Phases A-G4 + 12 audit fixes) and `feature/v2-frontend` (Claude-inspired UI v2 + cache + i18n) into master. F-013 fix applied (UTF-8 stdout reconfigure). 51 unit tests passing. Both UIs live: legacy at `/`, v2 at `/v2/`. |
| 2026-05-08 | **Audit (`audit/post-refactor`):** 15 findings — F-001 Engine Protocol resync, F-005-F-011 dead-code/unused-import sweeps in google.py + deepl.py, F-007 `html.unescape` fix; F-010 `$Translation` regex deferred; F-012 entry-script middle-layer threading deferred (Phase H). Smoke test: 36 passed |
| 2026-05-08 | **Phase G (`refactor/architecture`):** extract `selenium_utils/` (G1), `engines/google.py` (G2), `engines/deepl.py` (G3), `runner.py` (G4) |
| 2026-05-08 | **Phase F1.1-F1.6:** thread `RuntimeContext` (`ctx`) through configuration, DOCX I/O, engine dispatch, active engine bodies, `main()` |
| 2026-05-08 | **Phase E:** extract `engines/chatgpt_api.py` + `engines/__init__.py` registry scaffolding |
| 2026-05-08 | **Phase D:** isolate inactive Selenium engines under `engines/inactive/` |
| 2026-05-08 | **Phase C:** introduce `RuntimeContext` dataclass (foundation for F1) |
| 2026-05-08 | **Phase B:** extract `src/config.py` — module-level constants and parallel arrays |
| 2026-05-08 | **Phase A:** remove Yandex + Perplexity-API + dead code |
| 2026-05-09 | **v2 frontend (`feature/v2-frontend`):** Claude-inspired SPA at `web/v2/`. Tailwind 3.4 (compiled, not CDN), Alpine.js, drag-and-drop, 36-h cache, newsletter, i18n EN/FA, Playwright e2e. Legacy `/` preserved. |
| 2026-05-08 | **Phase 5 (review-rewrite-opus-4.7):** `prompt_hash` (sha256[:8]) recorded in translator/polisher last_call_data and aligner last_stats; progress bar + virastar skipped (out of scope / no PyPI package) |
| 2026-05-08 | **Phase 4 (review-rewrite-opus-4.7):** 10 unit tests + pytest setup (`tests/`); DB connection guarded by `MARIADB_HOST` env; concurrent job semaphore (default 2, override via `MTD_MAX_CONCURRENT_JOBS`) |
| 2026-05-08 | **Phase 3 (review-rewrite-opus-4.7):** `_display_len` (ZWNJ-aware) for all MAX_CHARS validation; sentinel-separated cross-group triple guard; per-content-type break ratio in `_split_distinct` |
| 2026-05-08 | **Phase 2 (review-rewrite-opus-4.7):** ZIP download endpoint + frontend single-download; job cleanup thread (10 min interval, 1 h max age); shared `call_with_retry` for transient OpenAI errors |
| 2026-05-08 | **Phase 1 (review-rewrite-opus-4.7):** RTL/bidi fix in aligner; English-residue fallback in polisher; server-side magic-bytes + 50 MB zip-bomb validation in launcher |
| 2026-05-08 | `llm_threshold=0` for BOTH Classic and Double aligners — fully mechanical, zero API calls |
| 2026-05-08 | Three-file download: `_PER_Classic.docx` added as `filename3`; `_find_classic_file()` in launcher |
| 2026-05-08 | Split section hidden for Persian+chatgpt-polish — eliminates Split/Aligner conflict |
| 2026-05-08 | Download delays: 800/1600ms → 1500/3000ms for Chrome multi-file permission |
| 2026-05-08 | `engineChecker()` now also fires on engine dropdown change |
| 2026-05-07 | Aligner v2: 11 legacy techniques injected into `aligner_per.py` (see decisions-2026.md) |
| 2026-05-07 | `llm_threshold` 70 → 90 (superseded by 2026-05-08 change above) |
| 2026-05-07 | Two-file download: `_PER_Double.docx` now served alongside main output |
| 2026-05-07 | `prompt_cache_retention: 24h` added to `splitting.py` |
| 2026-05-07 | Splitter fallback model fixed: `gpt-5_5-2026-04-23` → `gpt-5.5` |
| 2026-05-07 | Prompt files renamed `_fa` → `_PER` across all modules |
| 2026-05-07 | Aligner output renamed `_aligned` → `_PER_Double` |
| 2026-05-07 | UI: `chatgpt-polish` auto-selected + enabled only for Persian |
| 2026-05-07 | `local_launcher.py`: `_LANG_ALPHA3B` map, `_strip_timestamp()`, real backend fixes |
| 2026-05-07 | JS TDZ fix in `index.ejs` `engineChecker()` |
| Earlier | Default model upgraded to `gpt-5.5` (translator + polisher) |
| Earlier | `reasoning_effort` removed from translator (94 % token overhead) |
| Earlier | `{N}` moved from system prompt to user message (prompt cache compatibility) |
| Earlier | File collision protection (`_1`, `_2` suffix) |
| Earlier | Polling architecture: `/upload` → jobId → `/status/:id` |

---

## Quick Links

- Full architecture: [`docs/architecture.md`](docs/architecture.md)
- Translation quality rules: [`docs/translation-style.md`](docs/translation-style.md)
- Aligner algorithm: [`docs/subtitle-syncing.md`](docs/subtitle-syncing.md)
- All bugs: [`docs/error-catalog.md`](docs/error-catalog.md)
- All decisions: [`docs/decisions-2026.md`](docs/decisions-2026.md)
- Add feature: [`docs/playbooks/add-feature.md`](docs/playbooks/add-feature.md)
- Fix bug: [`docs/playbooks/fix-bug.md`](docs/playbooks/fix-bug.md)
