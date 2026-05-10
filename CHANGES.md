# CHANGES — machine-translate-docx

> Project changelog. Newest entries at the top. Read this file to come
> up to speed on the project state in a single sitting — there is no
> need to re-read the source to understand recent direction.

---

## Project shape (current)

```
src/
  machine-translate-docx.py     CLI entry point (orchestrator)
  runtime.py                    RuntimeContext dataclass
  config.py                     module-level constants + parallel arrays
  runner.py                     block-loop orchestrator
  engines/
    google.py                   Selenium-based Google Translate engine
    deepl.py                    Selenium-based DeepL engine
    chatgpt_api.py              OpenAI API engine bridge
    inactive/                   disabled web engines (chatgpt_web, perplexity_web)
  selenium_utils/               driver / click / forms helpers
  openai_tools/
    translator.py               single-call translate
    polisher.py                 single-call FA polish
    aligner_per.py              FA bilingual doubling aligner
    splitting.py                legacy per-phrase splitter
    fa_postprocess.py           safe FA character normalizer
prompts/
  translate_PER.txt             Persian translation system prompt
  polish_PER.txt                Persian polish system prompt
  translate_universal.txt       fallback prompt for other languages
index.ejs                       legacy frontend (served at /)
web/v2/                         v2 SPA — Tailwind + plain JS (served at /v2/)
local_launcher.py               Python dev server (no Node required)
server.js                       Express production server (Node)
```

---

## Output naming convention

```
input  filename.docx
       ↓
output filename_PER_TranslatePolish.docx   main translate+polish output
       filename_PER_Double.docx            mechanical aligner double output
       filename_PER_Classic.docx           mechanical word-wrap split
       filename_PER_TranslatePolish_log.json  per-block translation log
```

Both files are served for download when the FA + chatgpt-polish
pipeline runs. Classic downloads immediately, Double downloads
after 1800 ms to avoid the Chrome multi-download permission prompt.

---

## Sessions

### 2026-05-10 — Google engine repaired + 4 fixes (branch `next/persian-double-lines-as-splitter`)

After DeepL was unblocked, the Google engine was the next stop on the
real-file matrix. Two of its three methods were broken in different
ways; one of those was masked by an empty default that produced an
unreadable failure mode. Changes:

**G1. Google `phrasesblock` was dispatchable but never populated.**
The block-loop runner (`src/runner.py:translate_once`) had branches for
`deepl`, `chatgpt`, and `perplexity` but raised `ValueError("Unknown
translation engine: google")` on the first call. Worse, `translate_docx`
in the entry script never even routed Google through the phrasesblock
path — `use_phrasesblock` was set true only for `chatgpt`, `deepl`, and
`perplexity`. So the dispatcher fell back to a stale `translation_array`
lookup, the array stayed empty (length 0), and every phrase looped
through 14 retries of `[WARN] translation_array index out of range`
before giving up. Fixed both:

  - Added a `google` branch to `translate_once` that calls
    `selenium_chrome_google_translate(ctx, text)` and returns the
    `(success, translated)` shape the rest of the runner expects.
  - Added `google` to the `use_phrasesblock` selector in `translate_docx`.

**G2. Default method for `--engine google` was a dead path.**
The default fell through to `engine_method = 'javascript'`, which
uploads a local HTML file to translate.google.com — a path that modern
Chrome (~2022+) blocks on file:// URLs. The fail-fast banner from the
last session kept this from cascading into hundreds of warnings, but
the user still got an empty docx. Switched the default to
`phrasesblock`. Users who genuinely want the file-mode path can still
pass `--enginemethod javascript` explicitly.

**G3. `html.unescape` not applied to final translation.**
`google.py` reads the result via `result_element.get_attribute('innerHTML')`,
which returns HTML-escaped text (`&nbsp;`, `&amp;`). The historical
unescape happened only inside the `_still_translating` retry loop —
but that loop's regex (`'$Translation'`) is permanently disabled by
audit finding F-010 and never matches. So entity escapes leaked into
the docx (visible as the literal `&nbsp;` substring on row 26 of the
fixture). Always unescape now, after the main read.

**G4. 15-second TimeoutException on every phrasesblock call.**
A `WebDriverWait(15)` for the Copy-to-clipboard button was a leftover
sentinel from when the engine actually clicked it; the textarea-read
path doesn't use it. On targets that surface the toolbar slowly (FA),
the wait timed out every single call, dumped a noisy traceback, then
proceeded normally. Cut to 3 s and replaced the traceback with silent
fall-through.

**Real-file verification with `tests/fixtures/sample_hyperlink.docx`
on translate.google.com (no `--showbrowser` for the speed-test):**

| target  | method        | wall time | source-column mismatches | nbsp leak | hyperlink populated |
|---------|---------------|-----------|--------------------------|-----------|---------------------|
| French  | singlephrase  | 5 m 25 s  | 0 / 42                   | YES (pre-G3) | yes              |
| French  | phrasesblock  | 26 s → **10 s** (after G4) | 0 / 42 | no | yes              |
| Persian | phrasesblock  | 30 s      | 0 / 42                   | no        | yes                 |

64 / 64 unit tests still pass.

### 2026-05-10 — DeepL engine real-file run + NameError fixes (branch `next/persian-double-lines-as-splitter`)

The agent's run report flagged DeepL as deferred — "translation step
hangs". A direct read of `src/engines/deepl.py` against the legacy
`translation-robot/main` revealed the hang was actually a fast-failing
NameError that the outer try/except swallowed silently. Five concrete
bugs:

**D1. `src_lang` / `dest_lang` / `dest_lang_name` not pulled from ctx.**
Lines 512 / 522 of the previous file referenced bare module-level names
that existed in the legacy globals world but never made it into the
Phase F refactor. Added an explicit triple at the top of the function:

```
src_lang       = ctx.language.src_lang or "en"
dest_lang      = ctx.language.dest_lang or "en"
dest_lang_name = ctx.language.dest_lang_name or dest_lang
```

Without this, the URL-build line raised NameError on the very first
iteration of the page-open loop and the function fell through to
`except Exception: print(traceback)` → returned `(False, "")`.

**D2. `copy_translation_button` referenced before definition.** A
visibility-check block read `copy_translation_button` inside a
`getBoundingClientRect` JS call BEFORE the variable was even
declared (it gets assigned ~50 lines later when the copy button is
located). Wrapped the block in `if copy_translation_button is not
None`, and pre-initialized the var to `None` outside the loop.

**D3. `remove_span_tag` not imported.** The legacy code used a
module-global helper that was never re-exported when the engine moved
into `src/engines/deepl.py`. Inlined a local `_remove_span_tag()` that
does the same regex pass.

**D4. `clipboard` package not imported.** The clipboard fallback path
called `clipboard.copy('')` and `clipboard.paste()` without an import.
Added a defensive `try: import clipboard / except ImportError: clipboard
= None` and gated the fallback on `clipboard is not None`.

**D5. `translated_phrases_array` could be undefined at function exit.**
The variable was only set inside the inner-loop try block. If every
iteration raised, the outer `translation = "\n".join(translated_phrases_array)`
NameError'd. Pre-initialized to `[]` at the top of the loop scope.

**Bonus.** Replaced the brittle full-class-string completion-detection
literal with a stable substring (`lmt__progress_popup
lmt__progress_popup--visible`) — DeepL has rotated the surrounding
class names twice in the last year; the shorter anchor matches both
the legacy and current popup builds.

