# Testing Rules

---

## Before every commit

- [ ] `python -m py_compile` on every modified `.py` file — must exit 0
- [ ] No syntax errors in modified `.js` / `.ejs` sections

## Before marking a task done

- [ ] Mock server test passes (`--backend mock` mode)
- [ ] If API-related change: real backend smoke test with a small `.docx`
- [ ] Console log shows no `404` errors on model names
- [ ] Console log shows no `_FA` suffix in output filename
- [ ] Two-file download works if aligner pipeline is involved

## Regression tests for known bugs

| Bug | Check |
|-----|-------|
| E1 (model name) | `assert 'gpt-5.5' in model` — dot, not underscore |
| E2 (TDZ) | Verify `engineChecker()` uses local `getElementById`, not outer var |
| E3 (timestamp) | Downloaded filename must not start with 13 digits |
| E4 (double file) | Both `.docx` files appear in browser downloads |
| E6 (cache) | `cached_tokens > 0` in log JSON after second call to same document |

## Performance checks

- Translation call duration logged — flag if > 600 s
- `reasoning_tokens` in log — flag if > 50 % of total tokens (indicates `reasoning_effort` leak)
