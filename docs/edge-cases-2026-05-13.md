# Edge-case test session — 2026-05-13

Six synthetic docx files were generated and run through the full
pipeline (gpt-5.4-mini, basic split, with polish at reasoning=low).
Goal: surface any silent crash, silent corrupt-output, or unfriendly
failure mode on inputs the production tests don't normally cover.

## Setup

Fixtures created under `%TEMP%`:

| Name | Shape |
|------|-------|
| `edge_single.docx` | 2-row table, 3 cols ("1 / Hello", "2 / World") |
| `edge_header_only.docx` | 1 header-row table, 3 cols |
| `edge_mixed.docx` | 3 rows, EN column carries URL + bash command + Latin tokens |
| `edge_notable.docx` | no tables; plain paragraphs only |
| `edge_empty.docx` | a 0-row table |
| `edge   ( weird ) - filename.docx` | weird name with spaces and parens |

## Results

| Test | Exit | Outcome | Verdict |
|------|-----:|---------|---------|
| `edge_single` | 20 | `[FAIL] reason=engine_empty` (post-translate health check) | Acceptable. The pipeline expects an SMTV-shaped table with the EN column at index 2 and font / shading conventions; a hand-built `python-docx` table is detected as table but the engine sees no translatable cells. The failure is structured and the user is told why. |
| `edge_header_only` | 20 | same as above | Acceptable. |
| `edge_mixed` | 0 | Translator + polish ran cleanly on a 3-row table where the EN column had a URL, a bash command, and Latin tokens. | ✓ Output OK. URL kept byte-id (whitelist W1), bash command Persianised. |
| **`edge_notable`** | **1 → 20** | **CRASHED on `IndexError`. FIXED in this commit.** | **E1 new finding.** `parse.py:110` indexed `docxdoc.tables[0]` without a presence check. Fixed: raise `EmptyDocxError` with a clear message; exit 20 like every other no-input failure. |
| `edge_empty` | 20 | `[FAIL] reason=empty_docx` | Acceptable. |
| `edge   ( weird ) - filename` | 20 | parsed file fine (the weird name OK), then same `engine_empty` as `edge_single` | Acceptable for the same reason as `edge_single`. The weird filename did NOT cause any file-system issue. |

## New finding — E1

**Severity:** Low (defence-in-depth)
**Category:** Reliability
**Location:** `src/machine_translate_docx/docx_io/parse.py:110`

A docx with zero tables previously crashed the pipeline with
`IndexError: list index out of range`. The user got a stack trace,
not a structured failure.

```python
docx.word_translation_table_length = len(docxdoc.tables[0].rows)
```

Fixed by checking `if not docxdoc.tables:` first and raising
`EmptyDocxError("...no tables — pipeline expects an SMTV-shaped (No. |
EN | FA) table.")`. The launcher catches that as
`[FAIL] reason=empty_docx` and the job ends gracefully.

## What about the SMTV-table detection gap?

`edge_single` and `edge_header_only` failed with `engine_empty` because
the parser's column-2 scan returned empty content for every row. The
table existed but didn't match the SMTV format the pipeline expects.
This is **by design** — the production input always comes from the SMTV
template — but it would be worth a `[WARN]` print line explaining the
expectation when the parser sees a 3-column table whose middle column
is empty. **Parked**, not a blocker.

## Cancellation, parallel jobs, and restart paths

These three were originally listed as edge cases but require a live
launcher and an interactive user, not a one-shot CLI run. Quick code
review:

- **Cancellation mid-polish:** `local_launcher.py:cancel_job` sends
  SIGTERM / TerminateProcess to the job's `subprocess.Popen`. The
  polish call uses `timeout=1800` and respects standard signal
  delivery. C3 (audit 2026-05-13) closed the related race: a late
  `update_job` from the stdout reader no longer KeyError's when
  the job entry has already been popped. Manual test recommended
  next session; no code defect found this pass.

- **Parallel jobs:** `_MAX_CONCURRENT_JOBS = int(os.environ.get(
  "MTD_MAX_CONCURRENT_JOBS", "2"))` and a `threading.Semaphore`
  caps active subprocesses. The third upload waits at `acquire()`.
  Status reads use `self.state.lock`. No new defect found.

- **Restart mid-job:** uploads land in `uploads_dir`, the job entry
  is in-memory only (no persistence layer). A launcher restart loses
  the in-flight job state but the partial output (if any) stays on
  disk. **Parked** — building a job-state journal is a feature, not
  a fix.

## Bench rerun

`tools/aligner_bench.py` on the BMD + CTAW corpus after the parse-time
guard: 232 doubles / 0 over_limit (unchanged). 113 unit tests still
green.
