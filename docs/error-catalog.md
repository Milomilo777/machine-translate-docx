# Error Catalog

Recurring bugs, root causes, and fixes. Add an entry any time a non-trivial bug is fixed.

---

## E1 — Splitter fallback model 404

**ID:** E1  
**Status:** Fixed 2026-05-07  
**Symptom:** `splitting.py` retry path switched to model `gpt-5_5-2026-04-23` → OpenAI returned 404  
**Root cause:** Model name used underscore (`gpt-5_5`) instead of dot (`gpt-5.5`)  
**Fix:** `machine-translate-docx.py` line ~6431 — corrected to `gpt-5.5`  
**Regression test:** Check model string: `assert '.' in model_name and '_' not in model_name`

---

## E2 — JS Temporal Dead Zone crash in engineChecker()

**ID:** E2  
**Status:** Fixed  
**Symptom:** Page completely unresponsive after adding Persian engine auto-select; console: `Cannot access 'engineSelector' before initialization`  
**Root cause:** `engineChecker()` was called inside `setTargetLangs()` which ran before `const engineSelector` was declared in the outer `DOMContentLoaded` scope  
**Fix:** Inside `engineChecker()`, use `const engineSel = document.getElementById('translationEngine')` (local variable) instead of the outer `engineSelector`  
**Lesson:** Never reference outer `const`/`let` in a function that may be called before the declaration is reached (TDZ applies even inside closures)

---

## E3 — Timestamp prefix in downloaded filename

**ID:** E3  
**Status:** Fixed  
**Symptom:** Downloaded file named `1778036666789-myfile_PER_TranslatePolish.docx`  
**Root cause:** `local_launcher.py` saved uploads as `{timestamp_ms}-{filename}` and the output inherited the prefix  
**Fix:** `_strip_timestamp()` method in `local_launcher.py` — renames file to clean name before returning  
**Note:** If clean name already exists, the timestamped copy is deleted

---

## E4 — _PER_Double.docx not served for download

**ID:** E4  
**Status:** Fixed 2026-05-07  
**Symptom:** Aligner created `_PER_Double.docx` on disk; backend log confirmed it; but browser only downloaded the main file  
**Root cause:** `local_launcher.py` only read `Saved file name:` stdout line (main output); aligner output path was never communicated to launcher  
**Fix:**  
- `Job` dataclass gained `filename2: str | None = None`  
- `_find_double_file()` probes for `_PER_Double.docx` sibling  
- `/status/` endpoint returns `filename2` when present  
- `index.ejs` `pollJobStatus()` returns `{ filename, filename2 }`  
- `triggerDownload()` fires second download 800 ms after first

---

## E5 — Polisher ⟨⟨N⟩⟩ tag parser edge cases

**ID:** E5  
**Status:** Active — monitor  
**Symptom:** Occasionally polisher returns lines with variant tag formats; parser misses one or two lines  
**Root cause:** GPT sometimes uses slightly different Unicode angle brackets or adds spaces  
**Fix:** Parser has 4 fallback strategies; handles most cases  
**Watch for:** Lines count mismatch between input and polished output in log

---

## E6 — cached_tokens: 0 in splitting.py calls

**ID:** E6  
**Status:** Fixed 2026-05-07  
**Symptom:** All `splitting.py` API calls showed `cached_tokens: 0` despite identical system prompt  
**Root cause:** `extra_body={"prompt_cache_retention": "24h"}` was missing from `splitting.py`'s `chat.completions.create()` call  
**Fix:** Added `_cache_extra = {"prompt_cache_retention": "24h"}` and passed as `extra_body` to both `responses.create` and `chat.completions.create` in `splitting.py`

---

## E7 — Output suffix _FA instead of _PER

**ID:** E7  
**Status:** Fixed  
**Symptom:** Mock mode output file named `file_FA.docx` instead of `file_PER.docx`  
**Root cause:** `_fallback_output_path()` used `target_language.replace("-","").upper()` directly → `fa` → `FA`  
**Fix:** `_LANG_ALPHA3B` dict in `local_launcher.py` maps `'fa'` → `'PER'`; `_lang_suffix()` helper used everywhere

---

## E8 — Split Method + Aligner conflict (massive API calls)

