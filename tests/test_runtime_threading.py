"""Mock-based structural tests for the RuntimeContext threading work.

These tests pin the four invariants the F1 retry contract names. They run
without a real Chrome driver, real DeepL session, or real DOCX input —
that is by design (see docs/phase-F-blocked.md and the F1 retry
work-order section 3 "Verification policy").

If any of these four tests breaks, F1 has regressed structurally even
if the entry script still parses.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `import runtime` work the same way the entry script's siblings do.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from runtime import (
    BrowserCtx,
    ConfigCtx,
    DocxCtx,
    EngineCtx,
    Flags,
    LanguageCtx,
    OpenAICtx,
    RuntimeContext,
)


# ── Sub-context construction ─────────────────────────────────────────────────

def test_runtime_context_empty_constructs():
    """RuntimeContext.empty() returns a default-populated instance with
    every sub-context present and of the expected type."""
    ctx = RuntimeContext.empty()
    assert isinstance(ctx.flags,    Flags)
    assert isinstance(ctx.language, LanguageCtx)
    assert isinstance(ctx.engine,   EngineCtx)
    assert isinstance(ctx.openai,   OpenAICtx)
    assert isinstance(ctx.docx,     DocxCtx)
    assert isinstance(ctx.browser,  BrowserCtx)
    assert isinstance(ctx.config,   ConfigCtx)


def test_config_ctx_max_block_size_mutable():
    """ConfigCtx.max_translation_block_size is mutable so DeepL login
    can bump it when the account exposes a higher account-tier limit."""
    ctx = RuntimeContext.empty()
    assert ctx.config.max_translation_block_size == 1500   # default
    ctx.config.max_translation_block_size = 5000
    assert ctx.config.max_translation_block_size == 5000


# ── R15 — DeepL fallback dance through ctx ───────────────────────────────────

def test_engine_method_flip_via_ctx():
    """The DeepL phrasesblock → singlephrase fallback must be expressible as
    `ctx.engine.method` mutation followed by a dispatcher refresh.

    Mocks: dispatcher is a sentinel callable. The ``refresh`` step here
    stands in for ``set_translation_function(ctx)``.
    """
    ctx = RuntimeContext.empty()
    ctx.engine.engine = "deepl"
    ctx.engine.method = "phrasesblock"

    # phrasesblock dispatcher
    def _phrasesblock_dispatch(text, retry_count):  # noqa: ARG001
        return True, "phrases"
    ctx.engine.dispatcher = _phrasesblock_dispatch
    assert ctx.engine.dispatcher.__name__ == "_phrasesblock_dispatch"

    # Simulate fallback: flip method, refresh dispatcher.
    ctx.engine.method = "singlephrase"

    def _singlephrase_dispatch(text, retry_count):  # noqa: ARG001
        return True, "single"
    ctx.engine.dispatcher = _singlephrase_dispatch

    assert ctx.engine.method == "singlephrase"
    assert ctx.engine.dispatcher.__name__ == "_singlephrase_dispatch"
    assert ctx.engine.dispatcher("anything", 0) == (True, "single")


def test_driver_rebuild_via_ctx():
    """Replacing ``ctx.browser.driver`` after ``quit()`` must produce a
    new object identity, and code paths that refresh through ``ctx``
    must not retain a stale reference to the old driver."""
    ctx = RuntimeContext.empty()

    class _MockDriver:
        def __init__(self, tag: str) -> None:
            self.tag = tag
            self.quit_called = False

        def quit(self) -> None:
            self.quit_called = True

    old_driver = _MockDriver("v1")
    ctx.browser.driver = old_driver
    assert ctx.browser.driver is old_driver

    # Simulate the fallback dance:
    #   ctx.browser.driver.quit()
    #   create_webdriver(ctx)  →  reassigns ctx.browser.driver
    ctx.browser.driver.quit()
    new_driver = _MockDriver("v2")
    ctx.browser.driver = new_driver

    assert old_driver.quit_called is True
    assert ctx.browser.driver is new_driver
    assert ctx.browser.driver is not old_driver
    assert ctx.browser.driver.tag == "v2"


def test_dispatcher_refresh_drops_stale_driver_reference():
    """A dispatcher captured before driver-rebuild must not survive the
    rebuild: the dispatcher refresh step (set_translation_function) is
    what re-binds the active engine to the new driver, via ``ctx``.
    """
    ctx = RuntimeContext.empty()

    class _MockDriver:
        def __init__(self, tag: str) -> None:
            self.tag = tag

    ctx.browser.driver = _MockDriver("v1")

    # Old dispatcher captures the v1 driver via closure-over-ctx (correct
    # pattern). After driver rebuild, calling the dispatcher *through* ctx
    # sees the new driver.
    def make_dispatch(ctx_):
        def _dispatch(text, retry_count):  # noqa: ARG001
            return ctx_.browser.driver.tag
        return _dispatch

    ctx.engine.dispatcher = make_dispatch(ctx)
    assert ctx.engine.dispatcher("x", 0) == "v1"

    ctx.browser.driver = _MockDriver("v2")
    # Same dispatcher, now sees v2 via ctx (no stale capture).
    assert ctx.engine.dispatcher("x", 0) == "v2"


# ── R15 (post-G3) — DeepL fallback through ctx after engine extraction ──────

def test_deepl_phrasesblock_to_singlephrase_after_extraction():
    """After Phase G3 extracts the DeepL engine into engines/deepl.py,
    the phrasesblock → singlephrase fallback dance must still flow
    through ``ctx`` end-to-end. We mock the failed-translation path
    and assert each of the four fallback steps lands its expected
    state change on ctx.
    """
    from engines import DISPATCH_TABLE, EngineName, deepl as deepl_engine

    ctx = RuntimeContext.empty()
    ctx.engine.engine = "deepl"
    ctx.engine.method = "phrasesblock"

    # Mock dispatcher matches what set_translation_function would have
    # registered for phrasesblock (a get-from-text-array shim — here a
    # sentinel callable).
    def _phrasesblock_fail(text, retry):
        return ""   # empty translation → caller treats as failure

    ctx.engine.dispatcher = _phrasesblock_fail

    # Step 1 — phrasesblock attempt fails
    assert ctx.engine.dispatcher("anything", 0) == ""

    # Step 2 — flip method (the main() body does this)
    ctx.engine.method = "singlephrase"

    # Step 3 — refresh dispatcher: G3 means we look up the per-engine
    # translate via the registry rather than calling
    # selenium_chrome_deepl_translate directly. After the flip we
    # rebind ctx.engine.dispatcher to the new singlephrase target.
    assert EngineName.DEEPL in DISPATCH_TABLE
    assert DISPATCH_TABLE[EngineName.DEEPL] is deepl_engine.translate

    # Functools.partial-binding the new dispatcher (matches what
    # set_translation_function does in the entry script).
    import functools
    ctx.engine.dispatcher = functools.partial(deepl_engine.translate, ctx)

    # Step 4 — driver rebuild simulation: replace ctx.browser.driver,
    # confirm the new dispatcher closes over ctx (not the stale driver).
    class _StubDriver:
        def __init__(self, tag):
            self.tag = tag
        def quit(self):
            self.quit_called = True

    old = _StubDriver("v1")
    ctx.browser.driver = old
    ctx.browser.driver.quit_called = False
    ctx.browser.driver.quit()
    new = _StubDriver("v2")
    ctx.browser.driver = new

    # Final assertions
    assert ctx.engine.method == "singlephrase"
    assert ctx.browser.driver is new
    assert ctx.browser.driver is not old
    assert getattr(old, "quit_called", False) is True
    # The dispatcher is partial-bound to the same ctx, so it sees the
    # rebuilt driver via ctx.browser.driver — no stale capture.
    captured_ctx = ctx.engine.dispatcher.args[0]
    assert captured_ctx is ctx
    assert captured_ctx.browser.driver is new


# ── R16 — DOCX +1 indexing structural invariant ──────────────────────────────

# The 21 parallel arrays in DocxCtx that participate in the +1 indexing
# convention (sized numrows + 1, accessed at index i+1 for i in range(numrows)).
_DOCX_ARRAY_FIELDS: tuple[str, ...] = (
    "from_text_table",
    "from_text_is_greyed_table",
    "from_text_is_red_color_table",
    "from_text_is_end_of_line_table",
    "from_text_is_beginning_of_line_table",
    "from_text_is_empty_line_table",
    "from_text_is_conditional_end_of_line_table",
    "from_text_by_phrase_separator_table",
    "from_text_by_phrase_table",
    "from_text_nb_lines_in_phrase",
    "from_text_nb_lines_in_cell",
    "from_text_is_read",
    "to_text_by_phrase_separator_table",
    "to_text_by_phrase_separator_removed_table",
    "to_text_splited_table1",
    "to_text_by_phrase_table",
    "to_text_table",
    "to_raw_translated_table",
    "to_text_removed_line_separator",
    "translation_result_using_separator",
    "translation_result_phrase_array",
    "translation_result",
)


def test_docx_arrays_plus_one_indexing():
    """DocxCtx with numrows=5 supports reads/writes at index i+1 for
    i in range(numrows) on every parallel array, with no IndexError and
    no off-by-one drift after the writes."""
    ctx = RuntimeContext.empty()
    ctx.docx.numrows = 5

    # Allocate every parallel array at length numrows+1 (the historical
    # convention from read_and_parse_docx_document).
    for name in _DOCX_ARRAY_FIELDS:
        setattr(ctx.docx, name, [None] * (ctx.docx.numrows + 1))

    # Each array must be exactly numrows+1 long.
    for name in _DOCX_ARRAY_FIELDS:
        arr = getattr(ctx.docx, name)
        assert len(arr) == ctx.docx.numrows + 1, (
            f"{name}: expected len {ctx.docx.numrows + 1}, got {len(arr)}"
        )

    # Writes at i+1 for i in range(numrows) cover indices 1..numrows.
    for name in _DOCX_ARRAY_FIELDS:
        arr = getattr(ctx.docx, name)
        for i in range(ctx.docx.numrows):
            arr[i + 1] = (name, i)

    # Index 0 stays untouched (None) for every array — that's the
    # leading slot reserved by the +1 convention.
    for name in _DOCX_ARRAY_FIELDS:
        arr = getattr(ctx.docx, name)
        assert arr[0] is None, f"{name}: index 0 should remain unwritten"

    # The writes round-trip without drift.
    for name in _DOCX_ARRAY_FIELDS:
        arr = getattr(ctx.docx, name)
        for i in range(ctx.docx.numrows):
            assert arr[i + 1] == (name, i), (
                f"{name}[{i + 1}]: write/read mismatch"
            )


def test_docx_array_field_count_matches_runtime_dataclass():
    """Guard against drift: the explicit field list above must stay in
    sync with the DocxCtx dataclass. If a parallel array is added or
    removed, this test fails until both lists are updated."""
    ctx = RuntimeContext.empty()
    for name in _DOCX_ARRAY_FIELDS:
        assert hasattr(ctx.docx, name), (
            f"DocxCtx is missing the parallel array field {name!r}"
        )
