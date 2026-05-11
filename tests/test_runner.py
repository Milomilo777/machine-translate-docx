"""Mock-based tests for the block-loop runner."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from machine_translate_docx.runtime import RuntimeContext


def _mk_ctx_for_chatgpt_api() -> RuntimeContext:
    ctx = RuntimeContext.empty()
    ctx.engine.engine = "chatgpt"
    ctx.engine.method = "api"
    ctx.language.src_lang_name  = "English"
    ctx.language.dest_lang_name = "Persian"
    ctx.language.src_lang       = "en"
    ctx.language.dest_lang      = "fa"
    ctx.flags.aimodel = "gpt-5.5"
    ctx.flags.with_polish = False
    ctx.flags.word_file_to_translate = "/tmp/test.docx"
    ctx.docx.blocks_nchar_max_to_translate_array = ["hello world\nsecond line"]
    ctx.docx.docxfile_table_number_of_phrases    = 2
    return ctx


def test_runner_chatgpt_api_dispatches_to_single_call_path():
    """ChatGPT + API + translator triggers run_openai_single_call,
    not the block loop."""
    from machine_translate_docx.runner import selenium_chrome_translate_maxchar_blocks

    ctx = _mk_ctx_for_chatgpt_api()
    # Pre-set the translator so the runner skips its own setup.
    fake_translator = MagicMock()
    fake_translator.last_call_data = {"total_tokens": 0}
    ctx.openai.translator = fake_translator

    with patch("machine_translate_docx.runner.run_openai_single_call") as mock_single:
        mock_single.return_value = "salām dunyā\nkhat-e-dovvom"
        succeded, arr = selenium_chrome_translate_maxchar_blocks(ctx)

    mock_single.assert_called_once()
    assert succeded is True
    assert arr == ["salām dunyā", "khat-e-dovvom"]


def test_runner_block_loop_emits_progress_milestones(capsys):
    """Block-loop path emits PROGRESS:25 / 50 / 75 in order."""
    from machine_translate_docx.runner import selenium_chrome_translate_maxchar_blocks

    ctx = RuntimeContext.empty()
    ctx.engine.engine = "deepl"
    ctx.engine.method = "phrasesblock"
    # 4 blocks → after each: 25%, 50%, 75%, 100%.
    ctx.docx.blocks_nchar_max_to_translate_array = [
        "block one",
        "block two",
        "block three",
        "block four",
    ]
    ctx.docx.docxfile_table_number_of_phrases = 4
    ctx.browser.driver = MagicMock()

    with patch("machine_translate_docx.runner.selenium_chrome_deepl_translate") as mock_deepl:
        mock_deepl.return_value = (True, "translated")
        # The runner's translate_once for deepl returns the value as-is
        # (a tuple). The block-loop body unpacks (success, translated)
        # from it.
        selenium_chrome_translate_maxchar_blocks(ctx)

    out = capsys.readouterr().out
    # Markers fire in order. Don't assert exact contiguous strings —
    # just that all three milestones land.
    assert "PROGRESS:25" in out
    assert "PROGRESS:50" in out
    assert "PROGRESS:75" in out
    # And the order is preserved:
    p25 = out.index("PROGRESS:25")
    p50 = out.index("PROGRESS:50")
    p75 = out.index("PROGRESS:75")
    assert p25 < p50 < p75
