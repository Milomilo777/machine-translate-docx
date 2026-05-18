# FA Aligner — Corpus Baseline (2026-05-17)

These files are the empirical baseline the FA-aligner phase-3 rewrite was tuned against. They were extracted from 562 human-edited bilingual EN/FA broadcast docx files (BMD, NS, CTAW, AJAR, HL, VE, AW, …) inside `E:/00 Google Drive- All Translation files/`.

The aligner code lives in
`src/machine_translate_docx/openai_tools/persian_double_lines.py`.
Reusable extraction scripts live in `notes/scripts/` (gitignored — local-only).

## File map

### Phase-2 baseline (152 files, ~77K rows)

| File | What it is |
|------|-----------|
| `summary.json` | Per-folder + global stats: row counts, group counts, doubling ratio, char-length distribution, cut-after-punct distribution |
| `pre_count.tsv` | Frequency of tokens that appear immediately BEFORE a human cut point — drove the `DANGLING_PREPS` list decisions |
| `post_count.tsv` | Frequency of tokens that appear immediately AFTER a human cut — drove `LEADING_CONJUNCTIONS` / `LEADING_PREPS` |
| `bigram_top.tsv` | The 300 most frequent `(prev, next)` bigrams that human cuts ran through |
| `bigram_summary.json` | Bigram-extract pass summary |
| `dangling_in_pre.tsv` | How often each member of the current `DANGLING_PREPS` set actually appears in pre-cut position — guided which entries to keep vs drop |
| `leading_missing.tsv` | Post-cut tokens that were NOT in `LEADING_CONJUNCTIONS` — drove the +8 additions in v7.2 |
| `trailing_punct_dist.tsv` | Punctuation right before each cut (none / `،` / `:` / `.` / `؟` / …) |
| `char_length_dist.tsv` | Histogram of FA-cell display-char lengths |
| `group_size_dist.tsv` | Histogram of how many rows each phrase-group spans |
| `bigram_protection_eval.json` | For each candidate protected bigram: intact-occurrences vs broken-occurrences across the corpus — drove the +22 additions to `PROTECTED_BIGRAMS` |

### Phase-3 deep-dive (562 files, ~237K rows)

| File | What it is |
|------|-----------|
| `advanced_patterns.json` | Specifically tracked citation patterns (`(Reuters)`, `(VnExpress)` …), midline parens, midline dots, bracketed `[Türkiye]` tokens, quoted-name lengths, NS-country-opener patterns |
| `sage_summary.json` | 250-file BMD-only SAGE register study: speech-verb frequencies (`گفت` 2887 vs `فرمودند` 7 — the finding that drove the SAGE_PERSONA block in polish_PER.txt v7.4) |

### Aligner benchmarks

| File | What it is |
|------|-----------|
| `benchmark_summary.json` | 66-file held-out benchmark of the aligner — row exact match, over-limit count, triple runs, citation preservation, midline-no-double rate |
| `llm_rescue_summary.json` | 47-group hard-case study comparing pure-mechanical vs `llm_threshold=40` gpt-5.4-mini rescue (mechanical 7.5 % exact match → LLM-rescue 30.75 %) |

## Headline numbers from this baseline

```
Phase-3 totals
  files inspected      562
  FA rows analysed     236 967
  citations matched      5 697   (own-row 54.3 %, text+citation 45.7 %)
  midline parens         4 332
  midline dots          10 028

Aligner regression benchmark (66 held-out files)
  citation_preserved_pct   100.0
  over_limit_rows              0
  triple_runs                  0
  row_match_total_pct       70.1
  midline_paren_no_double   93.3
  midline_dot_no_double     96.7

Cost / quality of LLM rescue on hard groups
  mechanical exact_match    7.5 %
  LLM rescue exact_match   30.75 %
  tokens used               67 562   (~ 2 cents at gpt-5.4-mini rates)
```

## How to regenerate

The 6 MB raw `split_pairs.tsv` (one row per human cut point with surrounding context) was excluded from this snapshot because it is large and easily rebuilt. Run:

```
PYTHONPATH=src python notes/scripts/aligner_corpus_analysis.py
PYTHONPATH=src python notes/scripts/bigram_extract.py
PYTHONPATH=src python notes/scripts/bigram_protect_check.py
PYTHONPATH=src python notes/scripts/patterns_advanced.py
PYTHONPATH=src python notes/scripts/sage_bmd_corpus.py
```

Each script writes its results back into `notes/scripts/aligner_corpus_data/`, `notes/scripts/sage_corpus_data/`, and (for the benchmarks) `notes/scripts/benchmark_data/`.

## Why this file set was committed

Two reasons:

1. **Reproducibility of the aligner-phase-3 decisions.** Every list expansion (`LEADING_PREPS`, `PROTECTED_BIGRAMS`, the «که» removal from `DANGLING_PREPS`, the citation `_split_citation` heuristics) traces directly back to a frequency in one of these files. Anyone reviewing the aligner code later can verify the empirical basis without re-running the full extraction.

2. **Future tuning anchor.** When the corpus shifts (new programs, new editor conventions), re-running the scripts and diffing against these baselines is the fastest way to spot drift.
