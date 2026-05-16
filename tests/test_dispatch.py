"""Tests for src/machine_translate_docx/dispatch.py.

Covers the three public symbols:
  - use_phrasesblock   (pure predicate, no I/O)
  - set_translation_function (assigns ctx.engine.dispatcher)
  - set_array_dispatcher (injection seam for the array-lookup callable)

No real Chrome driver, OpenAI key, or DOCX file is required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import machine_translate_docx.dispatch as dispatch_mod
from machine_translate_docx.dispatch import (
    set_array_dispatcher,
    set_translation_function,
    use_phrasesblock,
)
from machine_translate_docx.runtime import RuntimeContext


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_array_dispatcher() -> MagicMock:
    """Return a fresh callable to inject as the array dispatcher."""
    fn = MagicMock(name="array_dispatcher")
    return fn


def _ctx(engine: str, method: str, splitonly: bool = True) -> RuntimeContext:
    """Build a minimal RuntimeContext with the given engine/method pair.

    ``splitonly=True`` suppresses the diagnostic prints inside
    ``set_translation_function`` so test output stays clean.
    """
    ctx = RuntimeContext.empty()
    ctx.engine.engine = engine
    ctx.engine.method = method
    ctx.flags.splitonly = splitonly
    return ctx


# ── use_phrasesblock ─────────────────────────────────────────────────────────

def test_use_phrasesblock_deepl_phrasesblock_returns_true():
    assert use_phrasesblock("deepl", "phrasesblock") is True


def test_use_phrasesblock_google_phrasesblock_returns_true():
    assert use_phrasesblock("google", "phrasesblock") is True


def test_use_phrasesblock_deepl_singlephrase_returns_false():
    assert use_phrasesblock("deepl", "singlephrase") is False


def test_use_phrasesblock_chatgpt_api_returns_true():
    # The docstring inside dispatch.py reads:
    # "API path always uses phrase-block" for chatgpt.
    # Any method value (including 'api') returns True.
    assert use_phrasesblock("chatgpt", "api") is True


def test_use_phrasesblock_unknown_engine_returns_false():
    assert use_phrasesblock("unknown_engine", "phrasesblock") is False


# ── set_array_dispatcher ─────────────────────────────────────────────────────

def test_set_array_dispatcher_replaces_callback():
    """set_array_dispatcher stores the callable in the module-level global."""
    original = dispatch_mod._array_dispatcher
    try:
        fake = _fake_array_dispatcher()
        set_array_dispatcher(fake)
        assert dispatch_mod._array_dispatcher is fake
    finally:
        # Restore so later tests in the run are not affected.
        dispatch_mod._array_dispatcher = original


def test_set_array_dispatcher_accepts_any_callable():
    """A plain lambda is also accepted (not just MagicMock)."""
    original = dispatch_mod._array_dispatcher
    try:
        sentinel = lambda *a, **kw: "result"  # noqa: E731
        set_array_dispatcher(sentinel)
        assert dispatch_mod._array_dispatcher is sentinel
    finally:
        dispatch_mod._array_dispatcher = original


# ── set_translation_function ─────────────────────────────────────────────────

def test_set_translation_function_deepl_phrasesblock_assigns_dispatcher():
    """deepl + phrasesblock → dispatcher is the injected array callable."""
    fake = _fake_array_dispatcher()
    original = dispatch_mod._array_dispatcher
    try:
        set_array_dispatcher(fake)
        ctx = _ctx("deepl", "phrasesblock")
        set_translation_function(ctx)
        assert callable(ctx.engine.dispatcher)
        assert ctx.engine.dispatcher is fake
    finally:
        dispatch_mod._array_dispatcher = original


def test_set_translation_function_deepl_method_flip_changes_dispatcher():
    """deepl phrasesblock → singlephrase flip changes the dispatcher.

    phrasesblock uses the injected array dispatcher.
    singlephrase uses a functools.partial wrapping the DeepL Selenium call.
    The two must be different objects.
    """
    fake = _fake_array_dispatcher()
    original = dispatch_mod._array_dispatcher
    try:
        set_array_dispatcher(fake)

        ctx = _ctx("deepl", "phrasesblock")
        set_translation_function(ctx)
        dispatcher_phrasesblock = ctx.engine.dispatcher

        ctx.engine.method = "singlephrase"
        set_translation_function(ctx)
        dispatcher_singlephrase = ctx.engine.dispatcher

        assert callable(dispatcher_phrasesblock)
        assert callable(dispatcher_singlephrase)
        assert dispatcher_phrasesblock is not dispatcher_singlephrase
    finally:
        dispatch_mod._array_dispatcher = original


def test_set_translation_function_google_singlephrase_assigns_dispatcher():
    """google + singlephrase → dispatcher is a functools.partial (callable)."""
    fake = _fake_array_dispatcher()
    original = dispatch_mod._array_dispatcher
    try:
        set_array_dispatcher(fake)
        ctx = _ctx("google", "singlephrase")
        set_translation_function(ctx)
        assert callable(ctx.engine.dispatcher)
        # singlephrase path must NOT be the array dispatcher
        assert ctx.engine.dispatcher is not fake
    finally:
        dispatch_mod._array_dispatcher = original


def test_set_translation_function_chatgpt_api_assigns_dispatcher():
    """chatgpt + api → dispatcher is the injected array callable."""
    fake = _fake_array_dispatcher()
    original = dispatch_mod._array_dispatcher
    try:
        set_array_dispatcher(fake)
        ctx = _ctx("chatgpt", "api")
        set_translation_function(ctx)
        assert callable(ctx.engine.dispatcher)
        assert ctx.engine.dispatcher is fake
    finally:
        dispatch_mod._array_dispatcher = original


def test_set_translation_function_raises_when_no_array_dispatcher_injected():
    """RuntimeError is raised if the injection seam was never populated."""
    original = dispatch_mod._array_dispatcher
    try:
        dispatch_mod._array_dispatcher = None
        ctx = _ctx("deepl", "phrasesblock")
        raised = False
        try:
            set_translation_function(ctx)
        except RuntimeError:
            raised = True
        assert raised, "Expected RuntimeError when _array_dispatcher is None"
    finally:
        dispatch_mod._array_dispatcher = original
