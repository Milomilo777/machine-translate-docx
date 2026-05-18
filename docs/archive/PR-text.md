# Pull request — Persian Double Lines as a Split Method

> Phase 15 of `docs/roadmap-persian-double-lines.md`. The `gh` CLI is not
> installed in the agent environment, so the PR is composed here for the
> user to open manually:
>
> ```
> gh pr create \
>   --base master \
>   --head next/persian-double-lines-as-splitter \
>   --title "Persian Double Lines as a Split Method" \
>   --body-file docs/PR-text.md
> ```
>
> Or via the GitHub web UI using the title + body below.

---

## Title

```
Persian Double Lines as a Split Method
```

## Body

## Summary

Decouples the FA aligner from the OpenAI-polish engine and turns it into
a generic `Persian Double Lines` Split Method that pairs with any engine.
Renames output suffixes per engine, activates two previously-inactive web
engines, adds a real-file fixture + live integration suite, and a
line-count reconciler for the LLM single-call path. All 15 phases of
[`docs/roadmap-persian-double-lines.md`](docs/roadmap-persian-double-lines.md)
are complete.

Full results, decisions, observed bugs, and recommended follow-ups are in
[`docs/agent-run-report.md`](docs/agent-run-report.md).

## What changed (top-level)

- **Engine ↔ splitter decoupled.** `chatgpt-polish` no longer drives the
  aligner; the aligner is reachable only via the new Persian Double Lines
  Split Method.
- **One file per job.** `_TranslatePolish` / `_Classic` / `_Double` are
  gone; each job emits one docx, with engine-aware suffixes
  (`_Polish`, `_chatGPT`, `_Google`, `_Deepl`, `_web_chatGPT`,
  `_web_Perplexity`) and an optional `_Double_Lines` tail.
- **Cache rewrite.** `LocalState.cache` switched from a list of file
  paths to a dict carrying the engine's main output, the source upload,
  and the translation arrays — a re-upload with a different splitter
  reuses the cached translation and applies the splitter on top
  (sub-2 s response, no engine call).
- **Web engines reactivated.** `chatgpt-web` and `perplexity-web`
  restored to `src/engines/`, registered in the dispatch table, exposed
  in both UIs. 0.9 s pre-sleep per phrase; graceful `(False, "")`
  fallback on selector breakage.
- **Module rename.** `openai_tools.aligner_per` →
  `openai_tools.persian_double_lines`. A thin shim re-exports every
  symbol so legacy imports keep working.
- **Line-count reconciler.** New
  `openai_tools.line_count_reconciler.reconcile_line_count` asks
  `gpt-5.4-mini` for an exact line-aligned re-emission when the
  translator returns a wrong line count; pads/truncates on final
  failure.
- **Cache UI feedback.** Both UIs surface a `splitterOnly` banner when
  a cache hit reused the translation but applied a fresh Split Method.
- **Two DeepL extraction-time NameError fixes** (Phase G3 leftovers
  surfaced by the new live tests).

## End-to-end matrix

| Engine          | Outcome     |
|-----------------|-------------|
| chatgpt (api)   | ✅ pass     |
| chatgpt-polish  | ✅ pass (basic + Persian Double Lines) |
| google          | ✅ pass     |
| deepl           | ⚠ deferred — translation step hangs (selector / anti-bot follow-up; see report §3) |
| chatgpt-web     | ⚠ deferred — guest-session UI changed upstream |
| perplexity-web  | ⚠ deferred — same |

The DeepL hang and the two web-engine selector breakages are documented
as recommended follow-ups in the run report. Their wiring (CLI passthrough,
runner dispatch, in-process splitter) is in place — only the upstream
selectors need refreshing.

## Test plan

- [x] `pytest tests/ --ignore=tests/test_v2_e2e.py -q` → 64 passed
- [x] `pytest -m live tests/integration -k "chatgpt or google"` → 5 passed
- [ ] DeepL selector audit (follow-up branch)
- [ ] chatgpt-web / perplexity-web selector refresh (follow-up branch)
- [ ] Live integration suite wired into nightly CI (follow-up)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
