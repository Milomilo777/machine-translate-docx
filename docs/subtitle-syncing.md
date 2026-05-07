# Subtitle Syncing — FASubtitleAligner

Full reference for `src/openai_tools/aligner_per.py`.

---

## Overview

`FASubtitleAligner` takes a bilingual DOCX table (column 1: EN, column 2: FA)
and produces a **double-line** output where each EN row is matched with a
≤48-character FA chunk. Long FA sentences are split and distributed across
multiple rows (single or double).

---

## Algorithm: 3 Passes

```
Pass 1 — SPLIT
  For each sentence group, break FA text into chunks ≤ MAX_LEN (48 chars).
  Split hierarchy (strict, no level-skipping):
    Level 1 — sentence-end punctuation  .  !  ?  ؟  (not ...)
    Level 2 — clause connectors  که، زیرا، اما، ولی، اگر، تا، چون ...
    Level 3 — punctuation  ،  ؛  :  —  –
    Level 4 — phrase boundary (verb-group end, noun-phrase end)
    Level 5 — word boundary (last resort)

Pass 2 — DISTRIBUTE
  Map chunks to rows (single or double). Never triple.
  Target doubling ratio: 25–55 %.
  Modulo-cycle distribution: doubles spaced evenly across all chunks
  (not clustered at the longest chunks as in previous versions).
  Weight pass: gives extra display time to heavy SOV last-lines.

Pass 3 — REFLOW
  Re-evaluate split points to reduce penalties (e.g. dangling prepositions,
  unbalanced chunk lengths, compound verb splits, dangerous verb pairs).
```

---

## Grouping

Rows are grouped into sentence groups by EN sentence-ending punctuation.

### CONTINUATION_STARTERS

If the **next** row's FA starts with a Persian conjunction, the current group
stays open instead of flushing. This prevents premature sentence-boundary
splitting when a clause spans two subtitle rows.

Starters: `که، و، تا، با، اما، ولی، یا، چون، زیرا، هرچند، بلکه، پس، سپس، بنابراین، چراکه`

### Preservation Check

If the existing FA segmentation is already balanced (mean chunk length 18–42
chars, short-chunk ratio < 34%, no chunk > 48), the mechanical re-split is
**skipped entirely** — the original rows are used as-is. This preserves good
translator output.

---

## LLM Review Pass

After mechanical passes, groups with alignment score < `llm_threshold` are
sent to `gpt-5.4-mini` for quality review.

**Current threshold: 0** (fully mechanical — LLM never called)

Groups with mechanical score **below** threshold are sent to LLM for review.
Score range is 0–100; higher = better mechanical quality.

- threshold=0 → **no LLM at all** — fastest, zero API cost (current setting)
- threshold=90 → only low-quality groups (score < 90) go to LLM — fast, ~10–20 %
- threshold=100 → all groups go to LLM — slowest, highest quality

In production test: 23 LLM calls for 102 groups added 11 seconds but produced no visible output improvement. Issues were in the translation phase (pre-aligner), not the distribution phase.

```python
# In machine-translate-docx.py (current):
_classic_aligner = FASubtitleAligner(
    model='gpt-5.4-mini',   # NEVER change this model
    llm_threshold=0,        # fully mechanical
    token_budget=0,
)
_double_aligner = FASubtitleAligner(
    model='gpt-5.4-mini',   # NEVER change this model
    llm_threshold=0,        # fully mechanical
    token_budget=0,
)

# To re-enable LLM for Double only:
# llm_threshold=90, token_budget=40_000
```

---

## Compound Verb Protection

### COMPOUND_PREFIXES (می‌ / نمی‌)
Never split before `می‌` or `نمی‌` — these always belong to the preceding verb.

### DANGEROUS_SPLITS (7 light-verb patterns)
Beyond prefix detection, 7 compound-verb pair patterns are protected:

