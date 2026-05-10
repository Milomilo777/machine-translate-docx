# Next-session handoff — thread docx globals to ctx, then extract parse + get_cell_data

> Read this first. Then `docs/agent-handoff.md` (older, persian-double-lines
> roadmap), `CHANGES.md` (most-recent first), and `PROJECT_MEMORY.md`
> (C1-C17 invariants).

---

## Status snapshot

```
date          2026-05-10  (close of previous session)
master tip    0f07c14     merge: extract-docx-parse into master
unit tests    63 / 63 pass
real-file     tasks.bat smoke = DeepL en→fr in ~28 s, 0/42 mismatches
recent tags   archive/persian-double-lines-as-splitter-2026-05-10
              archive/architecture-cleanup-after-audit-2026-05-10
              archive/extract-docx-parse-2026-05-10
deleted       all three next/* feature branches; only master remains
```

---

## What this session is for

Two extractions were deferred three times because they need a
prerequisite first:

  1. `read_and_parse_docx_document` — ~800 lines of input-side parsing.
  2. `get_cell_data` — per-cell read with shading / colour / hyperlink
     handling. Smaller (~440 lines) but uses the same global surface.

Both read **module globals** that have to be threaded through `ctx`
first. Trying to extract them without that prerequisite means duplicating
the same global-passthrough shim pattern we already used for cells.py
and save.py — and there are ~20 globals, not 4. The shim becomes ugly.

**This session is one focused pass: thread the globals to ctx, then
extract.**

---

## The global surface

### Required by `read_and_parse_docx_document`

| global               | declared at         | type / role                                |
|----------------------|--------------------|---------------------------------------------|
| `docxdoc`            | line 1050           | `docx.Document` — the python-docx Document  |
| `use_html`           | line 678            | bool — HTML CGI output mode                 |
| `docxfile`           | (typo — see note)   | unused, only in an error message            |
| `silent`             | line 659            | bool — CLI `--silent` flag                  |
| `E_mail_str`         | line 610            | str — author contact for error messages     |
| `PROGRAM_VERSION`    | line 3              | str — version banner for error messages     |
| `word_file_to_translate` | line 712        | already on `ctx.flags.word_file_to_translate` ✓ |

Note on `docxfile`: line 2495 has `print(f"Error: ... {docxfile}")`
referring to a name that does not exist as a global. The intended
reference is `word_file_to_translate`. Fix-as-you-go.

### Required by `get_cell_data` (additional)

| global                       | declared at | role                                |
|------------------------------|-------------|--------------------------------------|
| `shading_color_ignore_text`  | (config)    | already in `config.py` ✓              |
| `font_color_ignore_text_red` | (config)    | already in `config.py` ✓              |
| `font_color_ignore_text_grey`| (config)    | already in `config.py` ✓              |
| `dest_lang`                  | line 832    | already on `ctx.language.dest_lang` ✓ |

Plus calls into `_iter_paragraph_runs` (already moved to
`docx_io.runs`).

### Already on ctx (do NOT re-add)

```
ctx.docx.numrows / numcols / table / table_cells
ctx.docx.from_text_table  (and ~25 sibling parallel arrays)
ctx.docx.source_columns_snapshot
ctx.docx.translation_array
ctx.flags.word_file_to_translate
ctx.flags.word_file_to_translate_save_as_path
ctx.language.dest_lang / src_lang / dest_lang_name
ctx.engine.engine / method / dispatcher
ctx.flags.splitonly / with_polish / silent (already partial)
```

---

## Recommended phase plan

Each phase = one commit. Run `tasks.bat test` after every phase. Run
`tasks.bat smoke` after phases that touch the parse or save path.

### Phase G1 — add docxdoc + use_html + silent to ctx

In `src/runtime.py:DocxCtx`, add:

```python
docxdoc:  Any  = None       # python-docx Document
use_html: bool = False
```

In `src/runtime.py:FlagsCtx`, confirm `silent: bool = False` exists
(may already be there — check).

In `src/machine_translate_docx.py`, after `docxdoc = docx.Document(...)`
at line 1050, add:

```python
_get_ctx().docx.docxdoc  = docxdoc
_get_ctx().docx.use_html = use_html
```

(or include in the existing `_sync_globals_from_ctx` mirror.)

### Phase G2 — extract get_cell_data first (smaller, simpler)

Move to `src/docx_io/cells.py` as `get_cell_data(ctx, cell, row_n)`.
The signature already takes `ctx` and `cell`; the body just needs the
globals it currently reads to come from `ctx`. The thin shim in the
entry script keeps the same name.

### Phase G3 — extract read_and_parse_docx_document

Move to a new module `src/docx_io/parse.py`. The function already
takes `ctx`; rewrite all global reads to use ctx:

