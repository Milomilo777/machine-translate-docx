# CLAUDE.md — Machine Translate DOCX

> Router file. Keep it short. Heavy details live in `docs/`.

---

## Project Purpose

Translate DOCX files (broadcast Persian TV subtitles and general documents)
using DeepL, Google, or OpenAI (default `gpt-5.5`). The Persian pipeline
adds a second pass: a subtitle aligner that produces a bilingual
double-line `.docx`.

---

## High-Level Architecture

```
                ┌─ index.ejs            (legacy UI, served at /)
frontend ──────┤
                ├─ web/v2/index.html    (v2 SPA, served at /v2/)
                └─ web/v2/redesign.html (claude-palette redesign — preview)
                          │
                          ▼  POST /upload
              local_launcher.py
                  │
                  ▼  python -m machine_translate_docx.cli
              src/machine_translate_docx/cli.py  ──┐
                                                   ▼
                  ┌─ runtime.py        (RuntimeContext dataclass)
                  ├─ config.py         (constants + VALID_AI_MODELS)
                  ├─ runner.py         (block-loop orchestrator)
                  ├─ log_paths.py      (Log json file/ resolver + retention)
                  ├─ docx_io/          (parse, cells, runs, save)
                  ├─ engines/          (google, deepl, chatgpt_api)
                  ├─ selenium_utils/   (driver, click, forms)
                  └─ openai_tools/     (translator, polisher, …)

  Distributable .exe path (2026-05-14):
              packaging/mtd_entry.py
                  │
                  ▼  PyInstaller bundles entry + prompts/ + deps
              dist/mtd/mtd.exe  ──► same cli.main(), runs without
                                    Python / Chrome / MariaDB / hazm
```

See [`docs/architecture.md`](docs/architecture.md) and the SVG
diagrams in [`docs/diagrams/`](docs/diagrams/) for the full picture.

---

## Key Paths (post-2026-05-11 src/ layout migration)

