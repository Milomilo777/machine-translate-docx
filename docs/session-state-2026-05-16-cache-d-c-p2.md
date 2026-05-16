# Session State Report — 2026-05-16, Cache refactor + Sprint D-C partial + P2/P3 hygiene + matrix smoke

> Written from the architect role at the end of the
> `refactor/cli-py-sprint-d-final` second-pass session. HEAD is
> commit `e8b7062`. The branch is **NOT merged to master.** This
> doc is the canonical handoff for everything done after the prior
> Sprint D-A/B merge.

---

## TL;DR

Four phases ran on the existing `refactor/cli-py-sprint-d-final`
branch, then a real 9-case multi-engine matrix smoke verified the
whole stack survived. All 9 cases PASSED with real translations
(OpenAI API + Google web + DeepL web; both FA and VI).

| Phase | Status | Commits |
|---|---|---|
| 1 — Cache refactor | ✅ Done | `1ec1859` |
| 2 — Sprint D-C (`_sync_globals_from_ctx` collapse) | 🟨 Partial (deferred) | `cda1467` |
| 3 — P2/P3 hygiene | ✅ Done (5 commits) | `3b97fcc` `ded9d7e` `b073290` `588a2cf` `e8b7062` |
| 4 — Multi-engine matrix smoke (9 cases real) | ✅ Done — all pass | — (verification only) |

Master remains at `44c9f76` (the prior Sprint D-A/B merge). The
user runs their own end-to-end smoke before merging.

---

## Branch summary

```
Branch:           refactor/cli-py-sprint-d-final
Master tip:       44c9f76 (unchanged; branch ahead by 7 commits)
Branch HEAD:      e8b7062
Commits:
  1ec1859  Phase 1: raw-cache refactor — split_engine-independent cache key
  cda1467  Phase 2 partial — Sprint D-C: remove dead OpenAI mirror branches
  3b97fcc  P2.6: fix fd leak + immutable-ref mutation in cli.py stderr suppression
  ded9d7e  P2.7: route validate_json_string traceback to stderr
  b073290  P2.3: mask Telegram bot token in exception text + log lines
  588a2cf  P2.2: translation_log_writer.write_translation_log adds strip_prompts flag
  e8b7062  P3.3: simplify ``not foo == True`` to ``not foo`` (cli.py)
File sizes:
  src/machine_translate_docx/cli.py                          2,686 lines
  local_launcher.py                                          2,827 lines
  src/machine_translate_docx/statistics.py                     754 lines
  src/machine_translate_docx/engines/google_file_modes.py      857 lines
  src/machine_translate_docx/translation_log_writer.py         178 lines
Tests:            239 passed / 8 skipped (live) / 6 deselected on every commit
```

cli.py delta vs branch start of this second-pass session: 2,670 →
2,686 (+16 lines net — 2 for the translate_docx splitonly guard
+ 11 for io.StringIO comment + 3 trivial). Bridge code shrunk by
13 lines but documentation comments balanced the delta.

local_launcher.py delta: 2,645 → 2,827 (+182 lines net — the new
`_apply_basic_split` helper + `_mask_telegram_token` + reorders +
Telegram try/except guards).

---

## Phase 1 — Cache refactor (`1ec1859`)

### What landed

Six concrete changes in `local_launcher.py` per the spec encoded
in the three commit messages on `origin/claude/raw-cache-refactor`:

1. **`_cache_key`** drops `split_engine` from the SHA-256.
   Signature: `(payload, target_lang, engine, ai_model) -> str`.
   Legacy 5-tuple cache entries from before this commit are
   invisible (key shape changed) — users see a one-time "cold
   cache" period.

2. **B1-guard** in `_run_real_backend` generalised: forces
   `split_translate = False` for ALL engines in `_API_ENGINES`
   ({chatgpt, chatgpt-polish}), ALL target languages. Every
   API-engine job now emits a "raw" one-blob-per-phrase docx.

3. **New `_apply_basic_split(base_path, *, target_language)`**:
   spawns the CLI with `--splitonly --engine chatgpt
   --enginemethod api --aimodel gpt-5.4-mini` and
   `MTD_SKIP_STATS_BROWSER=1` in env. Parses
   `Saved file name:`, then `shutil.move` the subprocess
   output onto `base_path.name`. Falls back to raw on any failure.

