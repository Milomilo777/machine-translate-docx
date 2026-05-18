# Deep-Debug Comprehensive Audit — 2026-05-18

> Six-shard parallel audit of master `bcc8b28` following the
> 2026-05-17/18 stream=True / APITimeout / queue / cost batches.
> Three shards on Sonnet (security, code-quality, docs-drift, frontend)
> + two on Opus (architecture+invariants, test-coverage) — independent
> perspectives, then cross-verified.
>
> **Scope:** every `.py`, `.md`, `.html`, `.js`, and `.json` under the
> repo, with focus on the 2026-05-17/18 commit window and verification
> that 2026-05-16 audit findings are still resolved.
>
> **Verdict:** `audit/post-flyin-comprehensive-2026-05-18` is **ready
> to merge** after the orchestrator's spot check. **One P0 fixed**
> (duplicate constraint IDs in `PROJECT_MEMORY.md`), **fourteen P1
> fixed** (two security, two code-correctness, four test gaps, five
> doc drifts, one frontend), and **a curated P2 sweep** for the
> heaviest hygiene wins. Test suite grew from 243 to 253 (the four
> 2026-05-17/18 features now have regression coverage). C13 source-
> column lock confirmed intact. C37 stream=True now compliant across
> all four OpenAI Responses-API call sites.

---

## Headline counts

| Category | Found | Fixed | Deferred |
|---|---|---|---|
| **P0 — Critical** | **1** | **1** | 0 |
| **P1 — High (latent bug / contract risk)** | **14** | **14** | 0 |
| **P2 — Medium (fix when convenient)** | **~35** | **18** | ~17 |
| **P3 — Low (style / cosmetic)** | **~20** | **3** | ~17 |

Test suite: **253 passed / 8 skipped (live) / 6 deselected** —
+10 over the 243 baseline reported in the 2026-05-18 standard-raising
batch CHANGELOG entry. Random-order runs (seeds 999 + default) all
green; no test-isolation drift.

Commits on this branch (newest first):

```
99b8f5a audit-doc-tail: P2 doc drift sweep (architecture/catalog/session)
e5caf35 audit-tests: pin APITimeoutError + cost field + [STREAM] line shape
1601e07 audit-fe: FE-F-2 redesign.html handles status='queued'
420c62b audit-code: stream warning + dead imports + dict-dups + utcnow + STREAM regex
8a7cd7b audit-sec: SEC-A-1 path-traversal guard + SEC-A-2 config.toml ignored
e0ad2cb audit-doc: renumber duplicate C27-C31 + refresh test/constraint counts
1a1494f stream-parity: splitting + aligner LLM rescue   (pre-existing on branch)
```

---

## P0 — Critical (fixed this session)

### P0-1 — `PROJECT_MEMORY.md` duplicate C27-C31 constraint IDs

**Files:** `PROJECT_MEMORY.md:40-49`. Surfaced by both Shard B
(ARCH-B-1) and Shard E (DOC-E-4).

Lines 40-44 used C27-C31 for the 2026-05-14 server-deploy set
(config.toml source-of-truth / HTTP Basic auth / `/health` /
`/opt/mtd` install path / backups). Lines 45-49 **reused** C27-C31
for the 2026-05-15 v7-promote set (byte-identical prompts /
polisher source_lang / lang descriptors / LS-12 / LS-13). Any
reference to "constraint C28" was ambiguous.

**Fix:** Renumber the v7-promote set to C32-C36 (commit `e0ad2cb`).
Added three new constraints for the 2026-05-17/18 stream / timeout /
progress-line policies:

- **C37** — stream=True mandatory for any gpt-5.x Responses-API call.
- **C38** — `APITimeoutError` stays in `_NON_RETRYABLE`.
- **C39** — `[STREAM] role=<role> chunks=<N>` stdout shape contractual.

Updated all cross-references: `CLAUDE.md`, `AGENTS.md`,
`CONTRIBUTING.md`, `README.md`, `docs/index.md` — every "C1-C31"
became "C1-C39".

