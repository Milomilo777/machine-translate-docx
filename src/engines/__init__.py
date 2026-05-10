"""Active translation engine registry.

Adding a new engine should be:
  1. One new file in this package (e.g. ``mistral.py``)
  2. One member in :class:`EngineName` and one entry in
     :data:`ACTIVE_ENGINES` and :data:`DISPATCH_TABLE`
  3. Zero changes elsewhere

The dispatch table maps ``EngineName`` to the per-engine
``translate(ctx, text)`` callable. ``set_translation_function`` in the
entry script does not yet read from this table — it still hand-rolls
an if/elif tree over ``ctx.engine.engine`` + ``ctx.engine.method`` for
the DeepL phrasesblock → singlephrase fallback (R15). The table is
exposed for future migration; new code should prefer it.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Callable, Final

from runtime import RuntimeContext

from . import google
from . import deepl
from . import chatgpt_api
from . import chatgpt_web
from . import perplexity_web

__all__ = [
    "EngineName",
    "ACTIVE_ENGINES",
    "DISPATCH_TABLE",
]


class EngineName(StrEnum):
    """Stable, lower-case names for the active engines.

    Uses ``StrEnum`` (Python 3.11+) so that ``EngineName.GOOGLE == 'google'``
    is True without ``.value`` access — keeps the engine string compatible
    with the existing ``--engine`` CLI flag.
    """

    GOOGLE          = "google"
    DEEPL           = "deepl"
    CHATGPT         = "chatgpt"
    CHATGPT_POLISH  = "chatgpt-polish"
    CHATGPT_WEB     = "chatgpt-web"      # phase 8 — guest session
    PERPLEXITY_WEB  = "perplexity-web"   # phase 8 — guest session


# Membership-test set for fast ``engine in ACTIVE_ENGINES`` checks.
ACTIVE_ENGINES: Final[frozenset[EngineName]] = frozenset(EngineName)


# Engine dispatch table — populated incrementally as engines are extracted.
# Engines not yet here remain in the entry script and reach the dispatcher
# via the legacy ``set_translation_function`` glue.
DISPATCH_TABLE: Final[dict[EngineName, Callable[[RuntimeContext, str], tuple[bool, str]]]] = {
    EngineName.GOOGLE:         google.translate,
    EngineName.DEEPL:          deepl.translate,
    EngineName.CHATGPT_WEB:    chatgpt_web.translate,
    EngineName.PERPLEXITY_WEB: perplexity_web.translate,
    # EngineName.CHATGPT / CHATGPT_POLISH still flow through
    # run_openai_single_call in chatgpt_api.py and the legacy
    # block-loop dispatcher; a future phase will give them an
    # Engine Protocol entry point too.
}
