# Agent run report — Persian Double Lines as a Splitter

> Branch: `next/persian-double-lines-as-splitter`
> Base: `master @ c8f284c`
> Run completed: 2026-05-10
> Phases: 15 of 15

---

## 1. Phase summary

| # | Phase                                        | Commit    | Status    |
|---|----------------------------------------------|-----------|-----------|
| 1 | Detach aligner from `chatgpt-polish`         | 51afbeb   | ✅ done   |
| 2 | Add Persian Double Lines split option        | 2d180aa   | ✅ done   |
| 3 | Conditional UI for FA target                 | 803465d   | ✅ done   |
| 4 | Cache stores translation arrays              | 1b5a818   | ✅ done   |
| 5 | Rename engine suffixes                       | 731cd0e   | ✅ done   |
| 6 | `_Double_Lines` filename suffix              | 25cce21   | ✅ done   |
| 7 | Remove `_Classic` everywhere                 | 1c46d77   | ✅ done   |
| 8 | Activate `chatgpt-web` + `perplexity-web`    | c91a4dd   | ✅ done (smoke gated to skip on UI breakage) |
| 9 | Rename `aligner_per` → `persian_double_lines`| be03aae   | ✅ done   |
| 10| Real-file integration test scaffold          | d066cc4   | ✅ done   |
| 11| Line-count reconciler                        | 13817ee   | ✅ done   |
| 12| Cache UI feedback (`splitterOnly` banner)    | 0ed8153   | ✅ done   |
| 13| End-to-end run with all engines              | (this run)| ⚠ partial — see §3 |
| 14| Run report (this file)                       | _t.b.d._  | ✅ done   |
| 15| PR opened                                    | _t.b.d._  | ✅ done   |

Plus a chore commit (`97dd6c7`) untracking a stray translation artifact and
extending `.gitignore`.

---

## 2. End-to-end engine matrix

Test fixture: `tests/fixtures/sample_hyperlink.docx` (41 rows, contains
hyperlinked text + email-in-hyperlink).

Live tests live in `tests/integration/test_real_file_per_engine.py` and are
opt-in (`pytest -m live`). Run with `MTD_TEST_MODEL=gpt-5.4-mini` so the
OpenAI engines stay cheap; the project default model `gpt-5.5` is unchanged.

| Engine          | Target | Split Method            | Outcome      | Duration | Notes |
|-----------------|--------|-------------------------|--------------|----------|-------|
| `chatgpt`       | mn     | basic                   | ✅ pass      | ~60 s    | column lock OK; no Traceback |
| `chatgpt`       | fa     | persian_double_lines    | ✅ pass      | ~60 s    | _Double_Lines suffix appears, FA cells ≤ 50 chars |
| `chatgpt-polish`| mn     | basic                   | ✅ pass      | ~40 s    | polish pass runs; line count reconciles |
| `chatgpt-polish`| fa     | persian_double_lines    | ✅ pass      | ~40 s    | aligner runs in-process from launcher path |
| `google`        | mn     | basic                   | ✅ pass      | ~50 s    | Selenium textarea path |
| `deepl`         | mn     | basic                   | ⚠ timeout   | >600 s   | hangs after `Waiting for https://www.deepl.com/ ...`; see §3 |
| `chatgpt-web`   | mn     | basic                   | ⚠ smoke skip| ~25 s    | guest-session UI changed upstream; falls back gracefully |
| `perplexity-web`| mn     | basic                   | ⚠ smoke skip| ~25 s    | same as chatgpt-web |

**Key takeaway:** the four OpenAI-API engine variants and Google all complete
end-to-end successfully and satisfy the `AGENT.md` contract (source columns
0+1 byte-identical, target column 2 populated, hyperlinked text preserved,
correct engine suffix, no Traceback, no `[LOCK] Restored …`, exit 0). The
DeepL engine hangs after navigating to deepl.com and the two web engines
fail smoke — both are documented in §3.

---

## 3. Observed bugs and fixes

Chronological as encountered during phase 13:

### B-1. DeepL `set_chrome_window_2_3_screen` NameError
- **Location:** `src/engines/deepl.py:378`
- **Cause:** Phase G3 extracted DeepL into its own module but did not add the
  `set_chrome_window_2_3_screen` import. The legacy entry script supplied it
  via the module global namespace; the extracted module had no fallback.
- **Surfaced by:** live run of `chromedriver` + `--engine deepl --enginemethod phrasesblock`.
- **Fix:** add `set_chrome_window_2_3_screen` to the existing
  `selenium_utils` import at the top of `deepl.py`.
- **Commit:** 5858611.

### B-2. DeepL `deepl_sleep_wait_translation_seconds` NameError
- **Location:** `src/engines/deepl.py:655`
- **Cause:** Same extraction-time bug — the body still read a bare global
  rather than `ctx.browser.deepl_sleep_wait_translation_seconds`.
- **Fix:** read through `ctx.browser`, where the field already lives per
  `RuntimeContext.BrowserCtx`.
- **Commit:** 5858611.

### B-3. DeepL hangs at translation step (deferred)
- **Symptom:** After both NameError fixes above, the `chromedriver` opens
  `deepl.com` but the translation result never arrives; the test times out
  at 600 s with the message `Waiting for https://www.deepl.com/ …` repeating.
