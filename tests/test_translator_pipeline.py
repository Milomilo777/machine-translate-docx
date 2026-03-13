# pylint: disable=all
import pytest
from unittest.mock import MagicMock, patch
import json
import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from openai_translator.translator import OpenAITranslator

@pytest.fixture
def mock_translator():
    with patch('openai_translator.translator.OpenAI') as mock_openai:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            translator = OpenAITranslator()
            # Mock the client
            translator.client = MagicMock()
            return translator

def test_align_text_metadata_keys_stripped(mock_translator):
    # Mock API to return JSON with _split_reasoning, _merge_reasoning, L1..L5
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "_split_reasoning": "some reason",
        "_merge_reasoning": "another reason",
        "L1": "v1", "L2": "v2", "L3": "v3", "L4": "v4", "L5": "v5"
    })
    mock_translator.client.chat.completions.create.return_value = mock_response

    source_dict = {f"L{i}": f"src{i}" for i in range(1, 6)}
    target_dict = {f"L{i}": f"tgt{i}" for i in range(1, 6)}

    result = mock_translator.align_text("English", "Persian", source_dict, target_dict)

    assert len(result) == 5
    assert not any(k.startswith('_') for k in result.keys())
    assert "L1" in result and "L5" in result

def test_polish_text_blank_lines_preserved(mock_translator):
    # Mock API to return "line1\n\nline2\n\nline3" (3 content + 2 blank)
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "line1\n\nline2\n\nline3"
    mock_translator.client.chat.completions.create.return_value = mock_response

    # Patch repair_lines to capture its inputs
    with patch.object(OpenAITranslator, 'repair_lines', wraps=OpenAITranslator.repair_lines) as mock_repair:
        source_dict = {"L1": "s1", "L2": "s2", "L3": "s3"}
        target_dict = {"L1": "t1", "L2": "t2", "L3": "t3"}

        mock_translator.polish_text("English", "Persian", source_dict, target_dict)

        # ASSERT: repair_lines receives list of length 5, not 3
        mock_repair.assert_called_once()
        args, kwargs = mock_repair.call_args
        output_lines = args[1]
        assert len(output_lines) == 5
        assert output_lines == ["line1", "", "line2", "", "line3"]

        # ASSERT: warn != "FAILED" (since 5 - 3 = 2, diff is 2 <= 10, not FAILED)
        _, warn = OpenAITranslator.repair_lines(args[0], args[1], args[2], fallback=kwargs.get('fallback', None))
        assert warn != "FAILED"

def test_polish_text_lines_count_injected(mock_translator):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "line1\nline2"
    mock_translator.client.chat.completions.create.return_value = mock_response

    # We must patch _get_prompt so it returns something with {lines_count}
    with patch.object(mock_translator, '_get_prompt', return_value="Prompt with {lines_count} lines"):
        source_dict = {f"L{i}": f"s{i}" for i in range(42)}
        target_dict = {f"L{i}": f"t{i}" for i in range(42)}

        mock_translator.polish_text("English", "Persian", source_dict, target_dict)

        # Capture the system prompt sent to the API
        call_args = mock_translator.client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        system_content = next(m['content'] for m in messages if m['role'] == 'system')

        # ASSERT: "{lines_count}" NOT in captured prompt
        assert "{lines_count}" not in system_content
        # ASSERT: "42" IS in captured prompt
        assert "42" in system_content

def test_repair_lines_pads_with_persian():
    result, warn = OpenAITranslator.repair_lines(
        source_lines=["English A", "English B", "English C"],
        output_lines=["فارسی یک", "فارسی دو"],
        context="Polish",
        fallback=["فارسی الف", "فارسی ب", "فارسی پ"]
    )
    assert len(result) == 3
    # ASSERT: result[2] == "فارسی پ"   (not "English C")
    assert result[2] == "فارسی پ"

def test_build_translation_prompt_all_vars_injected(mock_translator):
    with patch.object(mock_translator, '_get_prompt', return_value="{source_lang} {dest_lang} {lines_count}"):
        result = mock_translator.build_translation_prompt("English", "French", "line1\nline2\nline3")

        # ASSERT: "{source_lang}" NOT in result
        assert "{source_lang}" not in result
        # ASSERT: "{dest_lang}" NOT in result
        assert "{dest_lang}" not in result
        # ASSERT: "{lines_count}" NOT in result
        assert "{lines_count}" not in result
        # ASSERT: "3" in result
        assert "3" in result