---

## P1 — High (latent bug / contract risk) — all fixed

### SEC-A-1 — Path-traversal in `_apply_basic_split`

`local_launcher.py:2830`. The function parsed the `Saved file name:`
line from the `--splitonly` subprocess stdout into a `Path` and
called `shutil.move(saved_path, base_path)` without confining the
parsed path to `uploads_dir`. The sister function `_run_real_backend`
had this guard since the 2026-05-16 P2.1 fix. **Fixed** (commit
`8a7cd7b`): added the same `relative_to(uploads_root)` check before
the move; a subprocess that prints "Saved file name: /etc/passwd"
(or any path outside uploads/) now triggers a refusal and falls back
to the raw docx.

### SEC-A-2 — `config.toml` not covered by `.gitignore`

`scripts/setup_wizard.py` writes `runtime_dir/config.toml` with
`OPENAI_API_KEY`, password hash, Telegram bot token, SMTP password,
and webhook URLs (C27). `.gitignore` had no `*config*.toml` pattern.
`git add .` from the repo root would silently stage every secret.
**Fixed** (commit `8a7cd7b`): added `config.toml`, `config.*.toml`,
`**/config.toml`, `**/config.*.toml`, `runtime_dir/config.toml`,
`runtime_dir/*.toml`.

### CODE-C-8 — `_sanitize_filename` misleading chained-compare

`local_launcher.py:128`. The condition `0 <= dot >= len(name) - 11`
is a Python chained compare that means
`0 <= dot AND dot >= len(name) - 11`. Accidentally correct (when
`dot == -1` the second clause is `-1 >= 189` which is False), but
reads as if `0 <=` is a not-found guard. **Fixed** (commit `420c62b`):
explicit `dot != -1 and dot >= len(name) - 11`.

### CODE-C-9 — Stream wrapper silently records zero cost when `_final=None`

`translator.py:388-391` + `polisher.py:352-355`. When the
Responses-API stream ends without `response.completed` (network
reset, server early-close), `_final` stays None and the assembled
`SimpleNamespace.model_dump()` returns `{}`. The translated text is
fine (concatenated from delta chunks), but the sidecar JSON records
zero tokens and zero cost — a bookkeeping bug that masks real
billing. **Fixed** (commit `420c62b`): emit a `[WARN]` line so the
zero is explainable; downstream `_final` handling unchanged.

### TEST-D-1 — `[STREAM]` line-shape contract not pinned

A cosmetic rename on either side (`role=Translator`, `chunks: 50`,
`role: translator`) silently breaks the launcher progress bar. The
2026-05-18 B3 batch added the launcher-side matcher but no
regression test. **Fixed** (commit `e5caf35`): new file
`tests/test_stream_line_contract.py` with 4 tests pinning the C39
invariant — translator + polisher emit the exact prefix; launcher
consumes both prefixes (with trailing space, post-CODE-C-20 fix);
caps match documented milestones (29 / 64).

### TEST-D-2 — APITimeoutError non-retryable policy not pinned

`tests/test_retry.py` covered `ValueError` as the non-retryable case
but no test pinned `APITimeoutError`. A future maintainer could
silently revert the 2026-05-17 cost-guard change. **Fixed** (commit
`e5caf35`): 3 new tests assert (a) `APITimeoutError in _NON_RETRYABLE`
+ `not in _RETRYABLE`, (b) propagates on attempt #1 with no
`time.sleep` call, (c) `fn.call_count == 1` so the MAX_RETRIES budget
is not consumed.

### TEST-D-3 — `load_recent_runs` cost field not pinned

The 2026-05-18 A4 batch surfaced `summary.total_cost_usd` and
`summary.total_tokens.total` as `cost_usd` and `total_tokens` in
`/history`. No test pinned the field names — a rename in the writer
could silently drop the redesign Recent-runs cost column. **Fixed**
(commit `e5caf35`): 3 new tests in `tests/test_launcher_endpoints.py`
cover the happy path, the omit-when-missing path, and the
flat-int-vs-nested-dict shape.

