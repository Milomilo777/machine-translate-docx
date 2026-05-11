"""Mock-based tests for the engines package registry.

chatgpt-web and perplexity-web were removed in the 2026-05-10 cleanup
pass — Cloudflare gating made them never-reach-prod. The corresponding
assertions ("web engines marked active", "dispatch table has web
engines") were dropped; this file now asserts they are NOT present so
a future accidental re-introduction is caught.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from machine_translate_docx.engines import EngineName, ACTIVE_ENGINES, DISPATCH_TABLE
from machine_translate_docx.engines import google as google_engine


def test_engine_name_values_match_cli_strings():
    assert EngineName.GOOGLE          == "google"
    assert EngineName.DEEPL           == "deepl"
    assert EngineName.CHATGPT         == "chatgpt"
    assert EngineName.CHATGPT_POLISH  == "chatgpt-polish"


def test_active_engines_set_complete():
    assert EngineName.GOOGLE          in ACTIVE_ENGINES
    assert EngineName.DEEPL           in ACTIVE_ENGINES
    assert EngineName.CHATGPT         in ACTIVE_ENGINES
    assert EngineName.CHATGPT_POLISH  in ACTIVE_ENGINES


def test_dispatch_table_has_google_entry():
    """G2 wired Google in. Subsequent extractions add the rest."""
    assert EngineName.GOOGLE in DISPATCH_TABLE
    assert DISPATCH_TABLE[EngineName.GOOGLE] is google_engine.translate


def test_web_engines_removed():
    """chatgpt-web and perplexity-web were deleted in 2026-05-10.

    The modules and the corresponding ``EngineName`` members are gone.
    A future accidental re-introduction would fail this test.
    """
    # Module imports must fail.
    import importlib
    for mod_name in ("machine_translate_docx.engines.chatgpt_web", "machine_translate_docx.engines.perplexity_web"):
        try:
            importlib.import_module(mod_name)
            assert False, f"{mod_name} should not be importable"
        except ImportError:
            pass

    # The corresponding EngineName members must not exist.
    assert not hasattr(EngineName, "CHATGPT_WEB"),    "CHATGPT_WEB EngineName came back"
    assert not hasattr(EngineName, "PERPLEXITY_WEB"), "PERPLEXITY_WEB EngineName came back"


def test_google_translate_signature():
    """Engine Protocol: translate(ctx, text) -> tuple[bool, str]."""
    import inspect
    sig = inspect.signature(google_engine.translate)
    params = list(sig.parameters)
    assert params[0] == "ctx"
    assert params[1] == "text"
