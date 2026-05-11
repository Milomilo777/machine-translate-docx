"""Block-loop translation runner.

The block-loop orchestrator iterates ``ctx.docx.blocks_nchar_max_to_translate_array``
and dispatches each block to the active engine. Two parallel paths:

  * **OpenAI single-call** (``ctx.engine.engine == "chatgpt"`` and
    ``ctx.engine.method == "api"``) — the entire document is translated
    in ONE OpenAI call (and optionally polished in one more). PROGRESS
    markers ``15``, ``30``, ``65`` fire from
    :func:`engines.chatgpt_api.run_openai_single_call`.

  * **Block loop** (every other engine) — per-block dispatch via the
    legacy ``translate_once`` shim, with recursive splitting on failure
    and a Google last-resort fallback. PROGRESS markers
    ``25``, ``50``, ``75`` fire from this module proportional to the
    number of blocks completed.

R7 + R14 contract
-----------------
PROGRESS marker order, values, and ``flush=True`` are unchanged.
``local_launcher.py`` parses these from stdout to drive the UI progress
bar; modifying them silently breaks the launcher contract.
"""
from __future__ import annotations

import datetime as _dt

from .runtime import RuntimeContext
from .config import DEFAULT_AI_MODEL

from .engines.chatgpt_api import run_openai_single_call
from .engines.google import (
    selenium_chrome_google_click_cookies_consent_button,
    selenium_chrome_google_translate,
)
from .engines.deepl import selenium_chrome_deepl_translate

from .openai_tools import OpenAITranslator, OpenAIPolisher

__all__ = ["selenium_chrome_translate_maxchar_blocks"]


