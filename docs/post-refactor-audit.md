# Post-refactor audit — `audit/post-refactor` branch

Branch base: `f798322` (Phase G4 — runner extraction)
Auditor: claude-opus-4-7
Audit date: 2026-05-08
Pytest result going in: 36 passed, 1 DeprecationWarning
Pytest result going out: 36 passed, no warnings

This is a critical-eyes review of the modules created or moved during
the Phase A→G refactor. It does not re-litigate already-decided design
calls (RuntimeContext shape, engine extraction order, hyphenated entry
script). It surfaces the bugs, drifts, and dead code each module
acquired during extraction.

---

## Summary

The refactor is **structurally sound**. Every PROGRESS marker, every
parallel array, the DeepL R15 fallback, and the OpenAI cache-retention
contract survived extraction unchanged. The audit found no regressions
that breaks the active code paths.

What it did surface, in order of severity:

* **One critical** — `engines/_base.py` Engine Protocol signature was
  out of sync with the post-F1 `translate(ctx, text)` shape. Anything
  doing `isinstance(mod, Engine)` would have given the wrong answer.
  *Fixed.*
* **Two highs** — a dead `str.unescape(...)` call on a plain string in
  `engines/google.py` (would `AttributeError` if hit) and a
  Windows-only `UnicodeEncodeError` in `local_launcher.py` when the
  console is `cp1252`. The first is fixed; the second is in a
  read-only file (per refactor work-order R12) and is documented
  below.
* **Several mediums and lows** — docstring drift (six dataclasses,
  twelve arrays — both stale), unused imports, a discarded
  `traceback.format_exc()` return value, a `\d`/`\%` invalid-escape
  regex string, a dead defensive None-check. All fixed in this
  branch.
* **Three "by design"** — bare `ctx.browser.driver.page_source`
  encoding pre-warm, dead "Browse your files" sentinel, malformed
  `$Translation` regex. The first two are documented as intentional
  for parity with the historical body. The third is a real latent
  bug, but fixing it changes wait-loop semantics; deferred.
* **One architectural** — `translate_docx`,
  `get_translation_and_replace_after`, and ~40 other functions in
  `src/machine-translate-docx.py` were *not* threaded by Phase F1.6.
  They still read module-level globals. `main()` is fully threaded and
  the new modules are fully threaded; the entry script's middle
  layer is the gap. Out of scope for trivial fixes — flagged for a
  future Phase H.

---

## Findings

| ID    | Severity  | File                          | Status   | One-liner                                                                |
|-------|-----------|-------------------------------|----------|--------------------------------------------------------------------------|
| F-001 | CRITICAL  | `src/engines/_base.py`        | Fixed    | Engine Protocol declared the pre-F1 signature; replaced with `(ctx, text)`. |
| F-002 | MEDIUM    | `src/runtime.py`              | Fixed    | Docstring said "six dataclasses" / "12 parallel arrays"; actual is 7 / 22+. |
| F-003 | LOW       | `src/engines/__init__.py`     | Fixed    | Docstring claimed `set_translation_function` reads from `DISPATCH_TABLE`; it doesn't. |
| F-004 | LOW       | `src/engines/chatgpt_api.py`  | Fixed    | `… if oai_translator else {}` is unreachable — caller already None-guards. |
| F-005 | LOW       | `src/engines/google.py`       | Fixed    | `urlencode`, `quote_plus` imports never used.                            |
| F-006 | MEDIUM    | `src/engines/google.py`       | Fixed    | `traceback.format_exc()` result discarded — silent failure.              |
| F-007 | HIGH      | `src/engines/google.py`       | Fixed    | `translation.unescape(translation)` — `str` has no `unescape` method.    |
| F-008 | LOW       | `src/engines/google.py`       | Documented | Bare `ctx.browser.driver.page_source` statement; comment says it is an encoding pre-warm. Kept for parity. |
| F-009 | LOW       | `src/engines/google.py`       | Documented | Dead "Browse your files" sentinel; preserved with the comment that explains why. |
| F-010 | LOW       | `src/engines/google.py`       | Deferred | `regex_still_translating_str = '$Translation'` — `

` is end-of-string, so the loop guard nearly never matches. Real bug, but flipping it changes wait-loop behavior. Defer. |
| F-011 | MEDIUM    | `src/engines/deepl.py`        | Fixed    | `json`, `requests`, `Keys` imports were unused.                          |
| F-012 | ARCH      | `src/machine-translate-docx.py` | Out of scope | ~40 entry-script functions still read module-level globals; F1.6 only threaded `main()` + leaves. |
| F-013 | HIGH      | `local_launcher.py`           | Read-only | First `print()` in `_process_job` contains U+25B6 / U+2014; crashes on Windows when stdout is `cp1252`. Workaround: `set PYTHONIOENCODING=utf-8`. |
| F-014 | LOW       | `src/engines/deepl.py`        | Fixed    | Regex string `"...\d+\%..."` raised invalid-escape DeprecationWarning.   |
| F-015 | LOW       | `src/engines/deepl.py`        | Documented | `closed_cookies_accept_message_bool` referenced as a local in `selenium_chrome_deepl_log_in` (would `NameError`); but inside `try/except: pass`, so silently swallowed. Cosmetic — `deepl_close_messages` already owns the canonical `ctx.browser.*` flag. |

