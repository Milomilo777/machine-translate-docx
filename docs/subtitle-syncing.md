# Subtitle Syncing — FASubtitleAligner

Full reference for `src/openai_tools/aligner_per.py`.

---

## Overview

`FASubtitleAligner` takes a bilingual DOCX table (column 1: EN, column 2: FA)
and produces a **double-line** output where each EN row is matched with a
≤50-character FA chunk. Long FA sentences are split and distributed across
multiple rows (single or double).

---

## Algorithm: 3 Passes

```
Pass 1 — SPLIT
  For each sentence group, break FA text into chunks ≤ MAX_LEN (50 chars).
  Split hierarchy (strict, no level-skipping):
    Level 1 — sentence-end punctuation  .  !  ?  ؟  (not ...)
    Level 2 — clause connectors  که، زیرا، اما، ولی، اگر، تا، چون ...
    Level 3 — punctuation  ،  ؛  :  —  –
    Level 4 — phrase boundary (verb-group end, noun-phrase end)
    Level 5 — word boundary (last resort)

Pass 2 — DISTRIBUTE
  Map chunks to rows (single or double). Never triple.
  Target doubling ratio: 25–55 %.

Pass 3 — REFLOW
  Re-evaluate split points to reduce penalties (e.g. dangling prepositions,
  unbalanced chunk lengths, compound verb splits).
```

---

## LLM Review Pass

After mechanical passes, groups with alignment score < `llm_threshold` are
sent to `gpt-5.4-mini` for quality review.

**Current threshold: 90** (raised from 70 on 2026-05-07 to reduce LLM calls and improve speed)

Groups with mechanical score **below** threshold are sent to LLM for review.
Score range is 0–100; higher = better mechanical quality.

- threshold=90 → only low-quality groups (score < 90) go to LLM — fast, ~10–20% of groups
- threshold=70 → fewer groups pass through LLM — default before this change
- threshold=100 → all groups go to LLM — slowest, highest quality

Lower the threshold if speed matters more than quality.
Raise it (up to 100) if quality matters more than speed.

```python
# In machine-translate-docx.py:
_aligner = FASubtitleAligner(
    model='gpt-5.4-mini',   # NEVER change this model
    llm_threshold=90,
    token_budget=40_000,
)
```

---

## Bridge Detection (rows skipped)

Rows where FA is not processed:
- Empty FA cell
- Grey-shaded cell (XML shading)
- Timecode pattern: `0:03-0:23`
- Speaker tags: `(m):`, `(f):`, `Narrator(m):`
- Show markers: `HOST:`, `SHOW:`, `TITLE:`, `WEEK`, `AIRDATE`
- Technical: `BMD ####`, `Fix1`, `Fix2`, `Ball Time`
- Captions: `CAPTION:`, `VO & ONSCREEN`
- URLs: `https://`, `http://`

---

## Hard Rules (absolute, never violated)

| Rule | Description |
|------|-------------|
| H1 | Each FA chunk ≤ 50 characters |
| H2 | No triple-line. Max 2× repetition (double) |
| H3 | Text preservation — joined chunks must equal original FA (after normalization) |
| H4 | Named entities in EN row N must appear in corresponding FA row(s) |
| H5 | Sentence-end punctuation always terminates a chunk (except `...`) |
| H6 | Compound verbs stay intact — never split between parts |
| H7 | `را` stays with its noun phrase |
| H8 | ZWNJ (U+200C) preserved byte-for-byte |

---

## Validation Gates

| Gate | Type | Check |
|------|------|-------|
| G1 | HARD | Triples == 0 |
| G2 | HARD | Over-50 chars == 0 |
| G3 | HARD | Joined chunks == original FA |
| G4 | HARD | All EN named entities present in corresponding FA |
| G5 | HARD | No compound-verb splits, no detached `را` |
| G6 | WARN | Doubling ratio inside [0.25, 0.55] |
| G7 | WARN | Avg alignment score ≥ 0.6 |

G1–G5 failures block output delivery.

---

## Output

- Saved as `{original_stem}_PER_Double.docx`
- Path is derived from the **original input file**, not the timestamped upload copy
- `local_launcher.py` detects it via `_find_double_file()` and serves it as `filename2`
