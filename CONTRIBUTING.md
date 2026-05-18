# Contributing

Short version: pull requests are welcome. Before you open one, please read the
checklist below.

## Development setup

```bash
# Python (3.11+)
pip install -r compile/requirements.txt
pip install -r requirements-test.txt

# Run the unit tests
python -m pytest tests/ --ignore=tests/test_v2_e2e.py

# Start the dev server (Python launcher; no Node required)
python local_launcher.py
# → http://127.0.0.1:3000/      (legacy UI)
# → http://127.0.0.1:3000/v2/   (v2 SPA)
```

The `Makefile` (Unix) and `tasks.bat` (Windows) give matching one-word targets
for the common flows: `make test`, `make smoke`, `make live-deepl`,
`make live-google`. See [`docs/testing.md`](docs/testing.md) for the full
test matrix.

## Before you commit

1. `python -m py_compile <changed_files>` — all changed Python files must
   parse.
2. `python -m pytest tests/ --ignore=tests/test_v2_e2e.py` — all unit tests
   must pass. The current baseline is 243 / 243.
3. If you touched anything in the translation pipeline, also run the smoke
   test: `make smoke` (DeepL en→fr, ~30 s, 0 / 42 source-column mismatches).
4. Update [`CHANGELOG.md`](CHANGELOG.md) with a one-paragraph entry under
   the current dated section.

## Project rules

The project has a small set of hard invariants documented in
[`PROJECT_MEMORY.md`](PROJECT_MEMORY.md) as `C1` through `C39`. The ones
that catch contributors out most often:

- **C1** — the aligner model is always `gpt-5.4-mini`. Do not parameterise
  it away. Centralised in `config.ALIGNER_MODEL`.
- **C4** — every OpenAI call must carry `extra_body={"prompt_cache_retention":
  "24h"}`. The translator / polisher / splitter all do this; new callers
  must too.
- **C13** — the source-language column (columns 0 + 1 of the docx table) is
  frozen. `save_docx_file` restores any drift before writing. Do not touch
  the source side from any engine or helper.
- **C15** — no bare `except:`. Always `except Exception:` (or a more
  specific class).
- **C18** — OpenAI model ids are validated against
  `config.VALID_AI_MODELS` at CLI parse time.

The full list lives in [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md); skim it
before sending a PR that touches the pipeline.

## Code style

[`.claude/rules/code-style.md`](.claude/rules/code-style.md) is the source
of truth. Highlights:

- Python: `snake_case`, type hints on public signatures, private helpers
  prefixed `_`, no bare `except:`, f-strings preferred.
- JavaScript (v2 frontend): `const` / `let` only (never `var`), explicit
  ARIA where applicable, all interactive behaviour wired by
  `addEventListener` (no Alpine, no framework).
- Comments explain *why*, not *what*.

## Reporting bugs

Open an issue with:
- What you did (input file shape, engine, language pair, CLI args).
- What you expected.
- What happened (stdout / stderr, the failure-archive folder if one was
  produced — see [`docs/telegram-alerts-setup.md`](docs/telegram-alerts-setup.md)
  for where those land).
- Output docx + log JSON sidecar if relevant. Strip anything sensitive
  first; the failure-archive is a 1:1 copy of your upload.

## Security

See [`SECURITY.md`](SECURITY.md). In short: please do not file public
issues for vulnerabilities — email the maintainers.
