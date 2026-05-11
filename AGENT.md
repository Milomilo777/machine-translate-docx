# AGENT.md — operating manual for AI agents on this repo

You are continuing work on `machine-translate-docx`. The user has
delegated this branch to you with full autonomy. Read this file
fully before any code change.

---

## Active branch

```
next/persian-double-lines-as-splitter
```

Do **not** push to `master` directly. When the work is done, open a
PR. The user will merge it manually.

---

## Mission

Decouple the FA aligner from the OpenAI-polish pipeline and turn it
into a generic Split Method that pairs with any engine. Rename
output suffixes per engine. Activate two previously-inactive web
engines. Add a real-file fixture and end-to-end test every engine.
Add a line-count reconciler for LLM engines. Produce a Markdown
report at the end.

Full plan: [`docs/roadmap-persian-double-lines.md`](docs/roadmap-persian-double-lines.md).
Current state and entry point: [`docs/agent-handoff.md`](docs/agent-handoff.md).

---

## Hard rules — never violate

1. **Source language column is frozen.** Columns 0 + 1 of any input
   docx must be byte-identical between parse-time and save-time. The
   `[LOCK] Restored …` log line being absent is part of the success
   criteria; if it appears, something drifted and you must fix the
   leak source — do not just suppress the message.

2. **Aligner model is hardcoded `gpt-5.4-mini`.** Never parameterise
   this away. The user has tested this model specifically.

3. **Translator + polisher default model stays `gpt-5.5`.** End-to-end
   tests *override* to `gpt-5.4-mini` via `--aimodel gpt-5.4-mini`
   to save cost. Do not change the project default.

4. **No `reasoning_effort` on the translator.** It caused 94 % token
   overhead.

5. **Every OpenAI API call** must include
   `extra_body={"prompt_cache_retention": "24h"}`.

6. **No `bare except:`.** Always `except Exception:` or specific.

7. **`local_launcher.py` `subprocess.Popen` must keep `bufsize=1`.**
   Without it, PROGRESS markers stall.

8. **No silent destructive ops** — `git reset --hard`, `force-push`,
   `rm -rf` outside `runtime_dir`, deleting tags, deleting branches
   other than your own intermediates: all require user confirmation.
   Stop and write the question into the handoff doc instead.

9. **All committed `.md` documentation is English.** Persian belongs
   to user conversation, never to a commit. Linguistic sample data
   in code fences is fine.

10. **Auto-commit + auto-doc.** After every code change:
    - Commit immediately on the current branch.
    - Update `CHANGELOG.md` (newest-first).
    - Push to origin.
    - Update `PROJECT_MEMORY.md` if a constraint or invariant changes.

11. **One file out per job.** No more multi-file outputs. If the user
    wants both the basic output and the Double-Lines variant, they
    issue two requests; the cache layer reuses the translation.

12. **Tests pass at every commit.** Run `pytest tests/
    --ignore=tests/test_v2_e2e.py -q` before each commit. If it
    fails, do not commit.

---

## Soft rules — strong defaults

- Functions over 200 lines: if you touch one substantively, extract.
- Type hints on new public functions.
- Docstrings on every new public function.
- One commit per logical change. Avoid 1000-line "do everything"
  commits.
- New module under `src/openai_tools/` or `src/engines/` should have
  a one-paragraph docstring at the top explaining what it owns.

---

## Boundaries that need user approval

Stop and write the question into `docs/agent-handoff.md` (under
`## open questions for user`) when you would otherwise:

- Add a new pip / npm dependency.
- Change the default OpenAI model in user-facing config (UI dropdown
  options, CLI default).
- Modify the API contract that the legacy `index.ejs` frontend uses
  (endpoint shapes, field names, response keys).
- Delete or rewrite a documented engine flow.
- Touch `prompts/translate_PER.txt` or `prompts/polish_PER.txt`
  (these are the user's pet prompts).
- Bypass `_sync_globals_from_ctx` or any of the C9–C13 invariants
  in `PROJECT_MEMORY.md`.

For routine changes (one function, one test, one helper, one
typo) — proceed without asking.

---

## End-to-end test contract

After implementation, run a real-file translation against the
fixture for **every engine** and verify:

```
fixture:  tests/fixtures/sample_hyperlink.docx
target:   mn  (Mongolian)  — keep test cheap and unambiguous
model:    gpt-5.4-mini for the OpenAI engines
```

For each output docx:

1. Source columns 0 + 1 match the parse-time snapshot exactly.
2. Target column 2 is non-empty for every translatable row.
3. Hyperlinked source text appears in the translated cell (not
   silently dropped — this is the regression we just fixed).
4. Output filename has the correct engine suffix
   (`_Google` / `_Deepl` / `_chatGPT` / `_Polish` / `_web_chatGPT`
   / `_web_Perplexity`).
5. If `Persian Double Lines` was selected, the filename also ends
   `_Double_Lines` and every FA cell ≤ 50 display chars.
6. No `Traceback` lines in the launcher stdout.
7. No `[LOCK] Restored N source-column cell(s)` line.
8. Exit status `done` (not `error`).

Web engines (`web_chatGPT`, `web_Perplexity`): smoke test only —
boot the engine, confirm the dispatcher resolves, attempt a single
short phrase. If it fails because of login or rate-limit, log the
failure but do not block phase completion.

---

## Communication

You operate without a human in the loop. The deliverable is the PR
+ the markdown report. Talk to the user only via:

- Commit messages (concise, conventional commit style).
- `CHANGELOG.md` (running log, newest-first).
- The final report at `docs/agent-run-report.md`.
- `docs/agent-handoff.md` for any blocker or open question.

Do not delete that handoff doc when you finish — overwrite its
status section with "complete" and append your final notes.
