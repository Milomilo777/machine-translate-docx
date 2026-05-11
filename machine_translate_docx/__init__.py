"""machine-translate-docx — thin namespace wrapper.

This package is the importable surface for ``pip install -e .``. The
real code still lives in the flat ``src/`` directory (each ``.py``
imports siblings by bare name, e.g. ``from runtime import …``); a
full conversion to package-relative imports is parked as a separate
refactor. Until then, importing this package has one side effect:
it appends the repository's ``src/`` directory to ``sys.path`` so
external callers who pip-installed this package can:

    >>> from machine_translate_docx import runtime, config
    >>> ctx = runtime.RuntimeContext.empty()

The same ``sys.path`` injection is performed by ``tests/conftest.py``
for in-repo callers; this wrapper extends that pattern to consumers
who installed via ``pip install -e .``.

Note: this is a soft wrapper, not a real package boundary. The
flat-layout caveats described in ``pyproject.toml`` still apply —
the goal here is "make `pip install -e .` succeed and let modern
tooling resolve the metadata", not "ship a redistributable wheel".
The next session can pick the full src-layout migration up; this
file is the cheapest possible interim step.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path


__version__ = "1.0.0"
__author__  = "SMTV / machine-translate-docx contributors"


# Path-fixup: when installed editable, ``__file__`` lives next to ``src/``
# inside the repository. When installed non-editable, ``src/`` does not
# exist next to the package — in that case we leave sys.path alone and
# the consumer gets a clean ImportError, which is the correct signal
# that they should `pip install -e .` from a clone rather than from PyPI
# (the wheel does not bundle the flat modules yet).
_src = _Path(__file__).resolve().parent.parent / "src"
if _src.is_dir() and str(_src) not in _sys.path:
    _sys.path.insert(0, str(_src))


__all__ = ["__version__", "__author__"]
