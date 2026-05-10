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
    # Pre-sleep aligned with legacy parity in the 2026-05-10 timing pass.
    # The legacy translation-robot/main has no inter-call sleep on either
    # web engine — page reload acts as the de-facto throttle. The phase 8
    # 0.9 s defensive guard was unjustified additive cost; now 0.0.
    # Source of truth: ``engines._timing`` constants.
    from engines._timing import CHATGPT_WEB_PRE_SLEEP, PERPLEXITY_WEB_PRE_SLEEP
    assert chatgpt_web.WEB_SLEEP_BETWEEN_PHRASES_SEC    == CHATGPT_WEB_PRE_SLEEP
    assert perplexity_web.WEB_SLEEP_BETWEEN_PHRASES_SEC == PERPLEXITY_WEB_PRE_SLEEP
    assert CHATGPT_WEB_PRE_SLEEP    == 0.0
    assert PERPLEXITY_WEB_PRE_SLEEP == 0.0


def test_google_translate_signature():
    """Engine Protocol: translate(ctx, text) -> tuple[bool, str]."""
    import inspect
    sig = inspect.signature(google_engine.translate)
    params = list(sig.parameters)
    assert params[0] == "ctx"
    assert params[1] == "text"
