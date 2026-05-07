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
index.ejs  ──POST /upload──►  local_launcher.py  ──subprocess──►  src/machine-translate-docx.py
                                     │                                      │
                              polls /status/:id                   translator.py  (gpt-5.5)
                                     │                            polisher.py    (gpt-5.5)
                              GET /download/:file                 aligner_per.py (gpt-5.4-mini, always)
```

See [`docs/architecture.md`](docs/architecture.md) for the full pipeline diagram.

---

## Key Paths

| Path | Role |
|------|------|
| `src/machine-translate-docx.py` | CLI entry point — orchestrates everything |
| `src/openai_tools/translator.py` | `OpenAITranslator` — single-call translate |
| `src/openai_tools/polisher.py` | `OpenAIPolisher` — single-call polish |
| `src/openai_tools/aligner_per.py` | `FASubtitleAligner` — bilingual doubling |
| `src/openai_tools/splitting.py` | Legacy per-phrase splitter (only when splitTranslate=true) |
| `local_launcher.py` | Local dev server (Python, no Node required) |
| `index.ejs` | Frontend — EJS template served by local_launcher |
| `prompts/translate_PER.txt` | Persian translation system prompt |
| `prompts/polish_PER.txt` | Persian polish system prompt |
| `prompts/translate_universal.txt` | Fallback prompt for other languages |

---

## Critical Commands

```bash
# Start local dev server (real backend)
E:\Python311\python.exe local_launcher.py

# Or use the bat launcher (auto-finds Python)
"run_local_launcher     -----------.bat"

# Run translation directly from CLI
E:\Python311\python.exe src/machine-translate-docx.py \
  --input file.docx --target-lang fa --engine chatgpt-polish
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
- [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md) — active constraints, recent changes
