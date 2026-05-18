# cli.py shrink — Sprint D handoff prompt for Claude Code Console

> **Status (2026-05-17 — ALL SPRINT D TASKS COMPLETE, merged to master):**
> Task A.4 (`run_statistics`), Task A.5 (`get_robot_usage_comment`),
> Task B (Google file-mode workers), and Task C (`_sync_globals_from_ctx`
> collapse) are all **DONE**. `_sync_globals_from_ctx` was deleted on
> 2026-05-17 in Sprint D-C slice 6 after the 176 bare-name reads were
> threaded through ctx across 6 atomic slices. Merge commits on master:
> `44c9f76` (D-A/B), `28512c3` (cache refactor + D-C partial + P2/P3),
> `5408f80` (D-C complete + P2/P3 round 2). Archive tags:
> `archive/2026-05-16-cli-shrink-sprint-d-final`,
> `archive/2026-05-16-cache-d-c-p2`,
> `archive/2026-05-17-sprint-d-c-complete`.
>
> This document is preserved as a historical record of the planning
> work. The threading-priority map and slice breakdown lives in
> `docs/session-state-2026-05-16-bridge-collapse.md`.
>
> `cli.py` is now **2,670 lines** (down from 3,947 at the start of
> this branch, and 4,395 since the original shrink began). Test
> suite: 239 passed / 8 skipped (live) / 6 deselected. Smoke
> (chatgpt-polish FA on `sample_hyperlink.docx`) green on every
> commit, C13 cols 0+1 byte-identical.
>
> **Previous status (Sprint D attempt 1, superseded):** Sprint D was
> attempted on `refactor/cli-py-sprint-d` but only the smallest
> helper (`local_time_offset`, −10 lines) extracted cleanly. The
> material below the line ruled the section below originally; the
> "pending" markers are now obsolete for A.4 / A.5 / B.

The big-payoff blocks are deferred to a follow-up session because they
need careful state-threading work that's not worth doing under time
pressure in this branch. Each task below is **self-contained** — start
a fresh Claude Code Console session, paste the task you want to run,
and it should have everything it needs.

---

## Task A — Extract the statistics + report cluster (~900 lines)

### Why this is the next biggest payoff

Five functions in `cli.py` make up the end-of-run statistics + report
cluster. They're print-heavy / log-write-heavy, run only after
translation succeeds, and never feed back into the translation
pipeline. Extracting them collapses ~900 lines into a thin shim.

| Function | Current line | Lines | What it does | Status |
|---|---|---|---|---|
| `local_time_offset` | ~3072 | 14 | tz-offset helper | ✅ extracted to `statistics.py` (Sprint D attempt 1) |
| `run_statistics(ctx)` | ~3076 | 232 | per-run stats dump + HTTP POST | ✅ extracted to `statistics.py` (Sprint D-A.4, commit `69bb2c5`) |
| `get_robot_usage_comment(ctx)` | ~3306 | 370 | HTML report builder | ✅ extracted to `statistics.py` (Sprint D-A.5, commit `0bcbdfd`) |
| `print_console_docx_file_translated(ctx)` | ~2965 | 107 | save-time progress reporter | ❌ **DO NOT extract** — it writes to cells (cell_set_1st_paragraph + cell_add_paragraph), it's part of the write-path, not stats |

(Line numbers approximate — file is mid-flux. Use Grep to find current
positions.)

**Important finding from Sprint D attempt 1:**
`print_console_docx_file_translated` was previously listed as
extraction-eligible, but reading the body shows it writes into
`ctx.docx.table_cells[*][2]` via `cell_set_1st_paragraph` and
`cell_add_paragraph`. It is not a reporting function despite the name —
it's the non-split write path. Leave it in cli.py until D-C threads its
remaining globals.

### Globals the historical bodies still read by bare name