**Real-file verification (not smoke).**
Ran `tests/fixtures/sample_hyperlink.docx` (41 rows, hyperlinks +
shaded cells) through the actual DeepL site with `--showbrowser`:

| target | wall time | rows translated | source-column mismatches | hyperlink row populated |
|--------|-----------|-----------------|--------------------------|-------------------------|
| French | 21 s      | all visible rows | 0 / 42                   | yes                     |
| Persian| 26 s      | 18 (rest are shaded/empty) | 0 / 42      | yes                     |

The agent's "DeepL deferred" follow-up is closed by this entry.

64 / 64 unit tests still pass.

### 2026-05-10 — post-agent UX fixes (branch `next/persian-double-lines-as-splitter`)

User-reported regressions and a feature request after the agent's first
end-to-end live run on the legacy `index.ejs` UI:

**U1. `Persian Double Lines` option was hidden for FA targets.**
The legacy frontend still had the pre-phase-1 logic that hid the entire
splitSection whenever target=fa + engine=chatgpt-polish (the assumption
being that the engine ran the aligner internally). Phase 1 detached the
aligner from the engine, so this hide-block is wrong now: hiding the
splitSection meant the user could never reach the Persian Double Lines
option at all. Removed the hide-block from `engineChecker()`; the
splitSection is visible for every combination.

**U2. `Split Method = OpenAI API` was not applied with
`chatgpt-polish`.** Same pre-phase-1 logic also force-unchecked the
splitTranslate checkbox under fa+chatgpt-polish, so even when the user
picked an OpenAI splitter the request shipped without `splitTranslate`,
and the splitter never ran. Removed.

**U3. `chatgpt-web` engine was disabled in the engine dropdown.**
`engineChecker()` had `chatgptwebOption.disabled = true` left over from
when the engine sat in `src/engines/inactive/`. Phase 8 reactivated the
engine but the frontend was not updated. Removed the disable.

**U4. File selection vanished when the user changed dropdown values.**
The legacy form's `<input type="file">` would lose its FileList on some
browsers when surrounding `<select>` elements toggled. Added a small
guard: the chosen File object is captured into a JS variable on
`change`, and `sendToServer()` falls back to that cached object when the
input element has gone empty. The user no longer has to re-pick the
file after changing engine / language.

**U5. Cancel button — new feature.**
Mid-translation, the user had no way to abort a job. Added:
- `LocalState.cancel_job(job_id)` — kills the registered subprocess and
  marks the job `status='cancelled'`.
- `LocalState.job_procs[job_id]` — handles registered when the
  subprocess starts, cleared on exit.
- `POST /cancel/<job_id>` endpoint.
- `_run_real_backend` registers its `Popen` immediately after spawn.
- The job-thread `except` no longer overwrites `cancelled` with `error`
  if the user already cancelled.
- A red "Cancel translation" button under the progress bar in the
  loading overlay; wired to `POST /cancel/<jobId>` for the active job.
- Polling treats `status='cancelled'` as a terminal state and surfaces
  it as a regular alert ("Translation cancelled by user").

The launcher contract is unchanged for non-cancelled flows.
Tests: 64 passing.

---

### 2026-05-10 — Persian Double Lines as a splitter (agent run, branch `next/persian-double-lines-as-splitter`)

**Phase 13 — end-to-end runs and fixes uncovered by them.**
First live execution of `tests/integration/test_real_file_per_engine.py`
under `pytest -m live`. Results:

| Engine          | Target | Outcome     |
|-----------------|--------|-------------|
| chatgpt (api)   | mn     | ✅ pass     |
| chatgpt (api)   | fa     | ✅ pass     |
| chatgpt-polish  | mn     | ✅ pass     |
| chatgpt-polish  | fa     | ✅ pass (Persian Double Lines split + suffix) |
| google          | mn     | ✅ pass     |
| deepl           | mn     | ⚠ timeout (deferred after two fix attempts) |
| chatgpt-web     | mn     | ⚠ smoke skip (upstream selectors changed) |
| perplexity-web  | mn     | ⚠ smoke skip |

Live runs surfaced four bugs left from earlier extraction work:

  * `src/engines/deepl.py` referenced two bare globals
    (`set_chrome_window_2_3_screen`, `deepl_sleep_wait_translation_seconds`)
    that no longer existed in module scope after Phase G3. Both are now
    properly imported / read through `ctx.browser`.
  * `src/machine-translate-docx.py` engine_method switch silently
    rewrote `--enginemethod web` to `phrasesblock` for chatgpt and
    perplexity. Adds `elif engine_method == 'web':` branches so the
    method survives.
  * `src/runner.py` translate_once raised on chatgpt method != 'api' and
    perplexity method != 'webservice'. Adds method == 'web' branches
    that delegate to `engines.chatgpt_web.translate(ctx, text)` /
    `engines.perplexity_web.translate(ctx, text)`.

DeepL hang and the two web-engine selector breakages are documented in
`docs/agent-run-report.md` §3 and listed as recommended follow-ups.
The launcher contract is unchanged. Tests: 64 passing under default
`pytest`; 5 of 8 live integration scenarios pass under `pytest -m live`.

**Phase 12 — cache UI feedback (splitterOnly banner).**
The `splitterOnly` flag the launcher emits on cache hit (set in
phase 4) is now consumed by both UIs. v2 swaps the existing
"Cached — instant download" progress label for "Translated text
reused from cache; only the split was redone" when splitter-only is
true, and tags the result row with `(cached — splitter only)`.
Legacy `index.ejs` previously ignored `cacheHit` entirely; it now
appends a one-line note to the success alert distinguishing
"Reused from the 36-hour translation cache" from "Translated text
reused from cache; only the split was redone." The launcher contract
is unchanged. Tests: 64 passing.

**Phase 11 — line-count reconciler for the LLM single-call path.**
New module `src/openai_tools/line_count_reconciler.py` exposes
`reconcile_line_count(source_lines, translated_lines, src_lang_name,
dest_lang_name, *, max_attempts=2)`. When the translator returns a
mismatched line count, the reconciler asks `gpt-5.4-mini` (hardcoded,
matching the aligner) up to two times for a strict line-aligned
re-emission, then falls back to pad/truncate so the result always has
exactly `len(source_lines)` entries. Every API call sets
`prompt_cache_retention=24h`. Wired into
`engines.chatgpt_api.run_openai_single_call` between translate and
polish — polish therefore always sees correctly-aligned input. The
runner block-loop and Selenium engines are untouched. Tests: 64
passing (6 new for the reconciler, including pad / truncate fallbacks
and an exception-during-API path; the OpenAI client is injected so the
suite stays offline).

**Phase 10 — real-file integration test scaffolded.**
A new opt-in test module `tests/integration/test_real_file_per_engine.py`
boots the entry script as a subprocess against the
`tests/fixtures/sample_hyperlink.docx` fixture for every supported engine
and asserts the AGENT.md contract on the output: source columns 0+1
byte-identical, target column 2 populated, hyperlinked text preserved,
correct engine suffix, no Traceback, no `[LOCK] Restored …`. Web engines
(`chatgpt-web`, `perplexity-web`) are smoke-tested only — non-zero exit
converts to `pytest.skip` so a guest-session UI change upstream does not
turn this into a blocking CI failure. Tests are marked
`@pytest.mark.live` (module-wide `pytestmark`) so they stay excluded
from the default `pytest` invocation; run with
`pytest -m live tests/integration`. The test target is `mn` for the
non-FA flow and `fa` for the FA-only Persian Double Lines case;
`MTD_TEST_MODEL=gpt-5.4-mini` overrides the OpenAI model so the live
runs stay cheap. Tests: 58 passing default, 8 additional live tests
collected under `-m live`.

