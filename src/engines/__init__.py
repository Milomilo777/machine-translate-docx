"""Active translation engine registry.

Adding a new engine should be:
  1. One new file in this package (e.g. ``mistral.py``)
  2. One member in :class:`EngineName` and one entry in
     :data:`ACTIVE_ENGINES` and :data:`DISPATCH_TABLE`
  3. Zero changes elsewhere

The dispatch table maps ``EngineName`` to the per-engine
``translate(ctx, text)`` callable. ``set_translation_function`` in the
entry script reads from here when re-pointing
``ctx.engine.dispatcher`` (e.g. during the DeepL phrasesblock →
singlephrase fallback).
"""
from __future__ import annotations

from enum import StrEnum
from typing import Callable, Final

from runtime import RuntimeContext

from . import google
from . import chatgpt_api

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

    GOOGLE         = "google"
    DEEPL          = "deepl"
    CHATGPT        = "chatgpt"
    CHATGPT_POLISH = "chatgpt-polish"


# Membership-test set for fast ``engine in ACTIVE_ENGINES`` checks.
ACTIVE_ENGINES: Final[frozenset[EngineName]] = frozenset(EngineName)


# Engine dispatch table — populated incrementally as engines are extracted.
# Engines not yet here remain in the entry script and reach the dispatcher
# via the legacy ``set_translation_function`` glue.
DISPATCH_TABLE: Final[dict[EngineName, Callable[[RuntimeContext, str], tuple[bool, str]]]] = {
    EngineName.GOOGLE: google.translate,
    # EngineName.DEEPL added in G3.
    # EngineName.CHATGPT / CHATGPT_POLISH wired through chatgpt_api in G3+.
}
