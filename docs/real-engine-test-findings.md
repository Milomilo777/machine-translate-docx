# Real-engine test pass — findings & follow-up backlog

> Run date: 2026-05-10
> Branch: `next/real-engine-tests-and-findings`
> Fixture: `tests/fixtures/sample_hyperlink.docx` (42 rows, EN source,
>          phrase-grouped subtitle template)
>
> One bug surfaced and was fixed inline because it blocked verification
> of the 24-h prompt cache (`B-003` below). Every other issue is
> queued for a dedicated hardening pass — do **not** fix mid-test, the
> next session will pick from this list.

---

## Logging surface — what exists today

| What | Where | Notes |
|------|-------|-------|
| `*_log.json` sidecar | next to the output `.docx` | written **only** when `ctx.flags.with_polish` is true and `translation_log["blocks"]` is non-empty (`src/docx_io/save.py:219-225`). Captures `cached_tokens` per call (translator + polisher) — confirmed live during T7. |
| `translation_log` dict | `ctx.openai.translation_log` | populated only on the chatgpt-polish path; DeepL / Google runs never touch it. |
| Local launcher state | in-memory `LocalState.jobs` dict | nothing on disk. PROGRESS markers parsed from subprocess stdout, error string captured to `jobs[id].error` — both vanish on launcher restart. |
| Server-side payload cache | `runtime_dir/cache/<hash>/` | TTL 36 h (`local_launcher.py:44`). Keyed on `sha256(payload + lang + engine + ai_model)`. |
| OpenAI 24-h prompt cache | sent on every API call | `extra_body={"prompt_cache_retention": "24h"}` in translator + polisher. Hit count comes back in `response.usage.prompt_tokens_details.cached_tokens` and is logged to the JSON sidecar. **Verified live in T5/T7 — see below.** |
| Failed-job archive / alerting | **none** | no quarantine folder, no email hook, no webhook. |

---

## Test matrix — results

| # | Engine | Method | Lang | Polish | Split tr | Split method | Time | Source col | Target rows | Notes |
|---|--------|--------|------|--------|----------|--------------|------|-----------|-------------|-------|
| T1 | DeepL  | phrasesblock | en→fr | – | off | basic | 27 s | 42/42 ✓ | 18 / 40 phrases | baseline |
| T2 | Google | phrasesblock | en→fr | – | off | basic | 12 s | 42/42 ✓ | 18 / 40 phrases | French diacritics OK in docx |
| T3 | Google | phrasesblock | en→de | – | off | basic | ~10 s | 42/42 ✓ | 18 / 40 phrases | German umlauts OK |
| T4 | DeepL  | phrasesblock | en→es | – | off | basic | ~25 s | 42/42 ✓ | 18 / 40 phrases | Spanish ¡, accents OK |
| T5 | chatgpt | api | en→fa | yes | off | basic | 33 s | 42/42 ✓ | 18 / 40 phrases | RTL + ZWNJ correct |
| T6 | chatgpt | api | en→fa | yes | **on** | basic (excel) | 33 s | 42/42 ✓ | **37 / 40 rows** | distribution worked correctly — *user-reported "all in row 0" regression NOT reproduced on this fixture* |
| T7a | chatgpt | api | en→fa | yes | off | basic | 30 s | 42/42 ✓ | 18 / 40 | first call after gpt-5.5-mini probe |
| T7b | chatgpt | api | en→fa | yes | off | basic | 10 s | 42/42 ✓ | 18 / 40 | **cache hit: 91.7 % translation, 76 % polish — verified** |
| T7c | chatgpt | api | en→fa | yes | off | basic |  9 s | 42/42 ✓ | 18 / 40 | second cache run, ratios stable |
| F1 | chatgpt | api | en→fa | – | off | basic | 27 s | 3/3 ✓ | – | **`empty_source.docx` reported success** ⇒ reproduces B-001 |

**Note on "18/40" for non-split runs:** the source fixture has phrase
groupings (one phrase spans 2-3 rows). The translation is written to
the *first* row of each phrase; subsequent rows of the same phrase are
intentionally left empty. With split-translation **on** (T6) the
translator distributes lines per-row → 37 / 40 rows populated. This
is by design.

**24-h prompt cache numbers (T7):**

```
First   call: cached / prompt — translation 5376/5860 (91.7 %)
                                polish      3328/4388 (75.8 %)
Second  call: cached / prompt — translation 5376/5860 (91.7 %)
                                polish      3328/4377 (76.0 %)
Third   call: cached / prompt — translation 5376/5860 (91.7 %)
                                polish      3328/4396 (75.7 %)
elapsed_seconds drops from ~9 to ~9 (reasoning + completion still
   cost the same — only prompt encoding is cached). Cost per run
   ~ $0.019.
```

---

## Bugs to fix in a follow-up commit (queue)

### B-001 — Empty / no-translatable-content runs reported as success

**Reproduction:**
```
docx with only a header row + two source-empty rows
→ chatgpt api en→fa
→ stdout: "Translation ended, file saved. Elasped time: 0:00:27"
→ output: 3-row docx with the source column intact and the target
  column empty in row 1+2 (only 'Persian' from the dropdown header)
```