| Pattern | Example |
|---------|---------|
| انجام + auxiliary | انجام می‌دهد، انجام داد |
| استفاده + auxiliary | استفاده می‌کند، استفاده کرد |
| صحبت/بیان/اعلام/تصمیم + auxiliary | صحبت کرد، تصمیم گرفت |
| نگاه + auxiliary | نگاه کرد، نگاه می‌کنند |
| دسترسی/آمادگی/توانایی + auxiliary | دسترسی دارد، آمادگی داشت |
| موفق/قادر + auxiliary | موفق شد، قادر می‌شوند |
| به وجود/راه‌اندازی + auxiliary | به وجود آمد، راه‌اندازی کرد |

---

## B4 Proportional Distribution

Based on empirical data from 3,036 broadcast rows: EN word-count maps to
FA display weight. Short EN rows (2 words) get 2.86× more FA budget than
average; long rows (7+ words) get 1.01× (baseline).

| EN words | FA weight |
|----------|-----------|
| 0–1 | 0.0 (bridge row) |
| 2 | 2.86 |
| 3 | 2.05 |
| 4 | 1.57 |
| 5 | 1.34 |
| 6 | 1.13 |
| 7+ | 1.01 |

---

## Weight Pass

After distribution: if an EN row has ≤4 words AND its FA chunk has ≥28 chars,
the **next** row is forced to display the same chunk (double). This addresses
the "heavy last line" problem from Persian SOV (verb-final) structure, where
the main verb cluster lands in the last subtitle row of a sentence.

---

## Split Target

`BREAK_RATIO_MEDIAN = 0.45` — 2-part splits use 45% of text length as the
split target instead of 50%. Empirically better for Persian because verb-final
SOV structure makes the second half heavier than the first.

---

## Content Types

| Type | Rule |
|------|------|
| NARRATION | Normal doubling (up to 55 %) |
| DIALOGUE | Conservative (warn above 30 %) |
| SPIRITUAL | Conservative (warn above 30 %) |
| NEWS_ATTR | Skip doubling (warn above 5 %) |
| INGREDIENT | Skip doubling (warn above 5 %) |

NEWS_ATTR: rows containing `(Reuters)`, `(AP)`, `(AFP)`, etc.
INGREDIENT: rows starting with a measurement unit or fraction (cooking content).
General cooking narrative uses NARRATION rules.

---

## 5-Part Alignment Score

| Part | Weight | Description |
|------|--------|-------------|
| Discourse marker match | 0.30 | EN "because" ↔ FA "چون" etc. |
| Per-row number match | 0.20 | Numbers in EN row appear in FA ±1 window |
| Punctuation alignment | 0.10 | Sentence-end `.!?؟` aligned |
| Length ratio FA/EN | 0.20 | 0.5–2.5× considered normal |
| Base | 0.10 | Constant floor |

---

## Bridge Detection (rows skipped)

Rows where FA is not processed:
- Empty FA cell (unless FA is a meaningful short word: نه، من، تو، آب، ما، او)
- Grey-shaded cell (XML shading)
- Timecode pattern: `0:03-0:23`
- Speaker tags: `(m):`, `(f):`, `Narrator(m):`
- Show markers: `HOST:`, `SHOW:`, `TITLE:`, `WEEK`, `AIRDATE`
- Technical: `BMD ####`, `Fix1`, `Fix2`, `Ball Time`
- Captions: `CAPTION:`, `VO & ONSCREEN`
- URLs: `https://`, `http://`
- Entire-row citations: `(euronews)`, `(source)` as sole content

Trailing citations `(source)` are **stripped** from FA cells before processing
(e.g. "این خبر مهم بود. (یورونیوز)" → "این خبر مهم بود.").

---

## Hard Rules (absolute, never violated)

| Rule | Description |
|------|-------------|
| H1 | Each FA chunk ≤ 48 characters |
| H2 | No triple. Max 2 identical (double only) |
| H3 | Text preservation — joined chunks must equal original FA (after normalization) |
| H4 | Named entities in EN row N must appear in corresponding FA row(s) |
| H5 | Sentence-end punctuation always terminates a chunk (except `...`) |
| H6 | Compound verbs stay intact — COMPOUND_PREFIXES + DANGEROUS_SPLITS |
| H7 | `را` stays with its noun phrase |
| H8 | ZWNJ (U+200C) preserved byte-for-byte |

---

## Validation Gates

