# Architecture — Machine Translate DOCX

## Full Pipeline Diagram

```
Browser (index.ejs)
   │
   │  POST /upload  (multipart: file + params)
   ▼
local_launcher.py  ──────────────────────────────────────────────────────────
   │  registers jobId (in-memory)
   │  saves upload as: uploads/{timestamp}-{filename}.docx
   │  spawns thread → _process_job()
   │
   │  GET /status/:jobId  (polled every 4 s by browser)
   │  GET /download/:filename
   │
   └─► subprocess: python -m machine_translate_docx.cli [args]   (PYTHONPATH=src)
            │
            ├─► [Google / DeepL] translator  →  output_PER_Google.docx
            │
            └─► [chatgpt-polish pipeline]
                    │
                    ├─► OpenAITranslator.translate()         ← translator.py
                    │       model: gpt-5.5
                    │       single call, whole file
                    │       extra_body: prompt_cache_retention 24h
                    │
                    ├─► OpenAIPolisher.polish()              ← polisher.py
                    │       model: gpt-5.5
                    │       single call, whole file
                    │       extra_body: prompt_cache_retention 24h
                    │       output: {stem}_PER_Polish.docx
                    │
                    └─► (optional Split Method = persian_double_lines)
                        FASubtitleAligner.align()            ← persian_double_lines.py
                            model: gpt-5.4-mini (hardcoded)
                            llm_threshold: 0
                            output: {stem}_PER_Polish_Double_Lines.docx
                            (run by local_launcher._apply_splitter,
                             not by the engine subprocess — phase 1)
```

## Component Responsibilities

### `src/machine_translate_docx/cli.py`
- CLI entry point, argparse, signal handling, `main()` orchestrator.
- Threads `ctx: RuntimeContext` through every pipeline step.
- Translator → polisher → aligner sequence.
- Emits `Saved file name: {path}` (parsed by `local_launcher.py`) and
  `PROGRESS:N` markers (parsed by the v2 frontend).

### `src/machine_translate_docx/openai_tools/translator.py`
- `OpenAITranslator` class
- Loads system prompt from `prompts/translate_{LANG}.txt`
- `_prompt_lang_code()` maps lang code to prompt file suffix (e.g. `fa` → `PER`)
- `_normalize_lang()` is read-only — do not modify
- Single API call with `prompt_cache_retention: 24h`
- Supports `gpt-5.x` (chat completions) and `o-pro` (responses API)

### `src/machine_translate_docx/openai_tools/polisher.py`
- `OpenAIPolisher` class
- Imports `_prompt_lang_code` from `translator.py`
- Uses `⟨⟨N⟩⟩` tag format for line markers
- 4-strategy parser for robust tag extraction
- `reasoning_effort: medium` only when `"mini"` in model name; non-mini defaults to `none` (downgraded from `high` 2026-05-12 — high cost ~3× wall-clock for diminishing quality gain)

### `src/machine_translate_docx/openai_tools/persian_double_lines.py`
- `FASubtitleAligner` class (the legacy `aligner_per.py` is a thin
  compatibility shim re-exporting from this module).
- Reads bilingual DOCX table (EN | FA columns)
- Mechanical pass: splits FA sentences into ≤50-char chunks, distributes as singles/doubles
- LLM pass: groups with score < `llm_threshold` sent to gpt-5.4-mini for quality review
- Bridge detection: skips grey cells, timecodes, empty FA, speaker tags
- Output: double-line bilingual DOCX

### `src/machine_translate_docx/network_utils.py` (2026-05-16)
- Startup-time helpers extracted from `cli.py`:
  - `test_internet(host, port, timeout)` — TCP probe against Google DNS,
    used as the "is the box actually online?" fallback when the config
    JSON fetch fails.
  - `fetch_country_data(url, *, http_timeout)` — region detection.
  - `check_mirror_url(url, *, http_timeout)` — driver-mirror
    reachability.
  - `set_se_driver_mirror_url_if_needed(country_name, mirror_url, *,
    restricted_countries, http_timeout)` — sets the
    `SE_DRIVER_MIRROR_URL` env var for users in restricted regions.
