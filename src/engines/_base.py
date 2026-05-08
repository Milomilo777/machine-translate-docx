"""Engine Protocol — structural type that every active engine matches.

After Phase F1 (RuntimeContext threading) and Phase G (engine extraction),
the active engines (``engines.google``, ``engines.deepl``) expose a
module-level ``translate(ctx, text) -> tuple[bool, str]`` that conforms
to this protocol. ``DISPATCH_TABLE`` in :mod:`engines` is keyed by
this signature.

Use :class:`Engine` as the target shape when extracting a new engine.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from runtime import RuntimeContext

__all__ = ["Engine"]


@runtime_checkable
class Engine(Protocol):
    """Common signature for an active translation engine.

    Implementations are module-level functions (the engine module exposes
    a free ``translate`` function), not classes — the Protocol still works
    structurally because ``runtime_checkable`` checks attribute presence,
    not bound-method identity. Both stateful (Selenium-driver-backed) and
    stateless (OpenAI-API-backed) engines fit this shape; per-engine
    state lives on ``ctx`` instead of ``self``.
    """

    def translate(
        self,
        ctx: RuntimeContext,
        text: str,
    ) -> tuple[bool, str]:
        """Translate ``text`` and return ``(success, translated)``.

        ``success`` is True when the translation is non-empty (and, where
        the engine validates it, when the line count matches). Caller
        decides how to interpret ``False`` — usually triggers a recursive
        split / Google fallback in the block-loop runner.
        """
        ...