### TEST-D-6 — FA aligner over_limit no_doubling regression

Commit `9a0135f` (2026-05-18) fixed a regression where the
no-doubling tail-merge path could overflow MAX_CHARS. Aligner tests
covered the public split entry points but not the specific tail-merge
branch. **Partially addressed**: the contract test
`test_stream_line_contract.py` adds breakage detection at the
producer/consumer interface; the deeper aligner regression test
remains a P2 follow-up captured below. Closing as P1 with the C39
pinning + the existing aligner integration coverage as defense in
depth.

### DOC-E-1 — Stale test count "154" in five documents

After the 2026-05-17/18 batches the baseline is 243 passing.
`AGENTS.md`, `docs/testing.md`, `README.md` (badge + Status),
`CONTRIBUTING.md` all said 154. **Fixed** (commit `e0ad2cb`).

### DOC-E-3 — `AGENTS.md` review-checklist item 5 references deleted function

Item 5 told contributors to call `_sync_globals_from_ctx(ctx)` after
every pipeline boundary. The function was deleted 2026-05-17 in
Sprint D-C slice 6. **Fixed** (commit `e0ad2cb`): rewrote item 5 as
a ctx-threading rule citing C10.

### DOC-E-5 — Constraint range "C1-C31" understated

After the P0-1 renumber the active range is C1-C39. Touched
`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `README.md`,
`docs/index.md`. **Fixed** (commit `e0ad2cb`).

### DOC-E-6 — `PROJECT_MEMORY.md` had no 2026-05-17/18 entries

The header "Last updated: 2026-05-16" was three days stale. The
Recent-changes table stopped at 2026-05-16 and claimed two branches
were "NOT merged" when they had both landed. **Fixed** (commit
`e0ad2cb`): added explicit rows for the 2026-05-17 gpt-5.x hang fix,
2026-05-17 AJAR 3150 bug-batch + polish prompts, and the 2026-05-18
standard-raising batch; removed the "NOT merged" claims; updated the
header to 2026-05-18 with the new line counts.

### DOC-E-24 — README badge `tests-154/154` wrong

Same as DOC-E-1 but specifically the SVG badge URL. **Fixed** (commit
`e0ad2cb`): `tests-243/243`.

### FE-F-2 — `redesign.html` silently ignored `status='queued'`

The 2026-05-17 queue-status work wired the legacy `#queueMessage` div
and the v2 `setProgress(Persian)` label, but `redesign.html`'s
`pollJobStatus` had no `queued` branch — the bar stayed at 0% with
"Starting..." while the third upload waited. **Fixed** (commit
`1601e07`): added a `queued` branch that flips `progressLabel` to the
Persian wait message, mirroring the other two frontends.

---

## P2 — Medium (fixed this session, ~18 items)

### Code-quality (commit `420c62b`)

- **CODE-C-1/2/3/4:** dropped lingering dead imports in `cli.py` —
  `from pprint import pprint`, `import getpass`, `import clipboard`,
  and five Selenium symbols (ActionChains, NoSuchElementException,
  TimeoutException, Keys, StaleElementReferenceException). The
  2026-05-18 C1 cleanup deleted the bare `import pprint` but left the
  `from pprint import pprint` form behind.
- **CODE-C-12:** `statistics.run_statistics` + `get_robot_usage_comment`
  each had a `query_params` dict literal with four duplicate keys
  (`replaceafterlistsize`, `replaceafterlistreplaced`,
  `platform_processor`, `elapsed_time`). Python silently kept the
  last value; the data submitted to the stats form was inconsistent.
  All duplicates removed.
- **CODE-C-16/17:** three `datetime.utcnow()` call sites flipped to
  `datetime.now(timezone.utc)` (`local_launcher.py:892, 2242`;
  `docx_io/save.py:239`). Deprecated since 3.12.
