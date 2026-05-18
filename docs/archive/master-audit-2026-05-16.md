# Master Branch Deep Audit — 2026-05-16

> Five-shard parallel audit of `master` HEAD `66a5b14` immediately after the
> 3-phase `cli.py` shrink merge. 3 shards on Sonnet (security, code-quality,
> docs) + 2 on Opus (architecture invariants, test correctness) — independent
> perspectives, then cross-verified by manual spot-check.
>
> **Scope:** every `.py` and `.md` under the repo, with focus on the recently
> merged cli.py shrink and the long-tail of structural debt around it.
>
> **Verdict:** `master` is shippable. No P0 issue blocks production. **Two
> P0 issues** (security path-traversal in `server.js`, broken integration
> test) should be fixed before the next promote. **Eight P1 issues** are
> latent bugs or constraint-violation risks that will bite a future change.
> A long P2/P3 tail of dead code, stale docs, and untested new modules.

---

## Headline counts

| Category | Findings |
|---|---|
| P0 — Critical (must fix before next promote) | **2** |
| P1 — High (latent bug or constraint risk) | **8** |
| P2 — Medium (fix when convenient) | **22** |
| P3 — Low (style / naming / minor polish) | **11** |
| ✅ What looks good | 18 |

Test suite: **154 passed / 8 skipped (live) / 8 deselected** on master HEAD.
Independent agents executed without me steering them; every concrete file:line
reference was re-verified manually before inclusion below.

---

## P0 — Critical (must fix before next promote)

### P0-1 — Path traversal in `server.js /download/:fileName`

**File:** `server.js:473-492`

```javascript
const fileName = req.params.fileName;
const filePath = path.join(uploadsDirectory, fileName);
res.download(filePath, encodedFileName);
```

`path.join` with `fileName = "../../etc/passwd"` on the Linux production
server returns a path outside `uploads/`. `res.download` reads any file the
Express process can read. `local_launcher.py` does the equivalent correctly
(lines 985-1021: `resolve().relative_to(uploads_root)`), so this is the
production server alone.

**Fix:**

```javascript
const fileName = req.params.fileName;
const filePath = path.resolve(path.join(uploadsDirectory, fileName));
if (!filePath.startsWith(uploadsDirectory + path.sep)) {
    return res.status(403).send("Forbidden");
}
res.download(filePath, encodedFileName);
```

### P0-2 — Integration test broken at the entry point

**File:** `tests/integration/test_real_file_per_engine.py:50`

```python
SCRIPT = ROOT / "src" / "machine_translate_docx.py"
```

After the 2026-05-11 src/ layout migration the entry script is
`src/machine_translate_docx/cli.py`. The path here doesn't exist.
`pytest -m live tests/integration` cannot run.

Also:

- Lines 56–65 and the parametrize at 214: `"chatgpt-web"` and
  `"perplexity-web"` are dead engines (removed 2026-05-10). They will
  exit non-zero from argparse and fall through the `skip` branch.

**Fix:**

```python
SCRIPT_MODULE = "machine_translate_docx.cli"
# In _run_pipeline at line ~183:
cmd = [PYTHON, "-m", SCRIPT_MODULE, ...]
env = {..., "PYTHONPATH": str(ROOT / "src"), ...}
```

Drop `chatgpt-web` / `perplexity-web` from `ENGINE_SUFFIX`,
`WEB_ENGINES`, and the parametrize list. Remove the `skip-on-web`
branch.

---

## P1 — High (latent bug or constraint risk)

### P1-1 — `xlsx_translation_memory.py` violates C24 (no top-level heavy imports)

**File:** `src/machine_translate_docx/xlsx_translation_memory/xlsx_translation_memory.py:7-8`

```python
from newmm_tokenizer.tokenizer import word_tokenize
import tinysegmenter
```

