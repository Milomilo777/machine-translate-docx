# CLAUDE.md — Machine Translate DOCX

> Router file. Keep it short. Heavy details live in `docs/`.

---

## Project Purpose

Translate DOCX files (broadcast Persian TV subtitles and general documents) using
OpenAI (gpt-5.5) and Google Translate. The Persian pipeline adds a second pass:
a subtitle aligner that produces a bilingual double-line `.docx`.

---

## High-Level Architecture

```
                ┌─ index.ejs       (legacy UI, served at /)
frontend ──────┤
                └─ web/v2/index.html  (v2 SPA, served at /v2/)
                          │
                          ▼  POST /upload
              local_launcher.py
                  │
                  ▼  subprocess
              src/machine-translate-docx.py  ──┐
                                               ▼
                  ┌─ src/runtime.py        (RuntimeContext dataclass)
                  ├─ src/config.py         (constants + tables)
                  ├─ src/runner.py         (block-loop orchestrator)
                  ├─ src/engines/          (google, deepl, chatgpt_api)
                  ├─ src/selenium_utils/   (driver, click, forms)
                  └─ src/openai_tools/     (translator, polisher, aligner_per)
```

See [`docs/architecture.md`](docs/architecture.md) for the full pipeline diagram.

---

## Key Paths

| Path | Role |
|------|------|
| `src/machine-translate-docx.py` | CLI entry point — orchestrates everything |
| `src/runtime.py` | `RuntimeContext` dataclass — threaded through engines |
| `src/config.py` | Module-level constants + parallel arrays |
| `src/runner.py` | Block-loop orchestrator |
| `src/engines/google.py` | Selenium-based Google Translate engine |
| `src/engines/deepl.py` | Selenium-based DeepL engine |
| `src/engines/chatgpt_api.py` | OpenAI API engine bridge |
| `src/engines/inactive/` | Disabled web engines (chatgpt_web, perplexity_web) |
| `src/selenium_utils/` | Driver/click/forms helpers |
| `src/openai_tools/translator.py` | `OpenAITranslator` — single-call translate |
| `src/openai_tools/polisher.py` | `OpenAIPolisher` — single-call polish |
| `src/openai_tools/aligner_per.py` | `FASubtitleAligner` — bilingual doubling |
| `src/openai_tools/splitting.py` | Legacy per-phrase splitter (only when splitTranslate=true) |
| `local_launcher.py` | Local dev server (Python, no Node required) — serves both UIs |
| `server.js` | Express server (Node.js production server) |
| `index.ejs` | **Legacy** frontend — EJS template, served at `/` |
| `web/v2/index.html` | **v2** frontend — Tailwind + Alpine SPA, served at `/v2/` |
| `web/v2/app.js` | Alpine factory `docTranslator()` for v2 |
| `web/v2/i18n.json` | English + Persian locales for v2 |
| `prompts/translate_PER.txt` | Persian translation system prompt |
| `prompts/polish_PER.txt` | Persian polish system prompt |
| `prompts/translate_universal.txt` | Fallback prompt for other languages |

---

## Critical Commands

```bash
# Start local dev server — opens LEGACY UI at /
E:\Python311\python.exe local_launcher.py
"run_local_launcher     -----------.bat"

# Start local dev server — opens v2 UI at /v2/
"run_local_launcher_v2.bat"

# Both UIs are served simultaneously by the same launcher.
# Legacy:  http://127.0.0.1:3000/
# v2:      http://127.0.0.1:3000/v2/

# Run translation directly from CLI
E:\Python311\python.exe src/machine-translate-docx.py \
  --input file.docx --target-lang fa --engine chatgpt-polish

# Run pytest (51 tests, ~3 s) — exclude live e2e by default
E:\Python311\python.exe -m pytest tests/ --ignore=tests/test_v2_e2e.py
```

---

## Output Naming Convention

| File | Pattern |
|------|---------|
| Translate + Polish | `{stem}_PER_TranslatePolish.docx` |
| Aligner double output | `{stem}_PER_Double.docx` |
| JSON log | `{stem}_PER_TranslatePolish_log.json` |

Both files are served for download when the aligner runs.

---

## Core Conventions

- **Models**: translator + polisher default to `gpt-5.5`; aligner is **always** `gpt-5.4-mini` (hardcoded, do not change)
- **Prompt cache**: every API call sets `extra_body={"prompt_cache_retention": "24h"}`
- **Lang codes**: output filenames use ISO 639-2/B (`fa`→`PER`, `ar`→`ARA`, `de`→`GER`)
- **`_normalize_lang()`** is read-only; for prompt file lookup use `_prompt_lang_code()` instead
- `reasoning_effort` is active in polisher **only** when `"mini"` is in the model name
- File collisions get `_1`, `_2` suffixes — never overwrite

---

## Safety Constraints

- Never commit `.env`, API keys, or `src/configuration/configuration.json` if it contains secrets
- Never change the aligner model — it must stay `gpt-5.4-mini`
- Never add `reasoning_effort` to the translator (causes 94 % reasoning token overhead)
- `_normalize_lang()` must not be modified — only `_prompt_lang_code()` maps prompt filenames

---

## Deeper Docs

- [`docs/architecture.md`](docs/architecture.md) — full pipeline, data flow
- [`docs/translation-style.md`](docs/translation-style.md) — Persian broadcast quality rules
- [`docs/subtitle-syncing.md`](docs/subtitle-syncing.md) — aligner algorithm & thresholds
- [`docs/testing.md`](docs/testing.md) — how to test locally
- [`docs/error-catalog.md`](docs/error-catalog.md) — known bugs & recurring issues
- [`docs/decisions-2026.md`](docs/decisions-2026.md) — architectural decision log
- [`docs/refactor-roadmap.md`](docs/refactor-roadmap.md) — Phase A→G design rationale
- [`docs/post-refactor-audit.md`](docs/post-refactor-audit.md) — post-refactor audit (D1-D7 + 15 findings)
- [`docs/phase-F-blocked.md`](docs/phase-F-blocked.md) — original F1 blocker note
- [`web/v2/README.md`](web/v2/README.md) — v2 frontend stack, deploy, file map
- [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md) — active constraints, recent changes
