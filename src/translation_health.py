"""Post-pipeline sanity checks on the parsed + translated state.

Added in the 2026-05-10 hardening pass to address B-001
(``docs/real-engine-test-findings.md``). The pipeline historically
emitted ``"Translation ended, file saved"`` even when the input had
no translatable content or the engine returned nothing. This module
draws a clear line: if either condition is true, raise — never let
the caller think the run succeeded.

Two checks:

  * :func:`assert_source_has_content` — runs after parse, before
    translate. Fails fast on empty / all-greyed input.
  * :func:`assert_translation_present` — runs after the engine has
    finished, before save. Fails when the non-empty-target / non-
    empty-source ratio drops below :data:`MIN_NONEMPTY_RATIO`.

Both raise :class:`exceptions.TranslationFailure` subclasses so the
entry script can catch one type and print a structured ``[FAIL]
reason=...`` line, which the launcher then parses into a job
``status=error`` plus :ref:`B-002 failure archive <B-002>`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from exceptions import EmptyDocxError, EngineReturnedEmptyError

if TYPE_CHECKING:
    from runtime import RuntimeContext


__all__ = [
    "MIN_NONEMPTY_RATIO",
    "assert_source_has_content",
    "assert_translation_present",
]


# Minimum acceptable ratio of non-empty target rows to non-empty source
# rows. The DeepL/Google phrase-grouped path writes the translation to
# the *first* row of every phrase group, leaving 50-60 % of rows empty
# by design (T5 baseline: 18 of 40 source rows had a translation).
# 0.30 is therefore a deliberately permissive floor: it catches
# "everything empty" / "single-row dumped output" without flagging a
# normal phrase-grouped run.
MIN_NONEMPTY_RATIO: float = 0.30


def _count_nonempty_rows(rows: list[str] | None) -> int:
    """Count rows that have at least one non-whitespace character.

    Mirrors the ``.strip()`` semantics that downstream cell-write code
    uses to decide whether a row is "empty".
    """
    if not rows:
        return 0
    return sum(1 for r in rows if r and r.strip())


def assert_source_has_content(ctx: "RuntimeContext") -> None:
    """Raise :class:`EmptyDocxError` if no row of the source column
    carries any translatable text.

    ``ctx.docx.from_text_table`` is the parallel array populated by
    :func:`docx_io.parse.read_and_parse_docx_document` from column 2
    of the table (the source-language column). A run where every
    entry is empty, whitespace, or greyed-out is a no-op — there is
    nothing for the engine to translate, and the launcher should
    surface that to the user instead of cheerfully saving an empty
    output.
    """
    nonempty = _count_nonempty_rows(ctx.docx.from_text_table)
    if nonempty == 0:
        raise EmptyDocxError(
            f"Input docx has no translatable text "
            f"(parsed {ctx.docx.numrows} rows, all empty / greyed). "
            f"Path: {ctx.flags.word_file_to_translate}"
        )


def assert_translation_present(ctx: "RuntimeContext") -> None:
    """Raise :class:`EngineReturnedEmptyError` when the engine produced
    nothing usable.

    Compares non-empty rows in ``ctx.docx.to_text_by_phrase_separator_table``
    (the per-row translation written by the engine) against the
    non-empty source rows. Below :data:`MIN_NONEMPTY_RATIO` the docx
    is considered an engine-failure rather than a successful run.

    Also fails when the engine produced *something* but the count is
    zero — a more obvious "engine returned empty body" symptom.
    """
    src_nonempty = _count_nonempty_rows(ctx.docx.from_text_table)
    if src_nonempty == 0:
        # assert_source_has_content should have caught this already;
        # treat as engine-empty here so we still surface the failure
        # cleanly if it slipped through.
        raise EngineReturnedEmptyError(
            "Source has no translatable text but reached the post-translate "
            "health check. (Consistency error — assert_source_has_content "
            "should have raised earlier.)"
        )

    tgt_nonempty = _count_nonempty_rows(ctx.docx.to_text_by_phrase_separator_table)
    ratio = tgt_nonempty / src_nonempty if src_nonempty else 0.0

    if tgt_nonempty == 0:
        raise EngineReturnedEmptyError(
            f"Engine produced no translation rows "
            f"(source had {src_nonempty} non-empty rows, target has 0). "
            f"Engine: {ctx.engine.engine}/{ctx.engine.method}"
        )

    if ratio < MIN_NONEMPTY_RATIO:
        raise EngineReturnedEmptyError(
            f"Engine produced too few translation rows: "
            f"{tgt_nonempty}/{src_nonempty} = {ratio:.0%} "
            f"(minimum {MIN_NONEMPTY_RATIO:.0%}). "
            f"Engine: {ctx.engine.engine}/{ctx.engine.method}"
        )