| Gate | Type | Check |
|------|------|-------|
| G1 | HARD | Triples == 0 |
| G2 | HARD | Over-48 chars == 0 |
| G3 | HARD | Joined chunks == original FA |
| G4 | HARD | All EN named entities present in corresponding FA |
| G5 | HARD | No compound-verb splits, no detached `را` |
| G6 | WARN | Doubling ratio inside content-type target range |
| G7 | WARN | Avg alignment score ≥ 0.6 |

G1–G5 failures block output delivery.

---

## Output

Two files produced:

| File | Suffix | `job` field |
|------|--------|-------------|
| Mechanical Classic | `_PER_Classic.docx` | `filename3` |
| Mechanical Double | `_PER_Double.docx` | `filename2` |

- Both paths derived from the **original input file**, not the timestamped upload copy
- `local_launcher.py` detects them via `_find_double_file()` / `_find_classic_file()` (3-strategy search each)
- Frontend triggers downloads at +1500ms (Double) and +3000ms (Classic) after main file

---

## ZWNJ-aware length validation (Phase 3, 2026-05-08)

Persian text uses ZWNJ (U+200C, "نیم‌فاصله") inside compound prefixes
(`می‌کند`، `کتاب‌ها`). The character is invisible — Word renders it with
zero width — so it must NOT count toward `MAX_CHARS = 48`.

`_display_len(text)` returns `len(text.replace(ZWNJ, ''))`. All hard
validation sites use it; raw `text[:MAX_CHARS]` slicing still uses raw
character count (which is *conservative* — the resulting visible chunk
is always ≤ MAX_CHARS).

## Cross-group triple guard sentinel (Phase 3, 2026-05-08)

Per-group `_enforce_no_triple` cannot see triples that straddle a group
boundary because bridge rows are not part of the flat row list. The
fix: insert a NUL-bracketed sentinel between groups' chunks before the
global pass and skip that slot when re-chunking.

```python
_SENTINEL = '\x00GROUP_BOUNDARY\x00'
flat = []
for gi, fc in enumerate(final_chunks):
    if gi > 0:
        flat.append(_SENTINEL)
    flat.extend(fc)
flat = self._enforce_no_triple(flat)
# re-chunk with pos += 1 to skip each sentinel
```

## Per-content-type break ratio (Phase 3, 2026-05-08)

`_split_distinct(text, n, content_type=...)` accepts an optional
content type. For 2-part splits the break ratio is read from
`_BREAK_RATIO_BY_TYPE`:

| Content type | Ratio | Reasoning |
|--------------|-------|-----------|
| `narration`  | 0.45  | Persian verb-final bias |
| `spiritual`  | 0.45  | Same as narration; legacy SAGE |
| `news_attr`  | 0.55  | Subject/event up front; balance later |
| `dialogue`   | 0.50  | Speaker turn vs. content — neutral |
| `ingredient` | 0.50  | Item + quantity — neutral |

When `content_type` is None, the legacy `BREAK_RATIO_MEDIAN=0.45` is
preserved so callers that have not been updated keep prior behaviour.

---

## RTL guarantee (Phase 1, 2026-05-08)

`_set_fa_cell` now ensures every rebuilt FA paragraph carries `<w:bidi/>` and
every run carries `<w:rtl/>`. This is required because `python-docx` does not
copy these markers when a run is replaced; without them, Word renders the FA
text in LTR direction, which appears mirrored / out-of-order on screen.

Two helpers (idempotent — safe to call multiple times):

```python
@staticmethod
def _ensure_rtl_paragraph(p):
    pPr = p._p.find(_qn('w:pPr')) or _insert_pPr(p)
    if pPr.find(_qn('w:bidi')) is None:
        pPr.append(OxmlElement('w:bidi'))

@staticmethod
def _ensure_rtl_run(run):
    rPr = run._r.find(_qn('w:rPr')) or _insert_rPr(run)
    if rPr.find(_qn('w:rtl')) is None:
        rPr.append(OxmlElement('w:rtl'))
```

Verification: open output `.docx` in Word — every FA paragraph must show RTL
arrow in the paragraph dialog; alternatively unzip and grep `word/document.xml`
for `<w:bidi/>` inside each FA cell paragraph.
