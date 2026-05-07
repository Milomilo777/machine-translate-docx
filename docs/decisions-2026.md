# Architectural Decisions — 2026

Log of significant design choices. Add an entry when a non-obvious approach is chosen.

Format: date, decision, alternatives considered, rationale.

---

## 2026-05-08 — Phase 4 of review-rewrite-opus-4.7 (testability + ops hygiene)

**Decision:** Three independent improvements that do not change observable
behaviour for end users but make the system safer to operate and modify.

**Tests alternatives:**
- `pytest-cov`, `pytest-mock` extras — rejected; goal is *minimum-deps* test
  pack so contributors can `pip install -r requirements-test.txt && pytest`.
- Tests as `unittest` — rejected; pytest is widely available and the tests
  use `assert` style.
- Tests touching real OpenAI / real DOCX — rejected; would require API keys
  in CI and slow the pre-commit loop.

**DB-guard alternatives:**
- Lazily try to connect on first use — current behaviour, has overhead per
  API call when MariaDB is not provisioned (most local-launcher runs).
- Hard requirement (raise on missing host) — rejected; many users don't
  want DB persistence at all.
- Env-driven opt-in (`MARIADB_HOST`) — chosen; zero overhead when unset,
  fully backward-compatible when set.

**Semaphore alternatives:**
- Per-engine queue — over-engineered for current scale.
- Hardcoded cap of 2 — chosen as default but exposed via
  `MTD_MAX_CONCURRENT_JOBS` so power users can raise it without code changes.
- No cap — current behaviour, can OOM the host on a 5-user burst.

**Constraints honoured:** Aligner model still `gpt-5.4-mini`. `_normalize_lang()` untouched. No `reasoning_effort` on translator. `prompt_cache_retention=24h` preserved.

---

## 2026-05-08 — Phase 3 of review-rewrite-opus-4.7 (aligner quality)

**Decision:** Three internal aligner improvements with no public-API change.

**`_display_len` alternatives:**
- Strip ZWNJ globally on input — rejected; ZWNJ has semantic meaning, must be preserved in stored output.
- Track display vs. raw separately — over-engineered; one helper covers every check site.

**Sentinel approach alternatives:**
- Run `_enforce_no_triple` over per-pair group boundaries only (compare last-of-G with first-of-G+1) — rejected because longer cross-group runs could still slip through if three consecutive groups all start/end with the same chunk.
- Carry bridge-row indices into the flat list as empty strings — rejected; misleading because empty strings already mean "no FA on this row" and would conflate two distinct meanings.
- NUL-bracketed sentinel — chosen; safe (no real chunk equals NUL bytes) and naturally breaks the existing run-counter logic.

**Per-type break ratio alternatives:**
- Continue with single 0.45 ratio — kept producing front-end ratios that felt unbalanced for news cells (verbs/objects clustered late even when subject/event were the focus).
- Learn ratio from data per file — out of scope; the dict is hardcoded and easy to tune later.

**Constraints honoured:** Aligner model still `gpt-5.4-mini`. `_normalize_lang()` untouched. No new API call sites.

---

## 2026-05-08 — Phase 2 of review-rewrite-opus-4.7 (visible-issue fixes)

**Decision:** Phase 2 ships three independent improvements: a single-shot ZIP download, a job-store cleanup thread, and a shared OpenAI retry helper.

**ZIP-download alternatives considered:**
- Three on-page download links instead of auto-download — rejected (extra clicks for repeat users).
- Keep multi-file auto-download with longer delays — already in place (E9) and still requires user-side permission click.
- Stream a tar.gz — rejected (no native tar support in Windows file explorer; ZIP wins on portability).

**Cleanup-thread alternatives:**
- WeakValueDictionary — wouldn't help because Job dataclasses are referenced from inside the dict itself.
- LRU cap (e.g. keep last 1000 jobs) — rejected because age-based pruning is more predictable for memory profiles in the absence of activity.

**Retry-helper alternatives:**
- `tenacity` library — adds an unnecessary dependency for ~30 LOC of logic.
- Per-module retry implementation — rejected (drift between three callers; this is exactly what bit us before in the splitter cache regression).
- Retry on every Exception — rejected (mask request bugs and burn tokens).

**Constraints honoured:** Aligner model still `gpt-5.4-mini`. `_normalize_lang()` untouched. No `reasoning_effort` on translator. `prompt_cache_retention=24h` preserved.

---

## 2026-05-08 — Phase 1 of review-rewrite-opus-4.7 (critical fixes only)

