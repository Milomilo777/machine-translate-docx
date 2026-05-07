"""Translator utility-function tests — language code normalization."""
from openai_tools.translator import _normalize_lang, _prompt_lang_code
from openai_tools._retry import prompt_hash


def test_lang_normalization_roundtrip():
    # English aliases collapse to the ISO 639-1 code.
    assert _normalize_lang("Persian") == "fa"
    assert _normalize_lang("Farsi") == "fa"
    assert _normalize_lang("FA-IR") == "fa"
    assert _normalize_lang("fa_ir") == "fa"
    # ISO 639-1 → ISO 639-2/B for prompt filename lookup.
    assert _prompt_lang_code("fa") == "PER"
    assert _prompt_lang_code("Persian") == "PER"
    # Unmapped language → fall through unchanged.
    assert _prompt_lang_code("xx") == "xx"


def test_prompt_hash_is_deterministic_and_short():
    h1 = prompt_hash("the system prompt body")
    h2 = prompt_hash("the system prompt body")
    h3 = prompt_hash("a different prompt body")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 8
    assert prompt_hash("") == "00000000"
