# Agent handoff — entry point

> Read this first. Then `AGENT.md` for the rules. Then
> `docs/roadmap-persian-double-lines.md` for the phase plan.

---

## Status

```
date          2026-05-10
branch        next/persian-double-lines-as-splitter (post-merge: archive tag)
base          master @ c8f284c (pre-merge)
phases done   15 of 15
post-phases   DeepL fixes, Google fixes, web-engine audit, timing alignment,
              perplexity block-mode, chatgpt-web pre/post submit split
status        merged to master 2026-05-10; branch tagged archive/*
```

Run report: [`docs/agent-run-report.md`](agent-run-report.md). Live
integration matrix after the post-phase fixes: 5 of 5 production
scenarios pass (all four engines real-file verified except the two
web-engine guest sessions — chatgpt.com Cloudflare gate and
perplexity.ai selector drift — which are recorded as recommended
follow-ups).

The `gh` CLI is not installed in the agent environment, so phase 15's
PR was not opened automatically. The PR title + body are pre-composed
in [`docs/PR-text.md`](PR-text.md) — open the PR manually via that
file or the GitHub web UI:

```
gh pr create \
  --base master \
  --head next/persian-double-lines-as-splitter \
  --title "Persian Double Lines as a Split Method" \
  --body-file docs/PR-text.md
```

## What the user just verified on master

- ChatGPT API engine end-to-end: works. Translated en→mn on a
  16-row sample.
- `[LOCK] Restored …` regression: closed (false-positive cured).
- Hyperlinked text in cells: now reaches the translator (no more
  silently-dropped link text).
- Google web javascript engine: inherent dead — modern Chrome
  blocks it on `file://` URLs. Fail-fast message added.
- 51 / 51 unit tests pass on master.

## What is missing on master that this branch fixes

- The aligner is glued to the chatgpt-polish engine. There is no
  way to use it with Google or DeepL.
- There is no engine suffix on output filenames; everyone gets
  `_PER` regardless of which engine produced it.
- `_Classic` is dead code that still ships.
- Two web engines (`chatgpt_web`, `perplexity_web`) sit in
  `src/machine_translate_docx/engines/inactive/`.
- The cache stores whole docx files, so the user pays for the
  engine again every time they want a different splitter.
- LLM engines occasionally return wrong line counts; the fallback
  is padding/truncation, not a re-ask.
- There is no real-file fixture in the repo and no end-to-end
  integration test.

## Decisions already made (do not re-litigate)

- `aligner_per` becomes a Split Method, not an engine option.
- The new option is named `Persian Double Lines` in UI,
  `persian_double_lines` in code.
- Default Split Method for FA: `Persian Double Lines`.
- Default Split Method for non-FA: `basic with excel file`.
- Output files: one per job. No more multi-file drops.
- Engine suffixes: `_Google`, `_Deepl`, `_chatGPT`, `_Polish`,
  `_web_chatGPT`, `_web_Perplexity`.
- Polish is a separate engine (`chatgpt-polish`) that does
  translate + polish but does NOT run the aligner. The aligner is
  reachable only through the Split Method dropdown.
- Cache stores translation arrays, not docx; a new split request
  reuses the cached translation and just re-splits.
- Line-count reconciler runs only for LLM engines, max 2 attempts
  with `gpt-5.4-mini`, then falls back to existing logic.
- End-to-end tests use `gpt-5.4-mini` to keep cost down. Project
  default model is unchanged.
- Web engines do not require login; they use a guest session and
  must sleep between phrase requests so the host site does not
  block. Old timing values may be on `origin/main`.
- Fixture path: `tests/fixtures/sample_hyperlink.docx`.
- `splitTranslate` checkbox stays. Unchecked = no split runs.

## Where to start

```
phase 1   detach aligner from chatgpt-polish post-translation block
              src/machine-translate-docx.py near the comment
              "Phase 2: Double — FA mechanical aligner (no LLM)"
              and the matching Classic block above it
phase 2   add the new Split Method option to both frontends
              index.ejs   (legacy, served at /)
              web/v2/index.html
phase 3   conditionally show / hide based on target language
phase 4   rewrite cache layer in local_launcher.py
phase 5   rename suffixes in save_docx_file + everywhere
phase 6   append _Double_Lines suffix when split = persian_double_lines
phase 7   remove _Classic everywhere
phase 8   reactivate chatgpt_web + perplexity_web
phase 9   rename module aligner_per.py → persian_double_lines.py
phase 10  copy fixture + add live integration test
phase 11  build src/machine_translate_docx/openai_tools/line_count_reconciler.py
phase 12  cache UI feedback (cacheHit + splitter_only flag)
phase 13  end-to-end test all engines
phase 14  write docs/agent-run-report.md
phase 15  open PR
```

Detail of each phase: `docs/roadmap-persian-double-lines.md`.

## Test fixture location

```
tests/fixtures/sample_hyperlink.docx
```

41 rows. Contains:
- A row with hyperlinked text (`hyperlink with alt text`).
- A row with an email address inside a hyperlink
  (`smtv.bot@gmail.com`).
- Cells with grey / blue / pink shading (which the engine must skip).
- A sample DOCX subtitle table with two header rows.

Use it for every engine's smoke + end-to-end run.

## Environment expectations

- `OPENAI_API_KEY` set in env (the user has it).
- `python E:/Python311/python.exe` is the working Python.
- Chrome installed for Selenium engines.
- Tests run via:
  ```
  E:/Python311/python.exe -m pytest tests/ --ignore=tests/test_v2_e2e.py -q
  ```
- Live integration test (you write in phase 10) runs only when
  `pytest -m live` is invoked explicitly.

## Constraints summary (the short list)

C1  aligner model = gpt-5.4-mini, never parameterise away.
C2  no reasoning_effort on translator.
C3  _normalize_lang() read-only.
C4  every OpenAI call: extra_body={"prompt_cache_retention": "24h"}.
C5  no timestamp prefix in output filenames.
C6  file collision suffix: _1, _2, never overwrite.
C7  both UIs (legacy / and v2 /v2/) keep working.
C8  local_launcher.py changes additive only.
C9  subprocess.Popen bufsize=1.
C10 _sync_globals_from_ctx after parse / driver-create / translate / split.
C11 selenium helpers with reassigned `driver` must seed from ctx.browser.driver.
C12 legacy frontend overlay-hide BEFORE await showAlert.
C13 source-language column frozen (deepcopy snapshot + restore).
C14 docs are English-only.
C15 no bare `except:`.
C16 input() respects --silent.
C17 archived branches are tags only (archive/*).

Full text in `PROJECT_MEMORY.md`.

## Open questions for user

(empty at handoff time — append here if you hit a blocker)

---

## When you finish

1. Make sure `pytest tests/ --ignore=tests/test_v2_e2e.py -q` is
   `51 passed` (or more, if you added unit tests).
2. Make sure all 15 phases have a commit on the branch.
3. Make sure `docs/agent-run-report.md` exists and is filled in.
4. `gh pr create --base master --head next/persian-double-lines-as-splitter`
   with a body that links the report.
5. Update this handoff doc's status to:
   ```
   status        complete; awaiting user PR review
   ```
6. Stop. Do not merge.
