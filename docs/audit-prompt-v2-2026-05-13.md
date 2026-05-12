# Deep architectural audit — prompt v2 — 2026-05-13

Re-issue of the Jules / Antigravity / Codex audit prompt with fixes for the
weaknesses uncovered in the first three passes (stale snapshots, hand-wavy
estimates, duplicate findings).

---

## What the prior prompts got wrong

1. **No snapshot anchor.** Jules read a stale branch (`fa8fa4a` not yet
   on it), produced "cache-cold prompts" claims that contradicted the
   committed state, and named retired functions as live bottlenecks.
   → Every audit must record the **commit hash** it was run against.
2. **Estimates instead of measurements.** All three external auditors
   guessed token counts ("~300 tokens"), coverage ("~25 %"), and
   complexity ("> 100 lines"). → Audit must invoke real tools
   (`tiktoken`, `radon` / `lizard`, `pytest --co -q`, `coverage`).
3. **No proof-of-read.** Several findings cited line ranges that were
   wrong or pointed at retired code. → Every finding cites a commit-anchored
   `path:line` pair AND the auditor must paste the exact code block being
   critiqued before naming the defect.
4. **No deduplication signal.** Auditors re-reported findings that prior
   passes had already closed. → Audit must run against an explicit
   exclude-list: every prior finding ID + the commit that closed it.
5. **"Mandatory categories" produced filler findings.** When a category
   had nothing wrong, auditors invented something. → Mandatory categories
   stay, but a clean category emits "no defect found; documented as
   reviewed" with a one-line evidence statement.

---

## The improved prompt

````
<task>
DEEP ARCHITECTURAL AUDIT — pass N — read-only.

PROJECT: machine-translate-docx (Python 3.11 + plain-JS SPA + Selenium
+ OpenAI API). 4 000-line CLI monolith, 2 900-line launcher, ~6 prompt
files, ~115-line aligner.

ANCHOR: Run against commit `<HASH>` of branch `master`. Record the
hash in the first line of your output report. Do NOT compare to any
other commit, branch, or fork.

EXCLUDE LIST (already fixed — do NOT re-report; reference by ID only):
  • Antigravity-light:  A1–A7
  • Codex (5.5) light:  A1–A15
  • Jules light:        A1–A13
  • Antigravity-deep:   B1–B20 (12 fixed, 8 deferred; see docs/audit-light-2026-05-12.md)
  • Jules deep:         B1–B8  (3 fixed, 2 stale rejected, 3 already covered)
  • debug-2026-05-11-night: F1, F2, F3, F7a, F7b, F7c   FIXED
                            F5, F6                       FIXED (closed by prompt rewrite)
                            F8                           OPEN — known
  Confirmed-open (do NOT re-report unless you have new evidence):
    F8 polish modify-rate report mismatch

DELIVERABLE: a single Markdown report at `docs/internal-audit-<date>.md`.

---

PHASE 0 — Tool inventory and snapshot proof

Before reading any source file, verify your tools work and record their
output. Paste each tool's first line of output into the report.

  $ git rev-parse HEAD                           # commit anchor
  $ git log -1 --format="%s"                     # last commit subject
  $ ls -la prompts/                              # files actually on disk
  $ wc -l src/machine_translate_docx/cli.py      # actual line count
  $ python -c "import tiktoken; print(tiktoken.__version__)"

If `tiktoken` is not installed:
  Pip-install in a venv WITHOUT touching the project venv. Token counts
  matter; do not guess.

PHASE 1 — Measured static analysis

For every prompt file under `prompts/`:
  • Count tokens with `tiktoken.encoding_for_model("gpt-4o").encode(...)`.
  • Report the SYSTEM-prompt static prefix length (the bytes that are
    byte-identical across every call). If the prompt is composed
    (e.g. `_smtv_locks.txt` + `translate_PER.txt`), measure the
    concatenated form.
  • Flag any prompt where the static prefix is < 1 024 tokens
    (OpenAI prompt cache cold) OR > 8 000 tokens (token-cost risk).