4. **`_apply_splitter`** routes:
   - `persian_double_lines` (FA only) → in-process FA aligner
   - `basic` / `openai` / `None` → `_apply_basic_split`
   The legacy "return base_path unchanged for non-PDL" fallback
   is gone.

5. **Order of operations** in `_process_job`: `cache_store`
   BEFORE `_apply_splitter`. The cache copy stays raw even if
   `_apply_basic_split` overwrites `base_path` via `shutil.move`.

6. **`_materialise_cached_output`** inherits the new
   `_apply_splitter` routing — cache replay for any splitter
   now takes ~10-30 s (file copy + splitonly subprocess) instead
   of the legacy ~5 min full re-translate.

### CLI preconditions (drive-by fixes)

The spec's command (`--splitonly --engine chatgpt --enginemethod
api`) was never end-to-end verified by the original spec author —
empirical test surfaced two CLI bugs that block it:

**a) `translate_docx` (cli.py)**: line 982-983 clears
`engine_method` to `''` (sentinel for splitonly), but the chatgpt
branch of `use_phrasesblock` always returns True regardless of
method. With method='', the runner is invoked and immediately
raises `ValueError: chatgpt method '' not supported`. Fixed by
adding `if ctx.flags.splitonly: return translation_succeded` as
the first statement of `translate_docx`. Semantically correct:
splitonly = "only split, don't translate".

**b) `create_webdriver` (selenium_utils/driver.py)**: the existing
C25 fast-path bypasses Chrome for chatgpt+api, but only when
method='api'. With splitonly clearing method to '', the fast-path
doesn't fire and Chrome launches anyway (~30 s wasted). Fixed by
adding `if ctx.flags.splitonly: return` after the C25 branch.
Splitonly never runs an engine, so it never needs Chrome
regardless of engine choice.

Both fixes are 1-2 lines each and necessary preconditions —
without them the launcher's basic-split spawn crashes (a) or
burns 30 s on a Chrome launch it never uses (b).

### Verification

- pytest: 239 pass, 8 skipped (live). The existing
  `test_launcher_endpoints.py::test_cache_key_*` tests already
  used the 4-arg signature — happy coincidence that survives
  the refactor.
- Isolated integration test (in-process, not via HTTP):
  - `_cache_key` 4-arg signature ✓
  - `LocalState.cache_store` + `cache_lookup` round-trip on a
    raw docx ✓
  - CLI `--splitonly --engine chatgpt --enginemethod api` with
    `MTD_SKIP_STATS_BROWSER=1`: exit=0, elapsed=30.6 s,
    `Saved file name:` emitted ✓
  - C13 cols 0+1 byte-identical, col 2 populated for 37/42 rows ✓

### Spec divergences (architect findings)

- Spec promised ~8 s cache replay. Actual: ~30 s. The remaining
  20+ s is module-load startup (hazm normalizer try/except,
  network_utils, etc.). Still a huge improvement over ~5 min
  full re-translate. A follow-up "lean startup" pass could
  bring it closer to the spec target.
- Spec said the CLI's splitonly path already worked. It didn't —
  see "CLI preconditions" above. Two small fixes added.

---

## Phase 2 — Sprint D-C partial (`cda1467`)

### What landed

Sprint D-C ("collapse `_sync_globals_from_ctx`") cannot land
in this session — the audit (refreshed on this branch HEAD)
shows **176 bare-name occurrences across 41 names** in cli.py.
Threading each occurrence safely requires per-function signature
changes + pytest + smoke per change. Per the prompt's stopping
rule: "Better partial than broken."

The smallest verifiable-dead branch of the bridge was deleted:
the three `setattr` calls that mirror
`ctx.openai.{translator,polisher,translation_log}` back to
cli.py's module globals. Empirically dead by grep:

- `oai_translator` — read at lines 294 (initial ctx-push) and
  1077 (module init). No other readers.
- `oai_polisher` — read at lines 298 and 1078. No other readers.
- `translation_log` — read at lines 302 and 1079. No other
  readers. The historical reader (`write_translation_log`) was
  extracted to `translation_log_writer.py` in Sprint D phase 3
  and now reads `ctx.openai.translation_log` directly via the
  shim at cli.py:1097.

Net change: −13 lines from `_sync_globals_from_ctx`.

### What's still in the bridge (the remaining 167 occurrences)

Sorted by count (re-confirmed on `e8b7062` HEAD):

| Name | Occurrences | Source |
|---|---:|---|
| `dest_lang` | 55 | `ctx.language` |
| `driver` | 19 | `ctx.browser` |
| `docxdoc` | 10 | `ctx.docx` |
| `translation_array` | 8 | `ctx.docx` |
| `from_text_nb_lines_in_phrase` | 7 | `ctx.docx` |
| `src_lang` | 6 | `ctx.language` |
| `from_text_table` | 5 | `ctx.docx` |
| `from_text_by_phrase_table` | 4 | `ctx.docx` |
| `translation_result_using_separator` | 4 | `ctx.docx` |
| `use_html` | 4 | `ctx.docx` |
| `translation_log` | 4 | `ctx.openai.translation_log`* |
| `numrows` / `table` / `table_cells` / `translation_result_phrase_array` | 3 each | `ctx.docx` |
| (smaller fields) | 1-2 each | mostly `ctx.docx` |

*`translation_log` still appears 4× in counts because the
module-level init + the initial `_get_ctx()` push still need to
run for the dataclass default to hydrate.

### Recommended ordering for the next D-C session

1. **Pilot:** thread `dest_lang` (55) — single biggest payoff,
   lowest risk (immutable string already on `ctx.language`).
   pytest + smoke after each ~10 readers threaded.
2. **High-value:** thread `driver` (19) and `docxdoc` (10).
   Both are already on `ctx.browser` / `ctx.docx`.
3. **Parallel arrays:** thread `from_text_*` / `to_text_*` /
   `translation_*` tables. Write to `ctx.docx.X` (preserve
   list identity for in-place mutation).
4. **OpenAI handles:** `translation_log` (the bridge already has
   the OpenAI branch removed, but the init scaffolding remains).
5. **Last:** delete `_sync_globals_from_ctx` entirely + the 6
   call sites in `main()` (search for
   `_sync_globals_from_ctx(ctx)`).

### Expected line drop after Task C

cli.py: 2,686 → ~2,000 (the natural ceiling identified in
docs/cli-shrink-phase3-handoff.md).

---

## Phase 3 — P2/P3 hygiene (5 commits)

Five independent quick wins from the 2026-05-16 master audit.
Each commit is small, focused, pytest-green.

### `3b97fcc` — P2.6: fd leak + immutable-ref mutation in stderr suppression

End-of-`main()` had:
```python
devnull = open(os.devnull, 'w')   # fd leaked at process exit
sys.stderr = devnull
sys.__stderr__ = devnull          # frozen ref mutated
```
Replaced with `sys.stderr = io.StringIO()` — in-memory discard,
no fd, no `__stderr__` mutation. Destructor noise still
suppressed (StringIO accepts `write()` silently).

### `ded9d7e` — P2.7: route validate_json_string traceback to stderr

`config.validate_json_string` printed full `traceback.format_exc()`
to stdout. Routed to stderr via `file=sys.stderr` so the
launcher's stdout parser cannot mistake it for a
`Saved file name:` / `PROGRESS:N` marker.

### `b073290` — P2.3: mask Telegram bot token in exception text

Three Telegram URL sites
(`_send_telegram_text` / `_send_telegram_alert` /
`_telegram_send_document`) build URLs containing the bot token.
`urllib.HTTPError.__str__` can include the request URL on some
Python builds — token leaks into tracebacks / log files.

Added `_mask_telegram_token(text, token)` helper at module top
(plain `.replace(token, "***")`). Wrapped each urlopen with
try/except that re-raises masked. The `except RuntimeError:
raise` short-circuit preserves intentional `"telegram rejected"`
messages (where the token is not present anyway) so the
existing `test_send_document_raises_on_telegram_rejection` test
still asserts on the clean message.

### `588a2cf` — P2.2: translation_log_writer.write_translation_log adds strip_prompts flag

Sidecar JSON bundles full translator + polisher system prompts
under `run_info.{translation,polish}_prompts.system_prompt`.
Useful for local debug, risky if the launcher's
`/download/<…>_log.json` route ends up serving them publicly.

Added keyword-only `strip_prompts: bool = False`. When True,
omits `system_prompt` and `user_prompt_sample` from each entry,
keeping only `prompt_hash`. Default False preserves legacy
behaviour exactly. Cli.py shim still calls 2-positional; future
config.toml wiring left to a follow-up.

### `e8b7062` — P3.3: simplify `not foo == True` to `not foo`

Two cosmetic sites in cli.py:917 and :926.
`not (foo == True)` is `not foo`. Same logic, less noise.

### Phase 3 items NOT taken in this session

From the audit's 11 P2 + 8 P3 catalog:

- **P2.1** (saved_filename path confinement, local_launcher.py:1747-1811)
  — skipped to keep commit count modest; medium effort. Would
  pair the existing `resolve()` + `relative_to(uploads_root)`
  pattern around the subprocess-emitted filename.
- **P2.4** (`openai_tools/splitting.py` missing `call_with_retry`
  wrap) — skipped; medium effort, involves understanding the
  legacy splitting path that's only invoked for `splitTranslate=
  true` AND `splitengine=openai`. Worth doing but not in this
  session.
- **P2.5** (`runner.py:240` dead perplexity branch) — ALREADY
  FIXED in master `8381215`. Skipped per prompt note.
- **P2.8** (PRICES table 3× duplication) — skipped; medium effort
  + cross-module touch. The drift potential is real but contained
  (no observed drift in current PRICES values).
- **P2.9** (response-API usage normalization duplicated) — skipped
  for the same reason as P2.8.
- **P2.10** (`LocalState.total_uploads` field unused) — skipped;
  trivial but cosmetic.
- **P2.11** (`_make_ssl_dir` placeholder files) — skipped;
  trivial but cosmetic.
- **P3.1** (`translation_succeded` → `translation_succeeded`)
  — skipped; mechanical but touches `runner.py`'s public API
  and risks subtle ripples. Worth a dedicated commit.
- **P3.2** (`E_mail_str` vs `E_MAIL_STR` consolidation) — skipped;
  trivial but multi-file.

---

## Phase 4 — Multi-engine matrix smoke (9 real cases)

Real end-to-end smoke against
`tests/fixtures/sample_hyperlink.docx`. CLI invoked directly via
subprocess (no launcher HTTP). Matrix:

| # | Case | Engine | Lang | Split | Result |
|---|---|---|---|---|---|
| 1 | chatgpt_fa_basic | chatgpt-api | fa | basic | PASS |
| 2 | chatgpt_polish_fa_basic | chatgpt-polish | fa | basic | PASS |
| 3 | chatgpt_polish_fa_double | chatgpt-polish | fa | persian_double_lines | PASS |
| 4 | chatgpt_vi_basic | chatgpt-api | vi | basic | PASS |
| 5 | chatgpt_polish_vi_basic | chatgpt-polish | vi | basic | PASS |
| 6 | google_fa | google | fa | basic | PASS |
| 7 | google_vi | google | vi | basic | PASS |
| 8 | deepl_fa | deepl | fa | basic | PASS |
| 9 | deepl_vi | deepl | vi | basic | PASS |

### Per-case results

```
case                         exit  saved  rows  c13  col2_pop   script_n   suffix    result
chatgpt_fa_basic             0     YES    42    OK    37/42     771        OK        PASS
chatgpt_polish_fa_basic      0     YES    42    OK    37/42     798        OK        PASS
chatgpt_polish_fa_double     0     YES    42    OK    37/42     825        OK        PASS
chatgpt_vi_basic             0     YES    42    OK    37/42     240        OK        PASS
chatgpt_polish_vi_basic      0     YES    42    OK    37/42     242        OK        PASS
google_fa                    0     YES    42    OK    37/42     782        OK        PASS
google_vi                    0     YES    42    OK    37/42     240        OK        PASS
deepl_fa                     0     YES    42    OK    37/42     792        OK        PASS
deepl_vi                     0     YES    42    OK    37/42     280        OK        PASS

