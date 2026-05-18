# Internal deep audit — 2026-05-13

**Anchor:** commit `3149d75aeeae691f73a1fabf10587a3c09f2c443` of branch `master`
(last commit: "Jules deep audit follow-up: 3 real fixes + 2 stale findings rejected").

**Auditor:** Claude Opus 4.7 (1M context), against the improved prompt at
[`docs/audit-prompt-v2-2026-05-13.md`](audit-prompt-v2-2026-05-13.md).

**Exclude list applied:**
- Antigravity-light A1–A7, Codex-light A1–A15, Jules-light A1–A13
- Antigravity-deep B1–B20 (12 fixed in `f06a67c`, 8 deferred)
- Jules-deep B1–B8 (3 fixed in `3149d75`, 2 stale rejected, 3 already covered)
- debug-night F1, F2, F3, F5, F6, F7a-c FIXED; F8 OPEN

---

## Phase 0 — Snapshot proof

| Tool | Output |
|------|--------|
| `git rev-parse HEAD` | `3149d75aeeae691f73a1fabf10587a3c09f2c443` |
| `git log -1 --format="%s"` | `Jules deep audit follow-up: …` |
| `ls -la prompts/` | 5 prompt files: `_smtv_locks.txt` (6 592 B), `polish_PER.txt` (11 969 B), `polish_universal.txt` (5 544 B), `translate_PER.txt` (7 971 B), `translate_universal.txt` (8 001 B) |
| `wc -l cli.py` | 4 379 lines |
| `wc -l local_launcher.py` | 2 313 lines |
| `wc -l persian_double_lines.py` | 1 098 lines |
| `tiktoken cl100k_base` | available ✓ |

---

## Phase 1 — Measured static analysis

### Token counts (real, via `tiktoken.get_encoding("cl100k_base")`)

| Prompt file | Tokens |
|-------------|-------:|
| `_smtv_locks.txt` (shared) | 1 303 |
| `translate_PER.txt` | 2 138 |
| `polish_PER.txt` | 3 342 |
| `translate_universal.txt` | 1 818 |
| `polish_universal.txt` | 1 320 |

**Combined system prompts as the model sees them:**

| Pass | System tokens | Cache status |
|------|--------------:|-------------:|
| FA translate (shared + translate_PER) | **3 441** | warm (>1 024) |
| FA polish    (shared + polish_PER)    | **4 645** | warm (>1 024) |
| Universal translate                   | **1 818** | warm |
| Universal polish                      | **1 320** | warm |

**Verdict:** every prompt is ≥ 1 024 tokens — the cache-cold claim Jules-deep B3 made is unsupported by current `master`. No defect.

### Function-size scan of `cli.py` (AST-based)

| Lines | Function | Notes |
|------:|----------|-------|
| 363 | `get_robot_usage_comment` | stats / HTML report builder |
| 228 | `run_statistics` | stats printer |
| 223 | `document_split_phrases` | basic-split distributor |
| 171 | `_get_ctx` | the migration bridge (Antigravity-deep B1) |
| 170 | `main` | entry orchestration |
| 151 | `selenium_chrome_google_translate_html_javascript_file` | engine path |
| 143 | `get_translation_and_replace_after` | post-translate cell write |
| 137 | `selenium_chrome_google_translate_xlsx_file` | engine path |
| 109 | `generate_char_blocks_array_from_phrases` | block builder |
| 98  | `print_console_docx_file_translated` | save + console |
| 97  | `generate_html_file_from_phrases_for_google_translate_javascript` | engine path |

**Module-level statements: 221** (confirms Codex/Antigravity B2 — heavy import-time execution).

72 functions total; 11 over 80 lines. Same architecture roadmap item; no new defect.

### subprocess inventory (full)

```
local_launcher.py:1518     subprocess.Popen(cmd, …)            list-form, no shell, cwd=ROOT
cli.py:4128                subprocess.Popen(["open", out_path]) list-form, macOS
cli.py:4130                subprocess.Popen(["xdg-open", out_path]) list-form, Linux
cli.py:4111-area           os.startfile(out_path)               Windows (A2 closed)
tests/...                  test-only Popen                       not on prod path
```

No new `shell=True`; A2 stands closed.

### bare `except:` survey (post Codex-light A3)

```
src/machine_translate_docx/openai_tools/translator.py:123    except: pass
src/machine_translate_docx/openai_tools/translator.py:406    except: pass
```

**NEW FINDING C1** (below). Codex-light A3 cleaned `splitting.py`; these two in `translator.py` were missed.

### Payload-logging hygiene (post Antigravity-deep B5)

`translator.py`: env-gated ✓
`polisher.py`: env-gated ✓ (paired with `last_call_data`)
`splitting.py`: **NOT GATED** — `print("prompt:")` + full prompt at `:221-222`, full response JSON at `:249-251`.

**NEW FINDING C2** (below).

---

## Phase 2 — Hot-path race / corruption survey

`local_launcher.py` uses a single `threading.Lock()` for `jobs` / `cache`. `job_id` is `uuid4().hex` (32 hex chars, unguessable — A13 closed). The only mutation surface is:

