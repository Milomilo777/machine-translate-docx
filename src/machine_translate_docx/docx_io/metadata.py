"""Output-side DOCX metadata writers.

Extracted from the entry script on 2026-05-16 as part of the cli.py
shrink phase 2. Two helpers live here:

* :func:`write_destination_language_in_docx_cell` — fills the lang
  marker cell (row 1, col 2 of the first table) with the human-readable
  destination language name, with a fallback to the ISO code.
* :func:`set_docx_properties_comment_for_history` — stamps a one-line
  audit comment into the docx core properties so users can tell at a
  glance which engine + program version translated the file.

Both helpers take their dependencies as explicit arguments so they
remain unit-testable without booting the rest of the pipeline.
"""
from __future__ import annotations

import datetime


def write_destination_language_in_docx_cell(
    docxdoc,
    *,
    splitonly: bool,
    dest_lang_name: str | None,
    dest_lang: str | None,
) -> None:
    """Write the destination-language label into cell (1, 2) of table 0.

    No-op when ``splitonly`` is True (the user is only running the
    splitter / aligner — no translation happened, so labelling the
    column would be misleading).

    Tries ``dest_lang_name`` first; on any exception (or if the name is
    empty) falls back to the ISO code ``dest_lang``. Silently tolerates
    documents whose first table has no (1, 2) cell — the historical
    behaviour we preserve byte-for-byte.
    """
    if splitonly:
        return
    try:
        docxdoc.tables[0].cell(1, 2).text = dest_lang_name
    except Exception:
        try:
            docxdoc.tables[0].cell(1, 2).text = dest_lang
        except Exception:
            pass


def set_docx_properties_comment_for_history(
    docxdoc,
    *,
    program_version: str,
    engine: str,
) -> None:
    """Stamp a one-line audit comment into the docx core properties.

    Format: ``Document translated by SMTV Robot version {V} using {E}
    engine on {dd/mm/YYYY HH:MM:SS}.``. The timestamp is the local wall
    clock at write time. Overwrites any previous comment unconditionally;
    the entry script only invokes this on a successful run.
    """
    now = datetime.datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    docxdoc.core_properties.comments = (
        f"Document translated by SMTV Robot version {program_version} "
        f"using {engine} engine on {dt_string}."
    )