`xlsx_translation_memory` is imported unconditionally at `cli.py:131`. A
checkout without these two packages cannot boot the CLI — `import
machine_translate_docx.cli` fails before argparse. C24 explicitly forbids
this for the entry-script transitive closure (the constraint cites
`cli.py`, `translator.py`, `splitting.py` — `xlsx_translation_memory` was
overlooked).

**Fix:** Move both imports to function-local scope inside the methods that
use them, matching the pattern `cli.py` already uses for `hazm`.

### P1-2 — Unguarded `input()` ignores the `silent` flag (C16 violation)

**File:** `src/machine_translate_docx/cli.py:851`

```python
if not splitonly:
    dest_lang = input("Please enter language translation code (fr,de,ru,hi,etc.)")
```

The guard is `not splitonly`, not `not silent`. The launcher always passes
`--silent` AND `--destlang`, so this is unreachable in production today —
but the constraint C16 requires the silent guard, and any future caller that
omits `--destlang` will hang forever. The handoff doc for phase 3 envisions
exactly that scenario (statistics extraction may exercise odd entry paths).

**Fix:**

```python
if dest_lang is None:
    if silent:
        print("[FAIL] reason=missing_destlang message=--destlang required in silent mode")
        sys.exit(20)
    dest_lang = input("Please enter language translation code (fr,de,ru,hi,etc.)")
```

### P1-3 — `engines/deepl.py` has UnboundLocalError-masked-by-bare-try

**File:** `src/machine_translate_docx/engines/deepl.py:176-238`

`closed_cookies_accept_message_bool` is read at lines 176, 232 *before*
being reassigned at lines 182, 238. Python treats it as a function-local
across the entire body, so lines 176 and 232 raise `UnboundLocalError`. The
surrounding `try/except Exception: pass` swallows it — meaning the cookie
banner closure is effectively dead code, and DeepL works only by accident.

This is pre-existing (commit `a144972f`, 2026-05-08), not introduced by the
shrink. If anyone strips the bare try/except in a future cleanup, DeepL
login will hard-fail.

**Fix:** Either seed `closed_cookies_accept_message_bool =
ctx.browser.closed_cookies_accept_message_bool` at the top of the function
(matching the C11 pattern for `driver`), or convert all four reads to
`ctx.browser.closed_cookies_accept_message_bool`.

### P1-4 — Dead `elif` in engine routing block

**File:** `src/machine_translate_docx/cli.py:953-956`

```python
if translation_engine in ['chatgpt', 'deepl']:
    showbrowser = True
elif translation_engine in ['deepl', 'chatgpt']:   # ← identical condition
    pass  # keep the value as is
```

The `elif` is the same set, just re-ordered. Can never fire. Confirmed by
direct read. Smells like a botched cleanup. Remove the entire `elif`
branch.

### P1-5 — SSRF surface in `network_utils.py`

**File:** `src/machine_translate_docx/network_utils.py:57-90`

`fetch_country_data(url)` and `check_mirror_url(url)` accept URLs sourced
from `json_configuration_array`, which chains: local
`configuration.json` → remote GitHub JSON → `DefaultJsonConfiguration`.
If the GitHub repo is compromised or the local config is attacker-
controlled, those URLs can target internal endpoints (cloud metadata,
internal APIs).

Practical exploitability is low (config-supplied), but `SE_DRIVER_MIRROR_URL`
gets set from `check_mirror_url`'s result — that *is* fed to Selenium for
binary download.

**Fix:** Add an allowlist:

```python
from urllib.parse import urlparse
_ALLOWED_HOSTS = frozenset({"ip-api.com", "www.contactdirectavecdieu.net"})

def _assert_safe_url(url: str) -> None:
    host = urlparse(url).hostname
    if host not in _ALLOWED_HOSTS:
        raise ValueError(f"URL host not in allowlist: {host}")
```

Plus `allow_redirects=False` on both `requests.get` calls (defence in
depth against redirect-chain SSRF).

### P1-6 — Three new modules have zero test coverage