### F-001 — Engine Protocol out of sync (CRITICAL)

`engines/_base.py` declared:

```python
def translate(self, source_text, src_lang_name, dest_lang_name) -> tuple[bool, str]: ...
```

But `engines.google.translate`, `engines.deepl.translate` (and the
DISPATCH_TABLE typing hint) all use:

```python
def translate(ctx: RuntimeContext, text: str) -> tuple[bool, str]: ...
```

The Protocol was the *aspirational* Phase B/C shape; the `RuntimeContext`
threading in F1 changed the actual contract. The docstring even said
"This is aspirational. The current Selenium engines (Google, DeepL)
still mutate module-level globals and won't conform until Phase C/F" —
but Phase F has shipped. Fix: rewrite the Protocol to the post-F1
shape and add the `RuntimeContext` import.

### F-007 — `str.unescape` (HIGH)

`engines/google.py`:

```python
translation = result_element.get_attribute('innerHTML')
translation = translation.unescape(translation)   # AttributeError
```

`str` has no `unescape` method. The intended call is `html.unescape`.
This sits inside a `while re.search(regex_still_translating_str, ...)`
loop whose regex is broken (F-010), so in practice the line is never
reached today — but it's a NameError waiting to happen. Fix in the
same module: import `html`, swap to `html.unescape(translation)`.

### F-013 — Windows console encoding (HIGH, read-only file)

Verified during the smoke test: launching the launcher with
`E:\Python311\python.exe local_launcher.py --backend mock` on a stock
Windows shell produces:

```
UnicodeEncodeError: 'charmap' codec can't encode character '▶'
in position 39: character maps to <undefined>
File "local_launcher.py", line 554, in _process_job
print(f"[job {job_id}] ▶ start — file: {original_name} | …")
```

The `_process_job` thread crashes on first call, the job stays
`pending` forever, and the upload loop hangs. Setting
`PYTHONIOENCODING=utf-8` (verified) avoids the issue.

`local_launcher.py` is on the refactor read-only list, so this audit
does not change it. Two options for whoever owns the launcher:

1. Set `sys.stdout.reconfigure(encoding="utf-8")` at startup (the
   entry script already does the equivalent), or
2. Strip the `▶`/`✓`/`✗`/`—` decorations, or
3. Document `set PYTHONIOENCODING=utf-8` in the launcher's bat
   wrapper.

### F-012 — Phase F1.6 threading is partial (architectural)

`main()` is threaded. `selenium_chrome_machine_translate`,
`set_translation_function`, `read_and_parse_docx_document`, and
`save_docx_file` are threaded. Roughly 25 of 69 entry-script
functions are threaded.

