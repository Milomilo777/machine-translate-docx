"""Final docx write path — engine-suffix, source-column lock, save.

Extracted from the entry script in the 2026-05-10 docx_io extraction
pass. Two public functions:

  * :func:`engine_suffix` — return the per-engine filename suffix
    appended after the lang code (``_Polish``, ``_chatGPT``, ``_Google``,
    ``_Deepl``).
  * :func:`save_docx_file` — apply the source-column defensive lock,
    derive the final output path with engine suffix and collision
    avoidance, then write the docx to disk.

The new ``save_docx_file`` takes all its external dependencies as
explicit parameters / kwargs:

    save_docx_file(
        ctx,
        docxdoc,
        *,
        silent: bool,
        write_translation_log_fn: Callable[[str], None],
    )

This keeps the function pure: no hidden module-global reads. The
entry-script shim passes the live globals through.
"""
from __future__ import annotations

import os
import re
import time
import traceback
from copy import deepcopy as _dc
from typing import Callable

from langcodes import Language

from runtime import RuntimeContext
from config import (
    google_translate_lang_codes,
    deepl_translate_lang_codes,
)


__all__ = [
    "engine_suffix",
    "save_docx_file",
]


def engine_suffix(ctx: RuntimeContext) -> str:
    """Return the per-engine filename suffix appended after the lang code.

    Phase-5 naming convention. chatgpt-web / perplexity-web entries
    were removed in the 2026-05-10 cleanup pass.

        google                       → _Google
        deepl                        → _Deepl
        chatgpt + api + with-polish  → _Polish
        chatgpt + api - with-polish  → _chatGPT

    Anything outside this table returns the empty string so the file
    keeps the legacy bare ``_{LANG}.docx`` name and nothing breaks.
    """
    engine = (ctx.engine.engine or "").lower().strip()
    method = (ctx.engine.method or "").lower().strip()
    if engine == "google":
        return "_Google"
    if engine == "deepl":
        return "_Deepl"
    if engine == "chatgpt":
        if method == "api":
            return "_Polish" if ctx.flags.with_polish else "_chatGPT"
    return ""


def _restore_source_column(ctx: RuntimeContext) -> None:
    """Restore snapshotted source-side cells (cols 0+1) before save.

    If anything in the pipeline mutated the source column — translation
    memory leak, an engine touching the wrong column, a helper rewriting
    cell text — bring them back to their parse-time state. The user's
    contract: source column is frozen, no engine and no process may
    change it.

    Failures are non-fatal — per-row exceptions are swallowed and the
    rest of the snapshot is restored.
    """
    try:
        restored = 0
        snap = ctx.docx.source_columns_snapshot or {}
        for (ri, cj), entry in snap.items():
            try:
                # Backwards-compat: older snapshots stored just the XML.
                if isinstance(entry, tuple):
                    orig_text, orig_tc = entry
                else:
                    orig_text, orig_tc = None, entry

                row = ctx.docx.table.rows[ri]
                if cj >= len(row.cells):
                    continue
                cell = row.cells[cj]
                # Primary check: visible text. python-docx may
                # re-serialise the XML with reordered namespace
                # attributes / whitespace even when the cell content
                # is identical, so byte-level XML comparison generates
                # false positives. Restore only when the visible text
                # genuinely drifted.
                if orig_text is not None and cell.text == orig_text:
                    continue
                cur_tc = cell._tc
                parent = cur_tc.getparent()
                if parent is None:
                    continue
                parent.replace(cur_tc, _dc(orig_tc))
                restored += 1
            except Exception:
                continue
        if restored:
            print(
                f"[LOCK] Restored {restored} source-column cell(s) before save "
                f"(text drift detected — translation memory leak suspected)"
            )
    except Exception as exc:
        print(f"[LOCK] Source-column lock skipped: {exc}")


