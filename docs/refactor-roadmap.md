# Refactor Roadmap — machine-translate-docx

> Status: Analysis complete. Refactoring NOT started.
> Last updated: 2026-05-08
> Source: Full read of `src/machine-translate-docx.py` (7,879 lines, ~328 KB)

---

## Current File Stats

| Metric | Value |
|--------|-------|
| Main file | `src/machine-translate-docx.py` |
| Total lines | ~7,879 |
| Top-level functions | ~90 |
| Global variables | Many (driver, dest_lang, engine_method, ...) |
| External libs | selenium, python-docx, openai, langcodes, tiktoken, psutil, undetected_chromedriver |

---

## Engine Inventory

| Engine | Method | Approx. lines | Notes |
|--------|--------|---------------|-------|
| Google Translate | Selenium (HTML file injection) | 2173–2296 | Generates HTML, opens in Chrome, reads result |
| Google Translate | Selenium (text file) | 2213–2296 | Via text file |
| Google Translate | Selenium (XLSX) | 2524–2660 | Via spreadsheet |
| DeepL | Selenium (UI automation) | 2747–3664 | Login + logout flow, retry logic |
| DeepL | API | (sharing block-loop) | Via HTTP, no Selenium |
| Perplexity | Selenium | 4214–4604 | Full browser automation |
| Perplexity | API | 4605–4737 | Direct HTTP |
| ChatGPT | Selenium | 3665–4062 | Browser automation |
| ChatGPT | API (openai SDK) | via OpenAITranslator | Already in `openai_tools/` — clean |
| ChatGPT + Polish | API (openai SDK) | via OpenAITranslator + OpenAIPolisher | Already in `openai_tools/` — clean |
| Yandex | Selenium | 2661–2719 | Older engine |

---

## Dependency Map (key global state)

```
driver          → Selenium WebDriver — shared by all Selenium engines
translation_engine / engine_method → routing logic in set_translation_function()
dest_lang / dest_lang_name         → used throughout
word_file_to_translate             → input path
word_file_to_translate_save_as_path → output path
blocks_nchar_max_to_translate_array → chunked text blocks for translation loop
translated_blocks                  → parallel array with translated content
```

**Entry point flow:**
```
main()
  └─ set_translation_function()       → sets global translation_function
  └─ initialize_translation_memory_xlsx()
  └─ read_and_parse_docx_document()   → reads DOCX → fills blocks array
  └─ create_webdriver()               → starts Chrome (Selenium)
  └─ translate_docx()                 → dispatches to engine
  └─ get_translation_and_replace_after()
  └─ document_split_phrases()         → Persian aligner / split
  └─ write_destination_language_in_docx_cell()
  └─ save_docx_file()
```

---

## Refactor Risk Assessment

**Overall risk: VERY HIGH**

| Area | Risk | Reason |
|------|------|--------|
| Global variable mesh | Very High | ~15+ globals mutated across 90 functions |
| Selenium engines | High | Fragile UI selectors; timing-dependent |
| `main()` function | High | Monolithic orchestrator, hard to test |
| DOCX read/write | Medium | `read_and_parse_docx_document()` — 280 lines, parallel arrays |
| OpenAI API path | Low | Already in clean `openai_tools/` modules |
| Persian aligner | Low | Just rewritten as clean standalone module |
| Prompts | Low | Already separate files in `prompts/` |

**Hardest parts to refactor:**
1. Global state shared between all functions — no clean boundaries
2. Selenium timing logic (retry, wait, cookie cleanup) scattered across engine functions
3. `read_and_parse_docx_document()` builds parallel arrays that everything else depends on
4. DeepL login/logout tied into translation flow

---

## Proposed Module Split (target structure)

