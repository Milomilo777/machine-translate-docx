# Antigravity audit — 2026-05-12

## Executive summary
- **Monolithic God-module:** `src/machine_translate_docx/cli.py` (4,300+ lines) is a severe maintainability bottleneck, mixing UI, driver management, and core business logic.
- **Security - Command Injection:** A high-severity risk exists in `cli.py` due to `subprocess.Popen(..., shell=True)` on unsanitized output paths, potentially allowing local privilege escalation via malicious filenames.
- **Prompt Cache Hostility:** Key OpenAI prompts start with variable data (e.g., "{n} lines"), which invalidates the prefix-based prompt cache for the entire document payload, significantly increasing costs.
- **Fragile State Synchronization:** The `_sync_globals_from_ctx` bridge in `cli.py` highlights the risks of the ongoing migration; any failure to call it at a pipeline boundary results in silent state drift.
- **Reliability - Swallowed Failures:** Widespread use of `except Exception: pass` and bare `except:` blocks (especially in `cli.py`) masks critical initialization and driver errors.

## Findings

### A1 — Monolithic `cli.py`
- **Severity:** High
- **Category:** Architecture
- **Location:** `src/machine_translate_docx/cli.py:1-4364`
- **What it is:** The file has grown to 4,364 lines and violates the Single Responsibility Principle. It contains CLI parsing, Selenium driver orchestration, regex lists for "bridge" rows, legacy VBA macro text, and the main pipeline loop.
- **Why it matters:** It is difficult to test in isolation, prone to merge conflicts, and creates a high cognitive load for developers.
- **Recommendation:** Extract `bridge_patterns` to `config.py`, move Selenium orchestration to `selenium_utils/driver.py`, and move document processing logic to a `Pipeline` class.
- **Effort:** L (1+ day)

### A2 — Command Injection in `open_app_docx_file`
- **Severity:** Critical
- **Category:** Security
- **Location:** `src/machine_translate_docx/cli.py:4111`
- **What it is:** On Windows, the script opens the translated file using `subprocess.Popen(["start", "", out_path], shell=True)`.
- **Why it matters:** Allows a malicious DOCX file (with a crafted name) to execute code in the context of the local user when the "Open file" feature is used.
- **Recommendation:** Use `os.startfile(out_path)` on Windows instead of `subprocess.Popen` with `shell=True`.
- **Effort:** S (<1h)

### A3 — Cache-hostile Prompt Prefixes
- **Severity:** High
- **Category:** Performance
- **Location:** `src/machine_translate_docx/openai_tools/translator.py:270`, `polisher.py:165`
- **What it is:** User prompts start with dynamic counts like `"Translate the following {n} lines:"`.
- **Why it matters:** OpenAI's prompt caching relies on exact prefix matches. By putting the line count at the very start, every document with a different line count misses the cache for the entire message body.
- **Recommendation:** Move dynamic metadata (line counts, filenames) to the *end* of the prompt or into a non-cached message role.
- **Effort:** M (half a day)

### A4 — Fragile State Bridge (`_sync_globals_from_ctx`)
- **Severity:** Medium
- **Category:** Architecture
- **Location:** `src/machine_translate_docx/cli.py:416-458`
- **What it is:** The architecture relies on an explicit synchronization function to mirror `RuntimeContext` state back to module-level globals for legacy functions to read.
- **Why it matters:** If a developer adds a new pipeline step but forgets to call `_sync_globals_from_ctx`, the backend will operate on stale or `None` state.
- **Recommendation:** Accelerate the removal of module-level globals; pass `ctx` explicitly to all 40+ remaining functions.
- **Effort:** L (1+ day)

### A5 — Synchronized Parallel Arrays Anti-pattern
- **Severity:** Medium
- **Category:** Architecture
- **Location:** `src/machine_translate_docx/runtime.py:80-110` (DocxCtx)
- **What it is:** State is managed across multiple independent lists (`from_text_table`, `to_text_by_phrase_separator_table`) that must stay aligned by index.
- **Why it matters:** Any logic error that appends to one list but not others leads to catastrophic misalignment of subtitles.
- **Recommendation:** Replace parallel arrays with a list of `SubtitleRow` objects.
- **Effort:** L (1+ day)

