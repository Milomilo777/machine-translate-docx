# Phase F1 BLOCKED — RuntimeContext threading

> Branch: `refactor/architecture`
> Status: F1 aborted before per-function threading began.
> Phases 0–E (commits eb99d20 → 1de5319) remain green and untouched.

## Why F1 was aborted

Reconnaissance over `src/machine-translate-docx.py` (read end-to-end via
the `Explore` agent, see commit notes and conversation history) produced
this catalogue:

| Concern | Count |
|---------|-------|
| Functions containing `global` declarations | 35 |
| Distinct global names referenced | 80+ |
| Total `global` statements | 100+ |
| Module-level setup statements (computed from `args` + JSON config) | 500+ |
| Cross-function call sites that propagate state through the dispatcher | 30+ |

Per-function conversion is mechanical (add `ctx: RuntimeContext`, drop
`global X`, rename `X` → `ctx.<sub>.X`, propagate `ctx` to call sites),
but each surgical edit must be exact. The identifier `driver` collides
with local variables inside several engine functions. The 21+ DOCX
parallel arrays in `read_and_parse_docx_document` share the `+1`
indexing convention (R16) where a single off-by-one silently corrupts
every output DOCX. The DeepL phrasesblock → singlephrase fallback (R15)
at lines 6034–6042 of the entry script:

```python
if translation_succeded == False and translation_engine == 'deepl' and engine_method == 'phrasesblock':
    engine_method = 'singlephrase'
    set_translation_function()
    try:
        driver.close()
        driver.quit()
    except:
        pass
    create_webdriver()
```

… must keep working **byte-equivalent** through `ctx.engine.method`,
`set_translation_function(ctx)`, `ctx.browser.driver.quit()`, and
`create_webdriver(ctx)`. None of these subsystems can be exercised
without a live Chrome driver, a real DeepL session, and a real DOCX
input — the agent has none of those.

The work-order text is unambiguous on this risk profile:

> F1 (RuntimeContext threading): Reduction NOT permitted. Either you
> complete it or you ABORT — partial threading that breaks active paths
> is worse than scaffold-only.

and

> If R15 cannot be preserved → ABORT.

R15 itself can be preserved mechanically (`ctx.engine.method` is mutable
in the existing dataclass), but the **broader threading** required to
reach the point where R15 is even called is the part that exceeds what
a single autonomous run can verify safely.

## What remains green

Phases 0–E are untouched:

```
1de5319  refactor(phase-E): extract chatgpt_api + registry scaffolding
49013a7  refactor(phase-D): isolate 2 inactive Selenium engines
14b312a  refactor(phase-C): introduce RuntimeContext dataclass — foundation
06e2c75  refactor(phase-B): extract config.py — constants and tables
0061657  refactor(phase-A): remove Yandex + Perplexity-API + dead code
eb99d20  refactor(phase-0): rehab test_aligner_split.py for aligner v2.0
```

Tests: 15 passing.
Entry script: 7,879 → 6,139 lines (−22.1 %).

## Phases F2–F5 also blocked

By the work order's dependency graph:

- **F2** (selenium_utils package) presumes F1's converted function
  bodies (the helpers were supposed to land already-threaded).
- **F3** (`google.py`) and **F4** (`deepl.py`) depend on F1 explicitly:
  the function bodies must already accept `ctx` before they can move
  to engine modules without breaking active paths.
- **F5** (block-loop `runner.py`) depends on F1 + the engine registry
  having ctx-aware callables.

## Recommended next steps for the human reviewer

1. **Live-testing infrastructure first.** Stand up a CI job that can
   exercise the DeepL Selenium path against either a real account or a
   carefully-mocked HTTP layer that replays a recorded DeepL session.
   Without it, every refactor risks silent breakage.

2. **One commit per function.** After (1) lands, F1 should proceed as
   ~35 separate small commits — one per function — each running the
   full integration suite. The branch can be PRed in batches.

3. **Alternative considered: decorator-based ctx injection.** Wrap
   each engine function with a decorator that pulls globals into a
   transient ctx. Lower disruption but adds runtime indirection — not
   recommended over plain threading once (1) is in place.

4. **Hold the line on R16.** When threading the 21+ DOCX parallel
   arrays into `ctx.docx`, add a `__post_init__` invariant on
   `DocxCtx` that asserts every list has the same length (or `0` for
   pre-init) before each pipeline stage.

The runtime backbone is in place (`src/runtime.py`, commit 14b312a)
and the four extracted modules from Phases A–E are independent of F1.
A future agent — or the same one with live-test infrastructure — can
pick this up without restarting from zero.