- Every dependency the historical bodies read from module globals is
  now an explicit keyword argument.

### `src/machine_translate_docx/translation_log_writer.py` (2026-05-16)
- `write_translation_log(ctx, log_path)` — owns the JSON sidecar
  emitted at end of run for every OpenAI engine.
- Reads `ctx.openai.translation_log` (mutated in-place by `runner.py`
  and `engines/chatgpt_api.py`), aggregates per-block tokens + cost +
  elapsed, stashes the canonical system prompts once under
  `run_info.translation_prompts` / `run_info.polish_prompts`, enriches
  `summary` with row counts and polish-touched lines, and writes the
  resulting dict to `log_path` as pretty-printed UTF-8 JSON.
- `cli.py` keeps a 2-line shim `write_translation_log(log_path)` so
  the injected callback in `docx_io/save.py` continues to see the
  historical 1-arg signature.

### `src/machine_translate_docx/statistics.py` (2026-05-16, Sprint D-A.4 + D-A.5)
- End-of-run reporting cluster — fire-and-forget helpers that never
  abort a translation. The launcher only cares about the docx +
  sidecar landing on disk, so failures here surface as a single
  "Warning failed to update stats" / "Warning failed to get
  available updates status" line and the run as a whole still
  succeeds.
- `local_time_offset(t=None)` — pure tz-offset helper (Sprint D
  attempt 1 extraction).
- `run_statistics(ctx)` — submits per-run state to the HTML stats
  form via a short-lived Chrome session. Heavy deps (selenium,
  psutil) lazy-imported inside the function body so callers of
  `local_time_offset` don't pay for them.
- `get_robot_usage_comment(ctx)` — navigates the active Selenium
  driver to the version-checker page, scrapes the rendered
  comment, and prints it. Same lazy-import shape.
- Both submission helpers honour `MTD_SKIP_STATS_BROWSER`: when
  set in the environment, the function short-circuits as the
  first statement. The cache refactor's launcher basic-split
  spawn will set this so cache-replay re-runs don't pay for a
  Chrome launch — the original translate already reported stats.
- `cli.py` keeps 3-line shims that delegate to the impl, so the
  call sites in `main()` don't need to change.

### `src/machine_translate_docx/engines/google_file_modes.py` (2026-05-16, Sprint D-B)
- Google's "file-mode" translation paths
  (`--enginemethod textfile / htmljavascript / xlsxfile`) —
  upload the whole document to translate.google.com rather than
  feeding phrases through the textarea one at a time. Rarely
  used compared to the default `singlephrase` method, but
  historically the only way to process very large docs.
- 3 top-level dispatchers:
  - `google_translate_from_text_file(ctx)`
  - `google_translate_from_html_javascript(ctx)`
  - `google_translate_from_html_xlsxfile(ctx)`
  Re-exported from `engines/__init__.py` so
  `cli.translate_docx` imports them via
  `from .engines import google_translate_from_*` cleanly.
- 7 internal helpers (3 selenium workers + 3 file generators +
  the chrome-downloads poller `get_last_downloaded_file_path`)
  — private to the module since their only callers are the
  dispatchers.
- Shares the cookies-consent helper with `engines/google.py` via
  `from .google import selenium_chrome_google_click_cookies_consent_button`.
- Lazy import of cli module globals (`xtm`, `xlsxreplacefile`,
  `from_text_table`, `src_lang`, etc.) matches the
  `docx_io/parse.py:88` pattern; selenium imports at module top
  because the whole module is selenium-only.
- Drive-by improvement (P2 from 2026-05-16 master audit):
  `sys.exit(7)` in the textfile worker's exception path is
  replaced with `raise TranslationFailure(reason=
  "google_file_mode_error", …)` so the launcher's
  structured-failure parser flips the job to `status=error`.

