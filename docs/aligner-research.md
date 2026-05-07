# Aligner Research — Techniques in the Literature vs. What We Do

> Research-only summary. Cross-references our `aligner_per.py` against
> recent academic and OSS work on bilingual subtitle alignment.
> Sources:
> [GitHub: ragymorkos/Subtitle-Alignment-Algorithm](https://github.com/ragymorkos/Subtitle-Alignment-Algorithm),
> [Springer 2018 — Lightly supervised alignment of subtitles](https://link.springer.com/article/10.1007/s11042-018-6050-1),
> [ScienceDirect — High-quality bilingual subtitle alignment](https://www.sciencedirect.com/science/article/abs/pii/S088523081100060X),
> [Springer 2018 — Bi-text alignment for English-Arabic SMT](https://link.springer.com/chapter/10.1007/978-3-319-75487-1_11),
> [arXiv 2025 — Segment, Embed, and Align](https://arxiv.org/pdf/2512.08094).

---

## What our `FASubtitleAligner` already does (recap)

| Layer | Technique |
|-------|-----------|
| Mechanical pass | Recursive split with quality-scored candidate boundaries |
| Persian-specific | `PROTECTED_BIGRAMS`, `DANGEROUS_SPLITS`, `COMPOUND_PREFIXES` (می‌/نمی‌), را-orphan ban |
| Distribution | B4 weight table (EN word count → FA char budget per row) |
| Doubling | `_DOUBLE_DENSITY` table; modulo-cycle distribution to spread doubles evenly |
| Cross-row | `CONTINUATION_STARTERS` lookahead; 5-part alignment score |
| Content type | NEWS_ATTR / INGREDIENT skip doubling; per-type `_BREAK_RATIO_BY_TYPE` (Phase 3) |
| Quality | per-group score → optional LLM batch (currently disabled, `llm_threshold=0`) |
| Safety | `_display_len` (ZWNJ-aware), cross-group sentinel triple guard, RTL bidi enforcement |

## Techniques in the literature we **do not** do (and the verdict)

### 1. Length-based statistical alignment (Gale-Church)
**Idea:** Align sentences/blocks by character-length ratio under a Gaussian
prior on the FA/EN length ratio.
**Status here:** We already use a length ratio as one of five alignment-score
parts (`_alignment_score` part 4: `0.5 ≤ FA/EN ≤ 2.5`). Gale-Church-style DP
is not implemented but would only matter for *re-alignment of already-mis-aligned
rows* — our input is row-aligned by upstream translation, so this is a non-issue.
**Verdict:** Skip — would solve a problem we don't have.

### 2. DP-based monotone search over chunk pairs
**Idea:** Optimal split is found by dynamic programming over all possible
chunk pairs with a cost function combining length, lexical similarity, and
positional preference.
**Status here:** `_recursive_split` is greedy with a 60/40 quality+balance
score; `_split_by_budget` is also greedy. DP would give a globally optimal
split per group.
**Verdict:** Worth a look. **Estimated effort:** ~80 lines of code. The
greedy approach already gets >90 score on most groups; DP would marginally
improve groups with several near-equal candidate splits. **Recommendation:**
Document but defer — not a high-impact change vs. effort.

### 3. Bilingual lexicon-based alignment scoring
**Idea:** A weighted bilingual dictionary scores how well an FA chunk aligns
to an EN row by overlap of mapped terms (e.g. "because"↔"چون").
**Status here:** We already do a lightweight version: `_BUILTIN_CUES`
(cause/result/contrast/concession/condition/time, 6 categories, ~25 terms).
**Verdict:** **Already implemented for the high-value cases.** Adding a
larger lexicon gives diminishing returns once SMTV-specific glossary terms
are covered.

### 4. Lightly-supervised speech recognition alignment
**Idea:** Use an ASR system on the audio track and align subtitles to ASR
output for frame-accurate timing.
**Status here:** N/A — no audio input in our pipeline.
**Verdict:** Skip. Out of scope.

### 5. Embedding-based segment alignment (arXiv 2025: Segment, Embed, and Align)
**Idea:** Use sentence embeddings (e.g. mBERT, LaBSE) to score how well an
FA chunk semantically matches an EN row, used in addition to length-based
alignment.
**Status here:** No embedding step. We have a discourse-cue dictionary
instead.
**Verdict:** **Worth a small experiment.** A locally cached embedding
model (e.g. `paraphrase-multilingual-MiniLM-L12-v2`, 120 MB, no API call)
could score FA↔EN row similarity in milliseconds. Risk: model download
size. **Effort:** ~50 lines of code + 120 MB download on first run + a
~5-minute first-startup penalty. **Recommendation:** Document; postpone
until we have a measurable quality gap on real broadcast files.

### 6. Chunk-pair training data extraction for SMT (Springer 2018, Arabic)
**Idea:** Extract bilingual chunk pairs from aligned subtitles to train a
phrase-based SMT system.
**Status here:** Not relevant — we use OpenAI for translation, not in-house
SMT.
**Verdict:** Skip.

## Small wins we **could** port today (≤ 30 LOC)

### a. Aspect-of-discourse cue expansion
**Current:** 6 categories (cause, result, contrast, concession, condition,
time) with ~25 EN→FA mappings.
**Proposal:** Add 4 more low-risk categories:
- **addition** — `also/moreover/in addition` → `همچنین، علاوه بر این، نیز`
- **sequence** — `then/next/finally` → `سپس، پس از آن، در نهایت`
- **example** — `for instance/such as/e.g.` → `برای مثال، مانند، از جمله`
- **emphasis** — `indeed/in fact/actually` → `در واقع، به‌راستی`

**Why:** These show up commonly in news/educational SMTV content. Cost:
~15 lines added to `_BUILTIN_CUES`. Risk: near-zero — same shape as
existing cues, same scoring path.

**Status:** Implemented in this PR (see Phase commit message).

### b. NE-aware split avoidance (pure-regex, no model)
**Current:** No specific handling — just word-boundary splitting.
**Proposal:** A small regex set marking spans inside which `_find_split_points`
must lower the quality score:
- 2-word capitalised English names in the EN row that map to a transliterated
  FA span (e.g. "John Smith" → "جان اسمیت")
- 4+ digit years (`2026`, `۲۰۲۶`)
- ALL-CAPS acronyms (already partly handled by W3 TECH_LOCK in the prompt,
  but the aligner doesn't know about this).

**Effort:** ~30 lines. **Risk:** false positives could over-penalise normal
splits. **Recommendation:** Defer until we see real cases of NE splits in
production logs.

## What we deliberately **do not** do, and why

| Avoided technique | Reason |
|--------|--------|
| Audio/timecode-aware alignment | No audio in pipeline |
| Reading-speed (CPS) constraint | DOCX rows are not timecoded |
| Shot-change detection | Same — no video input |
| Sentence-pair embedding cache | Disk and startup cost > current quality gap |
| External translation memory (TMX) | Would benefit pipeline but is a separate persistent-glossary feature, out of aligner scope |

## TL;DR

The aligner already implements the **high-impact** mechanical techniques
from the literature. The three ideas worth keeping on the table are
(1) DP-based optimal split (small accuracy bump, moderate code), (2)
embedding-based alignment scoring (real but uncertain win, real cost),
(3) discourse-cue dictionary expansion — done in this PR.