For every function > 80 lines in `cli.py`:
  • Report: line range, name, cyclomatic complexity (compute by hand:
    count `if / elif / for / while / try / and / or` branches inside
    the function and add 1).
  • Mark "L" if CC > 15, "M" if 8–15, "S" if ≤ 7.

For every `subprocess.Popen` / `subprocess.run` / `os.system` / `os.popen`
in the entire codebase:
  • Quote the exact line.
  • Note: shell=True? user-supplied path component? sanitised first?

For every `except:` (bare) or `except Exception: pass`:
  • Quote the surrounding 3 lines.
  • Justify: is the swallow intentional (e.g. optional sidecar) or risky?

For every `print(` that emits > one line of user / document data:
  • Same logging-hygiene treatment as Antigravity-light B5.

PHASE 2 — Trace 5 hot paths end-to-end

For each path below, list every file:line crossed, every state mutation,
every exit point. Identify any silent-fail edge case.

  P1  /upload → docx validation → cache lookup → subprocess spawn
       → first stdout line → progress marker → final file save
  P2  Translator single-call → reconciler (if mismatch) → polisher
       → cell write → save → aligner → save
  P3  DeepL login → translate block loop → fallback to singlephrase
       → fallback to google → save
  P4  v2 SPA upload → /status poll → cache-hit branch
       → splitter-only materialisation → download
  P5  Failure → TranslationFailure → [FAIL] reason=… → exit 20
       → launcher status=error → failure archive write
       → Telegram alert dispatch

For each, answer:
  • Where can data shape change? (e.g. line count, encoding, row count)
  • Where can a write succeed but produce a corrupt file?
  • Where is a global mutated that another thread might read?

PHASE 3 — Persian-specific

  • Run the aligner on a 0-line input, 1-line input, ZWNJ-only input,
    and a 1-row 600-char single-FA-string input. Record stats for each.
    Use `tools/aligner_bench.py` with `--llm-threshold 0`.
  • Open `prompts/translate_PER.txt` + `_smtv_locks.txt`. Verify the
    SHARED block is BYTE-IDENTICAL between translator and polisher
    (sha256 the concatenated prefix in both load paths).
  • Confirm the subtitle ≤ 50-char hard rule lives in code, not just
    in the prompt. Quote the enforcement site.

PHASE 4 — Repo hygiene

  $ git status --porcelain                 # uncommitted?
  $ git ls-files | grep -E "\\.(env|log)$" # committed secrets / logs?
  $ git ls-files | xargs grep -l "TODO\\|FIXME\\|HACK" | head -10
  $ find . -type f -name "*.bat"           # batch files
  $ ls .github/workflows/                  # CI presence
  $ cat pyproject.toml | grep -E "tool\\."  # linter config

PHASE 5 — Write the report

Use the same shape as prior audits (B<N> per finding) but with three
additional fields:

  - **Evidence:** paste the actual code block being critiqued (≤ 10 lines).
  - **Tool output:** if the finding is based on a tool measurement,
    quote the relevant tool output line.
  - **Duplicate-of:** if this builds on an existing finding ID, name
    it (e.g. "deep-A12 closed in f06a67c, new sub-defect").

Mandatory categories (Architecture, Performance, Reliability, Security,
Persian-specific, Workflow). If a category is clean, say so explicitly:
  "No new defect found; reviewed <file>:<lines> and confirmed
  intent." Do not invent filler.

End with a Cross-cutting section in the same shape as prior reports
PLUS a "Score" line: total findings, severity breakdown, % of
expected categories that produced real defects (vs "no defect found"),
and a one-line verdict on overall codebase health.

CONSTRAINTS
- Do NOT modify any file except writing the report.
- Do NOT re-run live OpenAI calls during the audit (no token cost).
- Do NOT compare to any prior fork or upstream.
- Do NOT invent file paths; cite only paths verified by `git ls-files`.
- Cap the report at 2 500 lines. Quality over quantity.
</task>
````

---

The remainder of this file is the audit I (Claude Opus 4.7) ran with
that prompt against commit `3149d75` of branch `master` on 2026-05-13.
See `docs/internal-audit-2026-05-13.md` for the full report.