**Decision:** A multi-phase rewrite branch was started after a full project review (Opus 4.7, 1M context). Phase 1 carries only fixes that are visible to end users or close a security gap; no refactor, no feature work.

**Phase 1 scope:**
- E10 RTL/bidi rebuilt-cell fix (`aligner_per.py`)
- E11 English-residue fallback after polish (`polisher.py`)
- E12 Server-side magic-bytes + 50 MB zip-bomb cap (`local_launcher.py`)

**Alternatives considered:**
- Bundle Phase 1 + Phase 2 (UX) — rejected because RTL and residue fixes are independently verifiable and benefit from a clean isolated commit so they can be cherry-picked back to `master` without UX changes.
- Skip server-side validation since the launcher is local — kept anyway because the same handler is shared with deployments and the cost (≤30 LOC) is trivial.

**Constraints honoured:** Aligner model still `gpt-5.4-mini`. `_normalize_lang()` untouched. No `reasoning_effort` on translator. `prompt_cache_retention=24h` preserved on every API call.

---

## 2026-05-08 — Three-file output (TranslatePolish + Classic + Double)

**Decision:** Persian pipeline now produces three files. Classic and Double are both fully mechanical (`llm_threshold=0`).  
**Alternatives:** One file (TranslatePolish only); two files (TranslatePolish + Double); ZIP all.  
**Rationale:** Classic is for reference/comparison with the pre-aligner output. Double is the aligned version. Both are now mechanical — the LLM aligner pass was found to produce no visible quality improvement and caused slow, expensive API calls per sentence group. The mechanical pass alone covers ~80-85% quality at zero API cost.  
**Note:** Classic and Double are currently functionally identical (same `llm_threshold=0`). Classic reserved for future differentiation (e.g., character-distribution algorithm vs. aligner algorithm).

---

## 2026-05-08 — Lower llm_threshold to 0 (fully mechanical aligner)

**Decision:** `llm_threshold` for both Classic and Double set to 0. No LLM review of any sentence group.  
**Alternatives:** Keep at 90 (LLM for low-quality groups); raise to 100 (LLM for all groups).  
**Rationale:** In production test, 23 LLM calls for 102 groups (22%) added 16.7s but produced no visible output improvement. The mechanical 3-pass algorithm is sufficient for distribution; quality issues originate in the translation phase (pre-aligner), not the distribution phase. Removing LLM also eliminates a confound when evaluating mechanical quality.  
**Reversible:** Set `llm_threshold=90, token_budget=40_000` in `machine-translate-docx.py` Double pass to re-enable.

---

## 2026-05-08 — Hide Split section for Persian+chatgpt-polish

**Decision:** When target language is `fa` AND engine is `chatgpt-polish`, the entire Split section (checkbox + dropdown) is hidden in the UI and `splitTranslate=false` is sent to the server.  
**Alternatives:** Keep Split visible; auto-switch to basic algorithm only; add tooltip explanation.  
**Rationale:** Split Method (OpenAI API) and the Aligner both distribute FA text across EN rows — they do the same job. Running both caused: (1) one OpenAI API call per phrase during splitting, (2) aligner re-distributing the already-split output, undoing split work. The aligner is the correct tool; the splitter is redundant and expensive in this pipeline.  
**Safety layer:** `engineChecker()` is also called on engine change, not just language change.

---

## 2026-05-08 — Download delays 1500ms/3000ms for multi-file Chrome

**Decision:** Sequential download delays changed from 800ms/1600ms to 1500ms/3000ms.  
**Rationale:** Chrome shows "allow multiple downloads?" notification for the 2nd and 3rd files. Longer delays give the user time to see and respond to the notification before the next download fires. 1500ms is the community-recommended minimum for reliable Chrome multi-download.

---

## 2026-05-07 — Aligner v2: inject 11 legacy techniques

**Decision:** Injected the following into `aligner_per.py` from audit of legacy modules
(para_bridge, hybrid_double, v9, fa-aligner-pro, pipe15) and critique findings:

