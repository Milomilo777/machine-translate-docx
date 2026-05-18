# Session State Report — 2026-05-16 (architect handoff)

> Written from the architect role. Reads the whole working state as of
> commit `543ee0d` (master HEAD) and tells the next session **exactly**
> where to start, with concrete recipes per open workflow.
>
> This document supersedes the older
> [`cli-shrink-phase3-handoff.md`](cli-shrink-phase3-handoff.md) for
> the cli.py shrink track only as a status report — the recipes there
> still apply for Sprint D.

---

## TL;DR

Three parallel workflows are open. They do not conflict at the file
level **except** at the cache-refactor / cli.py interface. Listed in
strict priority order:

| # | Workflow | State | Risk | First action |
|---|---|---|---|---|
| **1** | **raw-cache-refactor** | Stale branch + partial v2 worktree | 🔴 high (oldest, most pain) | Diff the two attempts, decide merge strategy |
| 2 | Sprint D — cli.py shrink continuation | Documented, scaffold landed | 🟡 medium | Open the existing handoff doc |
| 3 | P2/P3 hygiene from master audit | Documented | 🟢 low | Cherry-pick what you need |

The `feat(server-deploy)` work (commit `543ee0d`) is **already
landed** in master and is not on this list — that author closed it
out themselves in a separate session.

---

## Master health check

```
HEAD                  543ee0d feat(server-deploy): one-command VPS deploy + …
Tests                 239 passed / 8 skipped (live) / 6 deselected
cli.py line count     3,947 (down from 4,395 at the start of the day)
Open branches         3 local (master, raw-cache-v2, blissful-pasteur-dcab73)
                      1 remote-only (claude/raw-cache-refactor)
Worktrees             3 (main, raw-cache-v2, blissful-pasteur-dcab73)
New modules           network_utils, translation_log_writer,
                      docx_io/metadata, statistics, server_config
                      (all landed in master since c811d4d)
Documentation         CLAUDE.md, PROJECT_MEMORY.md, AGENTS.md,
                      docs/index.md, docs/architecture.md, docs/uml.md,
                      docs/master-audit-2026-05-16.md fully refreshed
```

Master is in good shape on its own. The problem is what is NOT in
master.

---

## Workflow 1 — raw-cache-refactor (HIGHEST PRIORITY)

### What it is

A user-facing bug: uploading the same file once with `persian_double_lines`
split and then again with `basic` split triggers a fresh translate +
polish run (~5 minutes, ~$0.40 wasted) because the cache key includes
`split_engine`. The refactor reworks the launcher so the CLI always
emits a "raw" single-blob-per-phrase docx, the cache stores that raw
output, and the launcher applies the requested splitter post-cache.

### Where it lives

Two parallel attempts, neither merged:

#### A. `claude/raw-cache-refactor` (remote branch, three commits)

```
34e15f4  b1-guard: generalize to all cached API engines + all languages
6fb0012  raw-cache architecture: complete
f5ad539  WIP: cache architecture refactor — partial (do NOT merge to master yet)
```