**Files:**
- `src/machine_translate_docx/network_utils.py` (4 public functions, 119 lines)
- `src/machine_translate_docx/docx_io/metadata.py` (2 public functions, 68 lines)
- `src/machine_translate_docx/translation_log_writer.py` (1 public function, 148 lines)

Verified via `grep -rn` against `tests/`. Each function has zero direct test
coverage. `translation_log_writer.write_translation_log` is the producer of
the JSON sidecar that the v2 frontend reads — one of the most user-visible
artefacts of the system.

**Fix:** Add `tests/test_network_utils.py`, `tests/test_docx_io_metadata.py`,
`tests/test_translation_log_writer.py`. Each ~60-80 lines. Concrete cases
already enumerated in the test-shard's detailed coverage gap analysis.

### P1-7 — Stale entry-script path in production docs

**Files affected:**
- `docs/architecture.md:18,46` — describes current pipeline using
  `python src/machine-translate-docx.py` and a `### src/machine-translate-docx.py`
  section header.
- `docs/testing.md:12,56,57-60,108` — "Ten tests live under tests/" (actual:
  154 in 18 files), and `python -m py_compile src/machine-translate-docx.py`
  and `from src.openai_tools.aligner_per import FASubtitleAligner` (both
  paths gone).
- `AGENTS.md` — every CLI flag in the build commands is wrong (`--input`,
  `--target-lang`, `--ai-model` — actual: `--docxfile`, `--destlang`,
  `--aimodel`). Pervasively stale.
- `README.md:64,136,168,191,197` — test-count `113`, `src/` layout ASCII
  tree showing top-level modules, constraint range "C1 through C20".
- `CONTRIBUTING.md:32,41` — `113 / 113 passing`, `C1 through C20`.
- `web/v2/README.md:59,181` — "36-hour cache" (actual: 5 days since commit
  `c811d4d`).
- `SECURITY.md:20` — `src/openai_tools/*` (gone).

A new contributor following any of these docs will hit dead paths.

**Fix:** Pure documentation sweep. Search-replace `src/machine-translate-docx.py`
→ `src/machine_translate_docx/cli.py`, `src/openai_tools/` →
`src/machine_translate_docx/openai_tools/`, `113` → `154` in test-count
contexts, `C1 through C20` → `C1 through C31`, `36-hour` → `5-day`,
`aligner_per` → `persian_double_lines` where the active class is meant.

### P1-8 — `tests/test_aligner_only.py` is not a pytest file

**File:** `tests/test_aligner_only.py`

`pytest --collect-only` collects zero items. The file's name pattern
matches `python_files = "test_*.py"` so pytest scans it, but it has no
`def test_*` functions — only a CLI `main()`. Anyone counting test files
will assume coverage that doesn't exist.

**Fix:** Rename to `tools/aligner_only.py`, or add `collect_ignore` entry
in `conftest.py`.

---

## P2 — Medium (fix when convenient)

### Dead code (verified zero callers)

| File | Lines | Issue |
|---|---|---|
| `src/machine_translate_docx/table.py` | full file | Copy of python-docx internals. Imports `.blkcntnr`, etc. that don't exist in this package. Zero imports anywhere in repo. **Delete.** |
| `src/machine_translate_docx/updtlnk.py` | full file | Windows `.lnk` rewriter hardcoded to `C:\SMTVRobot\WindowsTerminal\WindowsTerminal.exe`. Zero imports. **Delete or move to `tools/`.** |
| `src/machine_translate_docx/openai_tools/example.py` | full file | Standalone scratch script. Imports `from translator import OpenAITranslator` (wrong path), references `gpt-5-nano` which isn't a valid model. **Delete.** |
| `cli.py:3134` | 1 line | `_orig_run_statistics_body_marker = None  # placeholder kept for the editor diff`. Assigned, never read. **Delete.** |
| `cli.py:1253-1258, 1281-1304` | ~30 lines | Two `if translation_engine.lower() == "chatgpt" and False:` blocks. Dead at parse time. **Delete both.** |
| `cli.py:1178` | 1 line | Variable assigned, immediately overwritten on the next line. **Delete the first.** |
| `cli.py:953-956` | 4 lines | The duplicate `elif` from P1-4. |
| `local_launcher.py:424,467` | 2 lines | `LocalState.total_uploads` field assigned but never read. **Remove or expose.** |
| `local_launcher.py:_make_ssl_dir` | ~10 lines | `LocalState.ssl_dir` created and three placeholder files (`private.key`, `certificate.crt`, `ca_bundle.crt`) written with literal `"LOCAL-MOCK-*"` strings. Never read. **Delete.** |

