# Overnight debug session — 2026-05-11

Autonomous debug run launched while user is asleep. Goal: validate the
pipeline on real-world docx inputs after the 2026-05-11 src/ migration,
across engines (chatgpt-api+polish, deepl, google) and split methods
(basic, persian_double_lines), using **gpt-5.4-mini** to keep cost and
wall-clock down.

## Fixed today (before this run)

| # | Bug | Commit |
|---|-----|--------|
| F1 | `prompts/` not found after src/ migration (anchor 2 levels too deep) | `ddf7d62` |
| F2 | Health check compared raw `from_text_table` (449) vs `to_text_by_phrase_separator_table` (106) → spurious "24%" engine_empty failure | `d71f2da` |

## Open findings (pre-run)

- **F3 — translate took 286 s, polish took 3888 s (64.8 min) on the 78 KB VE file with gpt-5.5.** Unacceptable. Hypothesis: Responses API on gpt-5.x silently enables `reasoning.effort=medium` (translator log shows `reasoning_tokens=3624` — 50 % of completion). Polish runs through the same code path. C2 invariant says "no reasoning_effort on translator", but the Responses API default still spends reasoning tokens. Will retest with `gpt-5.4-mini` (per user instruction) before deciding whether to suppress reasoning explicitly.
- **F4 — distribution (basic / persian_double_lines) never calls LLM.** `split_with_algorithm()` is pure code. `llm_threshold` is already a no-op for both modes user cares about. No code change needed there.

## Test matrix

| Run | File | Engine | Split | Status | Wall-clock | Notes |
|-----|------|--------|-------|--------|------------|-------|
| T1 | sample_hyperlink.docx (28 KB) | chatgpt-polish (gpt-5.5) | basic | ✓ | 1:25 | baseline, before the F2 fix |
| T2 | AJAR 3145 (43 KB) | chatgpt-polish (gpt-5.4-mini) | basic | — | — | — |
| T3 | VE 3145 (78 KB) | chatgpt-polish (gpt-5.4-mini) | basic | — | — | — |
| T4 | AJAR 3145 | chatgpt-polish (gpt-5.4-mini) | persian_double_lines | — | — | — |
| T5 | VE 3145 | chatgpt-polish (gpt-5.4-mini) | persian_double_lines | — | — | — |
| T6 | sample_hyperlink.docx | google | basic | — | — | needs Selenium |
| T7 | AJAR 3145 | google | basic | — | — | needs Selenium |
| T8 | VE 3145 | google | basic | — | — | needs Selenium |
| T9 | sample_hyperlink.docx | deepl | basic | — | — | needs Selenium |
| T10 | AJAR 3145 | deepl | basic | — | — | needs Selenium |
| T11 | VE 3145 | deepl | basic | — | — | needs Selenium |

Findings, run outputs, and per-run notes get appended below as each test
finishes.

---
