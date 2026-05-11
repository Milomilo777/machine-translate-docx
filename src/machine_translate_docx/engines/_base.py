"""Engine Protocol — structural type that every active engine matches.

After Phase F1 (RuntimeContext threading) and Phase G (engine extraction),
the active engines (``engines.google``, ``engines.deepl``) expose a
module-level ``translate(ctx, text) -> tuple[bool, str]`` that conforms
to this protocol. ``DISPATCH_TABLE`` in :mod:`engines` is keyed by
this signature.

Use :class:`Engine` as the target shape when extracting a new engine.

Also exports :func:`_maybe_log_swallowed` — a tiny helper that turns
``except Exception:`` blocks into a debug-friendly logging point
without changing the production swallow behaviour. Set
``MTD_SELENIUM_VERBOSE=1`` in the environment to see what's being
swallowed; otherwise the helper is a no-op.
"""
from __future__ import annotations

import os
import sys
import traceback as _tb
from typing import Protocol, runtime_checkable

from ..runtime import RuntimeContext

__all__ = ["Engine", "_maybe_log_swallowed"]


def _maybe_log_swallowed(label: str, exc: BaseException) -> None:
    """Print a swallowed exception's type when verbose mode is on.

    R-7 (2026-05-11): the Selenium engines have many ``except Exception:``
    blocks where the swallow is intentional (optional cookie banner,
    `Browse your files` sentinel, etc.). When a real-engine run misbehaves
    in production the operator wants to know which of those swallows
    actually fired. Set ``MTD_SELENIUM_VERBOSE=1`` and rerun the job;
    each swallowed exception prints one line plus its short traceback to
    stderr. Default behaviour (env unset / empty) is a no-op so live
    runs stay quiet.
    """
    if not os.environ.get("MTD_SELENIUM_VERBOSE", "").strip():
        return
    try:
        # Single-line summary first (so a screenful of these stays
        # skim-friendly) followed by a 3-frame traceback.
        print(
            f"[selenium-swallowed] {label}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        frames = _tb.format_exception(type(exc), exc, exc.__traceback__, limit=3)
        for line in frames:
            for sub in line.rstrip().splitlines():
                print(f"    {sub}", file=sys.stderr, flush=True)
    except Exception:
        # Logging is best-effort; never let it surface as a new exception.
        pass


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
