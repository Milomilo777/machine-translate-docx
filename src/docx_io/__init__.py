"""DOCX I/O helpers — package home for python-docx wrappers.

Created in the 2026-05-10 architecture cleanup follow-up. The
historical entry script grew a small zoo of docx helpers
(``_iter_paragraph_runs``, ``cell_set_1st_paragraph``,
``cell_add_paragraph``, ``get_cell_data``, ``read_and_parse_docx_document``,
``save_docx_file``, etc.) that all live next to the orchestration
code; this package extracts them incrementally.

Module layout:

  - :mod:`docx_io.runs`  — paragraph/run iteration helpers.
  - (future) :mod:`docx_io.cells` — per-cell write helpers.
  - (future) :mod:`docx_io.parse` — read_and_parse_docx_document.
  - (future) :mod:`docx_io.save`  — save_docx_file.

Each module re-exports its public API at the package root via the
imports below, so callers can write:

    from docx_io import _iter_paragraph_runs

instead of caring which sub-module owns the helper.
"""
from __future__ import annotations

from docx_io.runs import _iter_paragraph_runs
from docx_io.cells import (
    add_paragraph as _cell_add_paragraph_impl,
    change_cell_font as _change_cell_font_impl,
    set_first_paragraph as _cell_set_first_paragraph_impl,
    get_cell_data,
)

__all__ = [
    "_iter_paragraph_runs",
    "_cell_add_paragraph_impl",
    "_change_cell_font_impl",
    "_cell_set_first_paragraph_impl",
    "get_cell_data",
]
