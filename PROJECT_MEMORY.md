# PROJECT_MEMORY.md — Machine Translate DOCX

Committed team memory. Keep it concise — no raw logs, no long discussion.
Summary + link to `docs/` for depth.

Last updated: 2026-05-07

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

---

## Key Architectural Decisions

See [`docs/decisions-2026.md`](docs/decisions-2026.md) for full log.

| Decision | Chosen approach |
|----------|----------------|
| Translation pipeline | Single-call (whole file in one API call), not block-by-block |
| Polish pipeline | Single-call, separate from translation |
| Aligner | Batch-mode `FASubtitleAligner`; `llm_threshold=90` (groups scoring < 90 go to LLM) |
| Frontend–backend comms | Polling: POST `/upload` → jobId → GET `/status/:id` every 4 s |
| Job store | In-memory dict in `local_launcher.py`; no persistence across restarts |
| Lang code convention | ISO 639-2/B in filenames; `_LANG_ALPHA3B` dict in `local_launcher.py` |
| Prompt file naming | `{action}_{LANG_CODE}.txt` — e.g., `translate_PER.txt`, `polish_PER.txt` |

---

## Important Terminology

| Term | Meaning |
|------|---------|
| `_PER_TranslatePolish` | Main output suffix — translate + GPT polish pipeline |
| `_PER_Double` | Aligner output — bilingual EN/FA double-line subtitle DOCX |
| `chatgpt-polish` | Engine name for the translate+polish pipeline |
| `bridge row` | Table row to skip in aligner (timecodes, speaker tags, empty FA) |
| `llm_threshold` | Minimum score below which a sentence group goes to LLM for review |
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

---

## Recent Important Changes (last 30 days)

| Date | Change |
|------|--------|
| 2026-05-07 | `llm_threshold` 70 → 10 (more LLM review in aligner) |
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
