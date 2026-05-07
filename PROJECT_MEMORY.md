# PROJECT_MEMORY.md — Machine Translate DOCX

Committed team memory. Keep it concise — no raw logs, no long discussion.
Summary + link to `docs/` for depth.

Last updated: 2026-05-08

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
| Aligner Classic | `FASubtitleAligner`; `llm_threshold=0`; fully mechanical; no API calls |
| Aligner Double | `FASubtitleAligner`; `llm_threshold=0`; fully mechanical; no API calls |
| Three-file output | TranslatePolish + Classic + Double; sequential browser downloads 0/1500/3000 ms |
| Split section visibility | Hidden when Persian + chatgpt-polish (aligner handles distribution) |
| Frontend–backend comms | Polling: POST `/upload` → jobId → GET `/status/:id` every 4 s |
| Job store | In-memory dict in `local_launcher.py`; `filename`, `filename2`, `filename3`; no persistence |
| Lang code convention | ISO 639-2/B in filenames; `_LANG_ALPHA3B` dict in `local_launcher.py` |
| Prompt file naming | `{action}_{LANG_CODE}.txt` — e.g., `translate_PER.txt`, `polish_PER.txt` |
| Java/Kotlin migration | Not recommended — API latency is bottleneck; python-docx has no Java equivalent |

---

## Important Terminology

| Term | Meaning |
|------|---------|
| `_PER_TranslatePolish` | Main output — translate + GPT polish pipeline |
| `_PER_Classic` | Mechanical aligner output (no LLM, `llm_threshold=0`) |
| `_PER_Double` | Mechanical aligner output (no LLM, `llm_threshold=0`) — currently identical to Classic |
| `chatgpt-polish` | Engine name for the translate+polish+align pipeline |
| `bridge row` | Table row to skip in aligner (timecodes, speaker tags, empty FA) |
| `llm_threshold` | Groups with score *below* this go to LLM. Currently 0 = all mechanical |
| `filename2` | Job field for `_PER_Double.docx` |
| `filename3` | Job field for `_PER_Classic.docx` |
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

---

## Recent Important Changes (last 30 days)

| Date | Change |
|------|--------|
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
