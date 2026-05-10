# Roadmap — Persian Double Lines as a Splitter

> Version: 2026-05-10
> Branch: `next/persian-double-lines-as-splitter`
> Owner of the human approval: project owner (PR-merger)
> Owner of the implementation: the AI agent

This is the engineering plan. Each phase is a single commit with a
single conceptual change. Tests must pass at every phase boundary.

---

## Goal in one sentence

Decouple the FA aligner from the OpenAI-polish engine, expose it as
a generic `Persian Double Lines` Split Method that pairs with any
engine, rename output suffixes to encode the engine, and produce
exactly one output file per job.

---

## End-to-end shape after the work

```
Engine dropdown:
  Google Translate
  DeepL
  OpenAI API                       (engine = chatgpt)
  OpenAI Translation + Polish      (engine = chatgpt-polish)
  ChatGPT (web)                    (engine = chatgpt-web,    NEW activation)
  Perplexity AI (web)              (engine = perplexity-web, NEW activation)

Split Method dropdown:
  basic with excel file            (default, all languages)
  OpenAI API                       (existing)
  Persian Double Lines             (NEW; default + visible only when target = fa)

Output filename pattern:
  {stem}_{LANG}_{Engine}[_Double_Lines].docx
    LANG    = ISO 639-2/B uppercase  (e.g. PER, MON, ENG)
    Engine  = Google / Deepl / chatGPT / Polish / web_chatGPT / web_Perplexity
    suffix _Double_Lines is appended only when the user selected
            Split Method = Persian Double Lines
  No more _Classic. No more _TranslatePolish (now _Polish).
  No more multi-file output. One job → one file.
```

---

## Phases

Each phase = one commit on the branch. Run pytest before committing.
Update `CHANGES.md` and push after every commit.

### Phase 1 — Detach the aligner from `chatgpt-polish` engine flow

The `aligner_per` call inside the `chatgpt-polish` post-translation
block in `src/machine-translate-docx.py` (the section that currently
runs Classic + Double passes) is removed. The engine still does
translate + polish; it no longer runs the aligner. The aligner code
stays in place — it just isn't invoked from this site any more.

Acceptance:
- A FA + chatgpt-polish job now produces exactly one file:
  `{stem}_PER_Polish.docx` (suffix rename happens in phase 5; for
  this phase it can stay `_PER_TranslatePolish.docx`).
- No `_PER_Classic.docx` or `_PER_Double.docx` in the output dir.

### Phase 2 — Add `Persian Double Lines` as a Split Method

In `index.ejs` and `web/v2/index.html`:

```html
<select id="splitEngine">
  <option value="basic">basic with excel file</option>
  <option value="openai">OpenAI API</option>
  <option value="persian_double_lines">Persian Double Lines</option>
</select>
```

In `local_launcher.py`, the `splitEngine` value flows through to the
backend as `--splitengine`. Map `persian_double_lines` to a new CLI
choice in `argparse`.

Acceptance:
- The dropdown shows the new option in both UIs.
- `--splitengine persian_double_lines` is accepted by the CLI.

### Phase 3 — Conditional UI: Persian Double Lines visible only for FA target

Update `engineChecker()` (or its v2 equivalent) so that when target
≠ `fa`, the `persian_double_lines` option is hidden and, if it was
the active selection, the dropdown auto-falls back to `basic`. When
target becomes `fa`, the option becomes visible and is auto-selected
as the default.

Keep the existing `splitTranslate` checkbox: when unchecked, no
Split Method runs regardless of the dropdown value.

Acceptance:
- Switching target to `fa` makes `Persian Double Lines` visible and
  pre-selected.
- Switching away from `fa` resets split to `basic`.

### Phase 4 — Cache layer rewrite: store translation_array, not docx

`local_launcher.py` `LocalState.cache` currently stores
`(timestamp, [(kind, docx_path), ...])`. Change to:

```python
self.cache[key] = (timestamp, {
    "translation_array": [...],          # list[str]
    "phrase_separator_table": [...],     # list[str]
    "engine": "chatgpt",
    "ai_model": "gpt-5.4-mini",
    "src_lang": "en",
    "dest_lang": "fa",
})
```

Cache key composition stays the same (`sha256(payload + dest_lang +
engine + ai_model)`) — split method is not in the key. On cache hit:
1. Skip the engine call entirely.
2. Run the requested splitter against the cached translation_array.
3. Write the resulting docx with the requested suffix.

This way a user who downloads `_chatGPT.docx` and then re-requests
the same source with `Persian Double Lines` gets the second file
without paying for translation again.

Acceptance:
- Two sequential POST /upload with the same source + engine but
  different splitEngine values: the second one completes in <2 s
  (no engine call).
- Cache eviction on expiry still works.
- Old single-file caches do not crash on read; they get evicted.

### Phase 5 — Rename engine suffixes

```
_TranslatePolish → _Polish
new suffixes:
  _Google           when engine = google
  _Deepl            when engine = deepl
  _chatGPT          when engine = chatgpt
  _Polish           when engine = chatgpt-polish
  _web_chatGPT      when engine = chatgpt-web
  _web_Perplexity   when engine = perplexity-web
```

Implement in `save_docx_file` / `_fallback_output_path`. Remove every
reference to `_Classic` from code and frontend.

Acceptance:
- For each engine, a fresh job produces a file with the right
  suffix.
- No file matches `*_Classic*` after a clean run.

### Phase 6 — Append `_Double_Lines` when split = Persian Double Lines

When `splitTranslate=true` and `splitEngine=persian_double_lines`
and target=fa, append `_Double_Lines` before `.docx`:

