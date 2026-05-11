"""DOCX parsing — read_and_parse_docx_document.

Extracted from the entry script in the 2026-05-10 G3 thread-globals
pass. The function reads a python-docx ``Document`` (carried on
``ctx.docx.docxdoc``), populates every parallel array on
``ctx.docx``, and emits a side-effect HTML preview when
``ctx.docx.use_html`` is true.

Dependencies kept on the entry script (lazy-imported inside the
function body to avoid an import cycle):

  * ``is_end_of_line`` / ``is_empty_line`` /
    ``is_beginning_of_line`` / ``is_conditional_end_of_line`` —
    stateless predicates over the ``eol_array`` / ``bol_array`` /
    ``eol_conditional_array`` constants in ``config.py``.
  * ``prepare_and_clear_cell_for_writing`` — owns its own ctx-aware
    body in the entry script and reads ``dest_lang`` / ``rtlstyle`` /
    ``dest_font`` from module scope.
  * ``split_phrases`` — already ctx-aware, but reads
    ``line_separator_str`` and ``use_html`` from module scope.

The colour-ignore list and the actual cell read are reached through
:func:`docx_io.cells.get_cell_data`, which itself reads
``ctx.config.shading_color_ignore_text``.

Constants:

  * ``E_MAIL_STR`` and ``PROGRAM_VERSION`` are referenced here only in
    the error-exit branches. They mirror the values in the entry
    script. If those drift, this module's banner drifts too —
    documented as an accepted duplication, not a behaviour bug.

Bug fix landed in the same pass: the original entry-script body
referenced an undefined name ``docxfile`` in the
"document does not have a table" error path. Replaced with
``ctx.flags.word_file_to_translate``.
"""
from __future__ import annotations

import re
import sys
import timeit
import traceback
from copy import deepcopy as _dc
from typing import TYPE_CHECKING

from ..docx_io.cells import get_cell_data

if TYPE_CHECKING:
    from ..runtime import RuntimeContext


__all__ = [
    "read_and_parse_docx_document",
    "E_MAIL_STR",
    "PROGRAM_VERSION",
]


# Author contact + program version — used only by the error-exit branches.
# Kept here as module constants so this module has zero entry-script reads.
E_MAIL_STR = "smtv.bot@gmail.com"
PROGRAM_VERSION = "1.0.0"


