# Antigravity deep audit — 2026-05-12

## Executive summary
- **Architecture — Legacy Debt:** roughly 65 % of the system still operates via a fragile "bridge" of module-level globals synchronized from a `RuntimeContext` object.
- **Security — Command Injection:** A critical risk in `cli.py` allows arbitrary code execution via crafted DOCX filenames when using the "Open file" feature.
- **Security — Browser Hardening:** The web layer lacks basic security headers (CSP) and uses unsafe `innerHTML` for rendering user/operator data, creating a multi-stage XSS path.
- **Performance — Cache Hostility:** System prompts use dynamic prefixes (e.g., line counts at index 0), which invalidates OpenAI's prompt cache and significantly increases operational costs.
- **Reliability — Silent Failures:** Widespread use of `except Exception: pass` and parallel subtitle arrays that can drift out of sync makes the system difficult to debug and prone to misaligned output.

## Findings

### A1 — Monolithic `cli.py`
- **Severity:** High
- **Category:** Architecture
- **Location:** `src/machine_translate_docx/cli.py:1-4364`
- **What it is:** The file has grown to 4,364 lines and violates the Single Responsibility Principle. It contains CLI parsing, Selenium driver orchestration, and core business logic.
- **Why it matters:** It is difficult to test in isolation and creates a high cognitive load for developers.
- **Recommendation:** Extract patterns to `config.py` and move Selenium orchestration to `selenium_utils/driver.py`.
- **Effort:** L (1+ day)

### A2 — Command Injection in `open_app_docx_file`
- **Severity:** Critical
- **Category:** Security
- **Location:** `src/machine_translate_docx/cli.py:4111`
- **What it is:** On Windows, the script opens the translated file using `subprocess.Popen(["start", "", out_path], shell=True)`.
- **Why it matters:** Allows a malicious DOCX file (with a crafted name) to execute code in the context of the local user.
- **Recommendation:** Use `os.startfile(out_path)` on Windows instead of `subprocess.Popen` with `shell=True`.
- **Effort:** S (<1h)

### A3 — Cache-hostile Prompt Prefixes
- **Severity:** High
- **Category:** Performance
- **Location:** `src/machine_translate_docx/openai_tools/translator.py:270`, `polisher.py:165`
- **What it is:** User prompts start with dynamic counts like `"Translate the following {n} lines:"`.
- **Why it matters:** OpenAI's prompt caching relies on exact prefix matches. By putting the line count at the very start, every document with a different line count misses the cache.
- **Recommendation:** Move dynamic metadata (line counts, filenames) to the *end* of the prompt.
- **Effort:** M (half a day)

### A4 — Fragile State Bridge (`_sync_globals_from_ctx`)
- **Severity:** Medium
- **Category:** Architecture
- **Location:** `src/machine_translate_docx/cli.py:416-458`
- **What it is:** The architecture relies on an explicit synchronization function to mirror `RuntimeContext` state back to module-level globals for legacy functions to read.
- **Why it matters:** If a developer adds a new pipeline step but forgets to call this bridge, legacy functions like `write_translation_log` will operate on stale data.
- **Recommendation:** Accelerate the removal of module-level globals; pass `ctx` explicitly.
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
- **What it is:** The v2 SPA renders components from `content.json` using `innerHTML`.
- **Why it matters:** Using `innerHTML` for text fields is a security risk if the JSON source is compromised.
- **Recommendation:** Use `textContent` for text and `replaceChildren()` for markup.
- **Effort:** S (<1h)

### A7 — Swallowed Errors in CLI Initialization
- **Severity:** Medium
- **Category:** Reliability
- **Location:** `src/machine_translate_docx/cli.py:214-230`
- **What it is:** Critical blocks (fetching online config, parsing arguments) are wrapped in `except Exception: pass`.
- **Why it matters:** Errors are silenced, leaving the program in an inconsistent state without user notification.
- **Recommendation:** Log errors at `WARNING` level; if fatal, raise a structured `TranslationFailure`.
- **Effort:** M (half a day)

### B1 — Incomplete Context Migration (Deep)
- **Severity:** High
- **Category:** Architecture
- **Location:** `src/machine_translate_docx/cli.py:416-458`
- **What it is:** Build on A4. The bridge function only mirrors a whitelist of fields.
- **Why it matters:** Subsystems like the `APILogger` were found to rely on module globals that were not in the initial whitelist, causing "silent" missing logs in earlier versions.
- **Recommendation:** Phase out `_sync_globals_from_ctx` by the end of May 2026.
- **Effort:** L (1+ day)