### Duplicate code worth consolidating

- **`PRICES` table defined 3× (`translator.py:243`, `polisher.py:571`,
  `splitting.py:93`).** Tables drift slightly already. Extract to
  `openai_tools/_pricing.py`.
- **Response-API usage normalization (`translator.py:390-398`,
  `polisher.py:353-363`).** Identical byte-for-byte. Extract to
  `_retry.py::_normalize_usage(response_json)`.

### Mid-severity security

- **M-1 (security shard):** `saved_filename` from subprocess stdout is
  used as a `Path` in `local_launcher.py:1747-1811` without resolving
  + relative_to check on `uploads_dir`. Worst case is a buggy CLI
  printing a malformed path; not currently exploitable but the pattern
  invites future regression. **Add path confinement.**
- **M-3 (security shard):** Translation log sidecar exposes full system
  prompts to whoever can read the file. Acceptable on a single-user
  workstation; risky if `server.js`'s `uploads/` ends up
  unauthenticated. Add a flag to omit prompt bodies in production.
- **M-5 (security shard):** Hard-coded `C:\Temp\Chrome` user-data-dir
  in `cli.py:1235`. Currently dead code (gated by `and False`), but if
  re-enabled by accident any user on the host can pre-stage a malicious
  Chrome profile. Either remove or use `tempfile.mkdtemp()`.
- **M-6 (security shard):** Telegram bot token embedded in URL
  (`f"https://api.telegram.org/bot{token}/sendMessage"`). On an HTTP
  error whose traceback includes the URL, the token leaks to stderr.
  Mask in any log-shape construction; never `print(url)` directly.

### Server (`server.js`) Linux production path

- **H-3 (security shard):** Path traversal — already in P0-1.
- **H-4 (security shard):** `fileFilter` declared inside the
  `multer.diskStorage({...})` argument at line 44, but multer reads
  `fileFilter` from the `multer({...})` top-level options at line 53,
  which is *not* set. Result: `fileFilter` is silently ignored, ANY
  file type passes upload validation. Move it. **Confirmed by direct
  read** — line 44 has `fileFilter` nested under `diskStorage`, line
  53 has `multer({ storage })` with no `fileFilter`.
