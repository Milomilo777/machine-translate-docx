"""Translator utility-function tests — language code normalization."""
from openai_tools.translator import _normalize_lang, _prompt_lang_code


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