- `xtm` — XlsxTranslationMemory singleton.
- `xlsxreplacefile`, `xlsxreplacefile_name` — CLI flag mirrors.
- `from_text_table`, `to_text_by_phrase_separator_table`,
  `to_text_by_phrase_table`, `translation_result_using_separator` —
  parallel arrays on `ctx.docx` (also mirrored to module scope by
  `_sync_globals_from_ctx`).
- `start_time`, `end_time`, `elapsed_time` — wall-clock anchors set
  in `main()`.
- `dest_lang`, `dest_lang_name`, `src_lang`, `dest_font` — language
  fields, also on `ctx.language`.
- `splitonly` — flag, also on `ctx.flags`.

### Suggested approach

1. Create `src/machine_translate_docx/statistics.py`.
2. Move all four functions with **explicit-argument signatures** —
   read everything off `ctx` where possible, and pass the few
   remaining globals (`xtm`, `xlsxreplacefile`, `start_time`,
   `end_time`) as keyword arguments to the public entry points.
3. Keep thin shims in `cli.py` that read the module-level globals
   and forward them, so the call sites in `main()` don't need to
   change (parallel to the pattern already used for
   `save_docx_file`, `write_destination_language_in_docx_cell`,
   `write_translation_log`).
4. Run `pytest tests/ --ignore=tests/test_v2_e2e.py` after every
   function. Expected: still 154 passed.

### Verification

- `pytest tests/ --ignore=tests/test_v2_e2e.py` — must stay at 154
  passed.
- Smoke test (manual, only if you want to be paranoid):

  ```
  PYTHONPATH=src E:\Python311\python.exe -m machine_translate_docx.cli \
      --docxfile tests/fixtures/sample_hyperlink.docx --destlang fa \
      --engine chatgpt --enginemethod api --aimodel gpt-5.4-mini \
      --with-polish --silent --exitonsuccess
  ```

  The run should finish with `Saved file name:` and the log JSON
  sidecar should appear under `Log json file/`.

### Expected line drop

cli.py 3,994 → ~3,100 (-22%).

---

## Task B — Extract the Google file-mode workers (~800 lines)

### Why this matters less

Google's "file-mode" engines (`enginemethod=textfile` /
`htmljavascript` / `xlsxfile`) translate the whole document by
uploading it to translate.google.com instead of textarea-translating
phrase-by-phrase (`singlephrase`) or block-by-block (`phrasesblock`).
They work but are rarely chosen — default is `singlephrase`. The
upside of extracting them is ~800 lines out of cli.py; the downside is
this code touches a lot of state and the risk of subtle regression is
real.

### Functions to extract together

| Function | Lines |
|---|---|
| `selenium_chrome_google_translate_text_file(ctx, text_file_path)` | ~82 |
| `selenium_chrome_google_translate_html_javascript_file(ctx, html_file_path)` | ~158 |
| `selenium_chrome_google_translate_xlsx_file(ctx, xlsx_file_path)` | ~140 |
| `get_last_downloaded_file_path()` | ~46 |
| `generate_html_file_from_phrases_for_google_translate_javascript(ctx)` | ~100 |
| `generate_text_file_from_phrases(ctx, text_file_path)` | ~54 |
| `generate_xlsx_file_from_phrases(ctx, xlsx_file_path)` | ~80 |
| `google_translate_from_text_file(ctx)` | ~16 |
| `google_translate_from_html_javascript(ctx)` | ~18 |
| `google_translate_from_html_xlsxfile(ctx)` | ~15 |

### Suggested approach

1. Create `src/machine_translate_docx/engines/google_file_modes.py`.
2. Move all ten functions together — they form one coherent
   sub-system. Most already take `ctx` so the signatures stay clean;
   the file-generators need access to `dest_lang`, `src_lang`,
   `from_text_table`, `xtm` (XlsxTranslationMemory) — pass as kwargs.
