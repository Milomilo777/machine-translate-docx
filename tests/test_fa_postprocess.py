"""T-1 (2026-05-11 audit) — unit tests for ``openai_tools.fa_postprocess``.

The module is pure and tiny: three character-set normalisations applied
via a single ``str.translate`` table. These tests pin the four hardlocks
the docstring promises (idempotence, ASCII untouched, ZWNJ untouched,
spacing untouched) so future refactors can't silently widen the scope.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from machine_translate_docx.openai_tools.fa_postprocess import normalize_fa  # noqa: E402


# ── Letter normalisations ────────────────────────────────────────────────


def test_arabic_yeh_becomes_persian_yeh():
    # ي (U+064A) → ی (U+06CC)
    assert normalize_fa("ي") == "ی"
    assert normalize_fa("ساعتي") == "ساعتی"


def test_arabic_kaf_becomes_persian_kaf():
    # ك (U+0643) → ک (U+06A9)
    assert normalize_fa("ك") == "ک"
    assert normalize_fa("كتاب") == "کتاب"


def test_no_change_to_already_persian_letters():
    assert normalize_fa("ی") == "ی"
    assert normalize_fa("ک") == "ک"
    # Round trip.
    assert normalize_fa(normalize_fa("ساعتي")) == "ساعتی"


# ── Digit normalisations ────────────────────────────────────────────────


def test_arabic_digits_become_persian_digits():
    # ٠..٩ (U+0660..U+0669) → ۰..۹ (U+06F0..U+06F9)
    arabic = "".join(chr(0x0660 + i) for i in range(10))
    persian = "".join(chr(0x06F0 + i) for i in range(10))
    assert normalize_fa(arabic) == persian


def test_persian_digits_unchanged():
    assert normalize_fa("۰۱۲۳۴۵۶۷۸۹") == "۰۱۲۳۴۵۶۷۸۹"


def test_ascii_digits_unchanged_inside_latin_tokens():
    # The HARDLOCK: GPT-4o must stay GPT-4o. hazm would rewrite this.
    assert normalize_fa("GPT-4o") == "GPT-4o"
    assert normalize_fa("ChatGPT 4.5 mini") == "ChatGPT 4.5 mini"


def test_ascii_digits_unchanged_in_persian_text():
    src = "نسخهٔ 12 از این برنامه"
    # Only the Arabic Yeh in "نسخهٔ" stays the same — wait, "نسخهٔ" is
    # already Persian. The 12 is ASCII and must remain ASCII.
    assert normalize_fa(src) == src


# ── HARDLOCK: untouched zones ────────────────────────────────────────────


def test_zwnj_untouched():
    # ZWNJ (U+200C) is a structural marker between morphemes.
    src = "می‌روم به مدرسه"
    assert normalize_fa(src) == src


def test_whitespace_untouched():
    src = "  این  متن   دو  فاصله دارد  "
    assert normalize_fa(src) == src


def test_quotes_and_punctuation_untouched():
    src = '"hello" — \'world\' [۲۰۲۶]'
    assert normalize_fa(src) == src


def test_harakat_untouched():
    # Persian harakat / diacritics live in U+064B..U+0652. They must
    # round-trip unchanged per HL-9 in the polish prompt.
    src = "دَر اَفسانهٔ تَنبَل"
    assert normalize_fa(src) == src


# ── Edge cases ───────────────────────────────────────────────────────────


def test_empty_input_returns_empty():
    assert normalize_fa("") == ""


def test_none_returns_none():
    # The implementation guards against None at the top of the function.
    assert normalize_fa(None) is None  # type: ignore[arg-type]


def test_idempotent_on_mixed_input():
    src = "ساعتي 12 ٤ و كتاب می‌گوید"
    once = normalize_fa(src)
    twice = normalize_fa(once)
    assert once == twice
    # And the actual content:
    expected = "ساعتی 12 ۴ و کتاب می‌گوید"
    assert once == expected
