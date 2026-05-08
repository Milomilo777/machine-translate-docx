# PROJECT_MEMORY.md — Machine Translate DOCX

Committed team memory. Keep it concise — no raw logs, no long discussion.
Summary + link to `docs/` for depth.

Last updated: 2026-05-09

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
| C8 | `local_launcher.py` is on the read-only refactor list — only encoding fix (F-013) and additive v2 routes are allowed | Prevent regression of long-stable launcher behavior |

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
| F-001 | `engines/_base.py` Engine Protocol declared pre-F1 `(self, source_text, src_lang_name, dest_lang_name)` shape; mismatch with `(ctx, text)` callers | **Fixed** 2026-05-08 — Protocol rewritten to post-F1 shape |
| F-007 | `engines/google.py` called non-existent `str.unescape` method (would `AttributeError`) | **Fixed** 2026-05-08 — `html.unescape` instead |
| F-010 | `engines/deepl.py` `regex_still_translating_str = '$Translation'` — `$` is end-of-string, never matches | **Deferred** — flipping changes wait-loop semantics; needs dedicated session |
| F-012 | ~44 entry-script functions in `src/machine-translate-docx.py` still read module-level globals; F1.6 only threaded `main()` + leaves | **Deferred (Phase H)** — out of audit's trivial-fix budget |
| F-013 | `local_launcher.py` `_process_job` printed `▶ ✓ ✗ —` → `UnicodeEncodeError` on Windows `cp1252` console | **Fixed** 2026-05-09 — `sys.stdout.reconfigure(encoding="utf-8")` at startup |

---

## Recent Important Changes (last 30 days)

| Date | Change |
|------|--------|
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