3. Re-export the three top-level dispatchers
   (`google_translate_from_text_file` /
   `google_translate_from_html_javascript` /
   `google_translate_from_html_xlsxfile`) from `engines/__init__.py`
   so `translate_docx` in cli.py imports them cleanly.
4. **DO NOT** delete the cookies-consent helper from
   `engines/google.py` — it's shared.
5. Run pytest after the move.

### Verification

- pytest — must stay at 154 passed.
- (Optional) Live smoke test with `--engine google --enginemethod
  textfile` against a small docx. Note: textfile mode needs Chrome
  + internet access.

### Expected line drop

cli.py 3,100 → ~2,300 (-26% on top of Task A).

---

## Task C — Collapse `_sync_globals_from_ctx`  **(deferred 2026-05-16)**

> Audit on `refactor/cli-py-sprint-d-final` found **176 bare-name
> occurrences across 41 mirrored names** in cli.py — too large for
> a single safe session under the pytest+smoke-per-change discipline.
> The full count map and recommended threading order live in
> `docs/session-state-2026-05-16-sprint-d-complete.md`.

### What it currently does

`_sync_globals_from_ctx(ctx)` (in cli.py, ~line 453, ~75 lines) is a
Phase H bridge that mirrors every public field of `ctx.docx`, plus a
handful from `ctx.language`, `ctx.browser`, and `ctx.openai`, onto the
cli.py module namespace. It's called **6 times** in `main()` at
pipeline boundaries.

The mirror exists so legacy helpers can read bare names like
`from_text_table` or `dest_lang` without having to thread ctx through
every callee. After Tasks A and B, the surviving callers of these
bare-name globals are:

- Whatever's left of the cell-write helpers and the few `cell_*`
  shims (`cell_set_1st_paragraph`, `cell_add_paragraph`,
  `change_cell_font` — all 1-line shims that read `dest_lang`,
  `dest_font`, `rtlstyle`).
- `prepare_and_clear_cell_for_writing` (reads `dest_lang`,
  `rtlstyle`).
- `split_phrases` (reads several config globals).
- `is_*_line` predicates (read `eol_array`, etc.).

### Suggested approach

1. Audit each remaining bare-name read with Grep against the cli.py
   source (`grep -nE '^\s*(if|=|return|print).*\b<name>\b' cli.py`).
2. For each helper that the audit catches, rewrite the function
   signature to take the relevant value(s) as kwargs.
3. Update the cli.py callers to pass the values.
4. Once **all** bare-name reads have been re-routed, delete
   `_sync_globals_from_ctx` and the 6 call sites in `main()`.

### Verification

- pytest — must stay at 154 passed.
- Live smoke test of at least 2 engines (chatgpt-polish + google)
  with the hyperlink fixture, because globals removal is the kind
  of refactor that breaks subtly under specific engine paths.

### Expected line drop

`_sync_globals_from_ctx` itself: -75 lines. Plus another ~30 from
collapsing the cell shims into direct module imports.

---

## Final state target

After Tasks A + B + C, `cli.py` should be **~2,000 lines** (down from
the 4,395 it started at — a 55% reduction). The file would then be:

1. Module setup + signal handling + atexit (~600 lines).
2. RuntimeContext bootstrap + argparse + chrome options (~400 lines).
3. Engine dispatch + translate_docx orchestrator + get_translation_*
   helpers (~500 lines).
4. document_split_phrases + tokenize/divide helpers (~300 lines).
5. `main()` (~200 lines).

This is roughly the natural ceiling — much smaller would require
either consolidating module-level setup into a function (~150 lines
saved) or splitting `translate_docx`, both of which are riskier.

---

## How to start

1. `git checkout refactor/cli-py-3-phase-shrink`
   (or branch off from it: `git checkout -b refactor/cli-py-3-phase-final`).
2. `git log --oneline -5` — should see `bd65ea8 cli.py shrink phase 3
   (own work)` at HEAD.
3. Pick one task above and paste it as the prompt.
4. Run pytest after every commit.
