"""Engine dispatch — single source of truth.

Until the 2026-05-10 architecture cleanup, three places had to agree
on which engine/method combination should do what:

  1. ``machine_translate_docx.py:translate_docx``
     decided whether the phrase-block runner runs.
  2. ``machine_translate_docx.py:set_translation_function``
     resolved ``ctx.engine.dispatcher`` for the per-call wrapper.
  3. ``runner.py:translate_once``
     handed off to the actual engine helper.

Three places ⇒ three opportunities for drift. Three real bugs landed
in this codebase from that drift (google routing, perplexity routing,
Google fallback contamination). This module collapses items 1 and 2
into one set of pure functions; ``runner.translate_once`` stays where
it is because the runner owns the recursive split-and-retry algorithm
that consumes the dispatch decision.

Two functions:

  * :func:`use_phrasesblock` — pure predicate. Given the engine and
    method, returns True if the block-loop runner should be used.
    Adding a new engine is one new branch here.
  * :func:`set_translation_function` — resolves
    ``ctx.engine.dispatcher`` for the per-call wrapper. Wires the
    array-lookup path for block-mode and the direct-call path for
    per-phrase mode.

The array-lookup helper currently lives in the entry script
(``selenium_chrome_translate_get_from_text_array``). Inject it via
:func:`set_array_dispatcher` at module load time so dispatch.py
doesn't need to import the entry script (which would form a circular
import — the entry script imports this module).

Future C3 extraction will move the array helper to its own module
and this injection seam can disappear.
"""
from __future__ import annotations

import functools
from typing import Callable, Optional

from runtime import RuntimeContext
from engines.deepl import selenium_chrome_deepl_translate
from engines.google import selenium_chrome_google_translate


__all__ = [
    "use_phrasesblock",
    "set_translation_function",
    "set_array_dispatcher",
]


# Injection point for the array-lookup dispatcher. The entry script
# calls :func:`set_array_dispatcher` once at module load.
_array_dispatcher: Optional[Callable] = None


def set_array_dispatcher(fn: Callable) -> None:
    """Register the array-lookup dispatcher.

    The entry script's ``selenium_chrome_translate_get_from_text_array``
    is bound here; ``set_translation_function`` reads it back. Done
    this way to avoid a circular import.
    """
    global _array_dispatcher
    _array_dispatcher = fn


def use_phrasesblock(translation_engine: str, engine_method: str) -> bool:
    """Return True if the engine + method combination should use the
    phrase-block runner (one engine call per ~max-block-size chars).

    Adding a new engine = one new branch here. Drift between this and
    ``set_translation_function`` is now impossible because there is no
    other place to drift to.

    chatgpt-web and perplexity-web are intentionally absent — both
    were deleted in the 2026-05-10 cleanup pass.
    """
    if translation_engine == "chatgpt":
        # API path always uses phrase-block — the OpenAI translator
        # populates the array up front and the dispatcher does
        # array lookup.
        return True
    if translation_engine == "deepl":
        return engine_method == "phrasesblock"
    if translation_engine == "perplexity":
        # Both the HTTP webservice path and classic phrasesblock use
        # the same block loop.
        return engine_method in ("phrasesblock", "webservice")
    if translation_engine == "google":
        # google-phrasesblock = textarea URL with \n-joined phrases.
        # Other google methods (javascript, textfile, xlsxfile) populate
        # the array up front in their own helpers and never reach the
        # block runner.
        return engine_method == "phrasesblock"
    return False


def set_translation_function(ctx: RuntimeContext) -> None:
    """Resolve the per-call dispatcher for the active engine + method.

    Writes ``ctx.engine.dispatcher``. Reads ``ctx.engine.engine`` /
    ``.method`` and ``ctx.flags.splitonly``.

    R15 contract: this is the function that re-points the dispatcher
    during the DeepL phrasesblock → singlephrase fallback. The
    structural test ``test_engine_method_flip_via_ctx`` pins it.
    """
    if not ctx.flags.splitonly:
        print("\ntranslation_engine=%s" % (ctx.engine.engine))
        print("engine_method=%s" % (ctx.engine.method))
        if ctx.engine.method == "phrasesblock":
            print(
                "maximum number of characters per block: %d"
                % ctx.config.max_translation_block_size
            )

    if _array_dispatcher is None:
        raise RuntimeError(
            "dispatch._array_dispatcher not injected. The entry script "
            "must call dispatch.set_array_dispatcher(fn) before the "
            "first set_translation_function call."
        )

    engine = ctx.engine.engine
    method = ctx.engine.method

    if engine == "deepl":
        if method == "phrasesblock":
            ctx.engine.dispatcher = _array_dispatcher
        else:
            # singlephrase fallback: each phrase is a fresh DeepL call.
            ctx.engine.dispatcher = functools.partial(
                selenium_chrome_deepl_translate, ctx
            )
    elif engine == "chatgpt":
        # API path populates ``translation_array`` up front; dispatcher
        # is just the array lookup. (chatgpt-web removed 2026-05-10.)
        ctx.engine.dispatcher = _array_dispatcher
    else:
        # google / perplexity-webservice paths.
        # (perplexity-web removed 2026-05-10.)
        if method == "textfile":
            ctx.engine.dispatcher = _array_dispatcher
        elif method == "singlephrase":
            ctx.engine.dispatcher = functools.partial(
                selenium_chrome_google_translate, ctx
            )
        else:
            ctx.engine.dispatcher = _array_dispatcher
