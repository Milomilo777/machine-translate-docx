"""JSON sidecar writer for the OpenAI translation/polish translation log.

Extracted from `cli.py` on 2026-05-16 as part of the cli.py shrink phase 3.

The translation log dict (``ctx.openai.translation_log``) is populated
incrementally by the runner / chatgpt_api single-call paths during the
translation + polish passes. This module owns the final
``write_translation_log(ctx, log_path)`` call that:

1. Aggregates per-block token + cost + elapsed totals.
2. Stashes the canonical system prompts ONCE under ``run_info`` (log
   compaction — they used to be repeated inside every block).
3. Enriches ``summary`` with row counts and polish-touched lines so
   the v2 frontend's run-summary card has everything it needs.
4. Writes the resulting dict to ``log_path`` as pretty-printed UTF-8 JSON.

Public API: :func:`write_translation_log`.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .openai_tools._retry import prompt_hash

if TYPE_CHECKING:
    from .runtime import RuntimeContext


__all__ = ["write_translation_log"]


def write_translation_log(ctx: "RuntimeContext", log_path: str) -> None:
    """Write ``ctx.openai.translation_log`` as pretty-printed JSON next to the docx.

    Idempotent: re-running with the same ``log_path`` overwrites the
    sidecar. The ``translation_log`` dict is mutated in place (summary
    + run_info enrichment).
    """
    translation_log = ctx.openai.translation_log
    blocks = translation_log.get("blocks", [])

    total_prompt = 0
    total_completion = 0
    total_total = 0
    total_cached = 0
    total_cost = 0.0
    total_elapsed = 0.0

    for b in blocks:
        for key in ("translation", "polish"):
            call = b.get(key) or {}
            tok = call.get("tokens") or {}
            total_prompt     += tok.get("prompt", 0)
            total_completion += tok.get("completion", 0)
            total_total      += tok.get("total", 0)
            total_cached     += tok.get("cached", 0)
            total_cost       += call.get("cost_usd", 0.0)
            total_elapsed    += call.get("elapsed_seconds", 0.0)

    # 2026-05-13: log_path lives in `Log json file/`; the docx still sits at
    # the user's chosen output location. Resolve it from the live ctx so the
    # run-summary card displays the real docx path, not a sibling under the
    # central log folder.
    try:
        _out_docx = ctx.flags.word_file_to_translate_save_as_path or ""
    except Exception:
        _out_docx = log_path.replace("_log.json", ".docx")
    translation_log["run_info"]["output_file"] = _out_docx

    # 2026-05-15 (log compaction): persist the translator + polisher system
    # prompts ONCE at the run_info level instead of repeating them inside
    # every block's translation/polish dict. The bodies are byte-identical
    # across blocks (v7 STATIC + JOB_CONFIG layout), so per-block storage
    # multiplied log size by `len(blocks)` for zero audit benefit.
    try:
        _tr = getattr(ctx.openai, "translator", None)
        if _tr is not None and getattr(_tr, "last_system_prompt", None):
            translation_log["run_info"]["translation_prompts"] = {
                "system_prompt":         _tr.last_system_prompt,
                "user_prompt_sample":    getattr(_tr, "last_user_prompt", "") or "",
                "prompt_hash":           prompt_hash(_tr.last_system_prompt),
            }
    except Exception as _e:
        print(f"[WARN] Could not stash translator prompts in run_info: {_e!r}")
    try:
        _po = getattr(ctx.openai, "polisher", None)
        if _po is not None and getattr(_po, "system_prompt", None):
            translation_log["run_info"]["polish_prompts"] = {
                "system_prompt":      _po.system_prompt,
                "user_prompt_sample": getattr(_po, "last_user_prompt", "") or "",
                "prompt_hash":        prompt_hash(_po.system_prompt),
            }
    except Exception as _e:
        print(f"[WARN] Could not stash polisher prompts in run_info: {_e!r}")

    # 2026-05-11 (#1 backlog) — enrich the summary with row counts +
    # polish-touched count so the v2 frontend's run-summary card and
    # quality-warning system have everything they need without doing a
    # second pass over the docx.
    _src_rows = ctx.docx.from_text_table or []
    _tgt_rows = ctx.docx.to_text_by_phrase_separator_table or []
    _src_n    = sum(1 for v in _src_rows if v and v.strip())
    _tgt_n    = sum(1 for v in _tgt_rows if v and v.strip())

    # Polish-touched lines: prefer the polisher's own lines_modified count
    # (an honest pre-reconcile figure). The legacy fallback to comparing
    # translation.output_text vs polish.output_text remains for verbose
    # logs that still carry the redundant input_fa_text field.
    _polish_touched_total = 0
    _polish_input_total   = 0
    for b in blocks:
        polish = b.get("polish") or {}
        if "lines_processed" in polish:
            _polish_input_total   += polish.get("lines_processed", 0) or 0
            _polish_touched_total += polish.get("lines_modified",  0) or 0
            continue
        before = (polish.get("input_fa_text") or "").split("\n")
        after  = (polish.get("output_text")  or "").split("\n")
        if not before or not after:
            continue
        n = min(len(before), len(after))
        _polish_input_total += n
        for i in range(n):
            if before[i] != after[i]:
                _polish_touched_total += 1

    translation_log["summary"] = {
        "total_blocks":        len(blocks),
        "total_tokens": {
            "prompt":          total_prompt,
            "completion":      total_completion,
            "total":           total_total,
            "cached":          total_cached,
        },
        "total_cost_usd":      round(total_cost, 6),
        "elapsed_total_seconds": round(total_elapsed, 3),
        "row_count":              max(len(_src_rows), len(_tgt_rows)),
        "source_rows_nonempty":   _src_n,
        "target_rows_nonempty":   _tgt_n,
        "polish_lines_touched":   _polish_touched_total,
        "polish_lines_total":     _polish_input_total,
    }

    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump(translation_log, fh, ensure_ascii=False, indent=2)

    print(f"[INFO] Translation log saved → {log_path}")
