# Playbook: Translate a Batch of Files

---

## Steps

1. **Prepare inputs**
   - Confirm all `.docx` files are well-formed (open in Word first)
   - Count input lines for expected output validation

2. **Start local server**
   ```bash
   set OPENAI_API_KEY=sk-...
   python local_launcher.py
   ```

3. **Upload and translate**
   - Open `http://127.0.0.1:3000`
   - Select target language: Persian (`fa`) → engine auto-selects `chatgpt-polish`
   - Upload file, wait for both downloads

4. **Validate outputs**
   - `_PER_TranslatePolish.docx` — open in Word, spot-check 10 lines
   - `_PER_Double.docx` — verify double-line layout, check for triples (none expected)
   - `_PER_TranslatePolish_log.json` — check `cached_tokens` > 0 (confirms cache hit after first call)

5. **Log failures**
   - Any structural anomaly → add to `docs/error-catalog.md`
   - Any translation quality pattern → note in `docs/translation-style.md`

6. **Check costs**
   - Review token usage in the log JSON
   - If `cached_tokens: 0` throughout, check `prompt_cache_retention` header