**ID:** E8  
**Status:** Fixed 2026-05-08  
**Symptom:** Log showed hundreds of "Splitting phrase" OpenAI API calls; job took much longer than expected; output quality not improved  
**Root cause:** When `chatgpt-polish` engine selected + `Split Method: OpenAI API` checked (default), the pipeline ran: translate → polish → **split each phrase with OpenAI** → aligner. The splitter and aligner both distribute FA text across EN rows — identical work done twice. The splitter's output was then re-distributed by the aligner, wasting all split work.  
**Fix:** `index.ejs` — `engineChecker()` hides `#splitSection` div and unchecks `splitTranslate` when target=`fa` AND engine=`chatgpt-polish`. `engineSelector.addEventListener('change', engineChecker)` added to trigger on engine switch.  
**Regression test:** For Persian + chatgpt-polish, log must show zero "Splitting phrase" lines.

---

## E9 — Only 1 of 3 files downloaded (Chrome multi-download block)

**ID:** E9  
**Status:** Mitigated 2026-05-08  
**Symptom:** Browser showed "allow multiple downloads?" notification; user didn't respond in time; only first file saved  
**Root cause:** Chrome (65+) blocks multiple downloads from same origin and shows a notification bar. Downloads triggered by `setTimeout` are treated as non-user-gesture and queued behind permission. With 800ms/1600ms delays, the notification appeared and timed out before user could respond.  
**Fix:** Delays increased to 1500ms/3000ms to give user time to respond to Chrome permission prompt. One-time "Allow" in Chrome permanently allows multiple downloads from `127.0.0.1`.  
**Note:** Not fully fixable without changing UX (e.g., show 3 download buttons instead). Current approach requires user to click Allow once.

---

## E10 — Persian text rendered mirrored / reversed in Word

**ID:** E10
**Status:** Fixed 2026-05-08 (Phase 1, review-rewrite-opus-4.7)
**Symptom:** Some FA cells in `_PER_Double.docx` / `_PER_Classic.docx` displayed glyphs in the wrong order or "mirrored" left-to-right when opened in Word.
**Root cause:** `aligner_per.py::_set_fa_cell` rebuilt cell content with `python-docx` runs but never copied the paragraph-level `<w:bidi/>` and run-level `<w:rtl/>` markers. When the source DOCX template did not carry these on every cell, the new text inherited LTR direction.
**Fix:** Added `_ensure_rtl_paragraph(p)` and `_ensure_rtl_run(run)` helpers (idempotent) and called them at the end of `_set_fa_cell`. Both insert the OOXML element only when missing.
**Regression test:** open output DOCX → every FA cell paragraph must contain `<w:pPr><w:bidi/></w:pPr>` and the run must contain `<w:rPr><w:rtl/></w:rPr>`.

---

## E11 — English residue rows after polish

**ID:** E11
**Status:** Fixed 2026-05-08 (Phase 1, review-rewrite-opus-4.7)
**Symptom:** Random rows in the polished FA output contained English text (the source verbatim) instead of Persian.
**Root cause:** Two paths produced this. (1) Translator's `SL_TEXT` fallback for unparseable lines — sometimes triggered too eagerly. (2) Polisher Strategy 4 raw passthrough — when no `⟨⟨N⟩⟩` tags were found and the line count happened to match, raw English content propagated unchanged.
**Fix:** Added `OpenAIPolisher._detect_en_residue(text)` (>40 % latin chars AND >5 words) and applied it after `_parse_output`. Flagged lines fall back to the pre-polish translator output for that index. Indices and replaced texts are recorded in `last_call_data["en_residue"]` so they appear in the run's JSON log.
**Regression test:** check `last_call_data["en_residue"]` is empty for clean documents; for documents that previously regressed, count should drop to ~0.

---

## E12 — Server-side DOCX upload validation missing

**ID:** E12
**Status:** Fixed 2026-05-08 (Phase 1, review-rewrite-opus-4.7)
**Symptom:** Server accepted any payload as `.docx`. Client-side magic-bytes check in `index.ejs` could be bypassed by sending a raw POST. No defense against zip-bomb DOCX uploads.
**Root cause:** `local_launcher.py::do_POST` wrote `payload` directly to disk without inspecting it.
**Fix:** Added `_validate_docx_payload(payload)` — (1) magic bytes must equal `PK\x03\x04` (ZIP local file header) and (2) sum of `ZipInfo.file_size` across entries must stay under `_MAX_DOCX_UNCOMPRESSED = 50 MB`. Called before `upload_path.write_bytes`.
**Regression test:** POST a non-ZIP payload → 400 + `"missing ZIP header"`. POST a 1 KB zip whose entries decompress to >50 MB → 400 + `"uncompressed size exceeds"`.

---

## Template for new entries

```
## E{N} — Short title

**ID:** E{N}
**Status:** Fixed {date} / Active
**Symptom:** What the user/developer observed
**Root cause:** One sentence — WHY it happened
**Fix:** What was changed and where (file + line if possible)
**Regression test:** (optional) How to confirm it won't regress
```
