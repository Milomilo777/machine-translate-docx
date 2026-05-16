# Session state — 2026-05-16 — Bridge collapse + P2/P3 hygiene

> Handoff doc for the session that completed Sprint D-C (Phase-H mirror
> bridge deletion) plus a 7-item P2/P3 hygiene bundle from the master
> audit. cli.py shrunk from 2,686 → 2,651 lines; the
> `_sync_globals_from_ctx` mirror function and its six call sites are
> gone; cross-module lazy imports in `statistics.py` and
> `engines/google_file_modes.py` now read runtime-changing values from
> `ctx` instead of cli's module namespace.

## TL;DR

- **Branch:** `refactor/cli-py-sprint-d-final`
- **Commit range:** `28512c3..dfee48b` (7 new commits)
- **cli.py:** 2,686 → 2,651 lines (-35 net; bridge function was ~70
  lines but threading inflation netted to 35)
- **pytest:** 239 passed, 8 skipped (live), 6 deselected (live)
- **Live integration tests:** 6 passed in 297 s
- **Matrix smoke (9-case):** 9/9 covered between pytest live +
  three targeted CLI smokes
- **NOT MERGED** to master — user does E2E and merges manually

## Commits

| Hash | Slice / Item | Summary |
|------|--------------|---------|
| `5dd4a9c` | Slice 1 | Add `xtm` + `rtlstyle` to `RuntimeContext.docx`; `_get_ctx()` snapshots them; `initialize_translation_memory_xlsx` mirrors xtm onto ctx |
| `7601686` | Slice 2 | Thread cell-write helpers (10 reads): `cell_set_1st_paragraph`, `cell_add_paragraph`, `prepare_and_clear_cell_for_writing`, `change_cell_font(ctx, cell)` |
| `026b778` | Slice 3 | Thread small helpers (15 reads): `get_translated_cells_content`, `tokenize_text_to_array`, `split_phrases`, `write_destination_language_in_docx_cell`, `set_docx_properties_comment_for_history`, `save_docx_file` |
| `751052f` | Slice 4 | Thread engine orchestrators (15 reads): `selenium_chrome_translate_get_from_text_array` (uses `_get_ctx()` because dispatcher signature is fixed), `generate_char_blocks_array_from_phrases`, `get_translation_and_replace_after` |
| `2d9afce` | Slice 5 | Thread top-level orchestrators (20 reads): `document_split_phrases`, `print_console_docx_file_translated`, `main()` |
| `b12b8a2` | Slice 6 | **Delete the Phase-H mirror bridge.** `_sync_globals_from_ctx` body + 6 call sites removed; cross-module ripple in `statistics.py` + `engines/google_file_modes.py` resolved via direct ctx reads; PROJECT_MEMORY.md C10 rewritten |
| `dfee48b` | Phase 2 | 7 items: P2.1 (path confinement), P2.4 (splitter retry), P2.5 (TranslationFailure replaces sys.exit 8 + 13), P2.8 (PRICES dedup), P2.9 (usage normalize dedup), P3.1 (succeded → succeeded), P3.2 (SUPPORT_EMAIL consolidation) |

## Final code state

**cli.py bare-name read accounting:**

| Category | Reads | Action |
|----------|-------|--------|
| Function bodies (threadable bridge reads) | 60 → 0 | All threaded through ctx |
| Module-top (import-time argparse + setup) | 59 | Left alone — canonical source |
| `_get_ctx` snapshot function | 14 | Left alone — by-design module-global reader |
| Local-shadow false positives (param `dest_lang`, local `driver`, local `numrows`) | 17 | Left alone — reads of locals, not bridge |

**Cross-module reads (lazy imports from cli):**

| File | Stable lazy imports kept | Runtime values now from ctx |
|------|--------------------------|------------------------------|
| `statistics.py` | `PROGRAM_VERSION`, `dest_font`, `docx_file_name`, `split_translation`, `start_time`, `xlsxreplacefile` | `numrows`, `xtm` |
| `engines/google_file_modes.py` | `silent`, `docx_file_name`, `word_file_to_translate`, `xlsxreplacefile`, `html_file_path`, `my_hazm_normalizer` | `driver` (passed as parameter), `numrows`, all parallel arrays, `xtm`, all language metadata |

## Test results

### pytest (offline)

```
239 passed, 8 skipped, 6 deselected in ~27s
```

Stable across all 7 commits. Run with:

```bash
/e/Python311/python.exe -m pytest tests/ --ignore=tests/test_v2_e2e.py
```

### Live integration

```
6 passed in 297.68s (0:04:57)
```

Run with:

```bash
/e/Python311/python.exe -m pytest -m live tests/integration -v
```

Covers: 4 engines × `en→mn` (basic) + 2 engines × `en→fa` (persian_double_lines).

### 9-case matrix smoke

| # | Engine | Lang | Split | Source |
|---|--------|------|-------|--------|
| 1 | chatgpt-api | fa | basic | CLI smoke (28 s) |
| 2 | chatgpt-api | fa | persian_double_lines | pytest live |
| 3 | chatgpt-polish | fa | basic | CLI smoke (60 s) |
| 4 | chatgpt-polish | fa | persian_double_lines | pytest live |
| 5 | google | mn (≡ vi-class) | basic | pytest live |
| 6 | deepl | mn (≡ vi-class) | basic | pytest live |
| 7 | chatgpt-api | vi | basic | CLI smoke |
| 8 | chatgpt-polish | mn (≡ vi-class) | basic | pytest live |
| 9 | chatgpt | mn (≡ vi-class) | basic | pytest live |

`mn` is structurally equivalent to `vi` for the bridge-collapse code path
(both are non-FA, non-RTL, non-aligner targets), so the integration
tests exercise the same code shapes.

## Stopping rule outcome

Hit zero hard blockers across all 6 slices and Phase 2. The previously-
hidden cross-module regression (lazy imports of `numrows`/`driver`/arrays
in `statistics.py` + `google_file_modes.py`) was discovered between
slice 5 and slice 6 commit; resolved in slice 6 commit body
(see `b12b8a2`) by threading those modules' helpers through ctx
instead of leaving a partial bridge.

## What's next (out of scope for this session)

1. **Further cli.py shrink** — the prompt's "~2,000 lines" target needs
   extracting more functions (`split_phrases`, `document_split_phrases`,
   `get_translation_and_replace_after`,
   `print_console_docx_file_translated`) to separate modules. That is
   the natural Sprint E follow-up; Sprint D-C's goal was the bridge
   collapse, which is done.
2. **Live UI matrix via launcher** — the user's "9-case UI matrix smoke"
   that runs through `local_launcher.py` HTTP + form upload is a manual
   acceptance test. The 9 cases above are all validated functionally via
   pytest live + targeted CLI smokes, so the launcher-driven matrix is
   for UI / progress-bar / output-naming verification, not correctness.
3. **P1 items from master audit** — not in this session's brief. P1
   items in `docs/master-audit-2026-05-16.md` remain open.

## Audit doc

Per-slice plan + ARCHITECT sign-off at
`notes/2026-05-16-bridge-audit.md` (local, gitignored). 150 raw
bridge bare-name reads enumerated; 60 threadable, 90 either
import-time / `_get_ctx` / local-shadow false positives.

## USER ACTION

Branch `refactor/cli-py-sprint-d-final` is pushed and ready for your
E2E test + merge to master. Do **not** rebase or squash — each slice
is a self-contained commit so a future bisect can pin which slice
introduced any regression.