The remaining ~44 (`translate_docx`, `get_translation_and_replace_after`,
`document_split_phrases`, `write_destination_language_in_docx_cell`,
`print_console_docx_file_translated`, …) still read globals like
`engine_method`, `translation_engine`, `oai_polisher`,
`from_text_table`, `to_text_by_phrase_separator_table`, etc. They
work today because those globals exist at module level — but the
F1.6 commit message ("zero `global` statements remain in main") is
narrowly true (in *main()*) and broadly misleading.

This is a real follow-up. Out of scope for the audit's trivial-fix
budget. Tag as Phase H.

---

## Smoke-test results (mock backend)

```
$ E:\Python311\python.exe -m pytest tests/
36 passed, 1 warning  (pre-fix; the DeprecationWarning is now gone)

$ set PYTHONIOENCODING=utf-8
$ E:\Python311\python.exe local_launcher.py --backend mock --no-browser --port 3008
$ curl -F file=@/tmp/sample.docx -F sourceLanguage=Auto -F targetLanguage=en \
       -F translationEngine=google http://127.0.0.1:3008/upload
{"ok": true, "jobId": "e0e5d6a9…", "cacheHit": false}

$ curl http://127.0.0.1:3008/status/e0e5d6a9…
{"ok": true, "status": "done", "filename": "sample_EN.docx",
 "error": null, "progress": 10}

$ curl -o /tmp/sample_EN.docx http://127.0.0.1:3008/download/sample_EN.docx
$ file /tmp/sample_EN.docx
/tmp/sample_EN.docx: Microsoft Word 2007+
```

**Cache-hit duplicate upload (chatgpt-polish)**:

```
$ curl -F translationEngine=chatgpt-polish … upload  # first call
{"ok": true, "jobId": "0731fd18…", "cacheHit": false}

$ curl -F translationEngine=chatgpt-polish … upload  # second call
{"ok": true, "jobId": "ae8e4908…", "cacheHit": false}
```

The second call should have hit the cache. It does not, because in
mock mode `cache_store` is never called — the cache write lives only
inside `_run_real_backend` (line 881). This is intentional: mock mode
is for UI exercising, not pipeline correctness. Documented for
completeness; not a finding.

---

## D1–D7 dimension scores

| Dimension          | Score      | Notes                                                                              |
|--------------------|------------|------------------------------------------------------------------------------------|
| D1 Correctness     | A−         | F-001 + F-007 fixed; F-010 deferred (latent dead-loop bug); F-013 launcher gap.    |
| D2 Smell           | B          | F-004 dead defensive guard; F-008/F-009 carried forward but documented as intentional. |
| D3 Dead code       | B+         | F-005 + F-011 removed; F-009 preserved with rationale.                             |
| D4 Security        | A          | No new attack surface; subprocess proxy-strip and content-length cap intact.       |
| D5 Performance     | A          | PROGRESS markers + cache TTL + `prompt_cache_retention=24h` all preserved.         |
| D6 Maintainability | B          | New modules read clean; entry script middle layer (F-012) is the drag.             |
| D7 Contract        | A          | Output filename suffixes (`_PER_TranslatePolish`, `_PER_Classic`, `_PER_Double`), aligner model `gpt-5.4-mini`, R15 fallback, R16 `+1` indexing — all unchanged. |

---

## Next steps

1. **Phase H — finish F1**: thread the remaining ~44 entry-script
   functions through `ctx`. Largest blocker is the parallel-array
   getter/setter pattern; mechanical regex sweep + per-function
   verification (the same playbook as F1.1–F1.6).
2. **F-010 fix**: replace `'$Translation'` with the right wait-marker
   regex once someone confirms what google translate actually emits
   while the result element is still pending. Independent of the
   refactor.
3. **F-013 fix**: pick one of the three workarounds in the launcher.
   The shortest is the `sys.stdout.reconfigure` line at startup.
4. **`audit/post-refactor` → `master`**: seven `fix(audit):` commits
   on top of `refactor/architecture`'s G4 head. Squash-merge OK; the
   commit messages are individually informative but the diff is small
   enough to land as one squash if preferred.