def selenium_chrome_translate_maxchar_blocks(
    ctx: RuntimeContext,
    selenium_webservice_perplexity_translate=None,
):
    """Run the block-loop pipeline over ``ctx.docx.blocks_nchar_max_to_translate_array``.

    Returns ``(translation_succeded, translation_array)``.

    ``selenium_webservice_perplexity_translate`` is injected by the
    caller so this module does not have to import the entry script
    (which has a hyphenated filename and is not importable). Pass the
    helper from the entry script's namespace.
    """
    translation_succeded = True
    translated_blocks = []

    # ── engine-agnostic single attempt ──────────────────────────────────────
    def translate_once(engine, method, text, attempt):
        if engine == "deepl":
            return selenium_chrome_deepl_translate(ctx, text, attempt)

        if engine == "google":
            # Google Translate: textarea path. The underlying helper
            # returns a plain string (possibly empty) — wrap it into the
            # ``(success, translated)`` shape the runner expects. Both
            # ``phrasesblock`` and ``singlephrase`` flow through here;
            # the difference is the size of ``text`` passed in.
            translated = selenium_chrome_google_translate(ctx, text)
            success = bool(translated and translated.strip())
            return success, translated

        if engine == "chatgpt":
            if method == "api":
                response, translated = ctx.openai.translator.translate(
                    ctx.language.src_lang_name, ctx.language.dest_lang_name, text
                )
                success = (
                    translated
                    and len(translated.split("\n")) == len(text.split("\n"))
                )
                return success, translated
            raise ValueError(
                f"chatgpt method '{method}' not supported (supported: api)"
            )

        if engine == "perplexity":
            if method == "webservice":
                if selenium_webservice_perplexity_translate is None:
                    raise ValueError(
                        "perplexity webservice helper not provided to runner"
                    )
                return selenium_webservice_perplexity_translate(ctx, text, attempt)
            raise ValueError(
                f"perplexity method '{method}' not supported (supported: webservice)"
            )

        raise ValueError(f"Unknown translation engine: {engine}")

    # ── recursive split-and-retry algorithm ─────────────────────────────────
    def translate_lines_block(lines, engine, method, attempt=1):
        if not lines:
            return ""

        joined = "\n".join(lines)
        success, translated = translate_once(engine, method, joined, attempt)

        if success and translated:
            return translated.strip()

        # Split block if possible
        if len(lines) > 1:
            mid = len(lines) // 2
            print(f"Splitting block of {len(lines)} lines...")
            left  = translate_lines_block(lines[:mid], engine, method, attempt)
            right = translate_lines_block(lines[mid:], engine, method, attempt)
            return (left + "\n" + right).strip()

        # Single-line fallback
        line = lines[0]
        print(f"Single-line fallback: {line}")

        success, translated = translate_once(engine, method, line, attempt)
        if success and translated:
            return translated.strip()

        # Google last-resort fallback for genuine engines (deepl,
        # perplexity webservice, chatgpt api). The web-LLM gate that
        # existed here was removed when chatgpt-web / perplexity-web
        # were deleted from the codebase.
        selenium_chrome_google_click_cookies_consent_button(ctx)
        translated = selenium_chrome_google_translate(ctx, line)
        if translated:
            return translated.strip()

        print(f"ERROR: Unable to translate line: {line}")
        return "Unable to get translation."

    # ── ChatGPT API setup ───────────────────────────────────────────────────
    if ctx.engine.engine == "chatgpt" and ctx.engine.method == "api":
        ai_model = ctx.flags.aimodel if ctx.flags.aimodel else DEFAULT_AI_MODEL
        ctx.openai.translator = OpenAITranslator(model=ai_model)
        ctx.openai.translator.set_filename(ctx.flags.word_file_to_translate)

        if ctx.flags.with_polish:
            try:
                ctx.openai.polisher = OpenAIPolisher(
                    model=ai_model, dest_lang=ctx.language.dest_lang
                )
                print(f"[INFO] Polish pass enabled (model={ai_model}, lang={ctx.language.dest_lang})")
            except FileNotFoundError as _e:
                print(f"[WARN] Polish disabled: {_e}")
                ctx.openai.polisher = None
            ctx.openai.translation_log["run_info"] = {
                "timestamp":   _dt.datetime.now().isoformat(timespec="seconds"),
                "input_file":  ctx.flags.word_file_to_translate,
                "model":       ai_model,
                "source_lang": ctx.language.src_lang,
                "dest_lang":   ctx.language.dest_lang,
                "with_polish": True,
            }
            ctx.openai.translation_log["blocks"] = []

    # ── OpenAI single-call mode ─────────────────────────────────────────────
    _single_call_done = False
    if (ctx.engine.engine == "chatgpt"
            and ctx.engine.method == "api"
            and ctx.openai.translator is not None):
        full_source = "\n".join(ctx.docx.blocks_nchar_max_to_translate_array)
        full_translated = run_openai_single_call(
            oai_translator=ctx.openai.translator,
            oai_polisher=ctx.openai.polisher,
            full_source=full_source,
            src_lang_name=ctx.language.src_lang_name,
            dest_lang_name=ctx.language.dest_lang_name,
            translation_log=ctx.openai.translation_log,
        )
        translated_blocks.append(full_translated)
        _single_call_done = True

    # ── Standard block loop (DeepL, Google, Selenium, all others) ────────────
    if not _single_call_done:
        _progress_blk_emitted: set[int] = set()
        for i, block in enumerate(ctx.docx.blocks_nchar_max_to_translate_array):
            print(
                f"Translating block {i + 1}/"
                f"{len(ctx.docx.blocks_nchar_max_to_translate_array)} "
                f"({len(block)} chars)"
            )

            success, translated = translate_once(
                ctx.engine.engine, ctx.engine.method, block, attempt=0
            )

            if not success:
                if ctx.engine.engine == 'deepl':
                    print("Cleaning up cookies...")
                    ctx.browser.driver.delete_all_cookies()

                print("Initial translation failed → recursive fallback")
                ctx.docx.translation_errors_count += 1
                ctx.browser.deepl_sleep_wait_translation_seconds *= 1.1

                translated = translate_lines_block(
                    block.split("\n"),
                    ctx.engine.engine,
                    ctx.engine.method,
                )

            if ctx.openai.polisher is not None:
                print(
                    f"Polishing block {i + 1}/"
                    f"{len(ctx.docx.blocks_nchar_max_to_translate_array)} ..."
                )
                _translated_before_polish = translated
                translated = ctx.openai.polisher.polish(block, translated)

                _lines_before = _translated_before_polish.split("\n")
                _lines_after  = translated.split("\n")
                _changed = sum(
                    1 for a, b in zip(_lines_before, _lines_after) if a != b
                )
                if translated == _translated_before_polish:
                    print(
                        f"[DIAG] Polish block {i+1}: NO CHANGE "
                        f"(check for API error or line-count mismatch above)"
                    )
                else:
                    print(
                        f"[DIAG] Polish block {i+1}: "
                        f"{_changed}/{len(_lines_before)} lines changed"
                    )

                ctx.openai.translation_log.setdefault("blocks", []).append({
                    "block_index":   i,
                    "source_text":   block,
                    "translation":   ctx.openai.translator.last_call_data.copy() if ctx.openai.translator else {},
                    "polish":        ctx.openai.polisher.last_call_data.copy(),
                })

            translated_blocks.append(translated)

            # PROGRESS:25 / 50 / 75 — block-loop milestones (R7, R14).
            # Single-call path emits its own 15/30/65 and never hits this loop.
            _n_blks = len(ctx.docx.blocks_nchar_max_to_translate_array)
            if _n_blks > 0:
                _blk_pct = int(((i + 1) / _n_blks) * 100)
                for _m in (25, 50, 75):
                    if _blk_pct >= _m and _m not in _progress_blk_emitted:
                        print(f"PROGRESS:{_m}", flush=True)
                        _progress_blk_emitted.add(_m)

            if i % 2 == 1 and ctx.engine.engine in ("chatgpt", "perplexity"):
                print("Cleaning up cookies...")
                ctx.browser.driver.delete_all_cookies()

    # ── Final validation ────────────────────────────────────────────────────
    full_text = "\n".join(translated_blocks)
    ctx.docx.translation_array = full_text.split("\n")

    if ctx.openai.polisher is not None:
        print(
            f"[DIAG] ctx.docx.translation_array ready: "
            f"{len(ctx.docx.translation_array)} lines "
            f"(expected {ctx.docx.docxfile_table_number_of_phrases}) — "
            f"THIS IS THE POLISHED DATA"
        )
        if ctx.docx.translation_array:
            print(f"[DIAG] First line sample: {ctx.docx.translation_array[0][:80]!r}")

    if len(ctx.docx.translation_array) != ctx.docx.docxfile_table_number_of_phrases:
        print(
            f"Line count mismatch: {len(ctx.docx.translation_array)} != "
            f"{ctx.docx.docxfile_table_number_of_phrases}"
        )
        translation_succeded = False

    return translation_succeded, ctx.docx.translation_array