def _resolve_output_path(ctx: RuntimeContext) -> None:
    """Compute ``ctx.flags.word_file_to_translate_save_as_path``.

    Adds the ISO 639-2/B language code (uppercase) and the engine
    suffix; appends ``_1``, ``_2`` … on collision so we never
    overwrite an existing file.
    """
    lang_code = ctx.language.dest_lang
    lang_name = None

    try:
        lang_name = google_translate_lang_codes[lang_code]
    except Exception:
        try:
            lang_name = deepl_translate_lang_codes[lang_code]
            for google_lang_code in google_translate_lang_codes.keys():
                try:
                    if (deepl_translate_lang_codes[lang_code].lower()
                            == google_translate_lang_codes[google_lang_code].lower()
                            and lang_code != google_lang_code):
                        lang_code = google_lang_code
                except Exception:
                    pass
        except Exception:
            pass

    lang_alpha3b_code = None
    try:
        Language.get(lang_code).to_alpha3()
        lang_alpha3b_code = Language.get(lang_code).to_alpha3(variant="B")
    except Exception:
        lang_alpha3b_code = None

    ctx.flags.word_file_to_translate_save_as_path = ctx.flags.word_file_to_translate
    if lang_alpha3b_code is not None:
        find_alpha3_code_suffix = f"(?i)_{lang_alpha3b_code}.docx$"
        if not re.search(find_alpha3_code_suffix, ctx.flags.word_file_to_translate):
            ctx.flags.word_file_to_translate_save_as_path = re.sub(
                "(?i)_{lang_alpha3b_code}.docx$", ".docx",
                ctx.flags.word_file_to_translate,
            )
            lang_alpha3b_code = lang_alpha3b_code.upper()
            engine_tag = engine_suffix(ctx)
            ctx.flags.word_file_to_translate_save_as_path = re.sub(
                "(?i).docx$",
                f"_{lang_alpha3b_code}{engine_tag}.docx",
                ctx.flags.word_file_to_translate,
            )
            print(f"\nAdding file name suffix _{lang_alpha3b_code}{engine_tag}.")

    if os.path.exists(ctx.flags.word_file_to_translate_save_as_path):
        stem = re.sub(r"(?i)\.docx$", "", ctx.flags.word_file_to_translate_save_as_path)
        idx = 1
        while os.path.exists(f"{stem}_{idx}.docx"):
            idx += 1
        ctx.flags.word_file_to_translate_save_as_path = f"{stem}_{idx}.docx"
        print(
            f"[INFO] Output file already exists — saving as: "
            f"{ctx.flags.word_file_to_translate_save_as_path}"
        )


def save_docx_file(
    ctx: RuntimeContext,
    docxdoc,
    *,
    silent: bool,
    write_translation_log_fn: Callable[[str], None],
) -> None:
    """Write the translated docx to disk.

    Steps:
      1. Resolve the output path (lang + engine suffix + collision avoid).
      2. Restore the snapshotted source column (defensive lock).
      3. Save the docx; on failure either prompt the user (interactive)
         or back off briefly (silent mode) and retry.
      4. If with_polish + a non-empty translation log, write the
         JSON sidecar via the injected ``write_translation_log_fn``.
    """
    # PROGRESS:90 — about to write the docx to disk. The aligner branch
    # in print_console_docx_file_translated also emits 90 (and 100), so
    # the launcher sees 90 either way.
    _resolve_output_path(ctx)
    _restore_source_column(ctx)

    file_saved = 0
    while file_saved == 0:
        try:
            docxdoc.save(ctx.flags.word_file_to_translate_save_as_path)
            file_saved = 1
            if ctx.flags.with_polish and ctx.openai.translation_log.get("blocks"):
                log_path = re.sub(
                    r"(?i)\.docx$",
                    "_log.json",
                    ctx.flags.word_file_to_translate_save_as_path,
                )
                write_translation_log_fn(log_path)
        except Exception:
            print(traceback.format_exc())
            if not silent:
                input(
                    "\n\nERROR: File saving failed. Please close microsoft "
                    "word or other program and press enter to save the "
                    "translated document.\n"
                )
            else:
                # No user to dismiss the prompt; back off briefly and
                # retry the save instead of hanging the launcher pipe.
                time.sleep(2)
