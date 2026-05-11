<!-- Thanks for sending a pull request!

Please keep the title concise and meaningful (`fix: …`, `feat: …`,
`docs: …`, `refactor: …`, `chore: …` — Conventional Commits style is
preferred but not required). -->

## What this PR does

<!-- One paragraph. What problem does this solve? What's the user-visible
change? Skip implementation details — the diff shows those. -->

## Why

<!-- Link the issue if any (`Closes #123`). Otherwise: a short
justification. "Because we should" is not enough — every change has a
cost, surface a concrete reason. -->

## How (only if non-obvious)

<!-- A short bullet list of the approach. Useful when the diff spans
multiple files or the change reverses a previous decision. Skip if
the diff is straightforward. -->

## Test plan

- [ ] `python -m pytest tests/ --ignore=tests/test_v2_e2e.py` — all
  green (current baseline: 113 / 113).
- [ ] `python -m py_compile <changed_files>` — every changed Python
  file parses.
- [ ] If the change touches the translation pipeline:
  `tasks.bat smoke` (Windows) or `make smoke` (Unix) — DeepL en→fr,
  exit 0, source 42/42 preserved.

## Invariant checklist

The project has a small set of hard invariants documented in
[`PROJECT_MEMORY.md`](../PROJECT_MEMORY.md). Tick the ones that
apply, or note "n/a" if the change is far away from these
concerns:

- [ ] **C1** — Did not change the aligner model away from
      `gpt-5.4-mini`.
- [ ] **C2** — Did not add `reasoning_effort` to the translator.
- [ ] **C4** — Every new OpenAI call carries
      `extra_body={"prompt_cache_retention": "24h"}`.
- [ ] **C7** — Both frontends still work (legacy `/` and v2 `/v2/`).
- [ ] **C13** — Source-language column is not modified by any new
      code path.
- [ ] **C15** — No `bare except:` introduced.
- [ ] **C18** — Any new OpenAI model id was added to
      `config.VALID_AI_MODELS`.

## Changelog entry

- [ ] Added a one-paragraph entry to [`CHANGELOG.md`](../CHANGELOG.md)
      under the current dated session, OR
- [ ] This change is too small to warrant a CHANGELOG entry
      (typo fix, internal-only refactor, doc-only change).

## Screenshots / output (if applicable)

<!-- Drop a screenshot or paste a terminal block when the change is
user-visible. -->
