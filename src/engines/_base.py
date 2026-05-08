"""Engine Protocol — structural type that every active engine should match.

This is aspirational. The current Selenium engines (Google, DeepL) still
mutate module-level globals and won't conform until Phase C/F threads
``RuntimeContext`` through them. Use :class:`Engine` as the target shape
when extracting a new engine into :mod:`engines`.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["Engine"]


@runtime_checkable
class Engine(Protocol):
    """Common signature for an active translation engine.

    Implementations may be stateful (e.g. a Selenium driver wrapper) or
    stateless (e.g. an OpenAI API caller). The protocol only requires the
    ``translate`` method.
    """

    def translate(
        self,
        source_text: str,
        src_lang_name: str,
        dest_lang_name: str,
    ) -> tuple[bool, str]:
        """Translate ``source_text`` and return ``(success, translated)``.

        ``success`` is True when the response had the expected line count
        (i.e. ``len(translated.split('\\n')) == len(source_text.split('\\n'))``)
        AND the translation is non-empty. False otherwise.
        """
        ...
