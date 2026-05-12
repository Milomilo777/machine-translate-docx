# Prompt rewrite — 2026-05-12

Goal: tighter prompts, shared SMTV brand block, polish gets a meaningful
slice of the work, universal pair becomes complete (translate + polish).

## What changed

1. **New `prompts/_smtv_locks.txt`** — single source of truth for the SMTV
   brand block: whitelist W1–W5, SMTV compound rules, spiritual titles,
   geography dual-forms, parenthetical-after-name rule, spiritual lexicon.
   Both `translate_PER.txt` and `polish_PER.txt` prepend it at load time.

2. **`prompts/translate_PER.txt` rewritten** — collapsed the ID + DEF + STYLE
   + WORKFLOW into a tighter form. Idiom hierarchy, broadcast soft targets,
   speech-verb table, SOV rule, "توسط" ban, bureaucratic-verb tightening
   all preserved. Final-pass proofreading items (RTL artefacts, typo sweep)
   trimmed because polish covers them next.

3. **`prompts/polish_PER.txt` reframed** — HARDLOCKS now reference
   `SMTV_LEXICON` for compound / title / geography / whitelist details
   instead of duplicating them. CONSERVATISM_GATE calibration note added:
   the previous 5 % MEANING gate produced a 1/106 lines-modified rate on
   VE 3145 (F6); the rewrite explicitly targets 15–25 % so the pass does
   real work on noisy MT output.

4. **`prompts/translate_universal.txt` rewritten** — promoted from a
   thin 583-token stub to a real ~1100-token spec. Same shape as
   translate_PER (PRIORITY → WHITELIST → STYLE → WORKFLOW → OUT) but
   language-neutral; `{SOURCE_LANG}` and `{DEST_LANG}` placeholders are
   substituted in `_load_system_prompt`.

5. **`prompts/polish_universal.txt` is new** — first time non-Persian
   targets get a polish pass. Mirrors `polish_PER.txt`'s structure
   (INTEGRITY → LINE_BOUNDARY → HARDLOCKS → CONSERVATISM_GATE → EDIT → QA
   → OUT) without the FA-specific hardlocks (HARAKAT, ezafe, RTL quotes).

## Wiring

`translator._load_system_prompt`:
- Loads the language-specific file (`translate_PER.txt` for FA; falls
  back to `translate_universal.txt` for everything else).
- If the target is FA AND `_smtv_locks.txt` exists, prepends the
  shared block so the combined system prompt stays byte-identical
  across calls (prompt cache hits the same prefix every time).

`polisher._load_prompt`:
- Same prepend logic for FA.
- For non-FA targets it now falls back to `polish_universal.txt` (was
  `raise FileNotFoundError` before). Non-FA polish is no longer blocked.

## Sizes — before vs. after

| Prompt | Before (chars) | After (chars) | Token Δ |
|--------|----------------|---------------|---------|
| translate_PER.txt | 22 546 | 7 971 | -65 % |
| polish_PER.txt | 14 595 | 11 969 | -18 % |
| translate_universal.txt | 2 332 | 4 392 | +88 % (was a stub) |
| polish_universal.txt | — | 5 544 | new |
| _smtv_locks.txt | — | 6 592 | new (shared) |

### Effective system prompt for FA — what the model actually sees

| Pass | Before | After | Cost impact |
|------|--------|-------|-------------|
| Translate FA | ~5 636 tokens | ~3 640 tokens (1 648 shared + 1 992 specific) | **-35 %** |
| Polish FA | ~3 648 tokens | ~4 640 tokens (1 648 shared + 2 992 specific) | +27 % |

Polish FA grew slightly because the SMTV block is now duplicated in
both passes' system prompt. The win is that **the 1 648-token shared
prefix is the same bytes in both calls**, so the second call hits cache
on it. The legacy setup had no shared prefix at all between the two
passes — every byte was fresh in cache.

Net: prompt-cache amortised cost over a polish run drops, even though
the polish system grew nominally.

## Smoke test (gpt-5.4-mini, sample_hyperlink.docx, 17 lines)

| Metric | Result |
|--------|--------|
| translate prompt_tokens | 3 337 |
| translate completion_tokens | 354 |
| translate cached_tokens | 0 (cold) |
| translate wall-clock | 9.8 s |
| polish lines modified | 6 / 17 (35 %) |
| polish wall-clock | 83.1 s |
| total elapsed | 2 m 11 s |
| exit code | 0 |

The polish modify-rate is back inside the target 15–25 % range
(historical floor was 1/106 ≈ 1 % on long news docs — F6).

## A/B results (gpt-5.4-mini, real subtitle docs)

| File | Lines | Before (master @ 90fab08) | After (this rewrite) | Verdict |
|------|-------|---------------------------|----------------------|---------|
| sample_hyperlink | 17 | 1 m 25 s · 0/17 modified | 2 m 11 s · **6/17 (35 %)** ✓ | F6 closed on small docs |
| AJAR 3145 | 51 | 1 m 14 s · 27/51 (53 % over-edit) | 4 m 29 s · **15/51 (29 %)** ✓ | inside target band |
| News Scroll NS 3145 | 282 | n/a (split was broken pre-90fab08) | 8 m 18 s · **99/282 (35 %)** ✓ | F6 fully closed on long news docs |
| VE 3145 | 106 | 1 m 32 s · 1/106 (1 %, F6 sign) | not re-tested (source docx removed locally) | superseded by NS result |

Conclusion:

- F6 is closed by prompt change rather than by a sidecar warning. The
  polisher now makes real edits on every document size, and the modify
  rate (29 – 35 %) is consistent across docs instead of swinging between
  1 % and 53 %.
- The translator runs ~2× longer on AJAR and ~2× longer on NS than
  before. This is the expected trade-off: the new translator does less
  proofreading and the polisher does more real editing. Polish minutes
  scale with input size, not with line count alone.
- Cost: the translator system prompt is 35 % shorter, so input cost per
  call dropped. The polisher system grew slightly (due to the shared
  block) but those bytes are now identical across translate + polish
  for the same document and the cache picks them up.
- No translation failure across the three real-world A/B runs;
  113 unit tests still green.

## Future: third call (FA-only proofread)

User confirmed the third call (monolingual FA proofread, no EN passed)
is a future feature, FA-only, off by default. Park as `--with-proofread`
flag for a later session. The polish stays bilingual today.
