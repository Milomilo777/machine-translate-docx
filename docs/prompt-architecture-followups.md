# Prompt Architecture Follow-ups (Out of Scope for v4)

> Status: pending. Captured during v4 prompt iteration on branch
> `claude/blissful-pasteur-dcab73`.
> Source: GPT-5.5 critique rounds + Claude reflection layer.
> The v4 prompt set addresses everything that can be fixed at the
> prompt layer. The items below require code changes and are deferred
> until v4 prompts are approved.

## Summary

Three architecture-level improvements surfaced during prompt iteration
but cannot be implemented purely at the prompt layer. They require
changes in:

- `src/machine_translate_docx/runner.py`
- `src/machine_translate_docx/openai_tools/polisher.py`
- `src/machine_translate_docx/openai_tools/translator.py`
- (new) `src/machine_translate_docx/validators/`
- (new) `tests/test_prompts_regression.py` + `tests/fixtures/prompts_regression/`

The v4 prompts contain stop-gap notes that reference these gaps
explicitly (e.g. "downstream validator will reject Latin residue").

---

## 1. Validator Layer (Machine-Deterministic Checks)

**Why:** Some checks are unreliable when delegated to an LLM:

- Exact line count
- Blank-line position preservation
- Latin leakage outside `ALLOWED_LATIN`
- `؛` / ASCII `;` outside protected quotes
- `باشه` / `توسط` residue
- Quote balance (`" "` only — no `«»`)
- W1–W4 protected span presence in output
- `\n` / `\t` / `%s` / `$VAR` literal preservation
- `⟨⟨N⟩⟩` tag presence and order (polish output)
- CPL budget on payload only

**Where:** `src/machine_translate_docx/validators/post_polish.py`
running after `polisher.run()`. A lighter variant
`validators/post_translate.py` runs after the translator.

**Behaviour:** On failure, the validator either:

- Re-prompts the model with a tight repair prompt — only the failing
  lines, only the failing rule.
- Or fails the job and surfaces to side-channel telemetry. No `[WARN]`
  markers or `⚠️` glyphs in output (v4 prompts already forbid those).

**Risk if skipped:** Silent contamination of broadcast subtitles with
Latin residue, missing protected spans, line-count mismatch, or `\n`
rendered as a real newline (line-count cascade failure).

---

## 2. Regression Test Suite

**Why:** Prompt v4 is large and rules interact. A fixed input set of
30–50 lines covering edge cases lets every prompt version be measured
against a stable baseline before promotion.

**Where:** `tests/test_prompts_regression.py` with fixtures in
`tests/fixtures/prompts_regression/`.

**Coverage targets (drawn from GPT-5.5 + Claude critique cycles):**

| # | Edge case | Tests rule |
|---|---|---|
| 1 | Ordinary quote with `باشه` inside | MN-4 vs LS-10 |
| 2 | Quoted EN title (W5) | W5 translation policy |
| 3 | Verbatim literary quote (scripture) | LS-10 byte-id |
| 4 | Numbers: ۳٬۰۰۰، ۱٬۰۰۰٬۰۰۰، ۲۰۲۶، S01E05، F-16 | EDIT ⑤ scope (year/code exclusion) |
| 5 | Vitamin D / H5N1 adjacent | W3 vs NOT-TECH_LOCK |
| 6 | Plain "dog" near `شخص- سگ` | SMTV coreference gate |
| 7 | Fragment with `توسط` | MN-5 prepositional path |
| 8 | Predicate with `توسط` | MN-5 active path |
| 9 | Short line: `باشه` / `AI` / `human rights` | G5 vs hygiene |
| 10 | Master speech with must/may/never | LS-7 + SA-6 |
| 11 | sky/heaven/heavenly distinct uses | SA-8 |
| 12 | `desperate` in two senses | False-friend table |
| 13 | `observe` in two senses | False-friend table |
| 14 | `urged` in three structures | Speech verb mapping |
| 15 | Semicolon inside vs outside quote | MN-6 vs LS-10 |
| 16 | Fluent FA with wrong negation | SA-1 |
| 17 | Fluent FA with invented certainty | SA-9 |
| 18 | Clean line that polish must skip | G9 |
| 19 | Bloated line that polish must compress | EDIT ⑥ |
| 20 | SAGE line — never NEWS persona | Q13 |
| 21 | EN URL in source, missing in [FA] | SA-11 PROTECTED_SPAN_PRESENCE |
| 22 | `تلویزیون استاد اعظم` → must correct | LS-11 BRAND_CHANNEL |
| 23 | already / no longer / yet aspect | SA-10 ASPECT/TIME |
| 24 | Persian sentence with Arabic `ك` / `ي` | MN-9 ORTHOGRAPHY |
| 25 | Brand name (Microsoft / Apple) | NON_WHITELIST ⑥ |
| 26 | `master chef` vs `Supreme Master` | SPIRITUAL_TITLE_GATE |
| 27 | `\n` placeholder preserved literally | W4 byte-id |
| 28 | `dramatic increase` vs `dramatic arts` | Context-aware FA map |
| 29 | Idiom `made my day` | SA-7 idiom-aware |
| 30 | `may help` vs `must help` | SA-6 modality detail |