**Diagnosed mechanism:**
- `src/runner.py:276` only flips `translation_succeded = False` on a
  line-count mismatch. Empty source → empty target → 0 vs 0 lines →
  count check passes.
- No "engine returned empty / nothing-to-translate" trap anywhere in
  the entry script or `runner.py`.
- The launcher therefore reports `status=done` on what is in fact
  a no-op run.

**Fix sketch:**
1. After parse + before translate: assert
   `sum(1 for v in ctx.docx.from_text_table if v.strip()) > 0`,
   otherwise raise `ValueError("input has no translatable text")`.
2. After translate + before save: assert that the ratio
   `non_empty_targets / non_empty_sources` ≥ `MIN_NONEMPTY_RATIO`
   (start with 0.5; configurable via env). On failure, set
   `translation_succeded = False` and propagate
   `error_reason = "engine_returned_empty"` to the launcher.
3. Surface the reason in the JSON sidecar AND in the launcher's
   `jobs[id].error` so the v2 frontend toast carries the real cause.
4. Add an integration test in `tests/integration/`: build a 3-row
   empty-source docx, run the chatgpt-mock engine, assert exit
   non-zero.

### B-002 — No failed-job archive / no alerting

**Symptom:** when a launcher subprocess fails, the input file +
traceback live only in stdout / in-memory state — no post-mortem
artifact, no operator notification.

**Fix sketch:**
1. Add `runtime_dir/failures/<job_id>__<ts>/` directory.
   - On launcher detecting `status == "error"`, copy:
     - the original upload,
     - the partial output (if any),
     - the captured stdout / stderr stream,
     - a small `meta.json` (lang / engine / model / timestamp / error).
2. Cheap free alerting (pick one — env-flag-gated):
   - `MTD_FAILURE_EMAIL=op@example.com` → `smtplib`-based plain-text
     email with the meta.json attached (no third-party dep).
   - `MTD_FAILURE_WEBHOOK=https://discord.com/api/webhooks/...` →
     POST a JSON summary (Discord / Slack / Mattermost incoming
     webhooks all accept the same shape).
   - As a no-config fallback: write an `UNREVIEWED.txt` sentinel in
     the failures dir so a human can `ls` and see at a glance.
3. Cleanup policy: prune folders older than N days (mirror the
   existing 1-h job-cleanup thread; default N=30).

### B-003 — Translation log JSON sidecar was always empty *(FIXED inline 2026-05-10)*

**Symptom found during T5:** `chatgpt_fa_polish_PER_Polish_log.json`
contained `run_info={"output_file": "..."}`, `blocks=[]`, all-zero
summary — even though the run took 33 s, made two API calls, and
populated `ctx.openai.translation_log` correctly.

**Root cause:** `write_translation_log()` reads the **module-level**
`translation_log` dict (entry script, line ~991), not
`ctx.openai.translation_log`. `_sync_globals_from_ctx` mirrored
`ctx.openai.translator` and `ctx.openai.polisher` back to the module
but never the log dict, so every chatgpt-polish run wrote an empty
sidecar.

**Fix landed in this commit:** added a 2-line `setattr` in
`_sync_globals_from_ctx` that mirrors `ctx.openai.translation_log`
back to the module level. Verified by re-running T5: sidecar now
carries full `run_info` + `blocks[0]` with translator + polisher
token tallies + cached counts.

This was fixed inline because cache verification (T7) was the whole
point of the test pass and was impossible to perform until this fix
was in.

### B-004 — `gpt-5.5-mini` is not a real model but is offered nowhere in code

**Reproduction:** running with `--aimodel gpt-5.5-mini` raises
`openai.BadRequestError: model 'gpt-5.5-mini' does not exist` (caught
by call_with_retry, then crashes the run).

**Root cause:** the project documents two valid models —
`gpt-5.5` (translator + polisher default) and `gpt-5.4-mini`
(aligner). The web frontend's model dropdown might still expose a
stale `gpt-5.5-mini` option, or a copy-paste from the aligner config
turned `gpt-5.4-mini` into `gpt-5.5-mini` somewhere — needs a
grep + a single source of truth.

**Fix sketch:**
1. Centralise the valid-model list in `src/config.py` as
   `VALID_AI_MODELS = ("gpt-5.5", "gpt-5.4-mini")`.
2. Validate `args.aimodel` at CLI parse time; reject unknown values
   with a helpful error message.
3. Validate the dropdown values in `index.ejs` and `web/v2/app.js`
   against the same list (or fetch the list from a `GET /models`
   endpoint so the two stay in sync).
4. Add a unit test:
   `assert all(m in VALID_AI_MODELS for m in <dropdown options>)`.

---

## Weaknesses / smaller suggestions

### W-1 — `_sync_globals_from_ctx` is whitelist-only and silently undermirrored
The function explicitly mirrors `dest_lang`, `src_lang`, `driver`,
`oai_translator`, `oai_polisher` — and as of B-003's fix,
`translation_log`. Any **other** module-level global that legacy
code reads-then-mutates is at risk of drifting silently. The current
list is whatever past bugs forced us to add; there is no guarantee
the next legacy helper that sneaks in a `global foo` will be caught.

