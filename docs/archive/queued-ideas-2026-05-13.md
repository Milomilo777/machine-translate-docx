# Queued ideas — 2026-05-13

Two product ideas raised during the FLYIN-1646 long-file test session.
Both parked for future implementation, not part of this run.

---

## Q1 — Pre-translated upload → "polish-only" mode

**Idea (user, 2026-05-13):**
If the user uploads a docx that already has Persian text in column 3,
the launcher could detect that and offer a *polish-only* run instead
of re-translating. The translator would skip, the polisher would run
against the existing FA + the English from column 2, and the diff
would be highlighted (e.g. tracked-changes or coloured runs) so the
human reviewer can see only the changes.

**Why it's interesting:**
- Saves translator cost for documents already translated by a junior
  translator who just wants a senior pass.
- Shorter wall-clock — no first pass at all.
- The diff overlay is the deliverable; today the user has to compare
  manually.

**Open design questions:**
- Detection heuristic: count non-empty FA rows; if > 50 % of EN rows
  have a FA partner, treat as pre-translated.
- Output naming: `…_PER_Polish_Review.docx`?
- Diff format: python-docx `w:ins` / `w:del` tracked-changes XML, or
  coloured runs with a sidecar JSON of edits?
- UI: a checkbox in the legacy frontend ("Polish only — keep existing
  FA") shown only when FA column has content.

**Effort estimate:** M (half a day) for detection + polish-only path;
+ M for the tracked-change writer.

---

## Q2 — Soft line-break inside a single cell

**Idea (user, 2026-05-13):**
Editors sometimes mark an invisible line boundary INSIDE a cell with a
`<enter>` (newline) so the cell visually wraps without the table
having a new row. Today the pipeline treats the cell as one chunk and
the boundary is lost on save. We need to:

1. Preserve `\n` (or `\r`) inside a single source-language cell during
   parse — record the boundary positions.
2. Pass them to the translator as a hint ("break the FA at the same
   relative positions") OR pass each fragment as its own atomic unit.
3. Re-emit the boundary in the FA cell on save.

**Example:**
```
EN cell:                       FA cell expected:
"in so many numbers            "آنگاه مردم به این تعداد نمی‌میرند.
 like that.
 (Qm: Yes, Master. Yes.)"        (بله، استاد. بله.)"
```

**Why it's interesting:**
- Today the pipeline merges the two fragments into one FA string and
  the visual boundary disappears.
- Affects every long-conference doc where speaker tags are embedded.

**Open design questions:**
- Should each fragment translate independently or as one block with
  preserve-newline instruction?
- Polisher contract: keep `\n` byte-for-byte in output?
- Aligner: should each fragment count as its own row for the
  ≤ 48-char rule, or use the whole cell budget?

**Effort estimate:** M (parser changes in docx_io/parse.py) + S
(translator / polisher prompt update) + S (aligner awareness).

---

## Notes on timing

The "60-minute polish" figure from the gpt-5.5 baseline run on 2026-05-11
is the same workload — translator + polisher — that gpt-5.4-mini does in
~1:30. Polish dominated. With `reasoning=none` on the larger model (F3
fix) and `reasoning=medium` on mini (current default), wall-clock dropped
~12×.

The 60-minute number is **not acceptable** as a steady state. The plan
is:
1. Stay on `gpt-5.4-mini` for routine work.
2. Run gpt-5.5 only on documents where the mini output failed manual
   review.
3. Once F8 (polish-modify-rate mismatch) and the aligner edge cases
   are closed, time the gpt-5.5 path again with `reasoning=none` and
   the trimmed phase-1 prompts. The expected wall-clock should drop
   well under 20 minutes for a typical 100-line document.
