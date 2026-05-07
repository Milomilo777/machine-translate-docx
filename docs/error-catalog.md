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