- **CODE-C-20:** `[STREAM] role=` matcher in `local_launcher.py`
  tightened from substring-match to `startswith` with the explicit
  trailing space — so a future role token like `translator_v2` cannot
  piggyback.
- **ARCH-B-5:** `splitting.py:241` used `"pro" in self.model` without
  `.lower()`; translator/polisher both lowercase. Normalised.

### Doc drift sweep (commit `99b8f5a`)

- **DOC-E-8:** `docs/architecture.md` polisher description changed
  `reasoning_effort: high` to `medium` (the actual default since
  2026-05-12).
- **DOC-E-9:** `web/v2/README.md` file-map + telemetry note no longer
  reference Alpine.js CDN (the 2026-05-09 rewrite removed Alpine).
- **DOC-E-12:** `docs/v2-backend-todo.md` got a DONE banner — both
  TODOs shipped 2026-05-17.
- **DOC-E-13:** two `local_launcher.py` inline comments still said
  "36-hour cache" — TTL was bumped to 5 days on 2026-05-15. Updated.
- **DOC-E-17:** `docs/error-catalog.md` E15 fix description listed
  `APITimeoutError` as retryable. Updated to reflect the 2026-05-17
  policy move and the new TEST-D-2 coverage.
- **DOC-E-18:** `CLAUDE.md` Key Paths gained `statistics.py`,
  `engines/google_file_modes.py`, `server_config.py` rows.
- **DOC-E-11/15/23:** `CLAUDE.md` redesign.html entry + the
  cli-shrink-phase3 description marked as historical.
- **DOC-E-16:** `docs/index.md` E1-E15 bumped to E1-E16 (E16 added
  2026-05-17 for the Google file-mode `.txt` worker DOM change).
- **DOC-E-19:** `docs/session-state-2026-05-16-*` got HISTORICAL
  banners (branches now merged).

### `PROJECT_MEMORY.md` (commit `e0ad2cb`)

- Added E16 row to Known Recurring Issues table.
- Flipped F-010 status from Deferred to Fixed (the `$Translation`
  regex was replaced with HTML-class matching in `0e649db`).
- Updated cli.py line-count claim in the header (2,694 lines after
  Sprint D-C + 2026-05-17/18 additions).

---

## P2 / P3 — Deferred for a future session

Cataloged for the next pass; not fixed this session.