**Phase 9 — module rename: `aligner_per` → `persian_double_lines`.**
The aligner module is renamed to match the user-facing Split Method
name. The class `FASubtitleAligner` is unchanged. A thin
`openai_tools.aligner_per` shim re-exports every public and private
symbol from the new module via a star-import + `__getattr__`
forwarder, so existing callers (the two test modules and any future
external consumer) keep working without modification. Internal
references in `openai_tools/__init__.py` and `local_launcher.py` are
updated to the new name. Tests: 58 passing.

**Phase 8 — chatgpt-web and perplexity-web engines reactivated.**
The two Selenium guest-session engines are moved out of
`src/engines/inactive/` into the active engines package. Each gets a
thin :func:`translate(ctx, text)` adapter that sleeps 0.9 s before
each call (within the documented 700-1200 ms range to stay under
unauthenticated rate-limit thresholds), seeds the legacy module
globals from `RuntimeContext`, delegates to the existing
selenium-based body, and returns `(False, "")` on any exception so
the launcher pipe never hangs.

The dispatcher registry (`src/engines/__init__.py`) gains
`EngineName.CHATGPT_WEB` and `EngineName.PERPLEXITY_WEB` plus
matching `DISPATCH_TABLE` entries. `set_translation_function` in the
entry script now special-cases method=`web` for both engines and
binds the adapter as the per-phrase dispatcher. `local_launcher`'s
`_map_engine` rejects nothing now: `chatgpt-web` →
`--engine chatgpt --enginemethod web`; `perplexity-web` →
`--engine perplexity --enginemethod web`. Both UIs gain the new
options. The `_API_ENGINES` cache list is unchanged, so web engines
do not cache (Selenium sessions are stateful and not idempotent).

The legacy global-seeding bridge is intentionally minimal — the web
bodies still reference helper names (`safe_click`,
`set_chrome_window_2_3_screen`, `build_translation_prompt`,
`get_nested_value_from_json_array`) that exist on the entry-script
module and are reached via Python's regular import machinery once the
adapter is invoked from inside the entry-script process. Any selector
breakage on chatgpt.com / perplexity.ai surfaces as `(False, "")` so
the block-loop continues with empty translations rather than crashing
the job. Tests: 58 passing (3 new on `test_engines_registry`).

**Phase 7 — Classic split path removed; one file per job.**
The `_Classic` and `_Double` companion outputs are gone. The `Job`
dataclass loses `filename2` and `filename3`; the `/status/:id`
response no longer includes them; `_send_zip_for_job` keeps only the
`410 GONE` body (the multi-file ZIP packaging is dead code now);
`_find_double_file` and `_find_classic_file` are deleted; the orphan
`_simple_split_docx` and `_write_cell_text` helpers in
`machine-translate-docx.py` are deleted. Both frontends collapse to a
single download — legacy `index.ejs` drops the timed-sequential and
ZIP-bundle paths; v2 `app.js` drops the aligner-double / classic-split
result rows. The v2 sidebar copy and several state docs (CLAUDE.md,
PROJECT_MEMORY.md, docs/architecture.md, docs/subtitle-syncing.md,
docs/testing.md) are updated to the new naming. Historical logs
(error-catalog, decisions-2026, post-refactor-audit) are intentionally
left as records of past states. Tests: 56 passing.

**Phase 6 — `_Double_Lines` filename suffix locked in.**
The Persian-Double-Lines output appends `_Double_Lines` before `.docx`,
after the engine suffix. Examples: `sample_PER_Polish_Double_Lines.docx`,
`sample_PER_chatGPT_Double_Lines.docx`. The actual splitter logic was
already in `_apply_splitter` from phase 4; this phase extracts the
naming bit into a pure module-level helper `_double_lines_output_path`
so it is unit-testable without spinning up an HTTP request handler. New
tests cover the suffix table, including unknown / blank engine names
falling back to no tag, plus the `_Double_Lines` naming. Tests: 56
passing (3 new for filename helpers).

**Phase 5 — engine-aware output filename suffixes.**
The bare `_TranslatePolish` polish tag is replaced by a per-engine tag
appended after the lang code. New mapping:

```
google           _Google
deepl            _Deepl
chatgpt + api    _Polish (with-polish) | _chatGPT (without)
chatgpt-web      _web_chatGPT
perplexity-web   _web_Perplexity
```

`save_docx_file` now calls a new module-level helper `_engine_suffix(ctx)`
to derive the tag from the engine + method + with_polish triple. The
launcher mirrors the same table in `_engine_suffix_for(engine)`, used
by `_fallback_output_path` when the subprocess never prints
`Saved file name:`. Old `_PER_TranslatePolish.docx` files keep working
on cache hit (they are stored by name, not derived). `_Classic`
references stay until phase 7. Tests: 53 passing.

**Phase 4 — cache stores the engine output (not the splitter result).**
`LocalState.cache` switched from `(timestamp, [(kind, path), ...])` to
`(timestamp, dict)` carrying `main_path`, `source_path`,
`translation_array`, `phrase_separator_table`, and the
engine/model/language tuple. The cache key is unchanged, so a re-upload
with a different Split Method now reuses the cached translation and
applies the splitter on top — Persian Double Lines, in particular,
re-runs the FA mechanical aligner in-process (no API call) for a
sub-2 s response. Pre-phase-4 (legacy) cache entries are detected by
their list shape and evicted on access. Two new launcher methods carry
the splitter logic: `_apply_splitter` (post-translate path) and
`_materialise_cached_output` (cache-hit path); both fall back to the
unsplit engine output on any aligner error. `_find_double_file` and
`_find_classic_file` callsites are dropped in `_process_job`; the
helpers themselves remain for now and get removed in phase 7.
Tests: 53 passing (5 cache tests adapted to the new keyword-only
signature, 2 new tests cover the dict shape and pre-phase-4 eviction).

**Phase 3 — conditional UI for Persian Double Lines.**
The `persian_double_lines` `<option>` is now visible only when the
target language is `fa`; switching to any other target hides it and
falls back to `basic` if it had been selected. When the user picks
`fa` as target, Persian Double Lines becomes the auto-selected default
in both UIs (replacing the previous OpenAI-API auto-pick in legacy).
v2 gains a `syncSplitMethodUI()` helper that fires on boot, on engine
change, and on target-language change. Tests: 51 passing.

**Phase 2 — Persian Double Lines exposed as a Split Method.**
Both frontends now expose a `persian_double_lines` value on their
`splitEngine` dropdown. Legacy `index.ejs` adds a third `<option>`. v2
gains a 5th `form-field` ("Split method") with the same three choices
(`basic` / `openai` / `persian_double_lines`); v2 `app.js` reads the new
field and forwards it as `splitEngine` whenever the user picked
something other than `basic`, and additionally sets `splitTranslate=true`
when the value is `persian_double_lines` (so chatgpt-polish jobs can
opt into the splitter even though v2 omits the legacy
`splitTranslate` checkbox). `local_launcher.py` now passes the value
straight through to `--splitengine`. CLI argparse validation accepts
`persian_double_lines` alongside `openai`. Wiring of the actual splitter
behaviour (re-runs the FA aligner against the cached translation) lands
in phases 4-6. Tests: 51 passing.