### `src/machine_translate_docx/docx_io/metadata.py` (2026-05-16)
- Output-side DOCX metadata writers extracted from `cli.py`:
  - `write_destination_language_in_docx_cell(docxdoc, *, splitonly,
    dest_lang_name, dest_lang)` — fills cell (1, 2) of the first
    table with the human-readable destination language name (fallback
    to ISO code); no-op when `splitonly` is True.
  - `set_docx_properties_comment_for_history(docxdoc, *,
    program_version, engine)` — stamps a one-line audit comment into
    the docx core properties.
- `cli.py` keeps zero-argument shims so the call sites in `main()`
  don't need to change.

### `local_launcher.py`
- `ThreadingHTTPServer` on configurable port (default 3000)
- Two modes: `real` (invokes actual backend) and `mock` (generates placeholder DOCX)
- `_strip_timestamp()` — removes `{13-digit-ts}-` prefix from output filename
- `_apply_splitter()` — runs the requested Split Method on the engine's
  translated docx (Persian Double Lines: in-process FA aligner)
- `_materialise_cached_output()` — cache-hit path that reuses the cached
  engine output and re-applies the requested splitter on top
- `Job` dataclass: `filename` only (one file per job after phase 7)

### `index.ejs`
- EJS template (served as plain HTML by local_launcher)
- `engineChecker()` — manages engine availability by target language
  - Persian: auto-selects `chatgpt-polish`, enables the option
  - Other languages: disables `chatgpt-polish`
- `pollJobStatus()` — returns `{ filename }`
- `triggerDownload()` — single docx download per job

## Output Files

```
uploads/
  {ts}-input.docx                    ← uploaded file (timestamped)

uploads/ (output written alongside uploads — one file per job):
  input_PER_Polish.docx                  ← chatgpt-polish, basic split (timestamp stripped)
  input_PER_Polish_Double_Lines.docx     ← chatgpt-polish + persian_double_lines split
  input_PER_Polish_log.json              ← cost/token log
```

## Prompt Files

```
prompts/
  translate_PER.txt      ← Persian translation system prompt
  polish_PER.txt         ← Persian polish system prompt
  translate_universal.txt← Fallback for other languages
```

Naming convention: `{action}_{ISO_639_2B_code}.txt`

## Legacy Component

`src/machine_translate_docx/openai_tools/splitting.py` — `OpenAISubtitleSplitter`  
Used only when `splitTranslate=true` in the UI. Makes per-phrase API calls.
Requires MariaDB. Use is discouraged; the aligner pipeline supersedes it.

## Distribution — Standalone .exe (2026-05-14)

```
packaging/mtd_entry.py
    │  sets MTD_FROZEN_ROOT = Path(sys.executable).parent
    ▼
packaging/mtd.spec   (PyInstaller, onedir, ~65 MB)
    │  collects:
    │    - prompts/                  (translate_PER, polish_PER, _smtv_locks,
    │                                 translate_universal, polish_universal)
    │    - python-docx XML templates
    │    - tiktoken BPE rank files
    │    - newmm-tokenizer Thai word list
    ▼
dist/mtd/mtd.exe   (+ _internal/ sibling)
    │
    │  At runtime:
    │    - `log_paths._find_project_root` honours MTD_FROZEN_ROOT
    │       → `Log json file/` lands next to mtd.exe
    │    - `translator._find_prompts_dir` honours MTD_FROZEN_ROOT
    │       → an override prompts/ next to mtd.exe wins,
    │         else falls back to bundled sys._MEIPASS/prompts
    │
    └─► same machine_translate_docx.cli.main() — zero behaviour drift
        from the dev-tree CLI. Only the OpenAI-API engine path is
        validated for the .exe (Google / DeepL paths still work but
        require a real Chrome + chromedriver on the user's box).

Why the OpenAI API path "just works" in the .exe:
  - `create_webdriver(ctx)` returns early for engine=chatgpt+api
    (no Chrome needed).
  - mysql.connector, hazm, undetected_chromedriver are lazy-loaded
    or wrapped in try/except with passthrough fallbacks.
  - The dev shell still sees the full feature set; only the
    .exe-friendly subset avoids the optional deps.

Build instructions: see `packaging/README.md`. Constraints C24-C26.
