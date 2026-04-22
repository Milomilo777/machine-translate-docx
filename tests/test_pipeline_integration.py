import os
import re
import time
import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from docx_translate_polish.pipeline import TranslationPipeline
from docx_translate_polish.core.config import TranslationConfig
from docx_translate_polish.translation.openai_engine import OpenAITranslator

FIXTURE_PATH = "tests/fixtures/sample_3lines.docx"

@pytest.fixture(autouse=True)
def setup_env():
    os.environ["OPENAI_API_KEY"] = "sk-fake-default"
    yield
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]

def test_1_invalid_api_key_surfaces_real_error():
    config = TranslationConfig(
        openai_api_key="sk-invalid-key-for-testing",
        default_model="gpt-5.4-mini",
        reasoning_effort="medium"
    )
    pipeline = TranslationPipeline(config=config)
    errors = []
    def capture(msg): errors.append(msg)

    # We expect an AuthenticationError or similar from the real openai client if we don't mock it,
    # but we want to test our surfacing logic.
    # To be safe and fast, we'll mock the internal client call to raise the error.
    with patch("openai.resources.chat.completions.Completions.create") as mock_create:
        mock_create.side_effect = Exception("AuthenticationError: 401 Unauthorized")

        pipeline.run(
            input_path=FIXTURE_PATH,
            src_lang="en", dest_lang="fa",
            progress_callback=capture
        )

    # ASSERT: at least one error message contains "ERROR" or "AuthenticationError"
    assert any("ERROR" in e or "AuthenticationError" in e for e in errors), \
        f"Expected error in log. Got: {errors}"

def test_2_output_filename_contains_timestamp():
    # Mock translator to return successful response
    mock_response_json = {
        "model": "gpt-5.4-mini",
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
        "choices": [{"message": {"content": "Line 1: ترجمه ۱\nLine 2: ترجمه ۲\nLine 3: ترجمه ۳"}}]
    }
    mock_translated_text = "ترجمه ۱\nترجمه ۲\nترجمه ۳"

    with patch("docx_translate_polish.translation.openai_engine.OpenAITranslator.translate") as mock_translate:
        mock_translate.return_value = (mock_response_json, mock_translated_text)

        config = TranslationConfig(openai_api_key="sk-fake", default_model="gpt-5.4-mini")
        pipeline = TranslationPipeline(config=config)
        output = pipeline.run(
            input_path=FIXTURE_PATH,
            src_lang="en", dest_lang="fa"
        )

    assert re.search(r"_PER_\d{8}_\d{6}\.docx$", output), \
        f"Expected timestamp in filename. Got: {output}"
    assert os.path.exists(output), f"Output file not created: {output}"
    # Cleanup
    if os.path.exists(output): os.remove(output)
    # Also cleanup log file
    log_file = output.replace(".docx", ".pipeline-log.json")
    if os.path.exists(log_file): os.remove(log_file)

def test_3_reasoning_effort_is_passed_to_api():
    captured_calls = []

    def mock_create(**kwargs):
        captured_calls.append(kwargs)
        # Raise to trigger the retry/failure path so we don't need full response mock
        raise Exception("Simulated API failure")

    with patch("openai.resources.chat.completions.Completions.create", side_effect=mock_create):
        config = TranslationConfig(
            openai_api_key="sk-fake",
            default_model="gpt-5.4-mini",
            reasoning_effort="high"
        )
        translator = OpenAITranslator(
            model=config.default_model,
            reasoning_effort=config.reasoning_effort,
            api_key=config.openai_api_key
        )
        try:
            translator.translate("en", "fa", "Line 1: Hello\nLine 2: World")
        except Exception:
            pass

    # ASSERT: First call included reasoning_effort="high"
    assert captured_calls[0].get("reasoning_effort") == "high", \
        f"reasoning_effort not passed to API. Calls: {captured_calls}"

def test_4_two_consecutive_runs_produce_two_different_files():
    mock_response_json = {"usage": {"prompt_tokens": 0, "completion_tokens": 0}, "choices": []}
    mock_translated_text = "ترجمه ۱\nترجمه ۲\nترجمه ۳"

    with patch("docx_translate_polish.translation.openai_engine.OpenAITranslator.translate") as mock_translate:
        mock_translate.return_value = (mock_response_json, mock_translated_text)

        config = TranslationConfig(openai_api_key="sk-fake", default_model="gpt-5.4-mini")
        p = TranslationPipeline(config=config)
        out1 = p.run(input_path=FIXTURE_PATH, src_lang="en", dest_lang="fa")

        # Ensure at least 1 second passes for different timestamp
        time.sleep(1.1)

        p2 = TranslationPipeline(config=config)
        out2 = p2.run(input_path=FIXTURE_PATH, src_lang="en", dest_lang="fa")

    assert out1 != out2, f"Both runs produced same filename: {out1}"

    # Cleanup
    for f in [out1, out2]:
        if os.path.exists(f): os.remove(f)
        lf = f.replace(".docx", ".pipeline-log.json")
        if os.path.exists(lf): os.remove(lf)
