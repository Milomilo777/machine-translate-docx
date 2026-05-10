"""ChatGPT API engine — single-call mode.

Thin wrapper around :class:`openai_tools.OpenAITranslator` and
:class:`openai_tools.OpenAIPolisher`. Translates the entire document in
ONE OpenAI call (and optionally polishes in one more), instead of looping
over per-block translations.

The block-loop orchestrator (``selenium_chrome_translate_maxchar_blocks``)
plus the per-block polish path remain in the entry script — they
dispatch across multiple engines (DeepL, Google, etc.) and splitting
the orchestrator is a separate phase.

PROGRESS markers (R7, R14)
--------------------------
The single-call path emits ``PROGRESS:15``, ``PROGRESS:30``, and
``PROGRESS:65`` (when polish runs) at the points the launcher's stdout
parser expects. These marker values, their order, and ``flush=True`` are
contractual with ``local_launcher.py``. Do not change them.

The remaining ``PROGRESS:75``, ``PROGRESS:90``, ``PROGRESS:100`` markers
fire in the entry script's save-and-align section, NOT here.

Reasoning-effort policy (R13)
------------------------------
This module never sets ``reasoning_effort``. The translator never sets
it (it caused 94% reasoning-token overhead in testing). The polisher
sets it only when ``"mini"`` is in the model name, and that decision
lives inside ``openai_tools/polisher.py`` — this module is a thin
wrapper and does not duplicate the rule.
"""
from __future__ import annotations

import time
from typing import Any

__all__ = [
    "run_openai_single_call",
]


def run_openai_single_call(
    *,
    oai_translator: Any,
    oai_polisher:   Any,                        # may be None — polish is optional
    full_source:    str,
    src_lang_name:  str,
    dest_lang_name: str,
    translation_log: dict,
) -> str:
    """Run translate + (optional) polish over the full document in one call.

    Returns the final translated text. Caller is expected to append it to
    ``translated_blocks`` and skip the per-block loop.

    ``translation_log`` is mutated in place: when polish is enabled, a
    block-shaped record is appended to ``translation_log["blocks"]`` so
    that ``write_translation_log`` sees the same shape as the block-loop
    path (R14).

    PROGRESS markers fire from inside this function — keep them here so
    the markers travel with the engine code.
    """
    total_lines = len(full_source.split("\n"))
    print(
        f"[INFO] OpenAI single-call mode: {total_lines} lines, "
        f"{len(full_source)} chars"
    )
    # PROGRESS:15 — file parsed, prompts loaded, ready to call OpenAI.
    print("PROGRESS:15", flush=True)

    _t_translate_start = time.time()
    _, full_translated = oai_translator.translate(
        src_lang_name, dest_lang_name, full_source
    )
    _t_translate = time.time() - _t_translate_start
    print("PROGRESS:30", flush=True)

    _td = oai_translator.last_call_data
    print(
        f"[TIMER] Translate: {_t_translate:.1f}s | "
        f"tokens: {_td.get('total_tokens', '?')} "
        f"(prompt {_td.get('prompt_tokens', '?')}, "
        f"completion {_td.get('completion_tokens', '?')}, "
        f"cached {_td.get('cached_tokens', 0)})"
    )

    # Phase 11 — line-count reconciler. The translator occasionally
    # returns N+1 (or N-1) lines for an N-line source; before phase 11
    # the polisher and the downstream cell writer would silently absorb
    # that drift. The reconciler asks gpt-5.4-mini up to two times for
    # an exact line-aligned re-emission, then pad/truncates if the LLM
    # cannot match. Polish runs AFTER this so it sees correctly-aligned
    # input.
    _src_line_count = len(full_source.split("\n"))
    _tr_line_count  = len(full_translated.split("\n"))
    if _tr_line_count != _src_line_count:
        from openai_tools.line_count_reconciler import reconcile_line_count
        print(
            f"[reconciler] line count mismatch: src={_src_line_count} "
            f"tr={_tr_line_count} — reconciling via gpt-5.4-mini"
        )
        reconciled = reconcile_line_count(
            full_source.split("\n"),
            full_translated.split("\n"),
            src_lang_name,
            dest_lang_name,
        )
        full_translated = "\n".join(reconciled)

    if oai_polisher is None:
        return full_translated

    print("[INFO] Polish pass (full document in one call) ...")
    _t_polish_start = time.time()
    _before_polish = full_translated
    full_translated = oai_polisher.polish(full_source, full_translated)
    _t_polish = time.time() - _t_polish_start
    print("PROGRESS:65", flush=True)

    _pd = oai_polisher.last_call_data
    print(
        f"[TIMER] Polish:    {_t_polish:.1f}s | "
        f"tokens: {_pd.get('total_tokens', '?')} "
        f"(prompt {_pd.get('prompt_tokens', '?')}, "
        f"completion {_pd.get('completion_tokens', '?')}, "
        f"cached {_pd.get('cached_tokens', 0)})"
    )

    _lines_before = _before_polish.split("\n")
    _lines_after  = full_translated.split("\n")
    _changed = sum(
        1 for a, b in zip(_lines_before, _lines_after) if a != b
    )
    if full_translated == _before_polish:
        print("[DIAG] Polish: NO CHANGE (check for API error above)")
    else:
        print(
            f"[DIAG] Polish: {_changed}/{len(_lines_before)} lines changed ✓"
        )

    translation_log.setdefault("blocks", []).append({
        "block_index":  0,
        "source_text":  full_source,
        "translation":  oai_translator.last_call_data.copy(),
        "polish":       oai_polisher.last_call_data.copy(),
    })

    return full_translated
