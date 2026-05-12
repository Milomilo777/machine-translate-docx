<!--
  JULES TASK PROMPT — DEEP ARCHITECTURAL AUDIT (Phase 2)
  File: jules-prompt-deep-audit.md
  Created: 2026-05-12
  Usage: Paste the content of <task> below into Jules as the task prompt.
-->

<task>
You are doing a **deep read-only architectural audit** of the same Python +
JavaScript project you audited in `audit-from-Jules -2026-05-12.md`.
That first pass identified 13 findings (A1–A13). **Do not re-report those.**
This second pass must go far deeper — read every file in the repo, examine
actual code at the line level, and produce one comprehensive report.

**STRICT RULE — DO NOT MODIFY ANY FILE.**
Read only. No edits, no re-formatting, no test runs that write artefacts.
Your single deliverable is one Markdown report at the project root:

  `audit-deep-2026-05-12.md`

(You may write that one file. Nothing else.)

---

## Context recap

- Entry point: `src/machine_translate_docx/cli.py` (~4 364 lines)
- Web layer: `local_launcher.py` (~96 KB) + `web/v2/` (JS SPA) + `index.ejs` (legacy EJS UI)
- Engines: `src/machine_translate_docx/engines/` — DeepL, Google, ChatGPT
- OpenAI tools: `src/machine_translate_docx/openai_tools/` — retry, reconciler,
  persian_double_lines, translator, polisher
- Runtime state: `src/machine_translate_docx/runtime.py` (DocxCtx, parallel arrays — A5)
- Prompts: `prompts/` — FA-specific .txt files
- Docs: `docs/`, `PROJECT_MEMORY.md`, `CLAUDE.md`, `CHANGELOG.md`
- Tests: `tests/`
- Already-fixed issues from `docs/debug-2026-05-11-night.md`: skip those.
- Still-open from that doc: **F5, F6, F8** (confirmed open by A8, A9, A10).

---

## PHASE 1 — Map the codebase (read everything, write nothing)

Before writing any finding, read these files **completely** in this order.
For each file, note: approximate line count, top-level symbols
(classes/functions/globals), and any immediate smell.

### 1-A  Core source tree

Read every `.py` file under `src/` top-to-bottom. Minimum files to read:

```
src/machine_translate_docx/__init__.py
src/machine_translate_docx/cli.py                ← monolith; read all 4 364 lines
src/machine_translate_docx/runtime.py
src/machine_translate_docx/docx_io/              ← all files
src/machine_translate_docx/engines/              ← all files
src/machine_translate_docx/openai_tools/         ← all files incl. _retry.py,
                                                    persian_double_lines.py,
                                                    line_count_reconciler.py
```

While reading `cli.py`, build a mental map of every function:
- Which still read module-level globals vs. which use `ctx` / `RuntimeContext`
- Exact locations of bare `except:` and `except Exception: pass`
- Every call to `subprocess` (note shell=True vs. shell=False vs. list-form)
- Every file-path construction (f-string, os.path.join, pathlib)
- Every place a `.docx` is written — can any produce a zero-byte or empty file?

### 1-B  Web / launcher layer

```
local_launcher.py         ← read all ~2 900 lines
server.js                 ← read fully
index.ejs                 ← read fully (legacy EJS template)
web/v2/                   ← read all JS/HTML/CSS files
```

For `local_launcher.py`:
- List every `subprocess.Popen` / `subprocess.run` call; note shell=True occurrences
- Identify every route handler; note which ones read user-supplied path components
- Find the failure-archive logic; trace job_id through every step
- Find the Telegram alert path; can it fire on a non-failure? Can it fail silently?
- Find any blocking I/O in async context (asyncio event loop, if used)

For `web/v2/app.js` (or equivalent):
- List every `innerHTML` / `outerHTML` / `document.write` assignment
- List every place user-controlled JSON is rendered into the DOM
- Check for missing `encodeURIComponent` on URL parameters
- Check for `eval()` or `new Function()`

### 1-C  Prompts & Persian logic

```
prompts/*.txt             ← every prompt file
src/.../openai_tools/persian_double_lines.py
src/.../openai_tools/translator.py
src/.../openai_tools/polisher.py
```

For each prompt file, evaluate:
- Is the **static prefix** as long as possible before any dynamic substitution?
  (OpenAI prompt cache works on prefix — the longer the static prefix, the more
  tokens are cached. Flag any prompt where variable substitution appears in the
  first 1 024 tokens.)
