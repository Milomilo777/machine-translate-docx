# Testing Guide

---

## 0. Unit Tests (Phase 4, 2026-05-08)

```bash
pip install -r requirements-test.txt
pytest
```

Ten tests live under `tests/`:

| File | Count | What it covers |
|------|-------|---------------|
| `tests/test_aligner_only.py` | 2 | Aligner Mechanical v2.0 deterministic core (post-rewrite) |
| `tests/test_polisher_parse.py` | 3 | `⟨⟨N⟩⟩` tag parser; `Line N:` legacy fallback; `_detect_en_residue` true/false/empty cases |
| `tests/test_translator_utils.py` | 1 | `_normalize_lang` + `_prompt_lang_code` round-trip |
| `tests/test_launcher_endpoints.py` | 15 | `local_launcher.py` cache helpers + `_append_subscriber` validation + idempotency |
| `tests/test_v2_e2e.py` | 4 | Live e2e — boots the launcher, drives Playwright. **Skipped by default** |

Tests construct their objects with `__new__` to bypass `__init__` and never
touch the OpenAI client / DOCX I/O / network — all run in <2 s with no API key.

### Live end-to-end tests (`pytest -m live`)

`tests/test_v2_e2e.py` exercises the v2 frontend against a real
`local_launcher.py` subprocess in mock mode, driven by Playwright + a
headless Chromium. Default `pytest -q` skips them via `addopts =
-m "not live"` in `pytest.ini`.

```bash
pip install playwright
playwright install chromium
pytest -m live -v                  # 4 tests, ~10–30 s wall time
```

Coverage:
1. `/v2/` returns 200 with the expected fallback markers.
2. `/v2/i18n.json` loads with both `en` and `fa` locales at parity.
3. Upload a tiny `.docx` → progress reaches 100 → download link appears
   and serves a valid DOCX (PK ZIP magic).
4. Locale toggle button flips `<html lang>` between `en`/`fa` and `dir`
   between `ltr`/`rtl`.

The Playwright tests wait for `Alpine.$data(document.body).i18n.en.title`
to populate before interacting — this is the only reliable signal that
the async `init()` in `app.js` (which awaits `fetch('/v2/i18n.json')`)
has fully resolved.

---

## 1. Syntax Check (fast, no API)

```bash
python -m py_compile src/machine-translate-docx.py
python -m py_compile src/openai_tools/translator.py
python -m py_compile src/openai_tools/polisher.py
python -m py_compile src/openai_tools/aligner_per.py
python -m py_compile src/openai_tools/_retry.py
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

| Engine | Target | Split Method | Expected output (single file per job) |
|--------|--------|--------------|---------------------------------------|
| `chatgpt-polish` | Persian (fa) | Persian Double Lines | `_PER_Polish_Double_Lines.docx` |
| `chatgpt-polish` | Persian (fa) | basic                | `_PER_Polish.docx` |
| `google`         | German (de)  | basic                | `_GER_Google.docx` |
| `chatgpt`        | Arabic (ar)  | basic                | `_ARA_chatGPT.docx` |

**Split Method default:** Persian Double Lines is auto-selected when target = `fa`; for any other target it is hidden and the dropdown falls back to `basic`.

---

## 4. Aligner Unit Test

```python
# Quick sanity: import and instantiate aligner
from src.openai_tools.aligner_per import FASubtitleAligner
a = FASubtitleAligner(model='gpt-5.4-mini', llm_threshold=10)
print("Aligner OK, threshold:", a.llm_threshold)  # should print 10
```

---

## 5. Single-File Download Test

After any job (one file per job since phase 7):
1. Exactly one docx appears in `$TMPDIR/machine_translate_docx_local/uploads/`
   matching the engine + split table in section 3.
2. Browser initiates a single download — no Chrome multi-download permission prompt.
3. Alert message lists exactly one filename.

---

## 6. Backend Log Checks

Look for these lines in the console output:

```
[job {id}] ▶ start — file: …
[job {id}] running real backend via: …
Saved file name: /path/to/{stem}_PER_Polish.docx
[job {id}] ✓ done in {N}s -> {stem}_PER_Polish_Double_Lines.docx
```

Red flags in logs:
- `cached_tokens: 0` on every call → `prompt_cache_retention` not applied
- `404` on model name → wrong model string (check for underscores vs dots)
- `_FA` in output filename → `_LANG_ALPHA3B` map not applied
- `timestamp-` prefix in final download name → `_strip_timestamp()` not called
- `Splitting phrase` lines appearing → Split section not hidden; user checked splitTranslate manually
- `LLM: N` where N > 0 in Double timer → `llm_threshold` not zero