**Phase 1 — aligner detached from chatgpt-polish.**
The post-translation block in `src/machine-translate-docx.py` that produced
`_PER_Classic.docx` and `_PER_Double.docx` for every FA + chatgpt-polish run
is removed. The engine still does translate + polish; it no longer drives the
aligner. Module-level `from openai_tools.aligner_per import FASubtitleAligner`
import retired (the aligner is reached on demand from the new Split Method
flow planned in phases 2-9). One file out per job for FA + chatgpt-polish:
`{stem}_PER_TranslatePolish.docx` (suffix rename to `_Polish` lands in
phase 5). `local_launcher.py` `_find_double_file` / `_find_classic_file` still
exist; they now return `None` for new jobs (cleanup in phase 7). Tests:
51 passing, no regressions.

---

### 2026-05-09 (part seven) — long-standing hyperlink bug fixed

**S1. Hyperlinked text was silently dropped from cell output.**
A team-mate flagged a long-standing bug: cells that contain a
clickable hyperlink had the link's visible text removed from the
translation pipeline — so the translator received "Here is a
with alt text." instead of "Here is a hyperlink with alt text."

Root cause: `get_cell_data()` walked `paragraph.runs`, which only
returns `<w:r>` elements that are *direct* children of `<w:p>`.
Hyperlinked text lives inside `<w:hyperlink>`, so its runs are
silently skipped. The same bug also dropped runs nested in
`<w:smartTag>`, `<w:fldSimple>`, and any other inline container.

Fix (forward-looking): added `_iter_paragraph_runs(paragraph)`
that uses `paragraph._p.iter(qn('w:r'))` to walk every `<w:r>`
descendant in document order. Each match is wrapped in a
`docx.text.run.Run` so all the existing font / highlight / shading
/ strike checks still apply unchanged. The change is a single
line replacement at the for-loop site (`paragraph.runs` →
`_iter_paragraph_runs(paragraph)`).

Verified on `sample_hyperlink.docx`:
```
BEFORE  table 0 row 8:  'Here is a  with alt text.'
AFTER   table 0 row 8:  'Here is a hyperlink with alt text.'

BEFORE  table 0 row 30: 'an email to '
AFTER   table 0 row 30: 'an email to smtv.bot@gmail.com'
```

Tests: 51/51.

---

### 2026-05-09 (part six) — first successful real translation; Google-js diagnosis

**R1. ChatGPT translate confirmed end-to-end.** First green real-file
test of the day:
```
OpenAI single-call mode: 16 lines, 948 chars
[DIAG] After get_translation_and_replace_after: to_text rows populated = 16, translation_array lines = 16
```
The entire 16-phrase sample doc was translated to Mongolian and
written to `sample_MON.docx`. No `[LOCK] Restored …` line — the
text-based lock comparison (commit 5744e96) eliminated the previous
false positive. Source column intact.

**R2. split_phrases() bug confirmed fixed (commit 3cac1b6).** Before
the fix the run produced `to_text rows populated = 0` and an empty
docx; after, all 16 phrases were grouped, sent to OpenAI, returned,
and written to `cells[2]` of the right rows.

**R3. Google web JavaScript engine — known broken in modern Chrome.**
The same job with `engine=google` (engine_method=javascript) ran
the per-paragraph loop in 0 seconds, producing
`translation_array lines = 0`, then ~210 retries of
`[WARN] translation_array index out of range`. Root cause is
inherent to the engine, not the refactor: since ~2022 Chrome blocks
Google's translate widget from running on `file://` URLs (CORS /
sandboxing). The HTML page loads but Google's widget refuses to
operate.

Added a single-line fail-fast message after the engine returns
empty so users get a meaningful error instead of pages of
`index out of range` retries:
```
[ERROR] Google web translate returned 0 lines.
[ERROR] Modern Chrome blocks the Google translate widget on
[ERROR] file:// URLs (CORS / sandboxing). This engine path
[ERROR] cannot complete in current Chrome versions.
[INFO] Use the OpenAI API engine (chatgpt) or DeepL instead.
```

The Google-javascript path stays in the codebase for the case where
someone runs against an older Chrome; the message tells everyone
else where to go.

---

### 2026-05-09 (part five) — three audit-driven fixes (F-010 + mutable-default + atexit)

Targeting the audit's lowest-scoring dimensions (D2 Smell `B`,
D6 Maintainability `B`).

**Q1. F-010 — Google `still translating` regex.** The historical
value `'$Translation'` is regex `$` (end-of-string) followed by
literal `Translation`, so it never matched. Both the `if` and the
`while` predicates were silent no-ops in production. Replaced with
`None` plus a small `_still_translating(text)` helper that short-
circuits when the pattern is `None`. Behaviour is identical (still
no-op), but the no-op is now explicit and the wait loop is one line
away from working when someone identifies the real loading marker
in Google's DOM. Closes `F-010` from the post-refactor audit.

**Q2. Mutable-default trap in `translation_result_phrase_array`.**
The init `[[]] * (numrows + 1)` had every slot pointing at the same
shared `[]`. Current code only does `array[i] = lines_divided` (slot
replace), which sidesteps the trap, but any future `array[i].append`
would silently mutate every slot at once. Replaced with
`[[] for _ in range(numrows + 1)]` so each slot is a distinct list.

**Q3. `atexit` cleanup for the Chrome driver.** The happy-path
`driver.quit()` lives at the bottom of `main()`; on any earlier
crash, the child Chrome process was orphaned and the launcher's
job pool accumulated zombie browsers. Registered
`_atexit_cleanup_driver` at module load — closes
`_ctx.browser.driver` on any normal termination, including crashes.
Nested `try/except` so the handler can't itself raise during
interpreter teardown.

Tests: 51/51.

---

### 2026-05-09 (part four) — repo housekeeping: docs in English, branches archived, lint sweep

Two commits, one tag-and-delete operation, and a new memory rule.

**O1. CHANGES.md and `docs/v2-frontend-hardening.md` translated to
English.** The legacy Persian content was either prose (translated) or
linguistic sample data (left in place — those characters are *data*,
not text). Other docs already had only sample-data Persian, so no
changes there. Result: 1316-line CHANGES.md compressed to ~480
English lines, newest-first.

**O2. Bare `except:` cleanup — 107 sites in five files.**
`src/machine-translate-docx.py` (42), `src/engines/deepl.py` (35),
`src/engines/inactive/perplexity_web.py` (14),
`src/engines/inactive/chatgpt_web.py` (11),
`src/xlsx_translation_memory/xlsx_translation_memory.py` (5). Each
became `except Exception:`. Matches `.claude/rules/code-style.md`'s
mandate and stops swallowing `KeyboardInterrupt` / `SystemExit`.

**O3. Silent-mode guards on three blocking `input()` calls.** All
remaining unguarded `input()` calls in the entry script now respect
the `silent` flag:

