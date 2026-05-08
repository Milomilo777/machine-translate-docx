"""Mock-based tests for the engines package registry."""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from engines import EngineName, ACTIVE_ENGINES, DISPATCH_TABLE
from engines import google as google_engine


def test_engine_name_values_match_cli_strings():
    assert EngineName.GOOGLE         == "google"
    assert EngineName.DEEPL          == "deepl"
    assert EngineName.CHATGPT        == "chatgpt"
    assert EngineName.CHATGPT_POLISH == "chatgpt-polish"


def test_active_engines_set_complete():
    assert EngineName.GOOGLE         in ACTIVE_ENGINES
    assert EngineName.DEEPL          in ACTIVE_ENGINES
    assert EngineName.CHATGPT        in ACTIVE_ENGINES
    assert EngineName.CHATGPT_POLISH in ACTIVE_ENGINES


def test_dispatch_table_has_google_entry():
    """G2 wired Google in. Subsequent extractions add the rest."""
    assert EngineName.GOOGLE in DISPATCH_TABLE
    assert DISPATCH_TABLE[EngineName.GOOGLE] is google_engine.translate


def test_google_translate_signature():
    """Engine Protocol: translate(ctx, text) -> tuple[bool, str]."""
    import inspect
    sig = inspect.signature(google_engine.translate)
    params = list(sig.parameters)
    assert params[0] == "ctx"
    assert params[1] == "text"