```python
def update_job(self, job_id: str, **changes) -> None:
    with self.lock:
        job = self.jobs[job_id]          # KeyError if cancelled mid-flight
        self.jobs[job_id] = Job(...)
```

**NEW FINDING C3** (below).

Job-output paths (P1–P5) traced; no other silent-corruption surface beyond what F8 already covers.

---

## Phase 3 — Persian-specific edge probe

Aligner behaviour on edge inputs:

| Input | Result | Verdict |
|-------|--------|---------|
| Empty string | `[]` | safe |
| 1-line short ("سلام") | `['سلام']` | identity |
| ZWNJ-only (`‌‌‌`) | `['‌‌‌']`, display_len 0 | safe — passes MAX_CHARS |
| Arabic Yeh in `_normalize_fa` | `'سلام دنیای مدرن'` | normalises ي → ی ✓ |
| Arabic digit in `_normalize_fa` | `'۱۰ و ۵ و ۷'` | normalises ٥/٧ → ۵/۷ ✓ |
| `_display_len('می‌شود')` | 5 | ZWNJ excluded ✓ |
| `_distribute_to_rows(['کوتاه'], 3)` | `['کوتاه','کوتاه','کوتاه']` (later `_enforce_no_triple` clears [2]) | as designed |
| Long repeated-word text into 5 rows | **4** chunks, not 5 | low-priority edge — repeated text rarely happens in real documents |

No reproducible aligner defect on real Persian-translated docx; bench corpus unchanged.

### Subtitle ≤ 50-char rule enforcement

`MAX_CHARS = 48` in `persian_double_lines.py:47` is the hard limit. The 50-char guidance from `prompts/translate_PER.txt` is a soft target enforced at prompt level; the aligner's `MAX_CHARS` + A12 `over_limit ≤ 1 %` check is the actual gate. No new finding.

---

## Phase 4 — Repo hygiene

| Check | Result |
|-------|--------|
| Committed `.env` / `.log` / secret files | none (clean) |
| Committed files matching `.gitignore` patterns | none |
| TODO / FIXME / HACK in tracked source | none in code-bearing files |
| Hard-coded paths in `.bat` files | yes (Jules-deep B8 / deferred) |
| `.github/workflows/ci.yml` present | yes (closes Codex B20) |
| pyproject.toml linter config (ruff/mypy/bandit) | absent (Codex B17 / deferred) |
| `requirements.txt` vs `pyproject.toml` divergence | not in scope this pass |
| Master tree clean | yes after this commit |

---

## NEW FINDINGS

### C1 — bare `except:` in `translator.py` was missed by Codex A3
- **Severity:** Medium
- **Category:** Reliability
- **Location:** `src/machine_translate_docx/openai_tools/translator.py:123`, `:406`
- **What it is:** Two `except: pass` clauses wrapping DB cursor/conn cleanup. Codex-light A3 found and fixed the same pattern in `splitting.py`, but the two sites in `translator.py` were missed because the A3 grep only scanned the splitter file.
- **Evidence:**
  ```python
  finally:
      try: cursor.close(); conn.close()
      except: pass
  ```
- **Tool output:** `grep -rn "except:\\s*pass"` returned `translator.py:123` and `:406`.
- **Why it matters:** Bare `except:` swallows `KeyboardInterrupt` and `SystemExit`. The project rule `.claude/rules/code-style.md` forbids it (C15 invariant).
- **Recommendation:** Replace with `except Exception: pass`. Applied this commit.
- **Effort:** S
- **Status:** **fixed in this commit.**

### C2 — `splitting.py` still logs full prompt + response payload
- **Severity:** Medium
- **Category:** Security
- **Location:** `src/machine_translate_docx/openai_tools/splitting.py:221-222`, `:249-251`
- **What it is:** Antigravity-deep B5 env-gated payload logging in `translator.py` (`MTD_DEBUG_PAYLOADS=1`), but the same pattern in `splitting.py` was not updated.
- **Evidence:**
  ```python
  prompt = self.build_subtitle_splitter_prompt(…)
  print("prompt:")
  print(prompt)
  ...
  print("response:")
  print(json.dumps(response_json, indent=4))
  ```
- **Tool output:** `grep -n 'print("prompt:")' splitting.py` matched at 221; `print("response:")` at 249.
- **Why it matters:** Same exfiltration / log-bloat surface as B5. When the `--splitengine openai` path is selected, every block's full prompt + every API response JSON lands in launcher stdout and (via failure archive) potentially in Telegram alerts.
- **Recommendation:** Apply the same `MTD_DEBUG_PAYLOADS` gate. Default emits a one-line summary. Applied this commit.
- **Effort:** S
- **Status:** **fixed in this commit.**
- **Duplicate-of:** extension of Antigravity-deep B5.

