"""machine-translate-docx — Word-document translation pipeline.

Translate ``.docx`` files through DeepL, Google, or OpenAI, with a
Persian polish pass tuned for broadcast subtitles. The CLI entry
point is :func:`machine_translate_docx.cli.main`; everything else
is library code consumed by the CLI, the v2 SPA's HTTP launcher,
or external scripts that pip-installed the package.

Sub-packages:

  * :mod:`machine_translate_docx.docx_io` — parse + cell read +
    write + final docx save (the entire docx-shaped surface).
  * :mod:`machine_translate_docx.engines` — translation engines:
    ``chatgpt_api`` (OpenAI single-call), ``deepl`` and ``google``
    (Selenium-driven), plus ``inactive/`` archives.
  * :mod:`machine_translate_docx.openai_tools` — ``translator``,
    ``polisher``, ``persian_double_lines`` (FA bilingual aligner),
    ``line_count_reconciler``, ``fa_postprocess``,
    ``splitting`` (legacy line splitter), and ``_retry`` helpers.
  * :mod:`machine_translate_docx.selenium_utils` — Chrome driver +
    click + form helpers shared by the Selenium engines.
  * :mod:`machine_translate_docx.xlsx_translation_memory` — Excel-
    file-backed translation memory.

Top-level modules:

  * :mod:`machine_translate_docx.runtime` —
    :class:`RuntimeContext` (replaces ~80 module globals).
  * :mod:`machine_translate_docx.config` — ``DEFAULT_AI_MODEL``,
    ``VALID_AI_MODELS``, language tables, JSON helpers.
  * :mod:`machine_translate_docx.runner` — block-loop dispatcher.
  * :mod:`machine_translate_docx.dispatch` —
    :func:`set_translation_function` (engine selection).
  * :mod:`machine_translate_docx.exceptions` —
    :class:`TranslationFailure` hierarchy.
  * :mod:`machine_translate_docx.translation_health` —
    ``assert_source_has_content`` and ``assert_translation_present``.
  * :mod:`machine_translate_docx.cli` — argparse + main entry.

The full architecture, including the failure path and the cost /
cache surface, is documented in ``docs/architecture.md`` and shown
in the SVG diagrams under ``docs/diagrams/``.
"""
from __future__ import annotations

__version__ = "1.0.0"
__author__  = "SMTV / machine-translate-docx contributors"
__license__ = "MIT"


__all__ = [
    "__version__",
    "__author__",
    "__license__",
]
