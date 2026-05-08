"""Active translation engine registry.

Adding a new engine should be:
  1. One new file in this package (e.g. ``mistral.py``)
  2. One member in :class:`EngineName` and one entry in
     :data:`ACTIVE_ENGINES`
  3. Zero changes elsewhere
"""
from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "EngineName",
    "ACTIVE_ENGINES",
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