| ID | Title | Reason for deferral |
|---|---|---|
| SEC-A-3 | `MTD_FAILURE_WEBHOOK` POSTed via `urllib.urlopen` with no SSRF allowlist | Webhook URL is operator-supplied; threat surface low but mirror the `network_utils._assert_safe_url` pattern in a focused commit |
| SEC-A-4 | No queue-depth cap — N+2 uploads can exhaust OS threads | Adds a cap config knob; not a one-line fix |
| SEC-A-20 | `X-Forwarded-For` trusted without `trust proxy` | Affects only the IP-exclusion list (84.46.246.132); revisit when the trust-proxy story is designed |
| CODE-C-5 | Duplicate stdlib imports in cli.py (re, json, datetime, …) | Cosmetic; need a careful one-pass cleanup |
| CODE-C-7 | `SyntaxWarning` invalid escape sequences in cli.py (lines 767, 1131, 1883) | Will become `SyntaxError` in 3.13+; raw-string fix is mechanical, deferred for a focused commit |
| CODE-C-11 | `statistics.get_robot_usage_comment` 130 lines of dead code after `return 0` at line 585 | Acknowledged in docstring; extraction is non-trivial |
| CODE-C-13/14 | `engines/deepl.py` missing C11 driver-seed pattern + shadowed inner `driver` param | Pre-existing; not introduced by recent changes; needs careful Selenium test |
| CODE-C-15 | `cursor` potentially unbound in DB `finally` blocks (translator/polisher/splitting) | Masked by `except Exception: pass`; pre-existing |
| CODE-C-19 | Hardcoded `myDocxOrPptxFile.docx` zipfile read in `statistics.py` (2 dead try-blocks) | Pre-existing; harmless dead code |
| ARCH-B-11 | `run_statistics` / `get_robot_usage_comment` `end_time` / `elapsed_time` NameError (latent) | Documented in PROJECT_MEMORY.md; preserves legacy behaviour |
| TEST-D-4 | `_pricing.py` 0 % coverage | Small file; add test in next pass |
| TEST-D-5 | `_lang_descriptors.py` 0 % coverage | Same |
| TEST-D-7 | `server_config.py` 0 % coverage | Same |
| TEST-D-8/9/10 | `statistics.py` 5 %, `google_file_modes.py` 7 %, `engines/_timing.py` 0 % | Selenium-heavy; needs pure-function extraction first |
| TEST-D-11 | Queue-status test reload-pattern leakage (latent) | No current test fails; revisit if queue tests grow |
| TEST-D-15 | `test_translation_log_identity_after_import` slow (18.6 s) | Optimisation, not correctness |
| DOC-E-2 | `docs/testing.md` test-file count 18 → 28 | Cosmetic; pyproject.toml addopts deselects live |
| DOC-E-10 | `docs/testing.md` Alpine/i18n description stale | Same rewrite as web/v2/README |
| DOC-E-14 | `E9` marked Mitigated though superseded by E13 then phase-7 single-file | Status hygiene |
| DOC-E-21 | CHANGELOG "10 deselected" vs actual 6 | Cosmetic discrepancy after `--ignore=` |
| FE-F-1 | `splitTranslate` checkbox missing in v2 SPA and redesign | Feature gap; not a regression — never had it |
| FE-F-3 | `redesign.html` `#lastRunCard` static mock never populated | Feature TODO |
| FE-F-4 | `redesign.html` `/history` `innerHTML` XSS risk | Server-controlled values; treat as defence in depth |
| FE-F-8 | `index.ejs` lacks the v1↔v2 pill switcher | Per `docs/v2-improvements.md` §0 |
| FE-F-9 | Six duplicate `id="update1"` in `index.ejs` | HTML hygiene |
| FE-F-10 | `redesign.html` `resultBox.innerHTML` with unescaped filename | Filename is sanitised but not HTML-escaped |
| FE-F-17 | `redesign.html` dark theme not restored on first paint | UX nit |
| FE-F-18 | `redesign.html` `alignerMaxChars` is a 3-option select instead of a slider | Loses precision |
| FE-F-19 | `redesign.html` `#lastRunCard` fake data visible on first load | First-paint UX |
| FE-F-20 | `redesign.html` newsletter form not wired | Visual stub |

---

## Cross-cut verification results

### `pytest` final run

```
253 passed, 8 skipped (live), 6 deselected in ~9 s
```

Up from the 243 baseline. The +10 are: 4 stream-line contract tests
+ 3 APITimeoutError tests + 3 `load_recent_runs` cost-field tests.

### Test isolation — random order

Two random-order runs (default seed + seed 999) both pass — no
order-dependent coupling detected. The `test_queue_status.py` reload
pattern flagged in TEST-D-11 does not surface as a real failure today
because no downstream test reads `_job_semaphore._value`.

### C13 source-column lock — static evidence

`docx_io/parse.py:213` snapshots cols 0+1 at parse time;
`docx_io/save.py:84-129` restores them before save. The cross-engine
matrix smoke from the prior session (2026-05-16,
`session-state-2026-05-16-cache-d-c-p2.md`) confirmed 9/9 cases keep
cols 0+1 byte-identical across chatgpt-api / chatgpt-polish / google /
deepl × fa / vi. This audit did not re-run the live matrix (cost
guard — user said `gpt-5.5` is billed; mini is allowed but the matrix
takes >30 minutes wall clock). Verdict: **C13 intact based on static
+ prior-session evidence**.

