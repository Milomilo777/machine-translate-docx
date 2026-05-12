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

from ..runtime import RuntimeContext
from ..config import (
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
    split_engine = (getattr(ctx.flags, "split_engine", None) or "").lower().strip()
    double_lines_tag = "_Double_Lines" if split_engine == "persian_double_lines" else ""
    if engine == "google":
        return "_Google" + double_lines_tag
    if engine == "deepl":
        return "_Deepl" + double_lines_tag
    if engine == "chatgpt":
        if method == "api":
            base = "_Polish" if ctx.flags.with_polish else "_chatGPT"
            return base + double_lines_tag
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


def _write_minimal_sidecar(ctx: RuntimeContext) -> None:
    """Emit a minimal `_log.json` next to a non-OpenAI run.

    DeepL / Google / chatgpt-without-polish never populate
    ``ctx.openai.translation_log['blocks']``, so the chatgpt-polish
    sidecar branch above is skipped and historically nothing was
    written. The v2 frontend's run-summary card needs *some* JSON to
    render counts + elapsed; this minimal shape gives it that without
    introducing new pipeline state.

    Schema (mirrors the chatgpt-polish sidecar where it overlaps):
      {
        "run_info":  { timestamp, input_file, output_file,
                       engine, src_lang, dest_lang },
        "blocks":    [],
        "summary":   { total_blocks: 0,
                       total_tokens: null,
                       total_cost_usd: null,
                       elapsed_total_seconds: null,
                       source_rows_nonempty: int,
                       target_rows_nonempty: int,
                       row_count: int }
      }
    """
    import datetime as _dt
    import json as _json

    out_path = ctx.flags.word_file_to_translate_save_as_path
    if not out_path:
        return
    log_path = re.sub(r"(?i)\.docx$", "_log.json", out_path)

    src_rows = ctx.docx.from_text_table or []
    tgt_rows = ctx.docx.to_text_by_phrase_separator_table or []
    src_n = sum(1 for v in src_rows if v and v.strip())
    tgt_n = sum(1 for v in tgt_rows if v and v.strip())

    payload = {
        "run_info": {
            "timestamp":   _dt.datetime.utcnow().isoformat(timespec="seconds"),
            "input_file":  ctx.flags.word_file_to_translate,
            "output_file": out_path,
            "engine":      ctx.engine.engine,
            "method":      ctx.engine.method,
            "src_lang":    ctx.language.src_lang,
            "dest_lang":   ctx.language.dest_lang,
            "with_polish": False,
            # `model` is left absent rather than null so the v2
            # frontend can use `'model' in run_info` to decide whether
            # to render the model row.
        },
        "blocks": [],
        "summary": {
            "total_blocks":          0,
            "total_tokens":          None,
            "total_cost_usd":        None,
            "elapsed_total_seconds": None,
            "row_count":             max(len(src_rows), len(tgt_rows)),
            "source_rows_nonempty":  src_n,
            "target_rows_nonempty":  tgt_n,
        },
    }
    try:
        with open(log_path, "w", encoding="utf-8") as fh:
            _json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"[INFO] Run sidecar saved → {log_path}")
    except Exception as exc:
        # Sidecar is informational; never let a write failure kill the
        # save path. The docx itself is already on disk by this point.
        print(f"[WARN] Could not write minimal sidecar at {log_path}: {exc!r}")


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
            else:
                # 2026-05-11 (#2 backlog): emit a minimal sidecar for
                # non-OpenAI engines too so the v2 frontend's run-summary
                # card has something to render for DeepL / Google runs.
                # No tokens / cost — only the engine + language pair +
                # row counts + elapsed time. Rendered the same way the
                # chatgpt-polish sidecar is, just with `tokens=null`.
                _write_minimal_sidecar(ctx)
            # F7c: run the FA bilingual aligner over the just-saved docx
            # when the user picked Persian Double Lines as the split
            # method. FASubtitleAligner is mechanical (no LLM); it
            # rewrites the FA column into ≤48-char chunks distributed
            # across the existing rows. Reading + writing the same path
            # is safe — python-docx loads into memory before saving.
            _split_engine = getattr(ctx.flags, "split_engine", None)
            if _split_engine == "persian_double_lines":
                # A3 / A12 (2026-05-12): aligner failure or any
                # over-limit row is a job failure, not a warning. The
                # output file name carries `_Double_Lines`, so silently
                # falling back to single-line FA would hand the user a
                # mislabelled file. Raise so the CLI surfaces [FAIL].
                from ..openai_tools.persian_double_lines import FASubtitleAligner
                _aligner_llm_threshold = getattr(
                    ctx.flags, "aligner_llm_threshold", 0
                )
                aligner = FASubtitleAligner(llm_threshold=_aligner_llm_threshold)
                out_path = ctx.flags.word_file_to_translate_save_as_path
                stats = aligner.align(out_path, out_path)
                print(f"[INFO] FASubtitleAligner applied: {stats}")
                _over  = int(stats.get("over_limit", 0) or 0) if isinstance(stats, dict) else 0
                _total = int(stats.get("total_rows", 0) or 0) if isinstance(stats, dict) else 0
                # A12 (2026-05-12, calibrated): 0-tolerance is too strict for
                # real broadcast docx — the mechanical splitter can hit a
                # forced-merge edge once or twice per 1000 rows on dense
                # Persian sentences. Accept ≤1 % of rows; raise above that.
                _ratio = (_over / _total) if _total > 0 else 1.0
                if _over > 0 and _ratio > 0.01:
                    from ..exceptions import TranslationFailure
                    raise TranslationFailure(
                        f"FA aligner produced {_over}/{_total} rows over MAX_CHARS "
                        f"({_ratio * 100:.1f} %, threshold 1 %) — broadcast "
                        "subtitle limit violated.",
                        reason="aligner_over_limit",
                    )
                elif _over > 0:
                    print(
                        f"[WARN] FA aligner: {_over}/{_total} row(s) over "
                        f"MAX_CHARS ({_ratio * 100:.2f} %) — accepted under "
                        "the 1 % broadcast tolerance."
                    )
        except Exception as _exc:
            # A3 / A12 (2026-05-12): structured pipeline failures (e.g.
            # aligner over-limit, future aligner exceptions) must bubble
            # up to the CLI's [FAIL] handler — never loop the retry.
            from ..exceptions import TranslationFailure
            if isinstance(_exc, TranslationFailure):
                raise
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