```
src/
├── cli.py                    ← argparse only, calls pipeline
├── config.py                 ← all constants, language maps, pricing
├── pipeline/
│   ├── __init__.py
│   ├── docx_reader.py        ← read_and_parse_docx_document()
│   ├── docx_writer.py        ← save, cell write, RTL helpers
│   ├── job_runner.py         ← orchestration (replaces main() body)
│   └── split_phrases.py      ← document_split_phrases(), split logic
├── engines/
│   ├── __init__.py
│   ├── base.py               ← TranslationEngine abstract base class
│   ├── google_selenium.py    ← all Google Selenium functions
│   ├── deepl_selenium.py     ← DeepL login/translate/logout
│   ├── deepl_api.py          ← DeepL API (no Selenium)
│   ├── perplexity.py         ← Selenium + API
│   ├── chatgpt_selenium.py   ← ChatGPT browser automation
│   ├── yandex.py             ← Yandex Selenium
│   └── registry.py           ← set_translation_function() → engine factory
├── selenium_utils/
│   ├── __init__.py
│   ├── driver.py             ← create_webdriver(), cleanup
│   ├── actions.py            ← safe_click, browser_fill_form_field_value
│   └── downloads.py          ← getDownLoadedFileNameChrome, etc.
├── openai_tools/             ← DO NOT TOUCH (already clean)
│   ├── translator.py
│   ├── polisher.py
│   ├── aligner_per.py
│   ├── fa_postprocess.py
│   └── _retry.py
└── utils/
    ├── language.py           ← langcodes, normalize_lang, alpha3
    ├── text.py               ← tokenize, divide_array, is_end_of_line
    └── logging.py            ← write_translation_log, run_statistics
```

---

## Persian-Specific Files — Never Auto-Merge

These files contain language-specific calibration that must stay isolated:

| File | Purpose | Rule |
|------|---------|------|
| `src/openai_tools/aligner_per.py` | FA subtitle alignment | Never merge with other engines |
| `src/openai_tools/fa_postprocess.py` | FA char normalization | Persian-only, safe subset only |
| `prompts/translate_PER.txt` | Translation instructions for FA | Human-reviewed, do not auto-generate |
| `prompts/polish_PER.txt` | Polish instructions for FA | Human-reviewed, do not auto-generate |
| `src/openai_tools/translator.py` | OpenAI translator | Works; only fix bugs |
| `src/openai_tools/polisher.py` | OpenAI polisher | Works; only fix bugs |

---

## Do Not Touch List

These behaviors must survive the refactor exactly:

1. **`split_translate=False` for fa+chatgpt-polish** — aligner handles distribution
2. **`gpt-5.4-mini` hardcoded for aligner** — never change to follow UI model selector
3. **`_normalize_lang()` interface** — do not modify; only `_prompt_lang_code()` maps prompt files
4. **ZWNJ (U+200C) preserved in all FA text** — byte-level pass-through
5. **DeepL Selenium login/logout sequence** — fragile; wrap but do not rewrite logic
6. **Timestamp stripping from output filenames** — `_strip_timestamp()` in local_launcher.py
7. **ISO 639-2/B suffix mapping** — fa→PER, ar→ARA, de→GER (in `local_launcher.py`)
8. **Prompt caching via Responses API** — gpt-5.x must use `client.responses.create()`
9. **`prompt_cache_retention: "24h"` in extra_body** — valid OpenAI param, keep it
10. **Sequential download 1800ms** — Classic first, Double after 1800ms (Chrome multi-download)

---

## Recommended Refactor Phases

### Phase A — No-risk extractions (2-3 hours, risk: LOW)
- Extract `config.py` (constants, maps, pricing)
- Extract `utils/language.py` (langcodes wrappers)
- Extract `utils/text.py` (tokenize, split helpers)

### Phase B — DOCX I/O isolation (4-6 hours, risk: MEDIUM)
- Extract `pipeline/docx_reader.py`
- Extract `pipeline/docx_writer.py`
- Eliminate parallel array globals — replace with a `DocxDocument` dataclass

### Phase C — Engine modules (8-12 hours, risk: HIGH)
- Create `engines/base.py` abstract interface
- Extract each engine to its own file
- Replace `set_translation_function()` with engine factory/registry

### Phase D — Selenium utilities (4-6 hours, risk: MEDIUM)
- Extract `selenium_utils/`
- Wrap timing logic in helper class

### Phase E — Pipeline and CLI (4-6 hours, risk: MEDIUM)
- Extract `pipeline/job_runner.py` from `main()`
- Slim `cli.py` to argparse only

---

## Decision

> ⚠️ Phase A only is safe to start immediately.
> Phases B–E require the full analysis output (English) before committing to execution.
>
> To get the clean analysis:
> ```powershell
> claude --model opus -p "...prompt..." > docs\analysis-raw.txt
> ```
> Then append the raw output to this file.

---

*This document will be updated when the clean English analysis is available.*