- Does the prompt mix system-level rules with per-document data in the same
  role/message? (That's cache-hostile — flag it.)
- Length: is it under the recommended system-prompt token budget?
- Persian-specific: does it address ZWNJ, half-space, RTL markers, subtitle
  line-length (≤ 50 chars), dual-line alignment?

For `persian_double_lines.py`:
- Trace the full algorithm step by step.
- Does it handle lines that contain ONLY punctuation / numbers correctly?
- Does it handle `\u200c` (ZWNJ) and `\u200f` (RLM) correctly?
- Can it produce misaligned output if the OpenAI call returns N≠expected lines?
- Are there edge-case inputs that would cause an IndexError or silent truncation?

### 1-D  Retry, reconciler, and reliability paths

```
src/.../openai_tools/_retry.py
src/.../openai_tools/line_count_reconciler.py
```

- `_retry.py`: Does it retry on `RateLimitError`? `APITimeoutError`?
  `APIConnectionError`? `AuthenticationError` (should NOT retry)?
  Is the back-off exponential or fixed? Is there a jitter?
  Can it retry forever? What is the max attempt count?
- `line_count_reconciler.py`: What happens if all attempts fail?
  Does the caller receive a clear error or a silently-padded list?
  Is the reconciler ever called with an empty list? What happens then?

### 1-E  Tests

```
tests/                    ← every test file
pyproject.toml            ← pytest config, markers
```

- List every test file and its approximate coverage target.
- Which modules have **zero** test coverage?
- Are `live` tests actually gated? What marker/condition controls them?
- Are there tests for the Persian aligner? The retry logic? The reconciler?
- Any test that imports but never asserts (useless tests)?

### 1-F  Docs and workflow files

```
CLAUDE.md
PROJECT_MEMORY.md         ← check C17, C20, C23 entries
docs/                     ← all .md files
CHANGELOG.md              ← last 20 entries
.github/                  ← CI/CD workflows
.claude/rules/            ← all rule files including security.md
pyproject.toml            ← linter/formatter config
Makefile
```

- Is `CLAUDE.md` still accurate? Does it describe modules/files that no longer exist, or omit new ones?
- PROJECT_MEMORY C20 (failure-archive + Telegram): does the actual code match the documented design?
- Are there any CHANGELOG entries marked "TODO" or "FIXME" that were never resolved?
- What linters are configured? Are any important ones missing (bandit, semgrep, mypy strict)?
- Does the CI workflow run on every push, or only on main?

---

## PHASE 2 — Write findings

After reading everything, write the report. Use **exactly** this structure
for each finding (same shape as A1–A13):

```
### B<N> — <short title>
- **Severity:** Critical | High | Medium | Low
- **Category:** Architecture | Performance | Reliability | Security | Workflow | Persian-specific
- **Location:** `path/to/file.py:line-line`
- **What it is:** 1–3 sentences. Quote ≤ 10 lines of code if helpful.
- **Why it matters:** concrete impact.
- **Recommendation:** what to do; tight and actionable.
- **Effort:** S (<1h) | M (half a day) | L (1+ day)
```

Number findings B1, B2, B3 … (continuing after the A-series).

### Mandatory finding categories to cover

You MUST produce at least one finding in each of the following categories.
If you genuinely find nothing wrong, write the finding as Severity: Low with
the explanation "no defect found; documented as reviewed."

**Architecture (deep)**
- The exact set of functions in `cli.py` that still read module-level globals
  (list them by name and line number)
- Dead code: functions/classes that are defined but never called from any
  import graph path
- Circular import risks in the `openai_tools/` sub-package
- Oversized functions: any function > 100 lines that is not obviously a
  data-table declaration — give the name, line range, and cyclomatic-complexity estimate

**Performance (deep)**
- Every blocking `time.sleep()` or synchronous HTTP call on a path that could
  be parallelised (list file:line for each)
- Token waste: any prompt that re-sends the full document context when only a
  diff was needed
- Any OpenAI call that does NOT set `max_tokens` / `max_completion_tokens`
  (unbounded response = cost risk)
- DOM re-render loops in `web/v2/app.js`: any `innerHTML` set inside a loop or
  a polling interval without a dirty-check

**Reliability (deep)**
- Every code path that writes a `.docx` file — can any of them complete
  "successfully" (no exception raised) but produce an empty or structurally-invalid
  document? Trace from the write call back to the data source.
- The Telegram alert path: can it throw an uncaught exception that kills the
  job thread? Is it in a try/except?
- `line_count_reconciler.py`: what is the worst-case output if the LLM returns
  garbage (random text, wrong count, empty string)?
- Race condition risk in `local_launcher.py`: if two requests arrive for the
  same `job_id` simultaneously, what happens to the output file?

**Security (deep)**
- Go beyond A2. List **every** `subprocess` call in the entire codebase
  (file:line, command, shell=True/False). For each one with `shell=True` or
  a command assembled from user/file data, assess the injection surface.
- File upload handler in `local_launcher.py`: is the MIME type checked?
  Is the file size capped? Is the filename sanitised before it touches the
  filesystem? Trace the upload path end-to-end.
- Does `index.ejs` or `server.js` set security headers
  (Content-Security-Policy, X-Frame-Options, X-Content-Type-Options)?
- Can a user enumerate job outputs of other users via the download endpoint?
  Is `job_id` truly unguessable?

**Persian-specific (deep)**
- `persian_double_lines.py`: walk through the algorithm for an edge-case input
  of exactly 1 line, 0 lines, and a line containing only ZWNJ characters.
  What does each case return?
- `prompts/translate_PER.txt` and `prompts/polish_PER.txt`: count the static
  prefix tokens before the first `{variable}` substitution. Is it > 1 024?
  (Under 1 024 means the cache is not warming up at all on short prompts.)
- Subtitle line-length rule: is the ≤ 50-char limit enforced in code, or only
  requested in the prompt? If only in the prompt, quote where and assess reliability.
- ZWNJ normalisation: is `\u200c` normalised before being sent to DeepL or
  Google? What does DeepL do with ZWNJ? (Note as "needs investigation" if unclear
  from the code alone.)

**Workflow / repo hygiene (deep)**
- Are there files committed that match patterns in `.gitignore` (e.g. `.env`,
  `*.log`, output `.docx`)? List any you find.
- Is there a `requirements.txt` or `requirements-lock.txt` that diverges from
  `pyproject.toml` dependencies? Pinned versions vs. ranges — which files are
  authoritative?
- The batch files (`compile.bat`, `run_local_launcher*.bat`, `tasks.bat`):
  do they contain hard-coded absolute paths (e.g. `C:\Users\...`) that would
  break on another machine?
- Any TODO/FIXME/HACK comment older than the last CHANGELOG entry — quote file
  and line.

---

## PHASE 3 — Cross-cutting observations

After the B-series findings, add a short section:

```
## Cross-cutting observations

### Migration progress
Estimate (based on line counts): what % of cli.py functions have been
migrated to pass `ctx` explicitly? What % still rely on `_sync_globals_from_ctx`?

### Test coverage estimate
For each major module, estimate coverage:
| Module | Estimated coverage | Has live tests? |
|--------|-------------------|-----------------|
| cli.py | ...% | yes/no |
| ...    | ...  | ...    |

### Prompt cache utilisation estimate
For each prompt file, estimate the static prefix token length.
Flag any prompt with < 1 024 static prefix tokens as "cache-cold."

### Top 5 highest-risk paths
List the 5 execution paths most likely to fail silently or corrupt output,
with a one-line description and the relevant finding IDs.
```

---

## Report format

```
# Antigravity deep audit — 2026-05-12

## Executive summary
(5–8 bullets covering the highest-impact NEW findings beyond A1–A13.)

## Findings
(B1, B2, … — use the shape above)

## Cross-cutting observations
(the three sub-sections above)
```

- Cite file paths and line ranges as `path:line` so the reviewer can jump.
- Quote at most ~10 lines of code per finding.
- Do NOT speculate beyond what the code shows.
- Do NOT re-report A1–A13. Reference them by ID if a new finding builds on them.
- Keep the whole report under ~3 500 lines.
- If you find something in `docs/debug-2026-05-11-night.md` already marked **fixed**, skip it.

---

## Constraints — DO NOT

- Do NOT modify any file except writing `audit-deep-2026-05-12.md`.
- Do NOT commit, open a PR, run the test suite, or start the dev server.
- Do NOT compare against any upstream fork.
- Do NOT invent file paths; only cite paths you have actually read.

When the report file is written, stop.
</task>