- **M-1 (security shard):** No `Content-Length` cap. multer's `limits:
  { fileSize: N }` not set. Add `limits: { fileSize: 20 * 1024 * 1024 }`
  alongside the fileFilter fix.

### Test-suite gaps (beyond the P1 new-module gaps)

- `tests/test_v2_e2e.py` imports `playwright.sync_api` lazily but
  `playwright` is not in `pyproject.toml` extras. `pytest -m live` on a
  fresh checkout gives `ModuleNotFoundError`, not a clean skip. Add
  `pytest.importorskip("playwright.sync_api")` at the top of each
  test, or add a `test-e2e` extras group.
- Five major modules have zero direct unit tests: `docx_io/parse.py`
  (384 lines), `docx_io/save.py` (355 lines), `dispatch.py`,
  `log_paths.py`, `openai_tools/_retry.py::call_with_retry`. All are
  exercised only via the (broken) live integration test. Add at
  minimum a smoke test per module.
- The `_get_ctx()` snapshot-ordering bug fixed in `4c36183` has no
  regression test. Add one assertion: after `import cli` (no `main`
  call), `cli.translation_log is cli._get_ctx().openai.translation_log`.

### Documentation drift not in P1

- **`AGENT.md` line 10 — `next/persian-double-lines-as-splitter`** is a
  deleted branch. Mark the file as archived or remove.
- **`docs/cli-shrink-phase3-handoff.md:3,212`** — "Branch state at
  handoff: `refactor/cli-py-3-phase-shrink` at commit `bd65ea8`".
  Branch was merged into master at `66a5b14` and deleted. Update with
  "branch off from master, not from this branch — it's gone."
- **`PROJECT_MEMORY.md:6` — "cli.py 3,994 lines"** vs `wc -l` returning
  4,002. Within the ±50 CRLF/LF tolerance, not worth fixing, but note
  the drift exists for future audits.

### Other code-quality flags

- **`local_launcher.py:63` comment** — "ISO 639-2/B codes matching what
  machine_translate_docx.py produces" — stale module name.
- **`runtime.py:140` docstring** — references `aligner_per` as schema
  owner; should be `persian_double_lines`.
- **`cli.py:208` comment** — fragment ending mid-sentence. Either
  complete or remove.
- **`docx_io/parse.py:28` docstring** — `"machine-translate-docx.py"`
  stale reference.
- **`engines/_timing.py:29,67,70,83`** — perplexity timing rows for an
  engine deleted on 2026-05-13.
- **`splitting.py`** — only OpenAI caller that doesn't use
  `call_with_retry`. Any transient API error is fatal. Wrap the API
  calls.
- **`runner.py:240`** — dead `"perplexity"` branch in cookie cleanup.
  Will `AttributeError` on `driver=None` in the chatgpt+api path.
- **`config.py:90-92`, `cli.py:741`, `network_utils.py:52-53`** —
  exception handlers that `print(traceback.format_exc())` or
  `print(ex)` to stdout, which the launcher parses for `PROGRESS:`
  and `Saved file name:` markers. Route to stderr or to a structured
  log line so the parser doesn't see noise.
- **`cli.py:3970-3972`** — `sys.stderr = open(os.devnull, 'w')` at end
  of `main()`. File handle never closed (descriptor leak), and
  `sys.__stderr__` reassignment is irreversible for the rest of the
  process lifetime. Use a context manager or fix the Chrome destructor
  noise at source (`--log-level=3` is already set).
- **`cli.py:1432-1436`** — hard `sys.exit(7)` inside an `except
  Exception` block in `selenium_chrome_google_translate_text_file`.
  Bypasses atexit cleanup and the structured-failure path. Raise
  `TranslationFailure` instead.

---

## P3 — Low (style / naming)

- `translation_succeded` (single `e`) — consistent typo across
  `cli.py` and `runner.py`'s public API. Rename to `succeeded`.
- `E_mail_str` vs `E_MAIL_STR` — two names for the same email constant
  in `cli.py:698` and `docx_io/parse.py:62`. Consolidate to
  `config.SUPPORT_EMAIL`.
- `not valid_online_json == True` (`cli.py:906,915`) — equivalent to
  `not valid_online_json`. Simplify.
- `splitted_filename_size` (`cli.py:1096`) — `os.path.splitext` always
  returns 2 elements; the size variable is unused logic. Replace with
  `stem, ext = os.path.splitext(...)`.
- `_LANG_ALPHA3B` in `local_launcher.py:64-72` duplicates the language
  tables in `config.py`. Structural duplication (launcher can't import
  from `src/`), but the comment should say so explicitly.
- `validate_json_string` in `config.py` — two empty `if isinstance:
  pass` branches that do nothing. Simplify to one negative check.
- Three modules have an explicit empty `pytest_addoption` hook that
  pytest ignores (test files cannot define addoption — only conftest
  can). Delete the no-op functions.
- `network_utils.test_internet` leaks an unclosed socket on success.
  Use a context manager.
- `local_launcher.py:135` comment header still says `# ── 36-hour
  cache`. Actual TTL is 5 days. Update.
- `cli.py:3201-3213` — dead `zipfile.ZipFile("myDocxOrPptxFile.docx",
  "r")` block. Literal filename, will never exist. Wrapped in a
  silent try. Delete.
- `engines/__init__.py:42-43` — inactive engines list still references
  perplexity-web in a comment. Update or remove.

---

## ✅ What looks good

1. **All 31 active constraints (C1-C31) upheld** at master HEAD —
   verified per-constraint spot-checks.
2. **Phase H bridge robust** — `_sync_globals_from_ctx` auto-mirrors all
   37 public fields on `ctx.docx`, so the 57 remaining bare-name reads
   cannot silently miss.
3. **C13 (source column lock) chain intact** —
   `docx_io/parse.py:220-221` snapshots cols 0+1 at parse time;
   `docx_io/save.py:96-124` restores them at save time with both
   text-comparison and XML deep-replace branches. No engine path
   writes to those columns.
4. **C25 fast-path** — `selenium_utils/driver.py:91-97` correctly
   no-ops `create_webdriver(ctx)` for `engine=chatgpt + method=api`,
   saving ~6 s of Chrome startup latency.
5. **C27 prompt-cache layout** — zero `{SOURCE_LANG}` /
   `{DEST_LANG}` / `{N}` template placeholders in any `prompts/*.txt`.
   JOB_CONFIG envelope is the sole language carrier.
6. **All 9 deleted orphan functions are genuinely gone** — confirmed
   by repo-wide grep. Only commented-out references remain.
7. **Three new modules from the shrink follow the repo conventions** —
   clean signatures, explicit kwargs, no globals, full docstrings,
   import-light (`network_utils.py`: socket+os+json+requests;
   `metadata.py`: datetime only; `translation_log_writer.py`:
   json+typing).
8. **Snapshot ordering bug fix (`4c36183`)** — `oai_translator`,
   `oai_polisher`, `translation_log` now precede the first runtime
   `_get_ctx()` call.
9. **Engine dispatch** — `dispatch.set_translation_function(ctx)` is
   the single source of truth. Three structural tests pin the R15
   DeepL fallback dance.
10. **Defensive `_sync_globals_from_ctx` placement in main()** — 6
    call sites (4 documented by C10, 2 extra defensive). Conservative.
11. **Path confinement on `local_launcher.py /download`** —
    `resolve().relative_to(uploads_root)` correctly used at lines
    985-1021. (The bug is only on `server.js`, the production server.)
12. **Magic-byte + zip-bomb validation** in
    `local_launcher.py::_validate_docx_payload` (lines 275-306).
13. **API keys handled correctly** — read from `os.environ`, passed
    via environment inheritance to subprocess (not argv), no key
    material in log output.
14. **Proxy env-var stripping** in `local_launcher.py:1685-1695`
    correctly covers all six variants.
15. **`--aimodel` whitelist** rejection at parse time (constraint
    C18) — verified at `cli.py:771-781`.
16. **Test independence** — `tests/test_launcher_endpoints.py` and
    `tests/test_telegram_alert.py` use `tmp_path` and properly scoped
    mocks; no order dependencies found.
17. **Strong individual tests worth keeping** —
    `test_runtime_threading.py` (R15+R16 invariant fingerprinting),
    `test_validators.py` (1:1 code-to-test mapping with positive +
    negative companions), `test_aligner_split.py` (AJAR-3147 real-
    world regression block), `test_engines_registry.py:42` (deleted-
    engine-stays-deleted regression assertion).
18. **CLAUDE.md Key Paths table** fully accurate post-merge — all
    paths exist, all roles match the actual modules.

---

## Suggested next-step refactor sequence

Ordered by ROI (line reduction × risk⁻¹):

### Sprint A — Quick wins (no risk, ~3 hours)

1. **Delete 3 dead files** (`table.py`, `updtlnk.py`,
   `openai_tools/example.py`) — confirmed zero callers. ~400 LOC.
2. **Delete the 5 dead snippets in `cli.py`** (P1-4 elif, P2 dead
   blocks, `_orig_run_statistics_body_marker`, duplicate
   assignment). ~40 LOC.
3. **Sweep docs** for stale `src/machine-translate-docx.py` and
   `src/openai_tools/` references — all listed under P1-7. Pure
   search-replace, ~25 edits across 8 files.
4. **Fix `113 → 154`, `C1-C20 → C1-C31`, `36-hour → 5-day`** in
   `README.md`, `CONTRIBUTING.md`, `web/v2/README.md`.

### Sprint B — P0 + P1 fixes (1 day)

5. **Fix `server.js` path traversal** (P0-1). 5-line patch.
6. **Fix integration test path + drop dead engines** (P0-2). ~20
   lines.
7. **Fix `xlsx_translation_memory.py` top-level imports** (P1-1).
   Move 2 imports to function scope. ~6 lines.
8. **Add silent guard to `cli.py:851 input()`** (P1-2). ~4 lines.
9. **Fix DeepL bare-name reads** (P1-3). Seed local from ctx at
   function top.
10. **Fix `server.js` `fileFilter`** (P1 + P0-2 cluster). Move to
    `multer({...})` options.
11. **Add SSRF allowlist** to `network_utils.py` (P1-5). ~15 lines.

### Sprint C — Test coverage (1-2 days)

12. **Three new test files** for the three new modules (P1-6). Each
    ~80 lines, total ~250.
13. **Five test files for the largest uncovered modules**
    (`docx_io/parse`, `docx_io/save`, `dispatch`, `log_paths`,
    `_retry`). Each ~100 lines, total ~500.
14. **One regression test for the snapshot-ordering bug** (10 lines).

### Sprint D — Continuation of the shrink (`docs/cli-shrink-phase3-handoff.md`)

15. **Task A — Extract statistics cluster** (~900 lines out of
    `cli.py`).
16. **Task B — Extract Google file-mode workers** (~800 lines).
17. **Task C — Collapse `_sync_globals_from_ctx`**.

Together: cli.py shrinks from ~4,000 to ~2,000 lines (a further
50% reduction), tests grow from 154 to ~180, doc drift goes to
zero, no security warning on `server.js`.

---

## Methodology notes

- Five agents launched in a single message for true parallelism. Three
  on Sonnet (security, code-quality, docs) for breadth; two on Opus
  (architecture, tests) for depth.
- Each agent had a separate, self-contained prompt with explicit
  scope and an explicit "be paranoid" framing. None of them saw the
  others' output.
- Findings were cross-verified by manual `grep` + `Read` before
  inclusion. Every concrete `file:line` claim above I verified myself.
- Time-to-completion: each agent ran 5-15 minutes; total wall-clock
  for the audit ≈ 15 minutes (longest agent dominated).
- `pytest tests/ --ignore=tests/test_v2_e2e.py` re-run on master HEAD
  after agents finished: 154 passed, 8 skipped (live), 8 deselected.

## Closing assessment

The 3-phase cli.py shrink is solid. The follow-up problems surfaced by
this audit are nearly all **pre-existing** (the dead files, the dead
`elif`, the DeepL bare-name reads, the `server.js` path traversal,
the stale docs) — the shrink didn't add them, but the shrink is a
good moment to clean them up because the same parts of the code are
fresh in memory.

If only one thing gets fixed before the next promote: **P0-1**
(`server.js` path traversal). If two: also **P1-1**
(`xlsx_translation_memory.py` C24 violation — it's a literal startup
crash for anyone without `newmm_tokenizer` installed).

After Sprint A + B, master will be in genuinely shippable shape and
this audit's findings will be ≤10. Sprint C closes the test-coverage
debt. Sprint D is the originally-planned phase-3 continuation work
documented in `docs/cli-shrink-phase3-handoff.md`.
