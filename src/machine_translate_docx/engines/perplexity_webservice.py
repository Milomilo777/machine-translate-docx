"""Perplexity HTTP-webservice engine.

Forwards translation requests to a local HTTP server (``127.0.0.1:8000``)
that wraps the Perplexity client. The server itself is out of scope for
this codebase — it lives in a sibling deployment.

Extracted from the entry script in C3.1 of the 2026-05-10 architecture
cleanup pass.

Public API
----------

  - ``translate(ctx, text, retry_count) -> (success, translation)``
  - ``selenium_webservice_perplexity_translate(ctx, text, retry_count)``
    (legacy alias used by ``runner.translate_once``)
"""
from __future__ import annotations

import requests

from ..runtime import RuntimeContext


__all__ = [
    "translate",
    "selenium_webservice_perplexity_translate",
]


_WEBSERVICE_URL = "http://127.0.0.1:8000/translate"


def selenium_webservice_perplexity_translate(
    ctx: RuntimeContext,
    to_translate: str,
    retry_count: int,
) -> tuple[bool, str]:
    """HTTP forwarder for Perplexity webservice.

    Reads ``ctx.language.src_lang_name`` and
    ``ctx.language.dest_lang_name`` in place of the historical module
    globals (Phase F1.1 contract). Returns ``(False, "")`` on any
    network or parse failure so the runner can retry or fall back.
    """
    try:
        payload = {
            "src_lang_name":  ctx.language.src_lang_name,
            "dest_lang_name": ctx.language.dest_lang_name,
            "text":           to_translate,
            "engine":         "perplexity",
            "retry_count":    2,
        }
        response = requests.post(_WEBSERVICE_URL, json=payload)
        translation = response.json()["translation"]
        return True, translation
    except Exception:
        return False, ""


# Engine Protocol entry point (translate(ctx, text) -> tuple[bool, str]).
# The webservice path is a single-shot per call; ``retry_count`` is kept
# in the legacy signature for compatibility with the runner's
# block-retry loop.

def translate(ctx: RuntimeContext, text: str) -> tuple[bool, str]:
    return selenium_webservice_perplexity_translate(ctx, text, 0)