def read_and_parse_docx_document(ctx: "RuntimeContext") -> None:
    """Parse the input DOCX into the parallel arrays on ``ctx.docx``.

    Threaded in Phase F1.3: every parallel array, table_cells, the
    table reference, and the row/column geometry move from module
    globals into ``ctx.docx``. The +1 indexing convention
    (arrays sized ``numrows + 1``, accessed at ``[i + 1]``) is
    preserved exactly. R16's structural test
    (``test_docx_arrays_plus_one_indexing``) pins this contract.

    Extracted to ``docx_io.parse`` in 2026-05-10 G3. The function now
    reads ``docxdoc`` and ``use_html`` from ``ctx.docx``,
    ``silent`` and ``splitonly`` and ``word_file_to_translate`` from
    ``ctx.flags``, and the source-cell colour-ignore list via
    :func:`docx_io.cells.get_cell_data`. Helpers that still live on
    the entry script are lazy-imported below.
    """
    # Lazy imports avoid a module-load cycle: machine_translate_docx.cli
    # imports docx_io at top, and these helpers live next to its
    # global state. The 2026-05-11 src-layout migration moved
    # `machine_translate_docx.py` into `machine_translate_docx/cli.py`;
    # before that, this import read `from machine_translate_docx import …`.
    from machine_translate_docx.cli import (
        is_end_of_line,
        is_empty_line,
        is_beginning_of_line,
        is_conditional_end_of_line,
        prepare_and_clear_cell_for_writing,
        split_phrases,
    )

    docx = ctx.docx
    docxdoc = ctx.docx.docxdoc
    use_html = ctx.docx.use_html
    silent = ctx.flags.silent
    splitonly = ctx.flags.splitonly

    # Original code captured `start = timeit.timeit()` but never read it
    # — kept here for behavioural parity with the legacy version.
    start = timeit.timeit()  # noqa: F841

    if use_html:
        print("Content-Type: text/html\n")

    docx.word_translation_table_length = len(docxdoc.tables[0].rows)

    nb_tables = len(docxdoc.tables)  # noqa: F841 — historical print uses this comment

    nb_character_total = 0  # noqa: F841 — historical local; unused downstream

    if use_html:
        print(
            "<!doctype html><head><meta http-equiv=""Content-Type"" "
            "content=""text/html"" charset=utf-8 /><title>Winword in python</title>"
            "</head><h2>tables</h2><span style=""font-family:monospace,monospace;"">"
        )

    # Number of tables</h2>nb_tables=", nb_tables  (legacy comment)

    numerrors = 0

    try:
        docx.table = docxdoc.tables[0]
    except Exception:
        # G3 fix: the original code referenced an undefined `docxfile`
        # name here. Replaced with the ctx-carried input path.
        print(
            f"Error: document {ctx.flags.word_file_to_translate} does not "
            f"have a table. Exiting."
        )
        sys.exit(14)
    docx.table_cells = [
        ['' for _ in range(len(docx.table.columns))]
        for _ in range(len(docx.table.rows))
    ]

    docx.numrows = len(docx.table.rows)
    docx.numcols = len(docx.table.columns)

    if docx.numcols <= 2:
        print("ERROR : The table has %s column but expected 3" % (docx.numcols))
        print("Exiting\n")

        print("\nDeveloper: %s" % (E_MAIL_STR))
        print("Program version: %s\n" % (PROGRAM_VERSION))
        if not silent:
            input("Enter to close program")
        else:
            print("Program ended with errors")
        sys.exit(11)

    docx.from_text_table = [''] * (docx.numrows + 1)
    docx.from_text_is_greyed_table = [0] * (docx.numrows + 1)
    docx.from_text_is_red_color_table = [0] * (docx.numrows + 1)
    docx.from_text_is_end_of_line_table = [0] * (docx.numrows + 1)
    docx.from_text_is_beginning_of_line_table = [0] * (docx.numrows + 1)
    docx.from_text_is_empty_line_table = [0] * (docx.numrows + 1)
    docx.from_text_is_conditional_end_of_line_table = [0] * (docx.numrows + 1)
    docx.from_text_by_phrase_separator_table = [''] * (docx.numrows + 1)
    docx.from_text_by_phrase_table = [''] * (docx.numrows + 1)
    docx.from_text_nb_lines_in_phrase = [0] * (docx.numrows + 1)
    docx.from_text_nb_lines_in_cell = [0] * (docx.numrows + 1)
    docx.to_text_by_phrase_separator_table = [''] * (docx.numrows + 1)
    docx.to_text_by_phrase_separator_removed_table = [''] * (docx.numrows + 1)
    docx.to_text_splited_table1 = [''] * (docx.numrows + 1)
    docx.to_text_by_phrase_table = [''] * (docx.numrows + 1)
    docx.to_text_table = [''] * (docx.numrows + 1)
    docx.to_raw_translated_table = [''] * (docx.numrows + 1)
    docx.to_text_removed_line_separator = [''] * (docx.numrows + 1)
    docx.translation_result_using_separator = [''] * (docx.numrows + 1)
    # `[[]] * n` would have every slot pointing at the same shared list,
    # so any future `array[i].append(...)` would silently mutate every
    # other slot. List-comprehension gives each slot a distinct list.
    docx.translation_result_phrase_array = [[] for _ in range(docx.numrows + 1)]
    docx.translation_result = [''] * (docx.numrows + 1)
    docx.from_text_is_read = [0] * (docx.numrows + 1)

    if use_html:
        print("<br>%s rows.<br>%d colums.<br>" % (docx.numrows, docx.numcols))

    for i, row in enumerate(docx.table.rows):
        col_no = 1
        row_n = i + 1

        p_remove_pause = re.compile(r'(?i)<pause>')
        p_remove_double_spaces = re.compile(r' +')
        p_remove_parenthesis_spaces = re.compile(r'\( +')

        try:
            for j, cell in enumerate(row.cells):
                docx.table_cells[i][j] = cell
                # Defensive lock: snapshot every source-side cell (columns 0
                # and 1 — line-number and EN text) so save_docx_file can
                # restore them before writing the docx to disk. Guarantees
                # the source language column is never altered by any engine
                # or helper, even via a future leak we haven't audited.
                # Store both the visible text and the deepcopy'd XML so the
                # save-time check can prefer text comparison (immune to
                # python-docx's XML re-serialisation noise) and only fall
                # back to XML restore on actual content drift.
                if j in (0, 1):
                    docx.source_columns_snapshot[(i, j)] = (cell.text, _dc(cell._tc))
                if col_no == 2:
                    cellvalue, docx.from_text_is_greyed_table[i], docx.from_text_is_red_color_table[i] = get_cell_data(ctx, cell, row_n)
                    cellvalue = p_remove_pause.sub(' ', cellvalue)
                    cellvalue = p_remove_double_spaces.sub(' ', cellvalue)
                    cellvalue = p_remove_parenthesis_spaces.sub('(', cellvalue)

                    try:
                        print("%d : %s" % (i, cellvalue), flush=True)
                    except Exception:
                        try:
                            print("%d : %s" % (i, cellvalue.encode("utf-8")))
                        except Exception:
                            print("%d : (unable to print content to screen)")

                    docx.from_text_is_end_of_line_table[i] = is_end_of_line(cellvalue) or docx.from_text_is_red_color_table[i]
                    docx.from_text_is_empty_line_table[i] = is_empty_line(cellvalue)
                    docx.from_text_is_beginning_of_line_table[i] = is_beginning_of_line(cellvalue)
                    docx.from_text_is_conditional_end_of_line_table[i] = is_conditional_end_of_line(cellvalue)

                    if docx.from_text_is_greyed_table[i] == 1:
                        docx.from_text_is_beginning_of_line_table[i] = 0
                        docx.from_text_is_end_of_line_table[i] = 0

                    if i == 2 and len(cellvalue) > 0:
                        docx.from_text_is_beginning_of_line_table[i] = 1

                    if i > 1:
                        # Test conditionel de fin de ligne
                        if docx.from_text_is_conditional_end_of_line_table[i - 1] == 1 \
                                and docx.from_text_is_beginning_of_line_table[i] == 1:
                            docx.from_text_is_end_of_line_table[i - 1] = 1
                            docx.from_text_is_beginning_of_line_table[i] = 1

                        # Verifier debut de ligne special
                        # Si ligne precedente est vide ou grisee:
                        #    Si ligne courante est non vide et non grisee
                        #        ligne courante est debut de ligne
                        if (docx.from_text_is_empty_line_table[i - 1] == 1
                                or docx.from_text_is_greyed_table[i - 1] == 1):
                            if (docx.from_text_is_empty_line_table[i] == 1
                                    and docx.from_text_is_greyed_table[i] == 1):
                                docx.from_text_is_beginning_of_line_table[i] = 1

                        # Verifier la ligne precedente est fin de ligne
                        # Si ligne precedente est non vide et non grisee
                        #    Si ligne courante est vide ou grisee
                        #        la ligne precedente est fin de ligne
                        if (docx.from_text_is_empty_line_table[i - 1] == 0
                                and docx.from_text_is_greyed_table[i - 1] == 0):
                            if (docx.from_text_is_empty_line_table[i] == 1
                                    or docx.from_text_is_greyed_table[i] == 1):
                                docx.from_text_is_end_of_line_table[i - 1] = 1

                        # Verifier que c'est vraiment un debut de ligne suivant une fin de ligne
                        # Si ligne precedente n'est pas fin de ligne
                        #    et ligne oourante est debut de ligne
                        #        la ligne courante n'est pas un debut de ligne
                        if (docx.from_text_is_beginning_of_line_table[i] == 1
                                and docx.from_text_is_end_of_line_table[i - 1] == 0
                                and docx.from_text_is_greyed_table[i - 1] == 0
                                and i > 2):
                            docx.from_text_is_beginning_of_line_table[i] = 0

                        # Verifier qu'on a pas loupe un debut de ligne
                        # Si ligne precedente est fin de ligne
                        #    et ligne oourante n'est pas grisee et pas debut de ligne
                        #        la ligne courante est un debut de ligne
                        if (docx.from_text_is_end_of_line_table[i - 1] == 1
                                and docx.from_text_is_greyed_table[i] == 0
                                and docx.from_text_is_beginning_of_line_table[i] == 0):
                            docx.from_text_is_beginning_of_line_table[i] = 1

                        if (docx.from_text_is_empty_line_table[i - 1] == 1
                                or docx.from_text_is_greyed_table[i - 1] == 1) \
                                and (docx.from_text_is_empty_line_table[i] == 0
                                     and docx.from_text_is_greyed_table[i] == 0):
                            docx.from_text_is_beginning_of_line_table[i] = 1

                        if docx.from_text_is_empty_line_table[i - 1] == 1:
                            docx.from_text_is_beginning_of_line_table[i - 1] = 0

                        if i == docx.numrows:
                            docx.from_text_is_end_of_line_table[i - 1] = 1

                    docx.from_text_table[i] = cellvalue
                col_no = col_no + 1

            if not splitonly and i > 1:
                prepare_and_clear_cell_for_writing(ctx, i, '')
            docx.from_text_is_read[i] = 1
        except Exception:
            var = traceback.format_exc()
            print(var)
            numerrors = numerrors + 1

    if docx.from_text_is_greyed_table[docx.numrows] == 0 \
            and docx.from_text_is_empty_line_table[docx.numrows] == 0:
        docx.from_text_is_end_of_line_table[docx.numrows] = 1

    split_phrases(ctx)

    # W-5 (2026-05-11): emit a one-line summary of the phrase-grouping
    # outcome so a fresh reader of the log understands why the output
    # docx has translations only on phrase-head rows. Without this line,
    # users opening a phrase-grouped output file (DeepL/Google) for the
    # first time consistently asked "why are 22 of my 40 cells empty?".
    _phrase_heads = sum(
        1 for v in docx.from_text_by_phrase_separator_table if v and v.strip()
    )
    _src_lines = sum(
        1 for v in docx.from_text_table if v and v.strip()
    )
    print(
        f"[INFO] Parsed {_src_lines} source lines into {_phrase_heads} phrase "
        f"groups — translation will be written to phrase-head rows; other "
        f"rows of the same phrase remain empty by design.",
        flush=True,
    )

    if use_html:
        print("<table border=1 width=800>")

    for row_n in range(1, len(docx.from_text_table)):
        try:
            if use_html:
                print("<tr>")
                print("<td width=50>", row_n)
                print("<td width=250>")

            if docx.from_text_is_beginning_of_line_table[row_n] == 1:
                if use_html:
                    print("<hr style=\"height:5px;border:none;color:#ffff00;background-color:#ffff00;\" />")

            if docx.from_text_is_greyed_table[row_n] == 1:
                if use_html:
                    print("'<span style=\"background-color: #DCDCDC\">%s</span>' (%s)" % (docx.from_text_table[row_n], len(docx.from_text_table[row_n])))
                    print("<hr style=\"height:5px;border-top: dotted 2px;color:##DCDCDC;background-color:#DCDCDC;\" />")
            else:
                if use_html:
                    print("'%s' (%s)" % (docx.from_text_table[row_n], len(docx.from_text_table[row_n])))

            if docx.from_text_is_end_of_line_table[row_n] == 1:
                if use_html:
                    print("<hr style=\"height:5px;border:none;color:#333;background-color:#333;\" />")

            if docx.from_text_is_empty_line_table[row_n] == 1:
                if use_html:
                    print("<hr style=\"height:5px;border-top: dotted 2px;color:##DCDCDC;background-color:#DCDCDC;\" />")
                    print("<td>is_greyed=%s<br>is_end_of_line=%s<br>is_empty_line=%s<br>is_beginning_of_line=%s<br>is_conditional_end_of_line=%s" % (
                        docx.from_text_is_greyed_table[row_n],
                        docx.from_text_is_end_of_line_table[row_n],
                        docx.from_text_is_empty_line_table[row_n],
                        docx.from_text_is_beginning_of_line_table[row_n],
                        docx.from_text_is_conditional_end_of_line_table[row_n]))

            if use_html:
                print("<td>'%s' (%d)<td>'%s' (%d)" % (
                    docx.from_text_by_phrase_table[row_n], len(docx.from_text_by_phrase_table[row_n]),
                    docx.from_text_by_phrase_separator_table[row_n], len(docx.from_text_by_phrase_separator_table[row_n])))
        except Exception:
            var = traceback.format_exc()
            print(var)
            numerrors = numerrors + 1