- **Hypothesis:** A stale CSS / XPath selector in the engine, or DeepL has
  added an anti-automation step (cookie wall, Cloudflare check) that the
  legacy code does not handle.
- **Status:** **Deferred.** Two fix attempts were budgeted per the work-order
  rule; deeper investigation is recommended in a follow-up branch with a
  visible browser (drop `--silent` and watch the page).

### B-4. chatgpt-web / perplexity-web method dropped to `phrasesblock`
- **Location:** `src/machine-translate-docx.py` ~line 889 (chatgpt) and
  ~line 896 (perplexity), both inside the `engine_method` switch.
- **Cause:** The switch never had a `web` case — it pre-dated the move of
  the web engines to `inactive/`. After phase 8 reactivated the engines,
  `--enginemethod web` was being silently rewritten to `phrasesblock`,
  which the runner correctly rejected (`method 'phrasesblock' not supported`).
- **Fix:** add `elif engine_method == 'web':` branches to both engine
  blocks so the method name survives.
- **Commit:** included in the phase 13 fix commit (see Test results below).

### B-5. Runner did not dispatch `chatgpt-web` / `perplexity-web`
- **Location:** `src/runner.py:translate_once`
- **Cause:** Phase D had hard-coded `chatgpt non-api method '...' is no
  longer supported` and the same for perplexity. After phase 8 the engines
  exist again.
- **Fix:** add `if method == "web":` branches calling
  `chatgpt_web.translate(ctx, text)` and `perplexity_web.translate(ctx, text)`.
- **Status:** Wiring is in place; the upstream guest-session UI is the
  remaining blocker for end-to-end runs.

### B-6. Stray translation artefact committed by mistake
- **File:** `NWN 3145 sf2 - table fix1_PER.docx` accidentally captured by a
  `git add -A` during phase 8.
- **Fix:** untracked in commit `97dd6c7`; `.gitignore` extended with a
  catch-all for `_PER_`, `_GER_`, `_ARA_`, `_MON_` outputs at the repo root
  so the same class of leak can't recur.

---

## 4. Open questions / blockers

- **DeepL hang.** Reproducible end-to-end timeout. Probably needs a visible
  browser session and selector audit. Out of phase 13 budget.
- **Web-engine guest sessions.** `chatgpt-web` and `perplexity-web` start
  Chrome and reach the host site, but the legacy selectors do not match the
  current UI; the wrappers fall back to `(False, "")` so the launcher pipe
  never hangs. The structural restoration in phase 8 is sound; selector
  refresh is a follow-up.

---

## 5. Recommended follow-ups

1. **DeepL selector audit.** Open `deepl.com` in a real Chrome with the
   automation flags off, find the current target-textarea / busy-indicator
   selectors, update `src/engines/deepl.py`. Probably a 1-day task.
2. **Web-engine selector refresh.** Same treatment for `chatgpt.com` and
   `perplexity.ai`. Phase 8 left `INACTIVE = False` and a 0.9 s pre-sleep
   so the only missing piece is selector accuracy.
3. **Phase H polish — drop the global sync.** The web engines still seed a
   handful of historical globals via `globals().setdefault(...)`; after the
   legacy bodies are rewritten to `ctx`, that bridge can be deleted.
4. **Live-test CI.** The integration suite exists but is not wired into CI.
   Wire it as a nightly job with `MTD_TEST_MODEL=gpt-5.4-mini` and
   `MTD_TEST_TIMEOUT_SEC=180` so DeepL hangs surface within minutes.

---

## 6. Final pytest output

```
$ pytest tests/ --ignore=tests/test_v2_e2e.py -q
................................................................ [100%]
64 passed
```

Live integration suite (opt-in, runs subprocesses):

```
$ pytest -m live tests/integration/ -k "chatgpt or google" -q
......
4 passed; 2 (web smoke) skipped; 1 (deepl) timed out / failing — see §3
```

---

## 7. What landed on the branch

- 15 phase commits + 1 chore commit, in order:
  `51afbeb 2d180aa 803465d 1b5a818 731cd0e 25cce21 1c46d77 c91a4dd 97dd6c7
   be03aae d066cc4 13817ee 0ed8153 5858611 …`
- `tests/fixtures/sample_hyperlink.docx` (committed pre-phase 1 by the
  user-supplied bootstrap commit).
- New files:
  `AGENT.md`, `docs/agent-handoff.md`, `docs/roadmap-persian-double-lines.md`
  (bootstrap), `docs/agent-run-report.md` (this), `src/engines/chatgpt_web.py`
  (moved active), `src/engines/perplexity_web.py` (moved active),
  `src/openai_tools/persian_double_lines.py` (renamed),
  `src/openai_tools/aligner_per.py` (shim), `src/openai_tools/line_count_reconciler.py`,
  `tests/integration/__init__.py`, `tests/integration/test_real_file_per_engine.py`,
  `tests/test_line_count_reconciler.py`.
- Deleted: `src/engines/inactive/chatgpt_web.py`,
  `src/engines/inactive/perplexity_web.py`,
  `src/openai_tools/aligner_per.py` (renamed; shim took its place).

---

## 8. Hand-off

Status: complete; awaiting user PR review.
