"""Polisher output-parsing and English-residue detection tests.

We construct an OpenAIPolisher instance without running its real __init__
(which requires OPENAI_API_KEY) — the methods under test do not touch
the OpenAI client.
"""
from machine_translate_docx.openai_tools.polisher import OpenAIPolisher


def _make_polisher() -> OpenAIPolisher:
    p = OpenAIPolisher.__new__(OpenAIPolisher)
    p.model = "gpt-5.5"
    p.last_call_data = {}
    return p


def test_parse_tag_format_primary():
    p = _make_polisher()
    raw = "⟨⟨1⟩⟩ خط اول\n⟨⟨2⟩⟩ خط دوم"
    out = p._parse_output(raw, ["", ""])
    assert out == ["خط اول", "خط دوم"]


def test_parse_legacy_line_format_fallback():
    p = _make_polisher()
    raw = "Line 1: aaa\nLine 2: bbb"
    out = p._parse_output(raw, ["", ""])
    assert out == ["aaa", "bbb"]


def test_detect_en_residue_flags_full_english_sentence():
    # >40% latin and >5 words → flagged.
    text = "This row was returned in English by mistake from the model"
    assert OpenAIPolisher._detect_en_residue(text) is True
    # Pure Persian → not flagged.
    assert OpenAIPolisher._detect_en_residue("این یک خط فارسی کامل است") is False
    # Short whitelist-style token (acronym) → not flagged.
    assert OpenAIPolisher._detect_en_residue("AI") is False
    # Empty / whitespace → not flagged.
    assert OpenAIPolisher._detect_en_residue("") is False
    assert OpenAIPolisher._detect_en_residue("   ") is False


def test_fa_postprocess_normalize_safe_subset():
    from machine_translate_docx.openai_tools.fa_postprocess import normalize_fa
    # Arabic Yeh / Kaf rewritten to Persian forms.
    assert normalize_fa("كاربرد ي") == "کاربرد ی"
    # Arabic-Indic digits rewritten to Persian-Indic.
    assert normalize_fa("٢٠٢٦") == "۲۰۲۶"
    # TECH_LOCK token left untouched (ASCII digits, ASCII hyphen).
    assert normalize_fa("GPT-4o و H5N1") == "GPT-4o و H5N1"
    # Quotes preserved (HL-11): no « » conversion.
    assert normalize_fa('گفت "سلام"') == 'گفت "سلام"'
    # ZWNJ untouched.
    assert normalize_fa("می‌گوید") == "می‌گوید"
    # Idempotent.
    once = normalize_fa("كاربرد ي ٢٠٢٦")
    assert normalize_fa(once) == once
