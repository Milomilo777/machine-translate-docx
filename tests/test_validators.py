"""Unit tests for the validator layer.

These tests run WITHOUT any API call. They feed hand-crafted source
+ output line pairs into the validator and assert the expected issue
codes appear (or don't).

The validator is opt-in via MTD_VALIDATOR_ENABLED; these tests set the
env var explicitly so the validator runs deterministically regardless
of the operator's shell environment.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make src/ importable without installing the package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


@pytest.fixture(autouse=True)
def enable_validator(monkeypatch):
    """Force the validator on for every test in this module."""
    monkeypatch.setenv("MTD_VALIDATOR_ENABLED", "1")


# ── Public API ───────────────────────────────────────────────────────────────

def test_disabled_returns_passing_report(monkeypatch):
    """When the env var is unset, the validator must be a no-op."""
    monkeypatch.delenv("MTD_VALIDATOR_ENABLED", raising=False)
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(["Hello"], ["bogus output that should fail"], "fa")
    assert rpt.passed is True
    assert rpt.enabled is False
    assert rpt.issues == []


def test_truthy_values_enable_validator(monkeypatch):
    from machine_translate_docx.validators import is_validator_enabled
    for v in ["1", "true", "TRUE", "yes", "on", "YES"]:
        monkeypatch.setenv("MTD_VALIDATOR_ENABLED", v)
        assert is_validator_enabled(), f"expected truthy: {v!r}"
    for v in ["", "0", "false", "no", "off", "FALSE", "anything-else"]:
        monkeypatch.setenv("MTD_VALIDATOR_ENABLED", v)
        assert not is_validator_enabled(), f"expected falsy: {v!r}"


# ── post_translate ───────────────────────────────────────────────────────────

def _codes(report) -> list[str]:
    return [i.code for i in report.issues]


def test_line_count_mismatch():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["a", "b", "c"],
        translate_output=["الف", "ب"],
        target_lang="fa",
    )
    assert not rpt.passed
    assert "LINE_COUNT_MISMATCH" in _codes(rpt)


def test_blank_position_mismatch():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["Hello", "", "World"],
        translate_output=["سلام", "دنیا", ""],
        target_lang="fa",
    )
    codes = _codes(rpt)
    # Both lines 2 and 3 have a blank-position mismatch.
    assert "BLANK_POSITION_MISMATCH" in codes


def test_persian_bashe_detected():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["OK, I'll check."],
        translate_output=["باشه، بررسی می‌کنم."],
        target_lang="fa",
    )
    assert not rpt.passed
    assert "PERSIAN_BASHE" in _codes(rpt)


def test_persian_bashe_not_a_substring_false_positive():
    """The regex uses word boundaries so 'باشهای' or fragments don't match."""
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["A word."],
        translate_output=["می‌باشهد یک کلمه."],   # 'می‌باشهد' is not 'باشه'
        target_lang="fa",
    )
    # Should NOT flag PERSIAN_BASHE for that fragment.
    assert "PERSIAN_BASHE" not in _codes(rpt)


def test_persian_semicolon_outside_quote():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["A. B."],
        translate_output=["الف؛ ب."],
        target_lang="fa",
    )
    assert "PERSIAN_SEMICOLON_OUTSIDE_QUOTE" in _codes(rpt)


def test_persian_semicolon_inside_quote_is_ok():
    """A '؛' inside a " ... " span is allowed (LS-10 verbatim quote)."""
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["He quoted scripture."],
        translate_output=["گفت: \"همانا؛ هر سختی آسانی است.\""],
        target_lang="fa",
    )
    assert "PERSIAN_SEMICOLON_OUTSIDE_QUOTE" not in _codes(rpt)


def test_toosat_emits_warning_not_error():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["The law was passed by the parliament."],
        translate_output=["این قانون توسط پارلمان تصویب شد."],
        target_lang="fa",
    )
    # Warning, not error — should still pass.
    assert rpt.passed is True
    codes = _codes(rpt)
    assert "TOOSAT_PASSIVE" in codes
    assert all(i.severity == "warning" for i in rpt.issues if i.code == "TOOSAT_PASSIVE")


def test_forbidden_glyph_warning_emoji():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["A line."],
        translate_output=["یک خط ⚠️"],
        target_lang="fa",
    )
    assert not rpt.passed
    assert "FORBIDDEN_GLYPH" in _codes(rpt)


def test_latin_leakage_in_persian_output():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["Visit our website for info."],
        translate_output=["برای website ما به اینترنت بزنید."],
        target_lang="fa",
    )
    assert "LATIN_LEAKAGE" in _codes(rpt)


def test_url_protected_span_preserved():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["Visit https://example.org"],
        translate_output=["به https://example.org مراجعه کنید."],
        target_lang="fa",
    )
    # URL must be preserved — no PROTECTED_SPAN_MISSING.
    assert "PROTECTED_SPAN_MISSING" not in _codes(rpt)


def test_url_protected_span_missing():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["Visit https://example.org"],
        translate_output=["از وب‌سایت ما دیدن کنید."],
        target_lang="fa",
    )
    assert "PROTECTED_SPAN_MISSING" in _codes(rpt)


def test_tech_code_preserved():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["The H5N1 outbreak."],
        translate_output=["شیوع H5N1."],
        target_lang="fa",
    )
    # H5N1 should be allowed by the tech-code mask, and present in output.
    assert "PROTECTED_SPAN_MISSING" not in _codes(rpt)
    assert "LATIN_LEAKAGE" not in _codes(rpt)


