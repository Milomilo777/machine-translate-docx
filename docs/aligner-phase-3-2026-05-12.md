# FA aligner — phase-3 (hybrid mechanical + LLM rescue) — 2026-05-12

Mechanical-only stays the default (threshold 0); the new LLM-rescue
path fires when a group is genuinely hard. Calibrated on real Google-Drive
docx (BMD 1322 + CTAW 1800 + CTAW 2038, 1124 FA rows / 415 sentence groups).

## API

```python
aligner = FASubtitleAligner(
    model='gpt-5.4-mini',   # mini only — we never spend reasoning on this
    llm_threshold=0,        # 0..100 (see below)
)
stats = aligner.align(input_docx, output_docx)
```

`llm_threshold` semantics:
- **0**: pure mechanical (default; every existing run is byte-identical with
  pre-phase-3 master output).
- **40** (recommended): LLM rescues only the hardest groups (~2 % of groups
  on the bench corpus). long-line count drops ~15 %, doubles stay in the 50 %
  band, total wall-clock ≈ +2 min on a 1000-row document, cost a few cents.
- **100**: LLM fires on every group with score > 0.

The aligner invokes the LLM when ``group_difficulty_score >= 100 - llm_threshold``.

## Difficulty scoring

For each group post-mechanical pass:

| Signal | Score |
|--------|-------|
| Each over-MAX_CHARS chunk | +60 |
| Each chunk ≥ 44 chars (tight) | +15 |
| Each chunk 40–43 chars (dense) | +6 |
| Each chunk ≤ 6 chars (orphan) | +15 |
| Triple-repeat run (≥3 identical rows) | +30 |
| Length spike vs median (forced merge) | +8 |
| Truncation tail (≥2 trailing empties) | +12 |

Capped at 100.

## Bench results

Corpus: 3 real Persian-translated subtitle docx (BMD 1322, CTAW 1800,
CTAW 2038). Total 1124 FA rows, 415 sentence groups.

| Threshold | Doubles | Long (>44) | Tight (≤6) | LLM fires | Tokens | Wall-clock |
|-----------|---------|------------|------------|-----------|--------|------------|
| 0         | 232 (56 %) | 160 | 4 | 0  | 0      | 4 s   |
| 30        | 224 (54 %) | 146 | 5 | 4  | 7 314  | 60 s  |
| **40 ★** | 217 (52 %) | 136 | 7 | 8  | 17 837 | 125 s |
| 50        | 209 (50 %) | 109 | 6 | 17 | 27 556 | 129 s |
| 60        | 192 (46 %) | 103 | 7 | 31 | 47 105 | 251 s |

Sweet spot is **40** — past it the LLM starts breaking doubles in
exchange for diminishing long-line wins.

## LLM contract

The rescue call uses:
- model = `gpt-5.4-mini`
- `reasoning.effort = low` (fast; the task is mechanical re-splitting)
- `prompt_cache_retention = 24h` on the system block
- timeout 120 s, shared `call_with_retry()` retry policy

System prompt: hard rules — exactly N rows, ≤48 visible chars each,
content-preservation, no preposition strands, no compound-verb split,
protected-idiom respect. Output validated client-side before being
accepted; on validation failure we fall back to the mechanical rows
(no silent corruption).

`en_parts` is now collected per group during parsing and passed to the
LLM as context — it never edits the FA from EN, it only uses EN to
judge phrase boundaries.

## Frontend (legacy)

`index.ejs` slider now labels:
- 0  — mechanical only (fast, no cost)
- 40 — balanced (recommended)
- 100 — model-driven (slow)

Slider only shows when Split Method = Persian Double Lines.

## What did NOT change

- Default behaviour: `threshold=0` is byte-identical with the pre-phase-3
  master. No silent quality regression on existing workflows.
- The mechanical splitter itself still drives every group. The LLM only
  rewrites a small minority that the score flags as rough.
- A12 tolerance (≤1 % over-limit accepted as [WARN], more as [FAIL])
  stands; phase-3's distribute-loop break already drives over_limit to 0
  on the bench corpus.

## Future

- Per-document adaptive threshold (start low, raise if mechanical pass
  produces many long lines).
- Cache LLM rescues across identical input groups in a single run.
- Optional `--with-proofread` third pass (FA-only, separate prompt) per
  the prompt-rewrite roadmap; not part of this phase.
