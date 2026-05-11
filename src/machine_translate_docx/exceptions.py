"""Project-wide structured exceptions for failures we want callers to
distinguish.

Added in the 2026-05-10 hardening pass to address B-001
(``docs/real-engine-test-findings.md``): a docx with no translatable
content used to fall through every check and exit with
``"Translation ended, file saved"``. The launcher / API caller had no
way to tell a successful run from a no-op run.

The two exceptions below are raised as soon as the no-op state is
detected and travel up to ``main()``, which prints a structured
``[FAIL] reason=...`` line and exits with a non-zero status. The
launcher's stdout parser flips the job to ``status=error`` and the
B-002 archive hook copies the input + meta.json into
``runtime_dir/failures/<job_id>__<ts>/``.
"""
from __future__ import annotations


__all__ = [
    "TranslationFailure",
    "EmptyDocxError",
    "EngineReturnedEmptyError",
]


class TranslationFailure(Exception):
    """Base class for structured translation pipeline failures.

    ``reason`` is a short machine-readable token (e.g. ``"empty_docx"``,
    ``"engine_empty"``); the human-readable message is the standard
    Exception message.
    """

    reason: str = "translation_failure"

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        if reason is not None:
            self.reason = reason


class EmptyDocxError(TranslationFailure):
    """Raised when the input docx has no translatable source text.

    ``read_and_parse_docx_document`` finishes parsing but every row of
    the source-language column (col 1) is empty / whitespace / greyed.
    There is nothing for the engine to translate.
    """

    reason = "empty_docx"


class EngineReturnedEmptyError(TranslationFailure):
    """Raised when the translator produces no usable output.

    Either the API returned an empty body, the runner's recursive
    splitting produced an empty result, or the ratio of non-empty
    target rows to non-empty source rows fell below
    ``MIN_NONEMPTY_RATIO`` (default 0.5). In every case the run cannot
    be reported as a success — there is no translation in the docx.
    """

    reason = "engine_empty"