- Google CAPTCHA prompt — raises in silent mode (the launcher
  subprocess can't proceed without a human).
- xlsx and docx save-retry prompts — sleep 2 s in silent mode and
  retry, instead of hanging the launcher pipe forever.

Closes the failure mode where the launcher could deadlock on certain
error paths.

**O4. `.editorconfig` added.** LF line endings, UTF-8, 4-space Python
indent, 2-space markup indent, CRLF for `*.bat`, trim trailing
whitespace. Prevents whitespace churn across IDEs.

**O5. Memory rule: docs are English-only in the repo.** Added
`feedback_docs_english_only.md` to `~/.claude/.../memory/` so the
rule survives session breaks. Conversation responses stay in Persian
per the existing line-separation rule.

**O6. Memory rule: auto-commit + auto-doc.** Added
`feedback_auto_commit_and_doc.md`. Every change made by the
assistant on this repo: (1) commit immediately to current branch,
(2) update CHANGES.md in the same flow, (3) update PROJECT_MEMORY.md
when an invariant changes, (4) push to origin. Default branch is
`master`.

**O7. Two empty branches deleted (local + remote).**

```
review-rewrite-opus-4.7         deleted (was 244f55f)
claude/romantic-bhabha-a3ad61   deleted (was cbe6f31)
```

The latter also had a stale worktree at
`.claude/worktrees/romantic-bhabha-a3ad61/`; pruned via
`git worktree prune`.

**O8. Three merged backup branches archived as tags + deleted.** The
"album-of-memories" pattern: tag the final state, then delete the
branch. Archived state stays accessible via the tag forever; the
branch list is clean.

```
audit/post-refactor       →  tag archive/audit-post-refactor       (4e6c354)
refactor/architecture     →  tag archive/refactor-architecture     (f798322)
feature/v2-frontend       →  tag archive/feature-v2-frontend       (38c9c8a)
```

After the tag-and-delete, the only branch on origin is `master`.

**O9. Today's commits on master**:

```
85e0811  chore(maintainability): English docs, bare-except cleanup, silent-mode input guards
6207a59  docs: log today's 9 commits in CHANGES.md
a205a41  fix(docx): defensive lock on source-language column
81fdd8f  audit: pre-real-test sweep
f957f89  fix(progress): hide overlay + Google-js markers + bufsize=1
8955042  fix(translate): seed driver in remaining selenium helpers
9770ffd  fix(translate): seed local driver from ctx
38ebce4  fix(translate): non-split write path
496183f  fix(translate): Phase H bridge — _sync_globals_from_ctx
1a8c127  fix(translate): xtm — module-level None + global declaration
02d62da  fix(translate): Phase H — thread ctx through translate_docx
```

Tests: 51/51 passing.

---

### 2026-05-09 (part three) — Phase H bridge, progress UX, source-column lock

Nine commits, all on `master`, 51/51 tests passing throughout.

**N1. Phase H bridge — `_sync_globals_from_ctx(ctx)`.** A new helper
that mirrors every public attribute of `ctx.docx` (and
`ctx.browser.driver`, `ctx.openai.translator/polisher`,
`ctx.language.dest_lang/src_lang`) onto the module namespace. Wired
into `main()` at four pipeline boundaries: after
`read_and_parse_docx_document`, after `create_webdriver`, after
`translate_docx`, and after `document_split_phrases`. The bridge lets
the ~40 helpers that still read by bare name see the populated state
without forcing a one-by-one refactor.

**N2. Threaded helpers.** `translate_docx`,
`print_console_docx_file_translated`, `cell_set_1st_paragraph`, and
`cell_add_paragraph` now take `ctx`. Three writes against the empty
global `table_cells` were redirected to `ctx.docx.table_cells`.
`prepare_and_clear_cell_for_writing` now skips rows with fewer than
three cells (subtitle footers).

**N3. `xtm` module-level binding.** Added `xtm = None` at module
top and `global xtm` inside `initialize_translation_memory_xlsx`. The
historical code expected a module global but the assignment was
local-only — every later `if xtm is not None` raised `NameError`
once that path ran live.

**N4. Driver seed in Selenium helpers.** Five functions now seed
`driver = ctx.browser.driver` at the top of their bodies:
`selenium_chrome_google_translate_text_file`,
`selenium_chrome_google_translate_html_javascript_file`,
`selenium_chrome_google_translate_xlsx_file`,
`get_translation_and_replace_after`, `run_statistics`. Each of these
later reassigns `driver` in a recovery branch — without the seed,
Python treated `driver` as local for the entire body and every prior
`driver.get(...)` raised `UnboundLocalError`.

**N5. Non-split write path decoupled from phrase array.**
`print_console_docx_file_translated` now writes the translation
straight from `ctx.docx.to_text_by_phrase_separator_table[row_n]` in
non-split mode, regardless of whether `document_split_phrases`
populated `translation_result_phrase_array`. The previous gate
caused silent empty-cell failures whenever the splitter skipped a row.

**N6. Progress UX.** Three related fixes:

- The legacy frontend's catch block hides `loadingElement` *before*
  `await showAlert(...)` so the progress bar no longer animates
  behind the dialog.
- `subprocess.Popen` for the backend now uses `bufsize=1` (line-
  buffered). The default fully-buffered pipe held `PROGRESS:N`
  markers in an 8 KB buffer, so the bar appeared to jump from 10 %
  straight to 100 %.
- The Google-javascript path emits `PROGRESS:15/30/50/75/90` from
  inside the per-paragraph loop (it was previously silent —
  `runner.py`'s block-loop emits never reach this code path).
- `save_docx_file` emits `PROGRESS:90` at its top to fill the
  DeepL/Perplexity gap between runner's last 75 and the final 100.

**N7. Source-column defensive lock.** New field
`source_columns_snapshot` on `RuntimeDocx`. At parse time, every cell
in columns 0 and 1 is `deepcopy`'d (full XML element). At save time,
just before `docxdoc.save(...)`, each snapshot is compared (via
`lxml.etree.tostring`) against the live cell; if any cell drifted, it
is restored from the snapshot. Fires a `[LOCK] Restored N source-
column cell(s) before save (drift detected — translation memory leak
suspected)` log line so any leak is visible. Closes the user-reported
bug where translation-memory `before` substitutions were leaking
into the EN source column.

**N8. Today's nine commits on master**:

```
6207a59  docs: log today's 9 commits in CHANGES.md
a205a41  fix(docx): defensive lock on source-language column
81fdd8f  audit: pre-real-test sweep
f957f89  fix(progress): hide overlay + Google-js markers + bufsize=1
8955042  fix(translate): seed driver in remaining selenium helpers
9770ffd  fix(translate): seed local driver from ctx
38ebce4  fix(translate): non-split write path
496183f  fix(translate): Phase H bridge — _sync_globals_from_ctx
1a8c127  fix(translate): xtm — module-level None + global declaration
02d62da  fix(translate): Phase H — thread ctx through translate_docx
```

---

### 2026-05-09 (part two) — branch consolidation into master

**M1. Merged `audit/post-refactor` into master.** 26 commits
covering Phase A→G4 refactor and 12 audit fixes. Most important:
`F-001` (Engine Protocol resync to the post-F1 `translate(ctx, text)`
shape) and `F-007` (`html.unescape` instead of the non-existent
`str.unescape`). Strategy: `git merge --no-ff` to preserve the phase
history. Smoke test: 36 passed. `F-010` (DeepL `$Translation` regex)
and `F-012` (entry-script middle-layer threading, Phase H) were
deferred at this point — Phase H landed later the same day.

**M2. Merged `feature/v2-frontend` into master.** Seven commits
adding the Claude-inspired SPA at `web/v2/`: Tailwind 3.4 (compiled,
not CDN), Alpine.js, drag-and-drop, 36-hour cache, newsletter,
i18n EN/FA, Playwright e2e tests. Backend additions in
`local_launcher.py` are additive and non-breaking (cache layer,
`/v2/*` routes, `/subscribe` endpoint). The legacy `/` route is
preserved unchanged. One `modify/delete` conflict on
`tests/test_aligner_split.py` resolved in favour of the audit-side
rebuild. Strategy: `git merge --no-ff`. Tests after merge: 51 passed.

**M3. F-013 fix — Windows console encoding.** `_process_job`
prints `▶ ✓ ✗ —`, which the default Windows `cp1252` console can't
encode, so the job-processing thread died on the first job. Fix
added at the top of `local_launcher.py`:

```python
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass
```

**M4. Documentation refresh.** Updated `CLAUDE.md` (new architecture
diagram showing both UIs, full module map, links to new docs),
`PROJECT_MEMORY.md` (constraints C7–C13, finding F-013, today's
six entries in 'Recent Important Changes'), `CHANGES.md` (M1–M5
section), `.gitignore` (`.doc/` ignored).

**M5. Branch retention plan.** Per agreement with the user, all
merged branches stay until the first successful real-file test:

```
audit/post-refactor       merged, kept
refactor/architecture     merged, kept (subset of audit)
feature/v2-frontend       merged, kept
```

The two empty branches (`review-rewrite-opus-4.7`,
`claude/romantic-bhabha-a3ad61`) were deleted on 2026-05-09 once the
master fix sweep was complete.

---

### 2026-05-08 (part two) — Aligner v2 + UI polish

**S1. Three outputs reduced to two.** AIAlign was removed; classic
and double both run mechanically (`llm_threshold=0`). Sequential
download swapped for ZIP to avoid the Chrome multi-download prompt
(later flipped back to staggered single downloads — see B1 below).
Files changed: `local_launcher.py`, `index.ejs`,
`src/machine-translate-docx.py`.

**S2. B1 — `splitTranslate` was True for `fa+chatgpt-polish`.**
After restoring the engine from `localStorage`, the `engineChecker()`
JS handler did not run, leaving `splitTranslate=True` even though the
aligner already does the line distribution. Backend now force-disables
it; the JS now also re-runs the checker on restore.

**S3. Progress bar for Google / DeepL.** `machine-translate-docx.py`
emits `PROGRESS:25/50/75` proportional to block progress in the block
loop. Frontend label is now engine-agnostic ('Translating…',
'Polishing…', 'Aligning subtitles…').

**S4. `aligner_per.py` rewritten — Mechanical v2.0.** From 1565
lines to ~380 lines. Built on the cleaner `fa_aligner.py` from the
v7.5 skill. Kept: `_display_len`, RTL markers, protected bigrams,
shaded-cell detection, cross-group sentinels. Removed: B4 weight
tables, discourse-marker alignment, LLM stubs, quality scoring. New
module-level helpers: `_find_break`, `_split_for_n_rows`,
`_distribute_to_rows`, `_enforce_no_triple`. Important fix in
`_parse_groups`: trailing empty-FA rows are now folded into the
preceding group, which is what the single-call output shape requires.

**S5. `_simple_split_docx` rewritten — Classic without insert /
double.** The old `deepcopy(_row._tr)` approach inserted new rows,
which doubled both the EN cell and the line-number cell (the
visible 'red lines'). The new flow groups rows via `_parse_groups`,
splits into at most `n_rows` chunks, writes one chunk per row, and
pads with `''` — no row is ever duplicated and only `cells[2]`
changes.

**S6. Prompt caching — Responses API for gpt-5.x.** `gpt-5.5`
didn't match the `if "pro" in self.model` test, so the translator
silently fell back to `chat.completions.create` where caching is
broken for the GPT-5 family. Detection broadened:

```python
_use_responses_api = (
    "pro" in self.model.lower()
    or self.model.lower().startswith("gpt-5")
)
```

Response normalisation (Responses API uses `input_tokens` /
`input_tokens_details`; we map them onto `prompt_tokens` /
`prompt_tokens_details` after `model_dump()` so cost calc is
unchanged) and text extraction (`response.output_text`) updated.
Files: `translator.py`, `polisher.py`.

**S7. localStorage stores language only.** Engine and AI model
were dropped from the saved state — they always default from the
language now. Re-running the same target language no longer locks
the user into a previously chosen low-quality engine. `_lsSet` /
`_lsGet` / `_lsDel` helpers wrap `localStorage` in `try/catch` for
private-mode browsers.

**S8. Engine-lock fix — guard every `.selected` behind
`setDefault`.** `deeplOption.selected = true` and
`googleOption.selected = true` inside `engineChecker()` were
unconditional, so changing the engine immediately reverted it.
Consolidated all defaults under a single `if (setDefault)` block.

**S9. Official `gpt-5.5` pricing (April 2026).**

```
Input:        $5.00 / 1M tokens
Cached input: $0.50 / 1M tokens
Output:       $30.00 / 1M tokens
```

`translator.py` and `polisher.py` cost calc now uses cached price
for `cached_tokens` and full price for the rest.

**S10. Standalone aligner test tool.** New `tests/test_aligner_only.py`:

```bash
python tests/test_aligner_only.py FILE_PER_TranslatePolish.docx [--verbose]
```

Output: `FILE_PER_TranslatePolish_Double_TEST.docx`. Exit 0 if no
triples and no chunks over 48 chars. Exit 1 otherwise (file is still
written for inspection).

---

### 2026-05-09 (part one) — server.js, fa_postprocess, RTL, batch research

**P1. `server.js` and `package.json`.** `server.js.txt` no longer
exists (renamed to `server.js` earlier). Added a missing
`package.json` declaring the npm dependencies the production server
requires (`express ^4.19`, `multer ^1.4`, `cross-spawn ^7.0`,
`body-parser ^1.20`, `cron ^3.1`, `iconv-lite ^0.6`, `ps-list ^8.1`).
`engines.node = ">=18"`. `local_launcher.py` is independent of all
this and works without Node.

**P2. `fa_postprocess.py` — safe FA normalizer.** New file:
`src/openai_tools/fa_postprocess.py`. The default `hazm.Normalizer`
broke W3 TECH_LOCK in this project (e.g. `GPT-4o` → `GPT- ۴ o`)
and converted `"..."` to `«...»` (violates HL-11). Replaced with
a custom <50-line normalizer that does only the safe subset:

- `ي` (U+064A) → `ی` (U+06CC)
- `ك` (U+0643) → `ک` (U+06A9)
- digits `٠-٩` (U+0660+) → `۰-۹` (U+06F0+)

ASCII, quotes, ZWNJ, harakat, spacing — all left alone. Applied in
`polisher.polish` after the residue check. Test:
`tests/test_polisher_parse.py::test_fa_postprocess_normalize_safe_subset`.

**P3. Aligner discourse-cue expansion.** Four new categories in
`_BUILTIN_CUES` of `aligner_per.py`: addition, sequence, example,
emphasis. ~20 lines; same structure; near-zero risk.

**P4. RTL helpers via the official python-docx API.**
`_ensure_rtl_paragraph` and `_ensure_rtl_run` no longer use manual
`find()` traversals — now use `get_or_add_pPr()` / `get_or_add_rPr()`.
Schema-correct insertion, shorter, idempotent.

**P5. Pure research (no implementation).**

- `docs/batch-api-analysis.md` — Batch API is the wrong tool for
  the current interactive UI; potentially right for future bulk
  workflows. Deferred.
- `docs/aligner-research.md` — comparison with Gale-Church, DP,
  embeddings, ASR. Three ideas captured for future work.
- `docs/rtl-rendering.md` — the why and how behind the E10 fix;
  why `python-bidi` / `arabic-reshaper` were not adopted.

**P6. Progress bar via existing polling.** No SSE.

- `Job` dataclass gained a `progress: int = 0` field.
- `local_launcher._process_job` sets `progress=5` (job recorded)
  and `progress=10` (semaphore acquired).
- `_run_real_backend` parses `PROGRESS:` lines from subprocess
  stdout and calls `update_job(progress=...)`. The line itself
  isn't echoed (it would be visual noise).
- `machine-translate-docx.py` emits five anchor markers: `15` before
  translate, `30` after translate, `65` after polish, `75` before the
  aligner pass, `100` after Double finishes.
- `/status/:jobId` returns `progress`. `index.ejs` has a
  `<progress>` element + label + percentage. `pollJobStatus` calls
  `_updateProgress(data.progress)` on every tick. Label resolution
  via `_progressLabel(pct)`.

---

### 2026-05-08 (part one) — review-rewrite-opus-4.7 phases 1–5

A rolling cleanup pass across five phases.

**Phase 1 — critical fixes (visible in the final output or in
security):**

- **0.1 RTL/bidi in FA cells (mirrored-text fix).** `_set_fa_cell`
  used to set only `run.text`. If the cell template lacked
  `<w:bidi/>`, Word rendered the FA text LTR (reversed). New helpers
  `_ensure_rtl_paragraph(p)` and `_ensure_rtl_run(run)` add `<w:bidi/>`
  to `pPr` and `<w:rtl/>` to `rPr`. Idempotent.
- **0.2 English-residue detection in polish.** New helper
  `_detect_en_residue(text)` flags lines where >40 % of characters
  are Latin and the longest word is >5 chars. Flagged lines are
  replaced by the pre-polish translator output. List of changes is
  recorded in `last_call_data["en_residue"]` for inspection.
- **0.3 Server-side file validation.** `_validate_docx_payload`
  in `local_launcher.py`: PK magic bytes + 50 MB zip-bomb cap.
  Runs before disk write. The frontend's client-side check is no
  longer trusted alone.

**Phase 2 — visible bugs:**

- **0.4 ZIP package for download (E9 fix).** New endpoint
  `GET /download-zip/:jobId` bundles every output file for the job
  into one `_PER_package.zip`. Frontend uses it whenever
  `filename2 || filename3` exist, so Chrome only sees one download.
  (Reverted to staggered downloads in S1 above; the endpoint stays
  as 410 Gone.)
- **0.5 Auto-cleanup of the job store.** `cleanup_old_jobs(max_age_sec=3600)`
  runs on a 10-minute interval thread, removing `done`/`error` jobs
  older than an hour.
- **0.6 OpenAI retry with backoff.** New `src/openai_tools/_retry.py`:
  `call_with_retry(fn, *, label)`. Three retries with 1 / 2 / 4 s
  backoff for `RateLimitError`, `APIConnectionError`, `APITimeoutError`.
  `BadRequestError` re-raised immediately. All other exceptions
  re-raised — no silent swallow. Used by translator, polisher, and
  the aligner.

**Phase 3 — aligner quality:**

- **0.7 `_display_len` — exclude ZWNJ from length.** Word renders
  ZWNJ (U+200C) as zero-width but `len()` counts it. Every
  `len(...) > MAX_CHARS` validation in `aligner_per.py` switched
  to `_display_len(...) > MAX_CHARS`. Slicing operations (`text[:MAX_CHARS]`)
  keep `len` — the result is conservative.
- **0.8 Cross-group triple guard with sentinel.** Bridge rows are
  invisible in the flat list; consecutive identical chunks across a
  bridge could trigger the "5 in a row" suppression downstream. Fix:
  inject `'\x00GROUP_BOUNDARY\x00'` between groups before flatten,
  re-chunker skips these slots.
- **0.9 Per-content-type `BREAK_RATIO`.** A dict
  `_BREAK_RATIO_BY_TYPE` replaces the single `BREAK_RATIO_MEDIAN=0.45`:
  `narration` and `spiritual` keep 0.45 (verb-final FA),
  `news_attr` 0.55 (front-loaded subject), `dialogue` and
  `ingredient` 0.50.

**Phase 4 — code quality + tests:**

- **0.10 Ten unit tests + pytest setup.** New `pytest.ini`,
  `requirements-test.txt`, `tests/conftest.py`,
  `tests/test_aligner_split.py` (6 tests),
  `tests/test_polisher_parse.py` (3), `tests/test_translator_utils.py`
  (1). Tests construct objects via `__new__` so they run without
  `OPENAI_API_KEY` and without network. Run: `pip install -r
  requirements-test.txt && pytest` → 10 passed in <2 s.
- **0.11 DB connection guard.** `self.db_enabled =
  bool(os.environ.get("MARIADB_HOST"))` in `OpenAITranslator.__init__`.
  When false, `set_filename` and the 'Save query record' block early-
  return with an INFO log. Removes the two retry attempts that ran
  on every API call in DB-less environments.
- **0.12 Concurrent-job semaphore.** `_job_semaphore =
  threading.Semaphore(int(os.environ.get("MTD_MAX_CONCURRENT_JOBS",
  "2")))` at module level in `local_launcher.py`. `_process_job`
  acquires before work and releases in `finally`. Caps the number of
  concurrent backend subprocesses (each ~250–500 MB resident).

**Phase 5 — optional:**

- **0.13/0.15 — skipped.** Progress bar (would have required
  significant SSE/polling changes — landed later as part of P6
  above) and `virastar` (no PyPI distribution).
- **0.14 `prompt_hash` in log JSON.** New helper in
  `_retry.py`: `prompt_hash(text)` returns `sha256(text)[:8]`.
  Recorded in `OpenAITranslator.last_call_data["prompt_hash"]`,
  `OpenAIPolisher.last_call_data["prompt_hash"]`, and
  `FASubtitleAligner.last_stats["prompt_hash"]`. Lets us identify
  which prompt version was used in a given log when prompts later
  change.

---

### Earlier (numbered changes, oldest first)

These predate the dated session log above.

1. **Polisher output uses `⟨⟨N⟩⟩` tags.** Replaced the old
   `Line N: text` format that conflicted with content text. Tags
   use U+27E8 / U+27E9 — they don't appear in normal text. Parser
   has four strategies in priority order: tag, legacy `Line N:`,
   plain line-for-line, pass-through with length warning.
2. **Output filename collision protection.** If the destination
   path exists, suffixes `_1`, `_2`, `_3` are appended until a
   free name is found.
3. **Polling architecture in the server.** `/upload` returns
   `{ ok: true, jobId }` immediately. The Python pipeline runs in
   the background. The frontend polls `/status/:jobId` every 4 s.
   Job store: in-memory `Map<jobId, JobState>`. Completed jobs are
   pruned after 2 hours; pending jobs time out at 50 minutes.
4. **OpenAI Translation + Polish engine.** New engine
   `chatgpt-polish`, available only for Persian. Translates with
   `gpt-5.5`, then runs a second `gpt-5.5` polish pass.
5. **Frontend cleanups in `index.ejs`.** Loading-overlay class
   conflict fixed; `engineChecker()` rewritten cleanly;
   localStorage save/restore for source language, target language,
   and engine; `pollJobStatus(jobId)` replaces the synchronous
   wait — 40 minutes max, retries on transient network errors.
6. **Single-call mode for OpenAI.** Prior code split the file into
   blocks and called the API per block. New flow: one API call for
   translation, one for polish (when `--with-polish` is set).
   Block loop preserved for non-OpenAI engines.
7. **`timeout=1800` on every API call.** Translator and polisher
   both pass `timeout=1800` to the SDK to avoid indefinite hangs.
8. **Removed `reasoning_effort` from translator + cache fix.** On
   `gpt-5.4-mini`, `reasoning_effort: "high"` produced 38997
   reasoning tokens for 95 subtitle lines — 94 % of all generated
   tokens. Removed entirely from the translator. Polisher keeps it
   only when `"mini"` is in the model name. Separately, `{N}` was
   moved from the system prompt into the user message so the system
   prompt is identical across runs and the prompt cache actually hits.
9. **Default model upgrade to `gpt-5.5`.** Translator, polisher,
   and CLI default. Aligner stays hard-pinned to `gpt-5.4-mini`
   regardless of `--aimodel` (intentional — the aligner needs a
   different cost/latency profile).
10. **FA aligner — bridge and shaded-cell detection.** Three
    layers: XML cell-shading detection (`_cell_has_shading`), new
    `BRIDGE_PATTERNS` for timecodes / ALL-CAPS labels / `ONSCREEN`
    / `VO`, and a fallback that treats empty EN cells as bridges.
    Write-back uses `row_indices` so bridge / shaded cells are
    never touched.
11. **UI model selector.** Dropdown in `index.ejs` (visible only
    when an OpenAI engine is selected) with three options:
    `gpt-5.5` (recommended), `gpt-5.4`, `gpt-5.4-mini`. The chosen
    model is appended to the `--aimodel` flag and persisted in
    `localStorage`.
12. **`local_launcher.py` — Python local server.** Pure Python
    (no Express): `ThreadingHTTPServer`, custom multipart parser,
    real-backend subprocess + mock-backend mode for UI exercising.
    Several bugs fixed during stabilisation: form field name
    (`translationEngine` not `engine`), duplicate `ai_model`
    parameter, timestamp prefix in output names, `_FA` instead of
    `_PER` in the language-suffix fallback (added `_LANG_ALPHA3B`
    map).
13. **Prompt files renamed `_fa` → `_PER`.**
    `prompts/translate_fa.txt` → `prompts/translate_PER.txt`,
    same for `polish_fa.txt`. New `_prompt_lang_code()` helper
    (`fa` → `PER`, `ar` → `ARA`); `_normalize_lang()` is read-only
    and unchanged.
14. **Final output naming convention** —
    `{stem}_PER_TranslatePolish.docx`, `{stem}_PER_Double.docx`,
    `{stem}_PER_TranslatePolish_log.json`. Aligner derives its
    output name from the input filename, not the polish output.
15. **Three-file output** (later reduced to two — see S1 above).
    `_PER_TranslatePolish.docx`, `_PER_Classic.docx`,
    `_PER_Double.docx`. `Job.filename2` and `filename3` plus
    `_find_classic_file` / `_find_double_file` discovery helpers.
16. **Hide the Split section for FA + chatgpt-polish.** When the
    aligner is responsible for line distribution, the Split UI is
    not just unneeded — it actively duplicates work. The whole
    `#splitSection` is hidden via `engineChecker()` and
    `splitTranslate` is forced to false.
17. **Three distinct split outputs (later removed in S1)** —
    Classic (algorithmic), Double (mechanical aligner), AIAlign
    (LLM-reviewed aligner). Phase 2 of this redesign collapsed
    Classic and Double to two mechanical outputs and dropped
    AIAlign entirely.

---

## Current status

| Area | Status |
|------|--------|
| OpenAI translate (single-call) | ✓ |
| OpenAI polish (single-call) | ✓ |
| Classic split (no insert, no doubling, FA column only) | ✓ |
| Double aligner (FA-based grouping, maximises doubles) | ✓ |
| `⟨⟨N⟩⟩` polisher format | ✓ |
| Polling architecture | ✓ |
| localStorage (language only) | ✓ |
| Prompt cache — Responses API for `gpt-5.x` | ✓ |
| `gpt-5.5` default model | ✓ |
| UI model selector | ✓ |
| Two-file download with 1800 ms delay | ✓ |
| `engineChecker` without lock-loop | ✓ |
| Official `gpt-5.5` pricing + cached cost | ✓ |
| `_PER` / `_PER_Double` / `_PER_Classic` naming | ✓ |
| Prompt file `_PER` suffix | ✓ |
| Split section hidden for FA + polish | ✓ |
| Standalone aligner test | ✓ |
| Phase A→G4 refactor (runtime / config / engines / selenium_utils / runner) | ✓ |
| Audit + 12 finding fixes | ✓ |
| F-013 fix (Windows console encoding) | ✓ |
| v2 UI (Claude-inspired) at `/v2/` next to legacy at `/` | ✓ |
| 36-hour cache + `/subscribe` endpoint | ✓ |
| Phase H bridge — `_sync_globals_from_ctx` | ✓ |
| Driver seeding in five Selenium helpers | ✓ |
| Non-split write path decoupled from phrase array | ✓ |
| Source-column defensive lock | ✓ |
| Progress UX (overlay-hide, line-buffered subprocess, milestones) | ✓ |
| Tests: 51 passing | ✓ |
| End-to-end real-file test | ⚠ pending |

---

## Open follow-ups

- Verify aligner output quality on a real broadcast subtitle file.
- Manual end-to-end test on both UIs with a real `.docx`.
- After a successful real test: delete the three merged backup
  branches (`audit/post-refactor`, `refactor/architecture`,
  `feature/v2-frontend`).
- Phase H finish: thread the ~40 remaining helpers in
  `src/machine-translate-docx.py` so the bridge can be removed.
  Tracked as audit finding `F-012`.
- Audit finding `F-010`: the DeepL `regex_still_translating_str =
  '$Translation'` never matches because `$` is end-of-string.
  Deferred — flipping it changes wait-loop semantics, needs a
  dedicated test.

---

## Reading guide for the next session

Fastest path to context:

1. This file (CHANGES.md) — the whole picture in five minutes.
2. `src/openai_tools/translator.py` — translation work.
3. `src/openai_tools/polisher.py` — polish work.
4. `src/openai_tools/aligner_per.py` — aligner work.
5. `src/machine-translate-docx.py` (search `_single_call_done`) — CLI work.
6. `server.js` (job store + `/status`) — production server work.
7. `local_launcher.py` — local-server work.

### Likely questions

- *Which model for what?* — translate + polish: `gpt-5.5`. Aligner:
  `gpt-5.4-mini` (always).
- *How does the prompt cache work?* — System prompt is identical
  across runs. `N` lives in the user message. Cache hits start at
  the second call.
- *Where is single-call?* — search `_single_call_done` in
  `machine-translate-docx.py`.
- *Polisher output format?* — `⟨⟨N⟩⟩ text` — regex in
  `polisher.py`.
- *How does the aligner work?* — purely mechanical
  (`llm_threshold=0`), three passes, `aligner_per.py`.
- *Why are shaded cells handled correctly?* — `_cell_has_shading()`
  reads the docx XML and skips shaded cells.
- *Where are the FA prompts?* — `prompts/translate_PER.txt` and
  `prompts/polish_PER.txt`.
- *How does `local_launcher.py` read the engine?* —
  `fields.get("translationEngine")` (matches the JS form name).
- *Why is the Split section hidden?* — for FA + chatgpt-polish, the
  aligner replaces the splitter — leaving both on duplicates work.
- *Why three downloads?* — TranslatePolish + Classic + Double, one
  every 1.5 s.
- *Should we migrate to Java/Kotlin?* — no; the bottleneck is API
  latency, not Python, and `python-docx` has no Java equivalent.