### A6 — XSS Risk in v2 Announcements
- **Severity:** High
- **Category:** Security
- **Location:** `web/v2/app.js:672`
- **What it is:** The v2 SPA renders various components using `innerHTML`.
- **Why it matters:** Using `innerHTML` for text fields is a security risk if the JSON source (e.g. content.json) is ever compromised.
- **Recommendation:** Use `textContent` for text and `replaceChildren()` with created elements.
- **Effort:** S (<1h)

### A7 — Swallowed Errors in CLI Initialization
- **Severity:** Medium
- **Category:** Reliability
- **Location:** `src/machine_translate_docx/cli.py:214-230`
- **What it is:** Critical blocks (fetching online config, parsing arguments) are wrapped in `except Exception: pass`.
- **Why it matters:** Errors are silenced, leaving the program in an inconsistent state without user notification.
- **Recommendation:** Log errors at `WARNING` level; if fatal, raise a structured `TranslationFailure`.
- **Effort:** M (half a day)

### A8 — Confirmed Open: F5 (Reconciler Convergence)
- **Severity:** Medium
- **Category:** Reliability
- **Location:** `src/machine_translate_docx/openai_tools/line_count_reconciler.py:120`
- **What it is:** The reconciler uses `gpt-5.4-mini` which often repeats the same formatting errors over its 2 attempts.
- **Why it matters:** LLM failure results in padding/truncation, which corrupts subtitle alignment.
- **Recommendation:** Increase `max_attempts` to 3 and vary the temperature or prompt on the final attempt.
- **Effort:** S (<1h)

### A9 — Confirmed Open: F6 (Polish Sensitivity)
- **Severity:** Low — needs investigation
- **Category:** Persian-specific
- **Location:** `prompts/polish_PER.txt:30-60`
- **What it is:** The polish prompt's `<CONSERVATISM_GATE>` is extremely aggressive (semantic shift ≥5% → ABANDON).
- **Why it matters:** Results in a 1% refinement rate for certain document types (Village/VE) vs 50% for others.
- **Recommendation:** Review register-specific sensitivity in the polish prompt.
- **Effort:** M (half a day)

### A10 — Confirmed Open: F8 (Polish NO CHANGE reporting)
- **Severity:** Low
- **Category:** Reliability
- **Location:** `src/machine_translate_docx/engines/chatgpt_api.py:136`
- **What it is:** System reports "refined N lines" but the diff check shows `NO CHANGE`.
- **Why it matters:** This happens because progress is logged based on lines *processed*, not lines *modified*.
- **Recommendation:** Update `polisher.py` to return the count of lines actually modified.
- **Effort:** S (<1h)

### A11 — Sync I/O in `local_launcher.py`
- **Severity:** Low
- **Category:** Performance
- **Location:** `local_launcher.py:910`
- **What it is:** `_send_file` uses blocking `read_bytes()` in the main thread.
- **Why it matters:** High-concurrency downloads could degrade the launcher's ability to respond to polling requests.
- **Recommendation:** Move to an async framework or use a thread pool for file reads.
- **Effort:** M (half a day)

### A12 — Credentials Leak via `os.environ`
- **Severity:** Low
- **Category:** Security
- **Location:** `src/machine_translate_docx/cli.py:4350`
- **What it is:** The script modifies the process `PATH` globally using `os.environ`.
- **Why it matters:** While not a leak in itself, global environment modification in a shared environment can leak configuration to subprocesses.
- **Recommendation:** Use the `env` argument in `subprocess.Popen` to pass specific variables instead of modifying the global environment.
- **Effort:** S (<1h)

### A13 — Path Validation for failure archive
- **Severity:** Medium
- **Category:** Security
- **Location:** `local_launcher.py:1550`
- **What it is:** The failure archive logic constructs paths using `job_id` and `timestamp`.
- **Why it matters:** If `job_id` is ever derived from user-controlled input, it could lead to directory traversal. Currently, `job_id` is a UUID, which mitigates this.
- **Recommendation:** Keep `job_id` as a server-side UUID only.
- **Effort:** S (<1h)