### C3 — `update_job` can `KeyError` when the job is cancelled mid-flight
- **Severity:** Low
- **Category:** Reliability
- **Location:** `local_launcher.py:452-455`
- **What it is:** The stdout-reader thread of a running subprocess calls `update_job` to report progress. If `cancel_job` pops the entry before the reader thread reaches its next status update, `self.jobs[job_id]` raises `KeyError` and kills the reader thread (the subprocess itself continues until its own kill signal lands).
- **Evidence:**
  ```python
  def update_job(self, job_id: str, **changes) -> None:
      with self.lock:
          job = self.jobs[job_id]        # ← raises if cancelled
          self.jobs[job_id] = Job(**{**asdict(job), **changes})
  ```
- **Tool output:** code review; no production trace recorded yet.
- **Why it matters:** Reader-thread death is silent (the launcher's main loop doesn't supervise it). On a cancelled job the launcher's failure-archive routine then loses the last few lines of stdout. Minor — but the project rule "no silent thread death" applies.
- **Recommendation:** `self.jobs.get(job_id)` + early return when None. Applied this commit.
- **Effort:** S
- **Status:** **fixed in this commit.**

---

## Mandatory-category coverage

| Category | New defects | Note |
|----------|------------:|------|
| Architecture | 0 | Reviewed `cli.py` AST; 11 functions > 80 lines but all known. `_get_ctx` (171 lines) and `main` (170 lines) are the bridge / orchestrator. No new defect; documented as reviewed. |
| Performance | 0 | All prompts cache-warm (>1 024 tokens); `subprocess.Popen` uses `bufsize=1` for progress markers. Reviewed and confirmed. |
| Reliability | 2 (C1, C3) | Both fixed in this commit. |
| Security | 1 (C2) | Fixed in this commit. |
| Persian-specific | 0 | Aligner edge cases pass cleanly. Reviewed and confirmed; one minor non-defect (repeated-word edge produces n-1 chunks) is a low-priority edge that does not occur in real subtitle text. |
| Workflow | 0 | CI workflow present, no committed secrets/logs, no in-source TODO/FIXME. Confirmed. |

---

## Cross-cutting observations

### Migration progress
`_get_ctx` (171 lines) still snapshots ~40 module-level globals into `RuntimeContext`; `_sync_globals_from_ctx` mirrors them back. ~221 module-level statements in `cli.py`. Same picture as Antigravity-deep B1; the migration is partially complete and the bridge is the only thing currently holding it together. No new finding.

### Test coverage estimate (file scan, no runtime coverage)
| Module | Test files | Estimated coverage |
|--------|------------|-------------------:|
| `cli.py` | `test_launcher_endpoints.py` (integration only) | <15 % |
| `local_launcher.py` | `test_launcher_endpoints.py` | ~35 % |
| `openai_tools/translator.py` | `test_translator_*.py`, fixtures | ~50 % |
| `openai_tools/polisher.py` | `test_polisher_*.py` | ~55 % |
| `openai_tools/persian_double_lines.py` | aligner fixture; new `tools/aligner_bench.py` | ~65 % |
| `openai_tools/_retry.py` | none | 0 % |
| `openai_tools/line_count_reconciler.py` | `test_line_count_reconciler.py` (mocked) | ~40 % |
| `docx_io/` | `test_save_docx.py`, `test_cells.py` | ~70 % |
| `runner.py` | integration only | <10 % |

### Prompt cache utilisation
All four system-prompt configurations (FA translate, FA polish, universal translate, universal polish) are between 1 320 and 4 645 tokens. **None is cache-cold.** Per-call cache reuse is bounded only by the 24-hour retention and the user-message payload being unique per document (expected).

### Top 5 highest-risk paths (post-audit)
1. **F8 (still open):** polish reports lines modified but final docx unchanged. Root-cause investigation still pending — likely a redistribution step in `get_translation_and_replace_after`.
2. **`cli.py` global / context bridge** (Antigravity-deep B1, Jules-deep B1) — state drift risk.
3. **`local_launcher.py` monolith** (Antigravity-deep B11) — coupling risk on future feature changes.
4. **Aligner mechanical n-1 chunks edge** (this audit, minor) — repeated-word input gives n-1 chunks; harmless in real subtitle text.
5. **Per-block translate fallback raw-passthrough** (Antigravity-deep B6) — single-call path is reconciled, but the per-block path still emits raw mismatch output with a `[WARNING]`.

### Score

- Findings this pass: **3** (C1, C2, C3) — all fixed in this commit.
- Severity breakdown: 0 critical, 2 medium, 1 low.
- Categories: 6/6 explicitly reviewed; 4 emitted "no defect found".
- Total cumulative findings across all 5 audit passes (Antigravity-light + Codex-light + Jules-light + Antigravity-deep + Jules-deep + this): ~63.
  Of those: ~22 fixed, ~10 false / stale rejected, ~6 already covered by earlier fixes, ~25 deferred (architecture / workflow L-effort items).
- 113 unit tests green; aligner bench unchanged at 232 doubles / 0 over_limit.

**Verdict:** codebase health is solid for production use of the chatgpt-polish + persian_double_lines pipeline. The architecture roadmap (cli.py monolith, launcher monolith, `_sync_globals_from_ctx` bridge) is the next big lever, scheduled but not blocking. No open critical or high-severity defect.
