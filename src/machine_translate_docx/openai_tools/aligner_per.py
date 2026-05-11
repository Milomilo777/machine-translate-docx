"""Compatibility shim — DEPRECATED.

Phase 9 of the persian-double-lines roadmap renamed this module to
``openai_tools.persian_double_lines`` to match the user-facing Split
Method name. This module re-exports every public symbol from the new
location so legacy callers keep working unchanged. Prefer the new name
in new code:

    from ..openai_tools.persian_double_lines import FASubtitleAligner

A future release may delete this shim once no caller references
``aligner_per`` any more.
"""
from __future__ import annotations

from .persian_double_lines import *  # noqa: F401,F403 — re-export everything
from . import persian_double_lines as _impl

# Mirror the underlying module's __all__ so ``from .aligner_per import *``
# behaves identically to importing from the new module.
__all__ = list(getattr(_impl, "__all__", []))


def __getattr__(name: str):
    """Forward any attribute access to the new module so private
    helpers (`_split_for_n_rows`, `_set_fa_cell`, `_normalize_fa`, …)
    stay reachable through the shim. Raises AttributeError if the new
    module does not define the name."""
    return getattr(_impl, name)
