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
                ┌─ index.ejs        (legacy UI, served at /)
frontend ──────┤
                └─ web/v2/index.html  (v2 SPA, served at /v2/)
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
                  ├─ docx_io/          (parse, cells, runs, save)
                  ├─ engines/          (google, deepl, chatgpt_api)
                  ├─ selenium_utils/   (driver, click, forms)
                  └─ openai_tools/     (translator, polisher, …)
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
| `src/machine_translate_docx/docx_io/` | parse, cells, runs, save (every docx-shaped operation) |
| `src/machine_translate_docx/engines/google.py` | Selenium-based Google Translate engine |
| `src/machine_translate_docx/engines/deepl.py` | Selenium-based DeepL engine |
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
| `prompts/translate_PER.txt` | Persian translation system prompt |
| `prompts/polish_PER.txt` | Persian polish system prompt |
| `prompts/translate_universal.txt` | Fallback prompt for other languages |

---

## Critical Commands

```bash
# Start local dev server — serves BOTH UIs (legacy + v2)
E:\Python311\python.exe local_launcher.py
"run_local_launcher_v2.bat"

# Legacy UI: http://127.0.0.1:3000/
# v2 UI:     http://127.0.0.1:3000/v2/

# Run the CLI directly (post-migration; sets PYTHONPATH on the fly)
PYTHONPATH=src E:\Python311\python.exe -m machine_translate_docx.cli \
    --docxfile file.docx --destlang fa \
    --engine chatgpt --enginemethod api --aimodel gpt-5.4-mini \
    --with-polish --silent --exitonsuccess

# After `pip install -e .`, the same CLI is reachable as `mtd …`
# (entry-point declared in pyproject.toml).

# Run pytest (113 tests, ~2 s) — `live` marker is deselected by default
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

## Safety Constraints

- Never commit `.env`, API keys, or
  `src/configuration/configuration.json` if it contains secrets.
- Never change the aligner model — it must stay `gpt-5.4-mini`.
- Never add `reasoning_effort` to the translator.
- `_normalize_lang()` must not be modified — only `_prompt_lang_code()`
  maps prompt filenames.
- The full invariant list (C1–C20) lives in
  [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md).

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
- [`docs/v2-future-ideas.md`](docs/v2-future-ideas.md) — tier-1..4
  backlog for the v2 SPA with 3-axis cost scoring.
- [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md) — active constraints C1–C22,
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

## Weekly newsletter export (C22)

When `MTD_TELEGRAM_TOKEN` + `MTD_TELEGRAM_CHAT_ID` are set, every
Saturday at 12:00 in `MTD_SCHEDULER_TZ` (default `Europe/Paris`)
the launcher uploads `subscribers.txt` as a Telegram document.
State persists at `runtime_dir/subscribers_report_state.json`;
the next launcher boot prints a one-line warning if last week's
attempt failed. Empty subscribers file → silent skip.
