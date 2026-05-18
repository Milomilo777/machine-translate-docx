# AGENTS.md — Machine Translate DOCX

Instructions for AI agents (Claude Code, Jules, Codex, etc.) and CI workflows.

This file is the **single entry point** for an agent landing on this
repo without prior context. Read it once; then defer to `CLAUDE.md`
(router) and `PROJECT_MEMORY.md` (the canonical constraint list
`C1–C39`).

---

## Build / Run Commands

```bash
# Install dependencies (Python 3.11+ required)
pip install -r compile/requirements.txt
pip install -r requirements-test.txt

# Start local dev server (serves BOTH UIs — legacy at /, v2 at /v2/)
python local_launcher.py                        # default port 3000, real backend
python local_launcher.py --backend mock         # mock mode (no API calls)
python local_launcher.py --port 3001            # custom port

# Direct CLI translation (post-2026-05-11 src/ layout)
PYTHONPATH=src python -m machine_translate_docx.cli \
    --docxfile <file.docx> \
    --destlang fa \
    --engine chatgpt --enginemethod api --aimodel gpt-5.4-mini \
    --with-polish --silent --exitonsuccess

# After `pip install -e .`, the same CLI is reachable as `mtd ...`
# (entry-point declared in pyproject.toml).
```

## Lint / Static Analysis

```bash
# Syntax check — must exit 0
python -m py_compile src/machine_translate_docx/cli.py
python -m py_compile src/machine_translate_docx/openai_tools/translator.py
python -m py_compile src/machine_translate_docx/openai_tools/polisher.py
python -m py_compile src/machine_translate_docx/openai_tools/persian_double_lines.py
python -m py_compile src/machine_translate_docx/openai_tools/_retry.py
python -m py_compile local_launcher.py

# Unit tests (243 pass; `live` marker deselected by default)
python -m pytest tests/ --ignore=tests/test_v2_e2e.py
```

---

## Done Criteria

A task is complete when:

- [ ] Modified Python files pass `py_compile` (no syntax errors).
- [ ] `pytest tests/ --ignore=tests/test_v2_e2e.py` still reports
      243/243 (or the new baseline if you added tests).
- [ ] Output naming convention respected — engine suffix per
      `docx_io/save.engine_suffix` (`_PER_Polish`, `_PER_chatGPT`,
      `_PER_Google`, `_PER_Deepl`, plus optional `_Double_Lines`).
- [ ] No secrets staged. `.env`, `*secret*`, `*apikey*`,
      `*password*`, `.claude/launch.json`, and
      `src/configuration/configuration.json` (when populated) must
      stay out of commits.
- [ ] `CHANGELOG.md` carries a one-paragraph entry under a dated
      heading (newest at top).
- [ ] `PROJECT_MEMORY.md` updated **only** if architectural
      knowledge changed (a new constraint, a deleted file, a flipped
      decision). Don't add per-PR notes there.
- [ ] If a recurring-bug pattern was hit, append to
      `docs/error-catalog.md`.
- [ ] All commits include `Co-Authored-By: Claude <noreply@anthropic.com>`
      (or the matching Sonnet/Opus identifier) when Claude made the
      change.

---

## Review Checklist

Before marking any coding task done:

1. **Model guard.** Aligner stays `gpt-5.4-mini` (constraint C1).
   Translator + polisher default to `config.DEFAULT_AI_MODEL`
   (`gpt-5.5`). `--aimodel <unknown>` rejected at parse time
   against `config.VALID_AI_MODELS` (C18).
2. **Cache guard.** Every new OpenAI API call passes
   `extra_body={"prompt_cache_retention": "24h"}` (C4).
3. **Reasoning guard.** Never set `reasoning_effort` on the
   translator (caused 94% reasoning-token overhead in testing — C2).
   Polisher uses it only when `"mini"` is in the model name.
4. **Source-column lock.** Columns 0 + 1 of the input docx are
   deepcopy-snapshotted at parse time and restored at save time
   (C13). Do not add code that writes into those columns.
5. **ctx threading (C10).** Every helper added or modified must
   read pipeline state from `ctx.<sub>.<field>` — never by bare
   module-global name in cli.py. The `_sync_globals_from_ctx` mirror
   bridge was deleted 2026-05-17 in Sprint D-C slice 6.
6. **No bare `except:`.** Always `except Exception:` or a more
   specific class (C15).
7. **`input()` respects `silent`.** Any new blocking prompt needs an
   `if not silent:` guard (C16).
8. **Lang code.** New language? Update `_LANG_ALPHA3B` in
   `local_launcher.py`, `_PROMPT_FILE_MAP` in `translator.py`, and
   add the matching `translate_{ISO639_2B}.txt` prompt file.
9. **Collision safety.** New file-output logic must call the
   `_resolve_output_path` collision avoider so existing files get
   `_1`, `_2` suffixes (never silent overwrite).
10. **No TDZ in `index.ejs` JS.** Use `document.getElementById()`
    inside the function rather than capturing outer-scope `const`
    declared later in the file (E2).

---

## Security Reminders

- `src/configuration/configuration.json` may contain DB / DeepL /
  Telegram credentials — never commit if populated. Keep the public
  template in `config.DefaultJsonConfiguration`.
- API keys come exclusively from environment variables
  (`OPENAI_API_KEY`, `DEEPL_API_KEY`,
  `GOOGLE_APPLICATION_CREDENTIALS`). Passed via `os.environ` to the
  subprocess only — never via CLI args (visible in `ps`).
- Telegram bot tokens (`MTD_TELEGRAM_TOKEN`) are masked in launcher
  logs and never echoed back in HTTP responses.
- The launcher strips `HTTP_PROXY` / `HTTPS_PROXY` (and lowercase /
  `ALL_*` / `NO_*` variants) from the subprocess environment before
  spawning the backend.
- Uploaded filenames are sanitised via `_sanitize_filename()` and
  payloads must pass `_validate_docx_payload` (PK header + 50 MB
  zip-bomb cap) before disk write.
- `.claude/` is gitignored — keep it that way.

---

## Repo Workflow Conventions

- **Default branch:** `master`.
- **Commit style:** imperative present tense (`Fix`, `Add`, `Update`,
  `Remove`). Keep the title under 70 chars; long detail goes in the
  body.
- **Branch lifecycle** (C23): test → commit → push → merge to master
  ASAP → tag `archive/<purpose>-<YYYY-MM-DD>` → delete. Never delete
  a branch without first creating the retroactive tag and pushing
  it.
- **Push cadence:** after every meaningful working state. Don't sit
  on local-only commits.
- **No force-push to `master` without explicit user consent.**
- **Co-author:** include the matching trailer when Claude wrote
  meaningful code:
  ```
  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  ```
  (Adjust to the actual model used.)

---

## When to update which doc

| You changed... | Update... |
|---|---|
| Public file map / module layout | `CLAUDE.md` Key Paths table |
| A constraint (or added one) | `PROJECT_MEMORY.md` C1–C39 table |
| The pipeline shape | `docs/architecture.md` |
| A recurring bug pattern | `docs/error-catalog.md` |
| An architectural decision | `docs/decisions-2026.md` |
| User-visible behaviour | `CHANGELOG.md` |
| v2 frontend slot definitions | `web/v2/content.json` (the *only* place) |
| Tests / test infrastructure | `docs/testing.md` |

Anything else is internal — leave docs alone.
