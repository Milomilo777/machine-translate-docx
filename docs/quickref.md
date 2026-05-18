# Quick reference — the whole repo in one page

> If you have 60 seconds, read this. Then go to the right deeper doc.
>
> Updated 2026-05-18.

---

## What this project does

Translate Word (`.docx`) documents — primarily broadcast Persian subtitles for Supreme Master TV — using OpenAI, DeepL, or Google as the translation engine. The Persian pipeline adds a second pass: a mechanical subtitle aligner that produces a bilingual double-line `.docx`.

## Entry points

| Path | What it does |
|---|---|
| `python -m machine_translate_docx.cli` | CLI translator. Also reachable as `mtd` after `pip install -e .` |
| `python local_launcher.py` | Dev server at `http://127.0.0.1:3000/`. Serves 3 frontends, spawns CLI subprocesses for each job |
| `dist/mtd/mtd.exe` | PyInstaller-built standalone Windows binary (~65 MB). Same CLI, no Python/Chrome/MariaDB needed |

## Frontends (all served by `local_launcher.py`)

| URL | UI |
|---|---|
| `/` | Legacy EJS template — `index.ejs` |
| `/v2/` | Plain-JS SPA — `web/v2/index.html` + `web/v2/app.js` |
| `/v2/redesign.html` | Claude-palette preview — single-file drop-in |

## Engines

| Engine | Backend | Default? |
|---|---|---|
| `chatgpt` | OpenAI API (Responses or chat.completions) | **yes** |
| `chatgpt-polish` | chatgpt + a 2nd polish pass | most common for Persian |
| `deepl` | Selenium-driven deepl.com | fallback for non-Persian |
| `google` | Selenium-driven translate.google.com | fallback |

## Models

| Role | Model | Notes |
|---|---|---|
| Translator + polisher (default) | `gpt-5.5` | Set in `config.DEFAULT_AI_MODEL`. Override with `--aimodel` |
| Aligner LLM rescue | `gpt-5.4-mini` | **Hardcoded** — `ALIGNER_MODEL` invariant, do not change |
| Line-count reconciler | `gpt-5.4-mini` | Cheap mini for output-shape fixes |
| Free tier (incentivized) | `gpt-5.4-mini`, `gpt-4.1-mini`, etc. | 10M tokens/day if data-sharing is on. `gpt-5.5` is **not** in the free list |

## Prompts

```
prompts/translate_PER.txt    Persian translation prompt
prompts/polish_PER.txt       Persian polish prompt
prompts/_smtv_locks.txt      Shared SMTV brand lexicon — prepended to both PER prompts at load time
prompts/translate_universal.txt   Fallback for non-Persian targets
```

## Output naming

`{stem}_{LANG}{_engine}{_Double_Lines?}.docx` — e.g. `AJAR 3152_PER_Polish_Double_Lines.docx`. Engine tag is `_Polish` / `_chatGPT` / `_Google` / `_Deepl`. Aligner adds `_Double_Lines`.

Every chatgpt-polish run writes `{stem}_PER_Polish_log.json` alongside the docx (tokens, cost, elapsed). DeepL/Google write a minimal sidecar.

## Critical commands

```bash
# Start the dev server (both UIs)
E:\Python311\python.exe local_launcher.py

# Direct CLI invocation
PYTHONPATH=src E:\Python311\python.exe -m machine_translate_docx.cli \
    --docxfile file.docx --destlang fa --engine chatgpt \
    --enginemethod api --with-polish --silent --exitonsuccess

# Run tests (278 passing, ~10 s)
E:\Python311\python.exe -m pytest tests/ --ignore=tests/test_v2_e2e.py

# Build the standalone .exe
.venv-build/Scripts/python.exe -m PyInstaller packaging/mtd.spec --clean --noconfirm
```

## Tests

- **278 passing** as of 2026-05-18 (random-order seed 42 also clean)
- Live tests (`live` marker) are deselected by default. Run with `pytest -m live` after starting the launcher
- Pure-Python tests run without OpenAI key, network, or Chromium

## Key env vars (top 5)

| Var | Default | What it does |
|---|---|---|
| `OPENAI_API_KEY` | — | Required for chatgpt / chatgpt-polish runs |
| `MTD_MAX_CONCURRENT_JOBS` | `2` | Cap on simultaneous backend subprocesses |
| `MTD_FORCE_NON_STREAM` | unset | Emergency rollback to non-stream Responses API |
| `MTD_POLISH_REASONING` | model default | `none` / `low` / `medium` / `high` / `xhigh` |
| `MTD_DEBUG_PAYLOADS` | unset | Dump full request + response to stdout |

**Full list of 23 env vars + 10 tuning constants:** [`docs/configuration.md`](configuration.md).

## Invariants (the things you can't break)

C1–C39 documented in [`PROJECT_MEMORY.md`](../PROJECT_MEMORY.md). Highlights:

- **C2** — never set `reasoning_effort` on the translator (causes 94 % reasoning-token overhead)
- **C4** — every OpenAI call must include `prompt_cache_retention: "24h"`
- **C13** — source columns 0+1 are byte-identical between input and output docx
- **C37** — `stream=True` is mandatory on every gpt-5.x Responses-API call (issue #2725 hang)
- **C38** — `APITimeoutError` is in `_NON_RETRYABLE` (cost-spiral guard)

## Self-healing surfaces

| Mechanism | Where | What it does |
|---|---|---|
| Retry with jitter | `openai_tools/_retry.py` | 5 attempts on transient errors |
| Stream circuit breaker | `openai_tools/_stream_circuit.py` | Auto-rollback to non-stream after 3 consecutive failures, probe-heal after 1h |
| Line-count reconciler | `openai_tools/line_count_reconciler.py` | gpt-5.4-mini fixes line-count drift, 4 attempts |
| Translation health checks | `translation_health.py` | Pre/post validation; refuse empty source / low-coverage output |
| Failure archive | `local_launcher.py` | `runtime_dir/failures/<id>/` with input + stdout + meta on every error |
| Email + webhook alerts | `local_launcher.py` | `MTD_FAILURE_EMAIL` / `MTD_FAILURE_WEBHOOK` |

## Architecture (one-line)

```
frontend → POST /upload → local_launcher.py spawns subprocess →
  python -m machine_translate_docx.cli →
  cli.py → runner → engines/{chatgpt,deepl,google} →
  (Persian path) openai_tools/{translator → polisher → persian_double_lines aligner} →
  docx_io/save → output .docx + .json sidecar → /download
```

Detailed pipeline: [`docs/architecture.md`](architecture.md). Diagrams: [`docs/diagrams/`](diagrams/) and [`docs/uml.md`](uml.md) (diagrams need refresh after 2026-05-18 stream-hardening + circuit-breaker additions).

## See also

- [`CLAUDE.md`](../CLAUDE.md) — fuller project router (5-min read)
- [`docs/index.md`](index.md) — index of all 40+ docs
- [`docs/configuration.md`](configuration.md) — every env var + tuning constant
- [`PROJECT_MEMORY.md`](../PROJECT_MEMORY.md) — invariants C1–C39 + known issues E1–E16
- [`docs/architecture.md`](architecture.md) — full pipeline + every key path