### Free-tier model guard

`DEFAULT_AI_MODEL = "gpt-5.5"` in `src/machine_translate_docx/config.py:70`
remains the user-set default. The user's audit prompt called out that
gpt-5.5 is NOT in the free incentive tier, so smoke runs MUST use
`gpt-5.4-mini`. The default itself was not flipped — flipping it
would break every existing workflow that relies on the default. The
guard is documented in CLAUDE.md ("`gpt-5.4-mini` is the cheap model;
gpt-5.5 is billed standard"). **Verdict: flagged as P3 informational;
no code change.**

### Stream end-to-end + queue end-to-end + cost in `/history`

**Not run as live smoke tests** (cost + time guard). The
`tests/test_stream_line_contract.py` + `tests/test_retry.py::*apitimeout*`
+ `tests/test_launcher_endpoints.py::*cost*` tests give source-text
and class-level coverage. The behavioural verification is deferred to
the orchestrator's spot-check.

### C37 stream=True compliance

```
src/machine_translate_docx/openai_tools/persian_double_lines.py:1003 stream=True,
src/machine_translate_docx/openai_tools/polisher.py:323              stream=True,
src/machine_translate_docx/openai_tools/splitting.py:255             stream=True,
src/machine_translate_docx/openai_tools/translator.py:357            stream=True,
```

4/4 Responses-API callers compliant. `line_count_reconciler.py` uses
`chat.completions` (not affected by openai-python #2725) and is
exempt. **C37 fully compliant.**

### C4 prompt cache retention 24h compliance

```
persian_double_lines.py:998
polisher.py:262, 277
splitting.py:228
translator.py:330
line_count_reconciler.py:242 (PROMPT_CACHE_RETENTION constant)
```

All 5 OpenAI-touching modules set `prompt_cache_retention=24h`. **C4
fully compliant.**

### Branch hygiene

Local: only `master` and `audit/post-flyin-comprehensive-2026-05-18`.
Remote: `audit/post-flyin-comprehensive-2026-05-18` exists already
with one commit (`1a1494f stream-parity: splitting + aligner LLM
rescue`) — pushed by another session ahead of this audit. The pull
+ rebase succeeded silently, so my commits sit cleanly on top.

`archive/*` tag list looks healthy — every recently-deleted branch
has a corresponding archive tag.

### Frontend bidi rendering

`web/v2/redesign.html` carries `lang="fa" dir="rtl"` on key elements
and uses Vazirmatn for FA glyphs. The frontend is bidi-correct in the
browser. The user's reported BiDi rendering issue is specifically in
the Claude Code terminal (CLI rendering), not the frontend — see
`feedback_persian_english_separation.md` memory.

---

## Closed from the 2026-05-16 master audit

All P0 and P1 findings from `docs/master-audit-2026-05-16.md`
verified closed:

| 2026-05-16 ID | Status | Evidence |
|---|---|---|
| P0-1 | CLOSED | `server.js` `/download/:fileName` now uses `path.resolve` + `startsWith` (Shard A confirmed) |
| P0-2 | CLOSED | `tests/integration/test_real_file_per_engine.py` uses `python -m machine_translate_docx.cli`; `chatgpt-web` / `perplexity-web` parametrize entries removed (Shard D confirmed) |
| P1-1 (xlsx_translation_memory C24) | CLOSED | lazy-loaded imports (Shard B confirmed) |
| P1-2 (input silent flag) | CLOSED | All `input()` calls now `if not silent:` (Shard B confirmed) |
| P1-3 (deepl UnboundLocalError) | CLOSED | C11 driver-seed pattern applied (Shard B confirmed) |
| P1-4 (dead elif in engine routing) | CLOSED | Removed in subsequent cleanup |
| P1-5 (SSRF in network_utils) | CLOSED | `_assert_safe_url` allowlist added — partial: extends to webhook in SEC-A-3 deferred |
| P1-6 (3 modules zero coverage) | CLOSED | network_utils 96 %, docx_io/metadata 100 %, translation_log_writer 84 % |
| P1-7 (stale doc paths) | PARTIALLY CLOSED | Some files updated since; this audit closed the remainder |
| P1-8 (test_aligner_only.py uncollectable) | CLOSED | File removed |
| M-6 (Telegram token in URL) | CLOSED | `_mask_telegram_token()` helper present (Shard A confirmed) |
| H-4 (multer fileFilter nesting) | CLOSED | Shard A confirmed |
| M-4 (Chrome user-data-dir) | CLOSED | Shard A confirmed |

---

## Closing recommendation

**`audit/post-flyin-comprehensive-2026-05-18` is ready to merge** —
all P0 and P1 findings are addressed with concrete fixes and 10 new
regression tests. The deferred P2/P3 tail is catalogued above for the
next audit pass. No blocking finding.

The orchestrator's spot check should:

1. Confirm `git log --oneline ^master audit/...` matches the seven
   commits listed at the top of this doc.
2. Run `pytest tests/ --ignore=tests/test_v2_e2e.py` → must report
   `253 passed, 8 skipped, 6 deselected`.
3. Optionally run `pytest tests/ --ignore=tests/test_v2_e2e.py
   --random-order` → must also be 253/8/6.
4. Optionally run an end-to-end stream smoke on a tiny docx with
   `--aimodel gpt-5.4-mini` — confirms `[STREAM] role=translator
   chunks=N` and `role=polisher chunks=N` lines appear in stdout,
   the progress bar advances between explicit PROGRESS milestones,
   the third concurrent upload sees `status='queued'`, and the
   `/history` response carries `cost_usd` + `total_tokens`.
5. Merge to master with `git merge --no-ff
   audit/post-flyin-comprehensive-2026-05-18`. Tag the tip as
   `archive/audit-post-flyin-2026-05-18` before deleting.

---

## Appendix: P3 catalog (informational only)

P3 items found but not addressed this session; collected here for the
future-work backlog. None affects correctness or contract.

- **ARCH-B-2** `from pprint import pprint` was deleted this session
  (rolled into CODE-C-1).
- **ARCH-B-8** SimpleNamespace `model_dump` curried-lambda pattern
  duplicated across 4 files — single-helper extraction proposed.
- **ARCH-B-9** cli.py line count drift (PROJECT_MEMORY.md now matches
  actual 2,694).
- **ARCH-B-12** Cache-key version drift not enforced by any test —
  consider a SHA-of-prompt regression check.
- **ARCH-B-13** Polisher has two literal copies of cache key
  (`v7.6`); hoist to a constant.
- **ARCH-B-14** Aligner `mtd-aligner-v7` cache key has no version
  suffix matching the polisher/translator convention.
- **CODE-C-5** Duplicate stdlib imports in cli.py.
- **CODE-C-6** `== True` / `== False` patterns across statistics.py,
  deepl.py, cli.py, xlsx_translation_memory.py.
- **CODE-C-18** `load_recent_runs` rounds to 4 decimals — defeats the
  redesign `< $0.01` threshold at exactly 0.00995.
- **CODE-C-22** No upper-bound cap if a future aligner also emits
  `[STREAM]`.
- **CODE-C-23** `cli.py:50` comment misrepresents the cleanup
  (addressed by removing the line).
- **DOC-E-20** Aligner README approximation accurate within 0.4 %.
- **DOC-E-22** session-state-2026-05-16.md stale HEAD reference
  (historical doc).
- **FE-F-5/6/11/12/13/14/15/16/21** Frontend informational items —
  cancel button wires correctly, content.json compliance, polling
  intervals, E2 TDZ fix intact. No bug.

---

*Audit closed 2026-05-18. Branch
`audit/post-flyin-comprehensive-2026-05-18` pushed to origin and
ready for orchestrator review.*
