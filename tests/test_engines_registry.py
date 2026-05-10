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
    assert EngineName.GOOGLE          == "google"
    assert EngineName.DEEPL           == "deepl"
    assert EngineName.CHATGPT         == "chatgpt"
    assert EngineName.CHATGPT_POLISH  == "chatgpt-polish"
    assert EngineName.CHATGPT_WEB     == "chatgpt-web"
    assert EngineName.PERPLEXITY_WEB  == "perplexity-web"


def test_active_engines_set_complete():
    assert EngineName.GOOGLE          in ACTIVE_ENGINES
    assert EngineName.DEEPL           in ACTIVE_ENGINES
    assert EngineName.CHATGPT         in ACTIVE_ENGINES
    assert EngineName.CHATGPT_POLISH  in ACTIVE_ENGINES
    assert EngineName.CHATGPT_WEB     in ACTIVE_ENGINES
    assert EngineName.PERPLEXITY_WEB  in ACTIVE_ENGINES


def test_dispatch_table_has_google_entry():
    """G2 wired Google in. Subsequent extractions add the rest."""
    assert EngineName.GOOGLE in DISPATCH_TABLE
    assert DISPATCH_TABLE[EngineName.GOOGLE] is google_engine.translate


def test_dispatch_table_has_web_engines():
    """Phase 8 restored chatgpt-web and perplexity-web."""
    from engines import chatgpt_web, perplexity_web
    assert DISPATCH_TABLE[EngineName.CHATGPT_WEB]    is chatgpt_web.translate
    assert DISPATCH_TABLE[EngineName.PERPLEXITY_WEB] is perplexity_web.translate
    # Both adapters take (ctx, text) and return (ok, translation).
    import inspect
    for fn in (chatgpt_web.translate, perplexity_web.translate):
        sig = inspect.signature(fn)
        params = list(sig.parameters)
        assert params[0] == "ctx"
        assert params[1] == "text"


def test_web_engines_marked_active():
    """Phase 8 flipped INACTIVE = False on the restored web modules."""
    from engines import chatgpt_web, perplexity_web
    assert chatgpt_web.INACTIVE    is False
    assert perplexity_web.INACTIVE is False
    # Sleep is in the documented 700-1200 ms range.
    for mod in (chatgpt_web, perplexity_web):
        assert 0.7 <= mod.WEB_SLEEP_BETWEEN_PHRASES_SEC <= 1.2


def test_google_translate_signature():
    """Engine Protocol: translate(ctx, text) -> tuple[bool, str]."""
    import inspect
    sig = inspect.signature(google_engine.translate)
    params = list(sig.parameters)
    assert params[0] == "ctx"
    assert params[1] == "text"