### B2 — Unreferenced Legacy Functions
- **Severity:** Low
- **Category:** Architecture
- **Location:** `src/machine_translate_docx/cli.py:1250, 1860, 3920, 4050`
- **What it is:** Functions like `getDownLoadedFileNameFirefox` and `join_from_lines` are defined but never called from any code path.
- **Why it matters:** Increases maintenance burden and bloats the 4,300-line god-module.
- **Recommendation:** Delete these functions to improve legibility.
- **Effort:** S (<1h)

### B3 — Prompt Cache Under-utilization
- **Severity:** High
- **Category:** Performance
- **Location:** `prompts/translate_PER.txt`, `prompts/polish_PER.txt`
- **What it is:** Static instruction prefixes are ~300-450 tokens.
- **Why it matters:** OpenAI caching is most effective above 1,024 tokens. Instruction bloat is actually beneficial here for cost-saving on the subsequent payload.
- **Recommendation:** Include more detailed style-guide examples in the system prompt to reach the 1,024-token warm-cache threshold.
- **Effort:** M (half a day)

### B4 — Blocking Binary Reads in Launcher
- **Severity:** Medium
- **Category:** Performance
- **Location:** `local_launcher.py:931-950`
- **What it is:** `_send_zip_for_job` reads the entire output archive into memory synchronously using `read_bytes()`.
- **Why it matters:** Blocks the main thread. Large zip files (50 MB+) will cause polling requests to time out during the read.
- **Recommendation:** Use a generator to stream chunks from disk.
- **Effort:** M (half a day)

### B5 — Brittle Driver Cleanup (Zombie Risk)
- **Severity:** Medium
- **Category:** Reliability
- **Location:** `src/machine_translate_docx/cli.py:150-180`
- **What it is:** The `atexit` cleanup for Selenium drivers depends on a successfully initialized `_ctx`.
- **Why it matters:** If the script crashes *during* initialization after spawning Chrome, the process is orphaned.
- **Recommendation:** Record PIDs to a lockfile/sidecar immediately upon spawning.
- **Effort:** M (half a day)

### B6 — Silent Failure in Aligner Edge-Cases
- **Severity:** Medium
- **Category:** Persian-specific
- **Location:** `src/machine_translate_docx/openai_tools/persian_double_lines.py:150-220`
- **What it is:** The aligner skips leading rows with empty FA cells before the first sentence group is parsed.
- **Why it matters:** Can produce a truncated document without raising an error.
- **Recommendation:** Assert that at least one group is parsed if the source table is non-empty.
- **Effort:** S (<1h)

### B7 — Missing Content Security Policy (CSP)
- **Severity:** Medium
- **Category:** Security
- **Location:** `local_launcher.py:860-900`
- **What it is:** The launcher serves the v2 SPA without any security headers.
- **Why it matters:** Combined with the `innerHTML` usage in `app.js` (A6), it allows successful XSS via a compromised `content.json`.
- **Recommendation:** Implement a strict CSP header.
- **Effort:** S (<1h)

### B8 — Hardcoded Local Paths in Batch Scripts
- **Severity:** Low
- **Category:** Workflow
- **Location:** `compile.bat`, `tasks.bat`
- **What it is:** Batch files contain absolute path assumptions or lack of `%~dp0` scoping.
- **Why it matters:** Hinders portability across developer machines.
- **Recommendation:** Scrape all batch files for hardcoded paths.
- **Effort:** S (<1h)

## Cross-cutting observations

### Migration progress
- **~35 %** of `cli.py` functions use `RuntimeContext` explicitly.
- **~65 %** rely on the `_sync_globals_from_ctx` bridge.
- Status: **Phase H (Bridge) is stable but risky.**

### Test coverage estimate
| Module | Estimated coverage | Has live tests? |
|--------|-------------------|-----------------|
| cli.py | ~15 % | No |
| local_launcher.py | ~40 % | Yes |
| openai_tools/ | ~70 % | Yes |
| docx_io/ | ~60 % | Yes |

### Prompt cache utilisation estimate
- **translate_PER.txt:** ~300 tokens (Cache-cold < 1024)
- **polish_PER.txt:** ~450 tokens (Cache-cold < 1024)
- **Universal:** ~200 tokens (Cache-cold < 1024)

### Top 5 highest-risk paths
1. **Unsanitized Output Opening:** Malicious filename → Command Injection (A2).
2. **Global State Desync:** Desync between `ctx` and globals → Data corruption (B1).
3. **Subtitle Row Misalignment:** Parallel array drift → Corrupt output (A5).
4. **Persistent Driver Leak:** Failed initialization → System memory exhaustion (B5).
5. **DOM-based XSS:** Malicious content → Script execution (A6, B7).