| Technique | Source | Effect |
|-----------|--------|--------|
| CONTINUATION_STARTERS (15 conjunctions) | legacy grouper | prevents premature sentence-group splits at که/چون/اما… |
| DANGEROUS_SPLITS (7 light-verb patterns) | legacy splitter | protects انجام داد، استفاوده کرد، صحبت کرد etc. |
| Weight pass | v9 aligner | fixes heavy-last-line from Persian SOV verb-final structure |
| Modulo-cycle distribution | hybrid_double | spreads doubles evenly (not clustered at longest chunks) |
| Preservation check | v9 aligner | skips re-split when existing FA is already balanced (mean 18-42) |
| 5-part alignment score | fa-aligner-pro | discourse(0.30)+numbers(0.20)+punctuation(0.10)+ratio(0.20)+base(0.10) |
| Per-row number alignment | critique fix | checks numbers in FA ±1 window per row, not whole group |
| BREAK_RATIO_MEDIAN=0.45 | pipe15 | splits at 45% of text (empirically better for SOV) |
| Content-type-aware double ratio | legacy | NEWS_ATTR/INGREDIENT warn >5%, DIALOGUE warn >30%, NARRATION >55% |
| Pipe normalization in _normalize_fa | legacy | strips `|` artifacts before scoring |
| Citation stripping (_strip_citation) | legacy | removes trailing (euronews) etc. from FA cells |

**Alternatives:** Apply selectively; apply all at once but flag for rollback.
**Rationale:** All 11 techniques address real mechanical quality issues identified
in production (heavy last lines, premature group splits, clustering doubles,
false-positive quality scores). Applied together they complement each other.
`_should_preserve_existing_segmentation()` acts as a safety valve to avoid
degrading already-good translator output.

---

## 2026-05-07 — Raise llm_threshold from 70 to 90

**Decision:** `FASubtitleAligner` default `llm_threshold` raised from 70 to 90.  
**Alternatives:** Keep at 70; lower to 10 (almost no LLM); raise to 100 (full LLM review).  
**Rationale:** At threshold=70, generation was already slow (LLM called for many groups).
Raising to 90 reduces LLM calls to low-quality groups only (score < 90), improving speed
significantly while still catching the worst mechanical alignments.  
**Note:** threshold meaning — groups with score *below* threshold go to LLM. Score 0–100,
higher = better mechanical quality. Raise threshold → more LLM. Lower threshold → less LLM.

---

## 2026-05-07 — Two-file download architecture

**Decision:** Job object carries `filename2`; frontend triggers two sequential downloads.  
**Alternatives:** Zip both files; separate endpoint; user manually downloads second file.  
**Rationale:** Zip requires extra library and changes UX. Separate endpoint adds complexity.
Sequential browser downloads (800 ms apart) work reliably across Chrome/Edge/Firefox.

---

## 2026-05-07 — Rename prompt files _fa → _PER

**Decision:** `translate_fa.txt` → `translate_PER.txt`; `polish_fa.txt` → `polish_PER.txt`.  
**Rationale:** Consistency with output filename convention (ISO 639-2/B codes).
New `_prompt_lang_code()` helper keeps `_normalize_lang()` untouched.

---

## 2026-03 — Single-call translation (whole file in one API request)

**Decision:** Translate the entire document in a single API call instead of block-by-block.  
**Alternatives:** Block-by-block (256-line chunks); paragraph-by-paragraph.  
**Rationale:** Block-by-block caused context loss at boundaries, inconsistent terminology, and
many round-trips. Single-call with gpt-5.5 handles large documents within context window and
produces more consistent output. Timeout set to 1800 s to accommodate large files.

---

## 2026-03 — Remove reasoning_effort from translator

**Decision:** `reasoning_effort` removed from `OpenAITranslator` API call.  
**Alternatives:** Keep it for better translation quality.  
**Rationale:** In testing, `reasoning_effort` caused 94 % of tokens to be reasoning tokens,
massively increasing cost with negligible quality improvement for translation tasks.
`reasoning_effort` remains in polisher only when model name contains `"mini"`.

---

## 2026-03 — Move {N} from system prompt to user message

**Decision:** Line count `{N}` removed from system prompt, added to user message instead.  
**Rationale:** System prompt must be identical across all requests for prompt cache to hit.
Including a per-document variable (`{N}`) in the system prompt invalidated the cache on every call.

---

## 2026-03 — Polling architecture (/upload → jobId → /status)

**Decision:** Upload returns jobId immediately; client polls `/status/:id` every 4 s.  
**Alternatives:** Long-polling; WebSocket; synchronous HTTP (wait for completion).  
**Rationale:** Translation can take 10–30 minutes for large files. Synchronous HTTP would
time out. WebSocket adds complexity. Polling is simple, reliable, and easy to debug.

---

## 2026-02 — FASubtitleAligner as separate pipeline stage

**Decision:** Aligner runs as a third stage after translate + polish, always using `gpt-5.4-mini`.  
**Alternatives:** Integrate alignment into polish step; use a deterministic algorithm only.  
**Rationale:** Alignment quality requires semantic understanding. Separating it as a distinct
stage keeps each component focused. Mini model is sufficient and cost-effective for this task.
Model is hardcoded to prevent accidental upgrade to a slower/costlier model.