```python
docxdoc            → ctx.docx.docxdoc
use_html           → ctx.docx.use_html
silent             → ctx.flags.silent
E_mail_str         → import from a small constants module, OR keep a
                     module-level constant in the new parse module
                     (only used in error messages, no behaviour)
PROGRAM_VERSION    → same — make it a constant or pass as kwarg
```

The fall-through `print(f"Error: document {docxfile} does not have
a table")` uses an undefined name. Replace with
`ctx.flags.word_file_to_translate`.

The thin shim in entry script keeps `read_and_parse_docx_document(ctx)`
working.

### Phase G4 — verify

  - `tasks.bat test`     — 63/63 pass
  - `tasks.bat smoke`    — DeepL en→fr in ~30 s, 0/42 mismatches
  - Check `tasks.bat live-google` if time permits.

### Phase G5 — commit + push + tag + delete branch

Same workflow as the previous three sessions:

```
git push origin <branch>
git checkout master
git merge --no-ff <branch> -m "merge: ..."
git push origin master
git tag -a archive/<branch-name>-2026-05-10 <branch> -m "..."
git push origin <tag>
git push origin --delete <branch>
git branch -d <branch>
```

---

## The branch to use

**Create the new branch as the FIRST action of the next session:**

```
git checkout master
git pull origin master
git checkout -b next/thread-docx-globals-to-ctx
```

All work happens on `next/thread-docx-globals-to-ctx`. Master stays
green and shippable.

---

## Things you (the next agent) might miss

1. **Auto mode is on; user has hands-off authorization.** Do not pause
   between phases. Make decisions yourself.

2. **Persian responses only.** No English words inside Persian
   sentences. English file names, function names, and code go in
   separate lines or code blocks. Hard rule.

3. **Repo docs (CHANGES.md, PROJECT_MEMORY.md, docs/*) must be
   English.** Conversation stays Persian.

4. **Auto-commit + auto-doc.** Every code change → commit + CHANGES.md
   update + push, in the same flow. No batching.

5. **17 invariants C1-C17 in PROJECT_MEMORY.md.** Especially:
     - C1: aligner model = `gpt-5.4-mini`, never parameterise away.
     - C3: `_normalize_lang()` is read-only.
     - C5: no timestamp prefix in output filenames.
     - C6: file collision suffix `_1, _2`, never overwrite.
     - C13: source-language column frozen via `source_columns_snapshot`.
     - C15: no bare `except:` — always `except Exception:`.

6. **Verification command for unit tests:**
```
PYTHON=E:/Python311/python.exe ./tasks.bat test
```
Expected: 63 passed.

7. **Verification command for real-file smoke:**
```
PYTHON=E:/Python311/python.exe ./tasks.bat smoke
```
Expected: ~25-30 s, output `_real_test/smoke_FRE_Deepl.docx`,
0/42 source-column mismatches.

8. **Legacy reference repo:** if the parse logic does something
   confusing, the original is at remote `upstream-old`
   (`git fetch upstream-old main`). Do not merge from it; only
   read for clarity.

9. **The PROGRESS:90 marker** is what `local_launcher.py` watches
   for to flip the progress bar. Don't strip it. Currently emitted
   in `save_docx_file` shim before delegating.

10. **xtm = None pitfall.** `xtm` is a module-level singleton built
    by `initialize_translation_memory_xlsx`. If you accidentally
    move parse code that uses `xtm` to a module that imports first,
    you'll get `xtm is None` errors. Keep `xtm` reads on the entry
    script side or thread it through ctx properly (currently
    pre-2026-05-10 hack: `xtm = None` at module top + `global xtm`
    in initializer).

11. **`_sync_globals_from_ctx`** is the Phase H bridge that mirrors
    `ctx.docx.*` to module globals. After you thread a global into
    ctx, also update `_sync_globals_from_ctx` so the legacy
    helpers downstream still see the value. Or eliminate the legacy
    helper at the same time.

12. **Tests live in `tests/`.** No tests cover `read_and_parse_docx_document`
    or `get_cell_data` directly. The smoke test covers them
    end-to-end. Consider adding a unit test for at least one of
    them in your extraction commit (the docx_io.parse module is
    a good seam for this).

---

## Past sessions (most recent first)

| date       | branch                                              | done                                                          |
|------------|-----------------------------------------------------|---------------------------------------------------------------|
| 2026-05-10 | next/extract-docx-parse                            | docx_io package: runs.py + cells.py + save.py                 |
| 2026-05-10 | next/architecture-cleanup-after-audit              | C1 web engines deleted, C2 entry rename + dispatch.py, C3 perplexity_webservice + dead code, C4 Makefile + tasks.bat |
| 2026-05-10 | next/persian-double-lines-as-splitter              | 15 phases of the persian-double-lines roadmap + DeepL/Google fixes + web-engine audit + timing alignment |

All three branches deleted; corresponding `archive/*` tags on origin.
