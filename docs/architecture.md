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
   └─► subprocess: python src/machine-translate-docx.py [args]
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
                    │       output: {stem}_PER_TranslatePolish.docx
                    │
                    └─► FASubtitleAligner.align()            ← aligner_per.py
                            model: gpt-5.4-mini (hardcoded)
                            llm_threshold: 10
                            output: {stem}_PER_Double.docx
```

## Component Responsibilities

### `src/machine-translate-docx.py`
- CLI entry point, argparse
- Orchestrates the full pipeline
- Calls translator → polisher → aligner in sequence
- Prints `Saved file name: {path}` to stdout (local_launcher reads this)

### `src/openai_tools/translator.py`
- `OpenAITranslator` class
- Loads system prompt from `prompts/translate_{LANG}.txt`
- `_prompt_lang_code()` maps lang code to prompt file suffix (e.g. `fa` → `PER`)
- `_normalize_lang()` is read-only — do not modify
- Single API call with `prompt_cache_retention: 24h`
- Supports `gpt-5.x` (chat completions) and `o-pro` (responses API)

### `src/openai_tools/polisher.py`
- `OpenAIPolisher` class
- Imports `_prompt_lang_code` from `translator.py`
- Uses `⟨⟨N⟩⟩` tag format for line markers
- 4-strategy parser for robust tag extraction
- `reasoning_effort: high` only when `"mini"` in model name

### `src/openai_tools/aligner_per.py`
- `FASubtitleAligner` class
- Reads bilingual DOCX table (EN | FA columns)
- Mechanical pass: splits FA sentences into ≤50-char chunks, distributes as singles/doubles
- LLM pass: groups with score < `llm_threshold` sent to gpt-5.4-mini for quality review
- Bridge detection: skips grey cells, timecodes, empty FA, speaker tags
- Output: double-line bilingual DOCX

### `local_launcher.py`
- `ThreadingHTTPServer` on configurable port (default 3000)
- Two modes: `real` (invokes actual backend) and `mock` (generates placeholder DOCX)
- `_strip_timestamp()` — removes `{13-digit-ts}-` prefix from output filename
- `_find_double_file()` — detects `_PER_Double.docx` sibling of main output
- `Job` dataclass: `filename` (main) + `filename2` (double, optional)

### `index.ejs`
- EJS template (served as plain HTML by local_launcher)
- `engineChecker()` — manages engine availability by target language
  - Persian: auto-selects `chatgpt-polish`, enables the option
  - Other languages: disables `chatgpt-polish`
- `pollJobStatus()` — returns `{ filename, filename2 }`
- `triggerDownload()` — triggers both files (filename2 delayed 800 ms)

## Output Files

```
uploads/
  {ts}-input.docx                    ← uploaded file (timestamped)

uploads/ (outputs written alongside uploads):
  input_PER_TranslatePolish.docx     ← main output (timestamp stripped)
  input_PER_Double.docx              ← aligner output (timestamp stripped)
  input_PER_TranslatePolish_log.json ← cost/token log
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

`src/openai_tools/splitting.py` — `OpenAISubtitleSplitter`  
Used only when `splitTranslate=true` in the UI. Makes per-phrase API calls.
Requires MariaDB. Use is discouraged; the aligner pipeline supersedes it.