def test_literal_backslash_n_preserved():
    from machine_translate_docx.validators import validate_translate_output
    # The literal sequence "\\n" (backslash + n) must survive.
    rpt = validate_translate_output(
        source_lines=["Press \\n to continue."],
        translate_output=["برای ادامه \\n را فشار دهید."],
        target_lang="fa",
    )
    assert "LITERAL_BACKSLASH_N_LOST" not in _codes(rpt)


def test_literal_backslash_n_lost():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["Press \\n to continue."],
        translate_output=["برای ادامه را فشار دهید."],
        target_lang="fa",
    )
    assert "LITERAL_BACKSLASH_N_LOST" in _codes(rpt)


def test_clean_persian_output_passes():
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=[
            "Welcome to Supreme Master TV.",
            "I'm Bounxou from Laos.",
            "",
            "Today's topic is compassion.",
        ],
        translate_output=[
            "خوش آمدید به سوپریم مستر تلویزیون.",
            "من بانخو هستم، اهل لائوس.",
            "",
            "موضوع امروز شفقت است.",
        ],
        target_lang="fa",
    )
    assert rpt.passed is True
    assert rpt.errors() == []


# ── post_polish ──────────────────────────────────────────────────────────────

def test_polish_tag_format_invalid():
    from machine_translate_docx.validators import validate_polish_output
    rpt = validate_polish_output(
        source_lines=["Hello."],
        fa_input_lines=["سلام."],
        polish_output=["سلام."],   # missing ⟨⟨1⟩⟩ prefix
        target_lang="fa",
    )
    assert not rpt.passed
    assert "TAG_FORMAT_INVALID" in _codes(rpt)


def test_polish_tag_number_mismatch():
    from machine_translate_docx.validators import validate_polish_output
    rpt = validate_polish_output(
        source_lines=["Line one.", "Line two."],
        fa_input_lines=["خط یک.", "خط دو."],
        polish_output=["⟨⟨1⟩⟩ خط یک.", "⟨⟨5⟩⟩ خط دو."],   # tag says 5 not 2
        target_lang="fa",
    )
    assert "TAG_NUMBER_MISMATCH" in _codes(rpt)


def test_polish_unexpected_blank_output():
    from machine_translate_docx.validators import validate_polish_output
    rpt = validate_polish_output(
        source_lines=["Hello."],
        fa_input_lines=["سلام."],
        polish_output=["⟨⟨1⟩⟩"],  # blank payload where FA was nonblank
        target_lang="fa",
    )
    assert "UNEXPECTED_BLANK_OUTPUT" in _codes(rpt)


def test_polish_persian_bashe_detected_in_payload():
    from machine_translate_docx.validators import validate_polish_output
    rpt = validate_polish_output(
        source_lines=["OK."],
        fa_input_lines=["باشه."],
        polish_output=["⟨⟨1⟩⟩ باشه."],
        target_lang="fa",
    )
    assert "PERSIAN_BASHE" in _codes(rpt)


def test_polish_clean_output_passes():
    from machine_translate_docx.validators import validate_polish_output
    rpt = validate_polish_output(
        source_lines=["Welcome to Supreme Master TV.", "Visit https://example.org"],
        fa_input_lines=["به سوپریم مستر تلویزیون خوش آمدید.", "از https://example.org دیدن کنید."],
        polish_output=[
            "⟨⟨1⟩⟩ خوش آمدید به سوپریم مستر تلویزیون.",
            "⟨⟨2⟩⟩ از https://example.org دیدن کنید.",
        ],
        target_lang="fa",
    )
    assert rpt.passed is True


def test_polish_protected_url_preserved():
    from machine_translate_docx.validators import validate_polish_output
    rpt = validate_polish_output(
        source_lines=["Visit https://example.org for info."],
        fa_input_lines=["از https://example.org برای اطلاعات دیدن کنید."],
        polish_output=["⟨⟨1⟩⟩ برای اطلاعات از وب‌سایت ما بازدید کنید."],
        # ^ polish dropped the URL — should flag.
        target_lang="fa",
    )
    assert "PROTECTED_SPAN_MISSING" in _codes(rpt)


def test_polish_line_count_mismatch():
    from machine_translate_docx.validators import validate_polish_output
    rpt = validate_polish_output(
        source_lines=["A.", "B.", "C."],
        fa_input_lines=["الف.", "ب.", "ج."],
        polish_output=["⟨⟨1⟩⟩ الف.", "⟨⟨2⟩⟩ ب."],
        target_lang="fa",
    )
    assert not rpt.passed
    assert "LINE_COUNT_MISMATCH" in _codes(rpt)


# ── Smoke test for non-FA target ─────────────────────────────────────────────

def test_non_fa_target_skips_persian_specific_checks():
    """For non-FA targets, Persian-specific lexical checks (باشه, توسط, ؛) are off."""
    from machine_translate_docx.validators import validate_translate_output
    rpt = validate_translate_output(
        source_lines=["He went there."],
        translate_output=["El fue allí."],
        target_lang="es",
    )
    codes = _codes(rpt)
    assert "PERSIAN_BASHE" not in codes
    assert "PERSIAN_SEMICOLON_OUTSIDE_QUOTE" not in codes
    assert "TOOSAT_PASSIVE" not in codes
    # Spanish output should also not trigger LATIN_LEAKAGE — that check is
    # FA-only since the universal target language can legitimately be Latin.
    assert "LATIN_LEAKAGE" not in codes