Branched from master `c811d4d` (= ~17 commits behind today's master).

The commit messages on `34e15f4` and `6fb0012` claim "tests pass" and
"py_compile clean" but list **defer items**:

- Real translation run with `chatgpt-polish` FA → verify B1-guard emits
  raw docx, cache stores it, served_path is split correctly.
- Cache replay: same file, switch from basic to `persian_double_lines`
  (and vice versa) → verify ~10 second total runtime, no API calls.
- Legacy cache entries from before this branch will be invisible (key
  shape changed); users see a one-time "cold cache" period.

**Nothing on this branch has been E2E-verified against a real run.**

#### B. `claude/raw-cache-v2` (local worktree, partial re-apply attempt)

Worktree: `.claude/worktrees/raw-cache-v2/` at `aebc1de`
(= master before `543ee0d`).

A later session realized branch (A) was stale relative to the cli.py
shrink and started re-applying the changes manually on top of modern
master. The re-apply is **incomplete**:

```
local_launcher.py                 | 75 ++++++++++++++++++++++-----------------
src/machine_translate_docx/cli.py | 24 +++++++++----
```

Only two file regions touched, both unstaged. The session ended with
an API error mid-edit. Key `MTD_SKIP_STATS_BROWSER` guard at cli.py
lines ~1542, ~1549, ~3230, ~3235 is in place; the launcher-side
`_apply_basic_split` is not yet re-applied.

### What master currently has (for comparison)

```
local_launcher.py:61      _API_ENGINES = {"chatgpt", "chatgpt-polish"}
local_launcher.py:137     _cache_key(payload, lang, engine, ai_model, split_engine)   ← still split_engine in key
local_launcher.py:1704    B1-guard targets persian_double_lines only
local_launcher.py:2400    _apply_splitter (no _apply_basic_split sibling)
cli.py                    no MTD_SKIP_STATS_BROWSER guard anywhere
```

### What the refactor changes (target state)

```
local_launcher.py         _cache_key(payload, lang, engine, ai_model)      ← drop split_engine
local_launcher.py         B1-guard targets ALL engines in _API_ENGINES (all langs)
local_launcher.py         New: _apply_basic_split(base_path) — spawns
                          `python -m machine_translate_docx.cli --splitonly
                          --engine chatgpt --enginemethod api`, parses
                          "Saved file name:", renames result to base_path.name
local_launcher.py         _apply_splitter routes:
                            persian_double_lines → in-process FASubtitleAligner
                            basic / openai / null → _apply_basic_split
local_launcher.py         _run_real_backend calls cache_store BEFORE _apply_splitter
cli.py                    Two new MTD_SKIP_STATS_BROWSER guards in the stats path
cli.py                    Drive-by fix: service = Service() ordering at ~line 3678
```

### Conflict analysis vs current master

| File | Branch claim | Master state | Conflict? |
|---|---|---|---|
| `local_launcher.py:61` (`_API_ENGINES`) | unchanged | same | None |
| `local_launcher.py:137` (`_cache_key`) | drops `split_engine` arg | still has it | Trivial — drop arg + callers |
| `local_launcher.py:1704` (B1-guard) | generalize | targets PDL only | Trivial — replace one conditional |
| `local_launcher.py:2400` (`_apply_splitter`) | adds branches | still old shape | Medium — additive |
| `local_launcher.py:_run_real_backend` | reorder cache_store / splitter | unchanged | Trivial — reorder two lines |
| `local_launcher.py:_materialise_cached_output` | calls splitter on cached docx | unchanged | Small — additive |
| `cli.py:~1542,1549,3230,3235` (stats guards) | new env-var checks | clean | Trivial — additive |
| `cli.py:~3678` (`service = Service()` ordering) | move up 2 lines | bug still there | Trivial fix |

**Verdict:** there is **no real conflict** — the branch is stale, not
divergent. It can be re-applied as a clean patch on modern master in
under an hour. The previous v2 attempt got the cli.py side roughly
done; the launcher side is what's left.

### Recommended path

**Do this**, in this order:

1. **Spin up a fresh branch off current master** —
   `refactor/raw-cache-2026-05-17` or similar. Do NOT try to rebase
   `claude/raw-cache-refactor` — its base is too old and the commits
   describe the work in pseudo-WIP form.

2. **Inspect what `raw-cache-v2` already has** —
   ```
   cd .claude/worktrees/raw-cache-v2
   git diff > /tmp/raw-cache-v2-partial.patch
   ```
   That patch is the cli.py side of the refactor and a partial launcher
   side. Apply it on the fresh branch and inspect.

3. **Cherry-pick the launcher changes from `claude/raw-cache-refactor`** —
   the three commits there describe the launcher mutations precisely.
   Read commits `6fb0012` and `34e15f4` (commit messages above), then
   re-implement the four launcher changes by hand on the new branch.
   Do NOT cherry-pick literally — the line numbers are wrong; use the
   commit messages as a specification.

4. **Local pytest + smoke test** —
   ```
   pytest tests/ --ignore=tests/test_v2_e2e.py
   ```
   then real translation:
   ```
   # Run 1: translate with persian_double_lines split
   # Run 2: re-upload same file with basic split — should be ~10s
   ```

5. **Once verified, merge to master, tag, delete branch.** Per
   constraint C23.

6. **Delete `claude/raw-cache-refactor`** (remote) and the
   `raw-cache-v2` worktree once the work lands. Update memory file
   `pending_cache_refactor.md`.

### What NOT to do

- Don't try to `git merge` or `git rebase` `claude/raw-cache-refactor`
  on master. Its base is `c811d4d`. The cli.py file has been shrunk by
  ~450 lines since then. The merge would surface conflicts that look
  like data corruption.
- Don't trust the WIP commit message on `f5ad539` — the subsequent
  commits `6fb0012` and `34e15f4` claim to finish the deferred work,
  but the E2E test that would verify the work was never run.

---

## Workflow 2 — Sprint D (cli.py shrink continuation)

Documented in [`cli-shrink-phase3-handoff.md`](cli-shrink-phase3-handoff.md).

State as of HEAD:

- ✅ Sprint D-A.1 — `local_time_offset` extracted to `statistics.py`
  (commit `064de4e`). +`statistics.py` scaffold ready for the rest.
- ⏸ Sprint D-A.4 — `run_statistics` (232 lines, 10+ globals).
- ⏸ Sprint D-A.5 — `get_robot_usage_comment` (370 lines, 12+ globals).
- ⏸ Sprint D-B — Google file-mode workers (~800 lines).
- ⏸ Sprint D-C — `_sync_globals_from_ctx` collapse.

**Correction landed**: `print_console_docx_file_translated` is the
non-split write path, NOT a stats helper. Removed from extraction
list.

**Why deferred**: each remaining function reads 10+ module-level
globals and pulls in Selenium imports. The safe pattern is one
extraction per function, full pytest + smoke after each — a
dedicated session worth of work.

**First action for the next Sprint-D session:**

1. Read [`cli-shrink-phase3-handoff.md`](cli-shrink-phase3-handoff.md).
2. Pick `run_statistics` (D-A.4). Decide between two patterns:
   - **Lazy import from cli** (mirrors `docx_io/parse.py:88`): cleanest,
     minimal call-site churn, mildly anti-pattern.
   - **Explicit kwargs shim**: every global threaded explicitly,
     verbose but pure.
3. Before extracting, **fix the latent bug** in `run_statistics:3226-3228`
   where `service = Service()` is assigned AFTER
   `webdriver.Chrome(service=service, …)` — that's `UnboundLocalError`
   waiting to fire, currently masked by a bare `except`.

---

## Workflow 3 — P2/P3 hygiene (low priority)

Documented in
[`master-audit-2026-05-16.md`](master-audit-2026-05-16.md).

11 P2 items and 8 P3 items remain. Highlights:

- `local_launcher.py:1747-1811` — `saved_filename` from subprocess
  stdout used as Path without confinement.
- `translation_log_writer.py` — sidecar exposes full system prompts
  (production-risk).
- `local_launcher.py:_send_telegram_*` — token embedded in URL
  (traceback-leak risk).
- `openai_tools/splitting.py` — missing `call_with_retry` wrapper.
- `cli.py:3970-3972` — `sys.stderr = open(os.devnull, 'w')` descriptor
  leak.
- Plus cosmetic typos (`translation_succeded`, `E_mail_str` vs
  `E_MAIL_STR`, …).

Each is independent and small. Pick whichever the workflow priorities
allow.

---

## Memory file status

The memory file at
`~/.claude/projects/.../memory/pending_cache_refactor.md`
is **stale**:

- It thinks master is at `c811d4d`. Master is at `543ee0d` (17 commits
  later).
- It thinks the branch is at `f5ad539` (WIP). The branch has two more
  commits on top: `6fb0012` (complete) and `34e15f4` (b1-guard
  generalize).
- It lists 6 pending items, of which only items 1, 6 (the E2E test)
  remain real. Items 2-5 were addressed in the two later commits on
  the branch but never verified.

**The next session must replace this file's content with a pointer to
the current document.**

---

## Recommended priority order for the next session

1. **Resolve Workflow 1** (raw-cache-refactor). 1-2 hours of focused
   work. This is the user-facing bug.
2. **Update the memory file** to reflect Workflow 1's resolution.
3. **(Optional) Begin Workflow 2** (Sprint D-A.4 `run_statistics`).
   This can also be deferred indefinitely — master is healthy without
   it.
4. **(Optional) Pick one P2 item** if extra capacity remains.

Do not start Workflow 2 before Workflow 1 lands. The cache refactor
touches `cli.py`'s stats path, which is the same area Sprint D-A is
trying to extract.

---

## Quick reference

| Path | Purpose |
|---|---|
| `docs/session-state-2026-05-16.md` (this file) | Architect handoff |
| `docs/cli-shrink-phase3-handoff.md` | Sprint D recipes |
| `docs/master-audit-2026-05-16.md` | P0/P1/P2/P3 catalog |
| `docs/uml.md` | UML diagrams (5 Mermaid) |
| `docs/diagrams/architecture-detailed-light.svg` | Module-level architecture |
| `~/.claude/projects/…/memory/pending_cache_refactor.md` | Stale — must be refreshed |

| Branch / worktree | State | Action |
|---|---|---|
| `master` | Healthy, HEAD `543ee0d`, 239 tests pass | Leave |
| `origin/claude/raw-cache-refactor` | Stale (17 commits behind), unmerged | Use commit messages as spec, do NOT merge |
| `.claude/worktrees/raw-cache-v2/` (`claude/raw-cache-v2`) | Partial re-apply, dirty | Diff to `/tmp/raw-cache-v2-partial.patch`, then delete |
| `claude/festive-colden-af72d9` (local only) | Pruned worktree, orphan branch | Delete with `git branch -D claude/festive-colden-af72d9` |
| `claude/blissful-pasteur-dcab73` | Unknown — not from this session | Investigate or leave |
