# AGENTS.md — Machine Translate DOCX

Instructions for AI agents (Claude Code, Jules, Codex, etc.) and CI workflows.

---

## Build / Run Commands

```bash
# Install dependencies (Python 3.11 required)
pip install -r compile/requirements.txt

# Start local dev server
python local_launcher.py                        # default: port 3000, real backend
python local_launcher.py --backend mock         # mock mode (no API calls)
python local_launcher.py --port 3001            # custom port

# Direct CLI translation
python src/machine-translate-docx.py \
  --input <file.docx> \
  --target-lang fa \
  --engine chatgpt-polish \
  --ai-model gpt-5.5
```

## Lint / Static Analysis

```bash
# If pylint is configured:
pylint src/machine-translate-docx.py src/openai_tools/

# Basic syntax check
python -m py_compile src/machine-translate-docx.py
python -m py_compile src/openai_tools/translator.py
python -m py_compile src/openai_tools/polisher.py
python -m py_compile src/openai_tools/aligner_per.py
python -m py_compile local_launcher.py
```

---

## Done Criteria

A task is complete when:
- [ ] Target file(s) modified correctly — no syntax errors (`py_compile` passes)
- [ ] Output naming convention respected (`_PER_TranslatePolish`, `_PER_Double`)
- [ ] No secrets or `.env` files staged
- [ ] `PROJECT_MEMORY.md` updated if architectural knowledge changed
- [ ] `docs/error-catalog.md` updated if a recurring bug was fixed
- [ ] `docs/decisions-2026.md` updated if an architectural decision was made
- [ ] All changes committed and pushed to `master`

---

## Review Checklist

Before marking any coding task done:

1. **Model guard** — is the aligner still `gpt-5.4-mini`?  
2. **Cache guard** — does every new API call include `extra_body={"prompt_cache_retention": "24h"}`?  
3. **Lang code** — new language added? Update `_LANG_ALPHA3B` in `local_launcher.py` AND `_PROMPT_FILE_MAP` in `translator.py` if a new prompt file exists.  
4. **Collision safety** — does new file output logic handle existing-file collisions?  
5. **Two-file download** — if aligner output path changes, update `_find_double_file()` in `local_launcher.py`.  
6. **No TDZ** — any new JS in `index.ejs` must not reference `const`/`let` variables before declaration (temporal dead zone).

---

## Security Reminders

- `src/configuration/configuration.json` may contain DB credentials — never commit if populated
- API keys come from environment variables only (`OPENAI_API_KEY`, `DEEPL_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`)
- `.claude/` directory is in `.gitignore` — keep it there

---

## Repo Workflow Conventions

- Default branch: `master`
- Commit style: imperative present tense (`Fix`, `Add`, `Update`, `Remove`)
- Always include `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` when Claude made the change
- Push after every meaningful working state
- Do not force-push `master` without explicit user consent