**Idea:** make the mirror walk every public attribute of
`ctx.openai` / `ctx.flags` / `ctx.language` (already does so for
`ctx.docx`). Cost: ~10 extra `setattr` calls per pipeline boundary.
Benefit: removes a whole class of "I added a ctx field, the global
copy stayed empty" bugs.

### W-2 — Persian text in stdout shows reversed characters on Windows console
DocX content is correct (verified). Only the Windows console fallback
to cp1252 / cp65001 reverses RTL for visual display. Operationally
harmless; cosmetically confusing during debugging.

**Idea:** the launcher already calls `sys.stdout.reconfigure(encoding="utf-8")`.
Could explicitly add `os.environ["PYTHONUTF8"] = "1"` at process
start so child subprocesses inherit it.

### W-3 — `aimodel` default `"gpt-5.5"` is hardcoded in two places
`src/runner.py:141` and `src/openai_tools/translator.py` /
`polisher.py` constructor defaults. Drift risk.

**Idea:** export a `DEFAULT_AI_MODEL` constant from `config.py` and
import everywhere.

### W-4 — `_log.json` is overwritten on second run with same name
`save_docx_file` does `_1` / `_2` collision avoidance for the docx
(C6) but the `_log.json` next to it follows the *new* path, so
running twice produces `foo_PER_Polish.docx` + `foo_PER_Polish_log.json`
(first run) and `foo_PER_Polish_1.docx` + `foo_PER_Polish_1_log.json`
(second run). This is **fine**, but worth pinning a unit test that
the pair always travel together.

### W-5 — Phrase-grouping looks like missing translations to a fresh user
The "18 / 40 rows have target text" pattern is correct (one cell per
phrase) but every reviewer who opens the output for the first time
asks the same question. Consider adding a one-line
`[INFO] N phrases / M lines — translation written to phrase head row`
print in the entry script.

### W-6 — Aligner runs only when `with_polish` is on AND target == fa
T5/T6 used `--with-polish` but no `--splitengine persian_double_lines`,
and the aligner did not fire. That's the correct behaviour, but the
"polish" name implies stylistic polish only — users may not know that
`Persian Double Lines` is a *separate* option from `--with-polish`.
Consider renaming the dropdown labels in the UI for clarity.

### W-7 — `[Purple highlight or shade]` row 10 silently dropped
T6 had row 10 as source `"[Purple highlight or shade]"` but target
empty — even though it is bracketed text, not greyed. Worth checking
whether the polisher is treating `[...]` as a comment / instruction
to skip. If so, document it; if not, file as a real bug.

### W-8 — `run_info["output_file"]` is *.docx but the docx may be renamed
Same root cause as W-4. The sidecar records the output filename based
on the path passed to `write_translation_log`, but if the launcher
later renames the file (e.g. to add `_1` for collision) the sidecar
points to a stale name.

---

## Verification commands used

```bash
# T1 (smoke)
PYTHON=E:/Python311/python.exe ./tasks.bat smoke

# T2-T4 (per-engine, per-language)
cp tests/fixtures/sample_hyperlink.docx _real_test/<name>.docx
cd _real_test && E:/Python311/python.exe ../src/machine_translate_docx.py \
    --docxfile <name>.docx --srclang en --destlang <lang> \
    --engine <engine> --enginemethod phrasesblock \
    --silent --exitonsuccess

# T5 (chatgpt baseline)
cd _real_test && E:/Python311/python.exe ../src/machine_translate_docx.py \
    --docxfile chatgpt_fa_polish.docx --srclang en --destlang fa \
    --engine chatgpt --enginemethod api --aimodel gpt-5.4-mini \
    --with-polish --silent --exitonsuccess

# T6 (split translation reproduction)
cd _real_test && E:/Python311/python.exe ../src/machine_translate_docx.py \
    --docxfile chatgpt_fa_split.docx --srclang en --destlang fa \
    --engine chatgpt --enginemethod api --aimodel gpt-5.4-mini \
    --with-polish --split --silent --exitonsuccess

# T7 (cache verify): same as T5, run twice, inspect _log.json
```

---

## Acceptance for the follow-up hardening pass

1. **B-001 fix landed + integration test for empty-source docx**
   that asserts a non-zero exit code.
2. **B-002 minimal slice landed:** `failures/<job_id>__<ts>/` folder
   exists and is populated for any run with `status == "error"`.
   Alerting is optional behind an env flag.
3. **B-004 fix landed:** unknown `aimodel` rejected at CLI parse
   time with a clear error.
4. **W-1 idea evaluated:** decide whether to expand
   `_sync_globals_from_ctx` to walk every public ctx field. If yes,
   land it; if no, add a comment in the function explaining why
   the whitelist is intentional.
5. **W-3 fix landed:** `DEFAULT_AI_MODEL` constant in `config.py`,
   imported everywhere.

The remaining W-* items (W-2, W-4, W-5, W-6, W-7, W-8) are nice-to-
have. Pick what fits the next session's budget; keep the rest in
this doc until they are done.
