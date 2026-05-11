"""Conservative post-processing for polished FA text.

Why a custom helper instead of `hazm.Normalizer`:
  hazm.Normalizer is excellent for general-purpose Persian text but
  breaks several HARDLOCKs of this project when run unsupervised:

  - Inserts spaces around hyphens inside ASCII technical codes
    (`GPT-4o` → `GPT- 4 o`), violating W3 TECH_LOCK in `translate_PER.txt`.
  - Converts ASCII digits inside Latin tokens to Persian digits
    (`GPT-4o` → `GPT-۴o`), violating W3 TECH_LOCK.
  - With `persian_style=True` (default) maps `"..."` → `«...»`,
    violating polish HL-11 (project mandates ASCII quotes for subtitles).
  - Inserts ZWNJ inside multi-word proper nouns (`چینگ های` →
    `چینگ‌های`), violating HL-4 SPIRITUAL_TITLES "byte-for-byte".

What this helper does (and only this):
  1. Arabic Yeh `ي` (U+064A) → Persian Yeh `ی` (U+06CC) — never
     appears legitimately in modern Persian.
  2. Arabic Kaf `ك` (U+0643) → Persian Kaf `ک` (U+06A9) — same.
  3. Arabic-Indic digits `٠-٩` → Persian digits `۰-۹` — both
     scripts share Unicode range pairs:
        ٠ U+0660 → ۰ U+06F0
        ٩ U+0669 → ۹ U+06F9

It does NOT touch:
  - ASCII content (Latin letters, ASCII digits).
  - Existing Persian digits.
  - ZWNJ, spacing, punctuation, quotes.
  - Diacritics (HARAKAT respected per HL-9).

Idempotent. Safe to apply repeatedly.
"""
from __future__ import annotations

# Arabic letter → Persian letter (single-character mappings only)
_LETTER_MAP = {
    'ي': 'ی',  # ي → ی
    'ك': 'ک',  # ك → ک
}

# Arabic-Indic digit (U+0660..U+0669) → Persian digit (U+06F0..U+06F9)
_DIGIT_MAP = {chr(0x0660 + i): chr(0x06F0 + i) for i in range(10)}

_TRANSLATE_TABLE = str.maketrans({**_LETTER_MAP, **_DIGIT_MAP})


def normalize_fa(text: str) -> str:
    """Apply the safe-subset normalization above. Pure / idempotent."""
    if not text:
        return text
    return text.translate(_TRANSLATE_TABLE)