**Behaviour:**

- Each fixture has token-level invariants (e.g. "output line N
  contains `بله` not `باشه`"), not exact-string match — LLM
  stochasticity rules out string equality.
- Tests run against `--backend mock` by default; `pytest --live` runs
  against real `gpt-5.5`.
- A new prompt version must pass ≥95% of invariants before promotion
  from `*_proposal_vN.txt` to `translate_PER.txt` / `polish_PER.txt`.

---

## 3. AUTHORING vs LOCKED Subtitle Mode (Long-Term)

**Why:** `LINE_BOUNDARY_LOCK` is the right policy when subtitle timing
is locked (production). But during initial authoring — when timing is
still being established — re-segmentation by Persian natural sentence
boundary would produce better results.

**Where:** Configuration flag in `runner.py`:

```python
runtime.subtitle_mode = "authoring" | "locked"
```

**Behaviour:**

- `authoring` mode: aligner may merge/split lines based on Persian
  sentence shape.
- `locked` mode (default, current behaviour): every line-count
  constraint applies.

**Current state:** The bilingual aligner
(`FASubtitleAligner`, `gpt-5.4-mini`) already handles re-segmentation
in a separate downstream stage, so this may be unnecessary for the
current pipeline. Re-evaluate only if aligner output quality plateaus.

---

## 4. Three Architecture-Level Critiques Already Resolved

For the record, these were raised by external critique but are
already correct in the existing code:

- **"Translator and polisher in one call"** — they are already two
  separate API calls in `runner.py`.
- **"SMTV_LEXICON not injected"** — `_smtv_locks.txt` is prepended to
  the system prompt of both engines for prompt-cache sharing
  (`openai_tools/translator.py` and `openai_tools/polisher.py`).
- **"AUTHORING_MODE for re-segmentation"** — partially handled by the
  existing `FASubtitleAligner` stage.

---

## Tracking

When v4 prompts are promoted to the canonical files
(`translate_PER.txt`, `polish_PER.txt`, `_smtv_locks.txt`), this
document moves to "scheduled for implementation". Until then, the
prompts contain stop-gap notes that reference these gaps explicitly.

## Iteration Trail

The prompt iteration files in this branch:

- `prompts/translate_PER.txt` — canonical, unchanged
- `prompts/polish_PER.txt` — canonical, unchanged
- `prompts/_smtv_locks.txt` — canonical, unchanged
- `prompts/*_proposal.txt` — v1 (first proposal, 2026-05-14)
- `prompts/*_proposal_v2.txt` — v2 (compacted, severity tags)
- `prompts/*_proposal_v3.txt` — v3 (PHASE_0_BASE, SA, LOCKED/MN split)
- `prompts/*_proposal_v4.txt` — v4 (ALLOWED_LATIN, LS-11, MN-9, SA-10/11, idiom-aware)
- `prompts/*_proposal_v5.txt` — v5 (MASTER_SPEECH fidelity tier, MN-10 NUMBER_FORMAT moved into PHASE_0_BASE, SA-12 LOGICAL_CONNECTOR, SA-13 COMPARISON_SCOPE, comma-before-number precedence, ambiguous-date Persianisation, Month D YYYY, quote title punctuation exception, URL punctuation attachment ban, SVU soft heuristic, ACRONYM-IN-PARENS pattern-bound, blank-policy reconciled with SA-11, [EN]-blank policy, idiom example "spill the beans → راز را فاش کردن")
- `prompts/*_proposal_v6.txt` — v6 — FINAL prompt iteration (MASTER EDIT ①–⑤ all skip explicit, W1–W4 → ALLOWED_LATIN consistency sweep, "start directly with translation" wording fix, SA-11 example preserves FA structure, Terminal punct example shows [FA]→BASE hygiene, locked Persian month names table, SL_TEXT sole-exception clause, reverse acronym pattern ACRONYM (Full Name), Oxford-comma clause exception, HARAKAT clarity split, MN-5 MASTER prepositional preference, SA-12/13 anchor-only constraint, MN-10 protected-span exemption)

## Next Step

After v6 approval, the prompt iteration phase ends. Next milestones:
1. Promote v6 → canonical `translate_PER.txt`, `polish_PER.txt`, `_smtv_locks.txt`.
2. Build the validator layer (Section 1) — machine-deterministic post-pass.
3. Build the regression test suite (Section 2) — 30 fixtures covering edge cases.
Further prompt rules should NOT be added until regression baseline exists.