| Path | Role |
|------|------|
| `src/machine_translate_docx/cli.py` | CLI entry point — orchestrator (was `src/machine_translate_docx.py`) |
| `src/machine_translate_docx/runtime.py` | `RuntimeContext` dataclass — threaded through engines |
| `src/machine_translate_docx/config.py` | `DEFAULT_AI_MODEL`, `VALID_AI_MODELS`, language tables |
| `src/machine_translate_docx/runner.py` | Block-loop orchestrator |
| `src/machine_translate_docx/dispatch.py` | `set_translation_function(ctx)` |
| `src/machine_translate_docx/exceptions.py` | `TranslationFailure` hierarchy |
| `src/machine_translate_docx/translation_health.py` | `assert_source_has_content`, `assert_translation_present` |
| `src/machine_translate_docx/network_utils.py` | Startup-time region / connectivity / driver-mirror helpers (extracted 2026-05-16) |
| `src/machine_translate_docx/translation_log_writer.py` | JSON sidecar writer for the OpenAI translation/polish log (extracted 2026-05-16) |
| `src/machine_translate_docx/docx_io/` | parse, cells (incl. `delete_paragraph`), runs, save, metadata |
| `src/machine_translate_docx/docx_io/metadata.py` | Output-side DOCX metadata writers — language label + history comment (extracted 2026-05-16) |
| `src/machine_translate_docx/engines/google.py` | Selenium-based Google Translate engine |
| `src/machine_translate_docx/engines/deepl.py` | Selenium-based DeepL engine (incl. `deepl_double_linefeed_between_phrases`) |
| `src/machine_translate_docx/engines/chatgpt_api.py` | OpenAI API engine bridge |
| `src/machine_translate_docx/engines/inactive/` | Disabled web engines (perplexity_web, etc.) |
| `src/machine_translate_docx/selenium_utils/` | Driver/click/forms helpers |
| `src/machine_translate_docx/openai_tools/translator.py` | `OpenAITranslator` — single-call translate |
| `src/machine_translate_docx/openai_tools/polisher.py` | `OpenAIPolisher` — single-call polish |
| `src/machine_translate_docx/openai_tools/persian_double_lines.py` | `FASubtitleAligner` — bilingual doubling |
| `src/machine_translate_docx/openai_tools/splitting.py` | Legacy per-phrase splitter (only when splitTranslate=true) |
| `src/machine_translate_docx/openai_tools/fa_postprocess.py` | Safe FA character normaliser (3 mappings) |
| `local_launcher.py` | Local dev server (Python, no Node required) — serves both UIs |
| `server.js` | Express server (Node.js production server) |
| `index.ejs` | **Legacy** frontend — EJS template, served at `/` |
| `web/v2/index.html` | **v2** frontend — plain JS SPA, served at `/v2/` |
| `web/v2/app.js` | Plain-JS app for v2 |
| `web/v2/content.json` | Announcements + stories (single source of truth for v2 UI copy) |
| `web/v2/redesign.html` | **Claude-palette redesign preview** — single-file drop-in (2026-05-16). Includes a header v1↔v2 pill switcher (persisted to `localStorage.mtd.uiPref`), full anti-indexing meta block, country-flag from IP, and the legacy index.ejs wiring ported into a single-screen layout. Hits the same `/upload`, `/status/:id`, `/download/:name`, `/cancel/:id`, `/count`, `/robotscount` endpoints. Needs `GET /history` (TODO #1 in `docs/v2-backend-todo.md`) to drive the Recent runs panel with real data. |
| `prompts/translate_PER.txt` | Persian translation system prompt |
| `prompts/polish_PER.txt` | Persian polish system prompt |
| `prompts/translate_universal.txt` | Fallback prompt for other languages |
| `packaging/mtd_entry.py` | PyInstaller wrapper that sets `MTD_FROZEN_ROOT` |
| `packaging/mtd.spec` | PyInstaller config (onedir, ~65 MB output) |
| `packaging/README.md` | Clean-venv build instructions |
| `src/machine_translate_docx/log_paths.py` | Central `Log json file/` resolver + 10-day retention; honours `MTD_FROZEN_ROOT` |

---

## Critical Commands

```bash
# Start local dev server — serves BOTH UIs (legacy + v2)
E:\Python311\python.exe local_launcher.py
"run_local_launcher_v2.bat"

# Legacy UI:        http://127.0.0.1:3000/
# v2 UI (current):  http://127.0.0.1:3000/v2/
# v2 redesign:      http://127.0.0.1:3000/v2/redesign.html

# Run the CLI directly (post-migration; sets PYTHONPATH on the fly)
PYTHONPATH=src E:\Python311\python.exe -m machine_translate_docx.cli \
    --docxfile file.docx --destlang fa \
    --engine chatgpt --enginemethod api --aimodel gpt-5.4-mini \
    --with-polish --silent --exitonsuccess

# After `pip install -e .`, the same CLI is reachable as `mtd …`
# (entry-point declared in pyproject.toml).

# Build a standalone Windows .exe for distribution (CLI only, OpenAI API
# path only). Onedir output is ship-ready: zip dist/mtd/ and send it.
# See packaging/README.md for the clean-venv setup that keeps the build
# at ~65 MB instead of 1.2 GB.
python -m venv .venv-build && .venv-build/Scripts/python.exe -m pip install \
    pyinstaller openai python-docx lxml requests tiktoken openpyxl \
    beautifulsoup4 json5 regex pyyaml python-bidi chardet clipboard \
    langcodes progressbar2 psutil screeninfo selenium pywin32 \
    newmm-tokenizer tinysegmenter httpx certifi
.venv-build/Scripts/python.exe -m PyInstaller packaging/mtd.spec --clean --noconfirm
# Output: dist/mtd/mtd.exe

# Run pytest (154 tests, ~2 s) — `live` marker is deselected by default
E:\Python311\python.exe -m pytest tests/ --ignore=tests/test_v2_e2e.py
```

---

## Output Naming Convention

One file per job. Filenames are `{stem}_{LANG}{_engine}{_Double_Lines?}.docx`.
The engine tag is `_Polish` / `_chatGPT` / `_Google` / `_Deepl`. The
`_Double_Lines` suffix is appended when the user picks Persian Double
Lines as the Split Method (FA target only).

| Engine + split                        | Output                                  |
|---------------------------------------|-----------------------------------------|
| chatgpt-polish + basic                | `{stem}_PER_Polish.docx`                |
| chatgpt-polish + persian_double_lines | `{stem}_PER_Polish_Double_Lines.docx`   |
| chatgpt + persian_double_lines        | `{stem}_PER_chatGPT_Double_Lines.docx`  |
| google                                | `{stem}_{LANG}_Google.docx`             |

Every chatgpt-polish run also writes `{stem}_PER_Polish_log.json`
next to the docx (token counts, cached counts, cost, elapsed).
DeepL / Google runs write a minimal sidecar with row counts only.

---

## Core Conventions

- **Models**: translator + polisher default to `config.DEFAULT_AI_MODEL`
  (`gpt-5.5`); aligner is **always** `config.ALIGNER_MODEL`
  (`gpt-5.4-mini`, hardcoded, do not change).
- **Whitelist**: CLI rejects `--aimodel <unknown>` at parse time
  (`config.VALID_AI_MODELS`).
- **Prompt cache**: every API call sets
  `extra_body={"prompt_cache_retention": "24h"}`.
- **Lang codes**: output filenames use ISO 639-2/B (`fa`→`PER`,
  `ar`→`ARA`, `de`→`GER`).
- **`_normalize_lang()`** is read-only; for prompt-file lookup use
  `_prompt_lang_code()` instead.
- `reasoning_effort` is active in polisher **only** when `"mini"` is
  in the model name; **never** set it on the translator (caused
  94% reasoning-token overhead in testing).
- File collisions get `_1`, `_2` suffixes — never overwrite.

---

## Runtime environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — | Required for any chatgpt / chatgpt-polish run |
| `MTD_MAX_CONCURRENT_JOBS` | `2` | Cap on simultaneous backend subprocesses. Each subprocess loads python-docx + openai client + tiktoken (~250-500 MB). A third upload while two are running gets `status='queued'` and waits at the semaphore until a slot frees. The frontend surfaces this as a Persian wait message ("در صف انتظار…") and resumes automatically. Raise at your own risk if you have RAM headroom. |
| `MTD_SKIP_STATS_BROWSER` | unset | When `=1`, `statistics.run_statistics` / `get_robot_usage_comment` early-return — saves a Chrome launch on the basic-split spawn (~22 s → ~8 s). |
| `MTD_DEBUG_PAYLOADS` | unset | When `=1`, full user_message + response JSON are echoed to stdout. Default mode logs only a redacted summary so subtitle content does not leak into archived logs / Telegram failure alerts. |
| `MTD_LOG_VERBOSE` | unset | When `=1`, the per-run sidecar JSON keeps `system_prompt`, `user_prompt`, and `response_raw` instead of dropping them. Multiplies log size; use only for one-off debug. |
| `MTD_VALIDATOR_ENABLED` | unset | When `=1`, the post-translate / post-polish validators run and log their findings. Off by default — validators are diagnostic, never reject output. |
| `MTD_POLISH_REASONING` | model-default | One of `none / low / medium / high / xhigh`. Overrides the per-model default in `polisher.py`. `mini` defaults to `medium`; non-mini defaults to `none`. Lowering speeds polish ~3× at some quality cost. |
| `MTD_FROZEN_ROOT` | unset | Set by the PyInstaller wrapper. Points to the bundled `prompts/` directory beside the .exe. Lets a packaged user drop a customised prompts directory next to the binary without rebuilding. |
| `MTD_TELEGRAM_TOKEN` + `MTD_TELEGRAM_CHAT_ID` | unset | When both set, every Saturday at 12:00 in `MTD_SCHEDULER_TZ` (default `Europe/Paris`) the launcher uploads `subscribers.txt` as a Telegram document. |

---

## Safety Constraints

- Never commit `.env`, API keys, or
  `src/configuration/configuration.json` if it contains secrets.
- Never change the aligner model — it must stay `gpt-5.4-mini`.
- Never add `reasoning_effort` to the translator.
- `_normalize_lang()` must not be modified — only `_prompt_lang_code()`
  maps prompt filenames.
- The full invariant list (C1–C31) lives in
  [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md).

---

## Anti-indexing posture (added 2026-05-16)

The tool is private — every frontend page must stay out of every search
index. `web/v2/redesign.html` ships a comprehensive `<meta name="robots">`
block targeting googlebot / bingbot / yandex / baidu / duckduckbot /
slurp + `referrer: no-referrer` + `Cache-Control: no-store`. Legacy
`index.ejs` and current `web/v2/index.html` already had the basic
`noindex, nofollow` meta. To complete coverage **server-side** add:

1. `GET /robots.txt` → `User-agent: *\nDisallow: /\n`
2. `X-Robots-Tag: noindex, nofollow, noarchive, nosnippet, noimageindex`
   on every launcher response (including `/download/*`).

Details + code snippet for `local_launcher.py` in
[`docs/v2-backend-todo.md`](docs/v2-backend-todo.md) §TODO #2.

---

## Deeper Docs

- [`docs/index.md`](docs/index.md) — hub for every other doc.
- [`docs/architecture.md`](docs/architecture.md) — full pipeline, data flow.
- [`docs/diagrams/`](docs/diagrams/) — SVG architecture diagrams
  (light + dark themes, embedded in `README.md`).
- [`docs/translation-style.md`](docs/translation-style.md) — Persian
  broadcast quality rules.
- [`docs/subtitle-syncing.md`](docs/subtitle-syncing.md) — aligner
  algorithm + thresholds.
- [`docs/telegram-alerts-setup.md`](docs/telegram-alerts-setup.md) —
  Telegram failure-alert setup + security.
- [`docs/testing.md`](docs/testing.md) — how to test locally.
- [`docs/error-catalog.md`](docs/error-catalog.md) — known bugs.
- [`docs/decisions-2026.md`](docs/decisions-2026.md) — architectural
  decisions log.
- [`docs/audit-2026-05-11.md`](docs/audit-2026-05-11.md) — the
  comprehensive 2026-05-11 audit + applied fixes.
- [`docs/cli-shrink-phase3-handoff.md`](docs/cli-shrink-phase3-handoff.md)
  — handoff prompt for the remaining cli.py shrink work (statistics
  cluster, Google file-mode workers, `_sync_globals_from_ctx`
  collapse). Authored 2026-05-16 after phases 1–3 of the shrink landed.
- [`docs/v2-future-ideas.md`](docs/v2-future-ideas.md) — tier-1..4
  backlog for the v2 SPA with 3-axis cost scoring.
- [`docs/v2-improvements.md`](docs/v2-improvements.md) — **NEW**
  (2026-05-16). Twelve design proposals for the v2 SPA, impact-vs-effort
  matrix, and the v1↔v2 version-switcher spec with drop-in code.
- [`docs/v2-backend-todo.md`](docs/v2-backend-todo.md) — **NEW**
  (2026-05-16). Endpoints the redesigned v2 frontend already calls but
  that the launcher does not yet implement: `GET /history?limit=N`
  (Recent runs panel), plus the server-side anti-indexing reinforcement
  (`/robots.txt` + `X-Robots-Tag` header).
- [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md) — active constraints C1–C31,
  recent changes.
- [`web/v2/README.md`](web/v2/README.md) — v2 frontend stack, deploy,
  file map.

## Announcement surfaces (C21)

The v2 SPA renders four content surfaces, all driven exclusively by
[`web/v2/content.json`](web/v2/content.json). Editing this one file
is the **only** way to change what visitors see:

| Slot | Where it appears |
|---|---|
| `pinned` | Single sticky banner at the very top of the page |
| `modal`  | One-time welcome dialog (per `id`) |
| `announcements` | Left column list |
| `stories` | Centre column tile grid |

Each `id` drives dismissal persistence — bumping it re-shows the
surface to every visitor. Set any slot to `null` to hide it.

(The `redesign.html` preview at `web/v2/redesign.html` reads its
announcement content from `index.ejs` instead of `content.json` —
see TODO in `docs/v2-improvements.md` for migrating it to the
same content.json pipeline when the redesign goes live.)

## Weekly newsletter export (C22)

When `MTD_TELEGRAM_TOKEN` + `MTD_TELEGRAM_CHAT_ID` are set, every
Saturday at 12:00 in `MTD_SCHEDULER_TZ` (default `Europe/Paris`)
the launcher uploads `subscribers.txt` as a Telegram document.
State persists at `runtime_dir/subscribers_report_state.json`;
the next launcher boot prints a one-line warning if last week's
attempt failed. Empty subscribers file → silent skip.

## v2 version switcher (C23, added 2026-05-16)

The `web/v2/redesign.html` page exposes a pill toggle in the header
that flips between the legacy UI (`/`) and the modern v2 UI (`/v2/`).
The user's choice is persisted to `localStorage.mtd.uiPref` and
applied as a redirect on subsequent visits. To make it bidirectional,
add the same switcher markup + script to `index.ejs` — code snippet
is in `docs/v2-improvements.md` §0.