All 9 cases PASSED.
```

Validator script lives at `notes/matrix_validate.py` (gitignored)
and checks:
- exit=0
- `Saved file name:` emitted
- Row count == 42
- C13 cols 0+1 byte-identical
- Col 2 populated for ≥17 rows
- Script content matches lang:
  - FA: ≥17 chars in U+0600..U+06FF
  - VI: ≥5 chars in U+1E00..U+1EFF or U+00C0..U+024F
- Engine suffix in filename matches expected
  (`_PER_chatGPT` / `_PER_Polish` / `_PER_Google` / `_PER_Deepl`,
  and same with `_VIE` for Vietnamese)

### Sample col 2 content (verified real translations, not mocks)

```
chatgpt_fa: "متن هایلایت‌شدهٔ فیروزه‌ای، متنی است…"
google_fa:  "متن هایلایت شده فیروزه ای متنی است…"
deepl_fa:   "متن برجسته شده با رنگ فیروزه‌ای، متنی…"
chatgpt_vi: "Văn bản được tô xanh ngọc là văn bản…"
google_vi:  "Văn bản được đánh dấu bằng màu ngọc lam là…"
deepl_vi:   "Văn bản được đánh dấu màu xanh ngọc là văn…"
```

DeepL ran successfully without `MTD_DEEPL_USER` /
`MTD_DEEPL_PASSWORD` set — it used the public web endpoint
(no login required for the open translation form). On a host
that needs Pro features, those env vars must be set.

### Architecturally interesting findings

- The PDL case (#3) at the CLI level produces the same output as
  basic (#2). The aligner runs **inside the launcher's
  `_apply_splitter`**, not the CLI. Direct-CLI testing of `--split
  --splitengine persian_double_lines` therefore exercises the
  same CLI code path as plain `--split`; PDL output is only
  realised when running through the launcher.
- All 9 cases produced 37/42 populated col-2 rows — that's the
  number of translatable rows in `sample_hyperlink.docx` after
  fixture-specific filters (timecodes, empty rows). Stable
  baseline.

---

## What the user does next

1. **Pull the branch:**
   ```bash
   git checkout refactor/cli-py-sprint-d-final
   git pull origin refactor/cli-py-sprint-d-final
   ```

2. **Run your own E2E smoke** (the canonical one + the cache replay
   check — this validates the launcher's HTTP layer, which the
   in-process integration test cannot exercise):
   ```bash
   # Standard smoke
   PYTHONPATH=$PROJ/src python -m machine_translate_docx.cli \
       --docxfile $PROJ/tests/fixtures/sample_hyperlink.docx \
       --destlang fa --engine chatgpt --enginemethod api \
       --aimodel gpt-5.4-mini --with-polish \
       --silent --exitonsuccess
   # Cache replay test (via launcher HTTP):
   python $PROJ/local_launcher.py   # leave running in another shell
   # Then POST upload with splitTranslate=true on the same fixture,
   # then re-upload with splitTranslate=false. Second call should
   # complete in ~10-30 s with "[cache hit]" in the launcher log.
   ```

3. **Merge to master** via no-ff per constraint C23:
   ```bash
   git checkout master
   git pull
   git merge --no-ff refactor/cli-py-sprint-d-final
   git tag archive/cache-d-c-p2-2026-05-16
   git push origin master archive/cache-d-c-p2-2026-05-16
   ```

4. **Delete the branch** (optional) — `git branch -d
   refactor/cli-py-sprint-d-final && git push origin --delete
   refactor/cli-py-sprint-d-final`. The archive tag preserves the
   tip.

5. **Plan the follow-up Sprint D-C dedicated session** — the
   bridge-deletion work needs ~6 h of focused threading time per
   the audit. The 5-name pilot (`dest_lang`) alone removes 55 of
   the 176 occurrences.

---

## What this session did NOT do

- **No master merge.** The branch tip `e8b7062` is on origin but
  not on master.
- **No touch of `claude/raw-cache-refactor` or its v2 worktree
  as git objects.** Used the commit messages as a written spec.
- **No full bridge deletion in Phase 2.** Documented as
  partial; full deletion is the next dedicated session's work.
- **No further P2/P3 items beyond the 5 commits.** The audit's
  long-tail items remain open — pick them off in future sessions.

---

## Pointers

- `docs/session-state-2026-05-16-sprint-d-complete.md` — prior
  Sprint D-A/B handoff (already merged to master at `44c9f76`)
- `docs/cli-shrink-phase3-handoff.md` — Sprint D-C task spec
  (still relevant)
- `docs/master-audit-2026-05-16.md` — full P0-P3 catalog
- `notes/matrix_validate.py` — Phase 4 validator script
  (gitignored, sample location for future smoke runs)
- This doc — canonical entry for the cache-refactor +
  Sprint D-C partial + Phase 3 + Phase 4 work
