# Testing Guide

---

## 1. Syntax Check (fast, no API)

```bash
python -m py_compile src/machine-translate-docx.py
python -m py_compile src/openai_tools/translator.py
python -m py_compile src/openai_tools/polisher.py
python -m py_compile src/openai_tools/aligner_per.py
python -m py_compile local_launcher.py
```

All must exit 0 with no output.

---

## 2. Mock Server Test (no API calls)

```bash
python local_launcher.py --backend mock --no-browser
# In another terminal or browser: http://127.0.0.1:3000
```

- Upload any `.docx`
- Select any language and engine
- Expected: placeholder DOCX returned within seconds
- No API key required

---

## 3. Real Backend Smoke Test (requires `OPENAI_API_KEY`)

```bash
set OPENAI_API_KEY=sk-...
python local_launcher.py
```

Open browser → `http://127.0.0.1:3000`

**Test matrix:**

| Engine | Target | Expected outputs |
|--------|--------|-----------------|
| `chatgpt-polish` | Persian (fa) | `_PER_TranslatePolish.docx` + `_PER_Double.docx` |
| `google` | German (de) | `_GER_Google.docx` (or similar) |
| `chatgpt` | Arabic (ar) | `_ARA_...docx` |

---

## 4. Aligner Unit Test

```python
# Quick sanity: import and instantiate aligner
from src.openai_tools.aligner_per import FASubtitleAligner
a = FASubtitleAligner(model='gpt-5.4-mini', llm_threshold=10)
print("Aligner OK, threshold:", a.llm_threshold)  # should print 10
```

---

## 5. Two-File Download Test

After a Persian `chatgpt-polish` job:
1. Both `_PER_TranslatePolish.docx` and `_PER_Double.docx` must appear in
   `$TMPDIR/machine_translate_docx_local/uploads/`
2. Browser must initiate two downloads (second with 800 ms delay)
3. Alert message must list both filenames

---

## 6. Backend Log Checks

Look for these lines in the console output:

```
[job {id}] done -> {stem}_PER_TranslatePolish.docx    ← main output
[job {id}] double file found -> {stem}_PER_Double.docx ← aligner output
Saved file name: /path/to/{stem}_PER_TranslatePolish.docx
[INFO] Aligned file saved: /path/to/{stem}_PER_Double.docx
```

Red flags in logs:
- `cached_tokens: 0` on every call → `prompt_cache_retention` not applied
- `404` on model name → wrong model string (check for underscores vs dots)
- `_FA` in output filename → `_LANG_ALPHA3B` map not applied
- `timestamp-` prefix in final download name → `_strip_timestamp()` not called
