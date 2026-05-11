"""Paragraph and run iteration helpers for python-docx.

Extracted from the entry script in the 2026-05-10 docx_io extraction
pass.

The single public helper :func:`_iter_paragraph_runs` walks every
``<w:r>`` element below a paragraph regardless of its parent — including
the runs nested inside ``<w:hyperlink>``, ``<w:smartTag>``,
``<w:fldSimple>`` and any other inline container.

Why this matters: ``paragraph.runs`` (the python-docx native iterator)
only returns the ``<w:r>`` elements that are *direct children* of
``<w:p>``. Hyperlinked text lives inside ``<w:hyperlink>`` and so its
runs are silently dropped — which silently dropped the visible
hyperlink labels from translated subtitle cells until the bug was
caught (see ``CHANGES.md`` 2026-05-09 part seven).

Using ``etree.iter`` walks the subtree in document order, the only
order that preserves the original sentence flow.
"""
from __future__ import annotations

from typing import Iterator

from docx.oxml.ns import qn
from docx.text.run import Run as _DocxRun


__all__ = [
    "_iter_paragraph_runs",
]


def _iter_paragraph_runs(paragraph) -> Iterator[_DocxRun]:
    """Yield every ``<w:r>`` element below ``paragraph`` wrapped in a
    python-docx ``Run`` object.
    """
    for r_elem in paragraph._p.iter(qn("w:r")):
        yield _DocxRun(r_elem, paragraph)
