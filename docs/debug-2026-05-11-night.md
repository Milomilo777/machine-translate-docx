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
| T2 | AJAR 3145 (43 KB) | chatgpt-polish (gpt-5.4-mini) | basic | ✓ | 1:14 | translate 16.7s, polish 23.3s, reconciler gave up after 2 attempts (got 90 want 51) — F5 |
| T3 | VE 3145 (78 KB) | chatgpt-polish (gpt-5.4-mini) | basic | ✓ | 1:32 | translate 28.1s, polish 32.7s, **only 1/106 lines changed** (vs 27/51 on T2) — F6: mini polish very weak on this file |
| T4 | AJAR 3145 | chatgpt-polish (gpt-5.4-mini) | persian_double_lines | ⚠ | 0:46 / 1:23 (T4c) | F7a (suffix) + F7b (split_engine binding) fixed in `01b3669` — T4c verified `_Polish_Double_Lines.docx`. **F7c open**: `FASubtitleAligner` still never invoked from cli.py — distribution falls through to `split_with_algorithm()`. Suffix is now correct but the actual double-line aligner pass is not running. F8 (polish "refined 51 lines" but file unchanged) still open. |
| T5 | VE 3145 | chatgpt-polish (gpt-5.4-mini) | persian_double_lines | ⚠ | 1:16 / 1:42 (T5c) | T5c verified `_Polish_Double_Lines.docx` after F7a+F7b fix. Same F7c open (aligner not invoked, basic algorithm used). |
| T6 | sample_hyperlink.docx | google | basic | ✓ | 0:18 | Chrome headless OK |
| T7 | AJAR 3145 | google | basic | ✓ | 0:35 | clean |
| T8 | VE 3145 | google | basic | ✓ | 1:05 | clean |
| T9 | sample_hyperlink.docx | deepl | basic | ✓ | 0:36 | clean |
| T10 | AJAR 3145 | deepl | basic | ✓ | 1:44 | clean |
| T11 | VE 3145 | deepl | basic | ✓ | 3:52 | clean |

Findings, run outputs, and per-run notes get appended below as each test
finishes.

---

## Final summary (post-run)

### Outputs delivered (all next to source file in `Downloads/00 Translation Files/`)

| File | Outputs |
|------|---------|
| AJAR 3145 | `_PER_Polish.docx`, `_PER_Polish_Double_Lines.docx` (T4c), `_PER_Google.docx`, `_PER_Deepl.docx` |
| VE 3145   | `_PER_Polish.docx`, `_PER_Polish_Double_Lines.docx` (T5c), `_PER_Google.docx`, `_PER_Deepl.docx` |

### Fixes committed

| Commit | What |
|--------|------|
| `ddf7d62` | F1: prompts/ search reaches project root after src/ migration |
| `d71f2da` | F2: health-check compares phrase-grouped source vs target (no more false "24%" failures) |
| `[engine_suffix]` | F7a: append `_Double_Lines` when `split_engine == 'persian_double_lines'` |
| `01b3669` | F7b: snapshot `--splitengine` value onto `ctx.flags.split_engine` (was a no-op before) |

### Still open — needs user review

- **F3 — gpt-5.5 + Responses API spends huge reasoning tokens on translator+polisher.** First VE run with gpt-5.5: translate 286 s + polish 3888 s (64.8 min). The translator response showed `reasoning.effort=medium` and `reasoning_tokens=3624` (50 % of completion) even though the project invariant C2 says "no reasoning_effort on translator". The Responses API appears to enable reasoning by default on gpt-5.x; the explicit suppression that exists for chat.completions doesn't reach it. **Recommendation:** add `reasoning={"effort": "minimal"}` to the Responses API call in `translator.py` (and `polisher.py` when not the mini model). With gpt-5.4-mini the same files complete in 1:14 – 1:55, so the regression is gpt-5.5-specific.
- **F5 — reconciler doesn't converge on AJAR 3145.** Translator returned 90 lines for 51-line source; reconciler asked twice and got 90 both times, then padded/truncated. Output still saved, but means subtitle lines may be mis-aligned. Likely a prompt issue in the reconciler — it should split paragraphs back to one-line-per-row but mini is over-segmenting.
- **F6 — gpt-5.4-mini polish very weak on VE (1/106 lines changed).** AJAR got 27/51 ≈ 53 %, VE got 1/106 ≈ 1 %. Different docs, very different rates — suggests the polish prompt is sensitive to input phrasing. Worth a prompt review.
- **F7c — `FASubtitleAligner` is exported but never invoked.** `grep FASubtitleAligner src/machine_translate_docx/cli.py` returns one *comment* and the import is absent at run-time. The persian_double_lines pipeline today goes through the same `split_with_algorithm()` as basic split — only the filename suffix differs. The aligner module itself (mechanical v2.0) is intact; what's missing is the wire-up in cli.py: after translation but before save, when `ctx.flags.split_engine == 'persian_double_lines'`, call the aligner to expand each row into the bilingual double-line layout. Needs a careful re-read of the phase-9/15 roadmap to put the hook back in the right place.
- **F8 — polish reports "refined N lines" but file shows NO CHANGE.** Seen on T4 (51 lines reported refined, but `[DIAG] Polish: NO CHANGE (check for API error above)`). Suggests the polisher accepts the model output, then later the cell-write step doesn't pick it up — or the diff comparison itself is wrong (model returns identical-looking polished text that fails the `before == after` check because of an invisible character difference?). Worth a closer look at `chatgpt_api.py` around the `_before_polish == full_translated` check.

### Process / output issues (not bugs in production code)

- Three scratch `sample_test_*.docx` and stray output files were accidentally committed during this session and removed in follow-up commits — pattern to watch.
- Background tasks piped through `| tail -N` buffered output until process exit. For multi-hour runs, log straight to a file. Captured this as a tooling note, no code change.

---