```
sample_PER_chatGPT_Double_Lines.docx
sample_PER_Polish_Double_Lines.docx
```

For non-FA or other split methods: no `_Double_Lines` suffix.

Acceptance:
- FA + Persian Double Lines split: filename ends `_Double_Lines.docx`.
- Same source + same engine + split=basic: filename ends with the
  engine suffix only.

### Phase 7 — Remove `_Classic` everywhere

Strip the Classic split helper, its file lookup, the `filename3`
field on the Job dataclass, the corresponding frontend download
trigger, and all docs that mention `_PER_Classic`. The Double
output also collapses to a single file (the engine output, possibly
with `_Double_Lines` suffix).

Acceptance:
- Grep for `_Classic` and `_PER_Classic` in the repo returns 0 hits
  (excluding archived `archive/*` tags).
- `Job` dataclass no longer has `filename3`.

### Phase 8 — Activate `web_chatGPT` and `web_Perplexity`

Move from `src/engines/inactive/` to `src/engines/`. Register in
the dispatcher. Add the engine choices to the legacy + v2 frontends.
Map `chatgpt-web` and `perplexity-web` engine strings in
`local_launcher.py::_map_engine`.

Each web engine should sleep ~700-1200 ms between phrase requests
to avoid being rate-limited. If the previous behaviour can be found
on `origin/main`, restore that exact sleep value.

Acceptance:
- The two engines appear in both UI dropdowns.
- A smoke test boots Chrome, navigates to the engine, and either
  translates a one-sentence input or fails gracefully without
  hanging the launcher pipe.

### Phase 9 — Rename module `aligner_per.py` → `persian_double_lines.py`

Rename the file. Update every import. Keep a thin shim
`aligner_per.py` that re-exports the same names for any external
caller (deprecation comment included). The class name
`FASubtitleAligner` stays — only the module path changes.

Acceptance:
- `from src.openai_tools.persian_double_lines import FASubtitleAligner`
  works.
- All existing tests still pass without modification.
- `aligner_per` import still works (shim).

### Phase 10 — Add fixture and a real-file integration test

Copy `sample_hyperlink.docx` into `tests/fixtures/` (already done
during agent setup; verify it is committed). Add
`tests/integration/test_real_file_per_engine.py` (live-marked, opt-in)
that loops every engine and runs the end-to-end pipeline against
the fixture, verifying the contract from `AGENT.md`.

Acceptance:
- `pytest -m live tests/integration/test_real_file_per_engine.py`
  exists and is runnable; it is excluded from the default `pytest`
  invocation.

### Phase 11 — Line-count reconciler for LLM engines

New module `src/openai_tools/line_count_reconciler.py`. Single
public function:

```python
def reconcile_line_count(
    source_lines: list[str],
    translated_lines: list[str],
    src_lang_name: str,
    dest_lang_name: str,
    *,
    max_attempts: int = 2,
) -> list[str]:
    """Re-emit translated_lines with len == len(source_lines).

    Calls gpt-5.4-mini with both texts and asks for an exact
    line-aligned re-emission. Falls back to padding/truncation on
    final failure.
    """
```

Wire it into `runner.py` block-loop only when:

```python
ctx.engine.engine == "chatgpt" and ctx.engine.method == "api"
```

(i.e. the LLM engines, not Selenium). Trigger only when
`len(translated.split("\n")) != len(source.split("\n"))`. Polish
pass is run after the reconciler.

Acceptance:
- A test docx where the LLM normally returns N+1 lines is now
  written with exactly N lines.
- No regression on docx that already match line-for-line.

### Phase 12 — Cache key + UI feedback

Update the launcher's `cacheHit` JSON payload so the frontend can
distinguish "cache hit, splitter applied" from "cache hit, identical
output". When the user re-requests with a different split method,
display a banner like
`Translated text reused from cache; only the split was redone.`
in both UIs.

Acceptance:
- Two sequential POSTs with same source + different split: the
  second one's response carries `cacheHit: true, splitter_only: true`.
- Frontend banner appears.

### Phase 13 — End-to-end run with all engines

Drive the launcher locally (mock backend off, real backend on) and
upload `sample_hyperlink.docx` against each engine in turn. Capture
stdout, save the output docx alongside the report.

```
en → mn   for non-FA flow
en → fa   for the FA flow with Persian Double Lines split
```

For OpenAI-API-based engines, the test runs against `gpt-5.4-mini`
to keep cost low. The configuration override is via a
`MTD_TEST_MODEL` env var read in `chatgpt_api.py`; default is
unchanged (`gpt-5.5`).

Acceptance:
- All seven combinations run to completion or produce a clear
  failure that is logged in the run report.

### Phase 14 — Compose `docs/agent-run-report.md`

Markdown report covering every phase, every commit hash, every
engine's outcome, every decision the agent made. Sections:

```
1. summary table — engine × outcome × duration × notes
2. files written, with download paths
3. observed bugs and fixes (chronological)
4. open questions / blockers (if any)
5. recommended follow-ups
6. final pytest output
```

This is the human-readable deliverable. The user reads this first
when they come back.

### Phase 15 — Open the PR

`gh pr create --base master --head next/persian-double-lines-as-splitter`
with a body that links to the report and lists the phases. Stop
working after the PR is up. Do not merge it; the user merges.

---

## What to do if you get stuck

1. Write the question into `docs/agent-handoff.md` under
   `## open questions for user`.
2. Park the work on a sub-branch
   `next/persian-double-lines-as-splitter/blocked-{phaseN}`.
3. Continue with later phases that do not depend on the blocker.
4. Mention the blocker in the run report.
