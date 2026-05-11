"""Unit tests for the 2026-05-10 post-test hardening pass.

Covers:

  * **W-3 + B-004** — model-id whitelist in ``config.py``.
  * **B-001** — empty-source / engine-empty health checks in
    ``translation_health.py``.

The B-002 failure-archive code lives in ``local_launcher.py`` and is
exercised by integration / smoke tests rather than unit tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from machine_translate_docx.config import (  # noqa: E402  — sys.path tweak above
    DEFAULT_AI_MODEL,
    ALIGNER_MODEL,
    VALID_AI_MODELS,
    is_valid_ai_model,
)
from machine_translate_docx.exceptions import (  # noqa: E402
    EmptyDocxError,
    EngineReturnedEmptyError,
    TranslationFailure,
)
from machine_translate_docx.runtime import RuntimeContext  # noqa: E402
from machine_translate_docx.translation_health import (  # noqa: E402
    MIN_NONEMPTY_RATIO,
    assert_source_has_content,
    assert_translation_present,
)


# ─────────────────────────────────────────────────────────────────────
# W-3 + B-004 — model-id whitelist
# ─────────────────────────────────────────────────────────────────────


def test_default_ai_model_is_in_whitelist():
    assert DEFAULT_AI_MODEL in VALID_AI_MODELS


def test_aligner_model_is_in_whitelist():
    """C1 in PROJECT_MEMORY.md: aligner is always gpt-5.4-mini.

    The whitelist must include it so the v2 frontend dropdown can
    show it as a valid override without the CLI rejecting it.
    """
    assert ALIGNER_MODEL in VALID_AI_MODELS


def test_is_valid_ai_model_accepts_known():
    assert is_valid_ai_model("gpt-5.5") is True
    assert is_valid_ai_model("gpt-5.4-mini") is True


def test_is_valid_ai_model_rejects_unknown():
    # B-004 reproduction — the exact string a user typed pre-fix.
    assert is_valid_ai_model("gpt-5.5-mini") is False
    assert is_valid_ai_model("gpt-3.5-turbo") is False
    assert is_valid_ai_model("") is False


def test_is_valid_ai_model_treats_none_as_valid():
    """``None`` means "use the default"; the CLI parse layer applies
    the default later — we should not reject None here."""
    assert is_valid_ai_model(None) is True


# ─────────────────────────────────────────────────────────────────────
# B-001 — translation health checks
# ─────────────────────────────────────────────────────────────────────


def _make_ctx_with_source(source_rows, target_rows=None):
    """Tiny RuntimeContext stub with the two parallel arrays we need."""
    ctx = RuntimeContext.empty()
    ctx.docx.numrows = len(source_rows)
    ctx.docx.from_text_table = list(source_rows)
    ctx.docx.to_text_by_phrase_separator_table = (
        list(target_rows) if target_rows is not None else []
    )
    ctx.flags.word_file_to_translate = "test.docx"
    ctx.engine.engine = "chatgpt"
    ctx.engine.method = "api"
    return ctx


def test_assert_source_has_content_passes_when_one_row_has_text():
    ctx = _make_ctx_with_source(["", "hello world", ""])
    # No raise expected.
    assert_source_has_content(ctx)


def test_assert_source_has_content_raises_on_all_empty():
    ctx = _make_ctx_with_source(["", "  ", "\n", ""])
    with pytest.raises(EmptyDocxError) as exc_info:
        assert_source_has_content(ctx)
    assert exc_info.value.reason == "empty_docx"
    # Reason token is structured, message carries human context.
    assert "no translatable text" in str(exc_info.value).lower()


def test_assert_source_has_content_handles_none_table():
    ctx = RuntimeContext.empty()
    ctx.docx.from_text_table = None  # legacy state pre-parse
    with pytest.raises(EmptyDocxError):
        assert_source_has_content(ctx)


def test_assert_translation_present_passes_when_above_threshold():
    """Source has 4 non-empty rows; target has 2. Ratio = 0.5 ≥ 0.30."""
    ctx = _make_ctx_with_source(
        source_rows=["a", "b", "c", "d"],
        target_rows=["A", "", "C", ""],
    )
    assert_translation_present(ctx)  # no raise


def test_assert_translation_present_passes_at_phrase_grouped_baseline():
    """Real-engine fixture pattern: 18 of 40 source rows have a target.

    Ratio 18/40 = 0.45 ≥ MIN_NONEMPTY_RATIO 0.30 — must not flag.
    """
    src = ["x"] * 40
    tgt = ["y"] * 18 + [""] * 22
    ctx = _make_ctx_with_source(src, tgt)
    assert_translation_present(ctx)


def test_assert_translation_present_raises_when_target_empty():
    """Engine returned nothing — every target row blank."""
    ctx = _make_ctx_with_source(
        source_rows=["a", "b", "c"],
        target_rows=["", "", ""],
    )
    with pytest.raises(EngineReturnedEmptyError) as exc_info:
        assert_translation_present(ctx)
    assert exc_info.value.reason == "engine_empty"
    assert "no translation rows" in str(exc_info.value).lower()


def test_assert_translation_present_raises_on_low_ratio():
    """4 source rows, 1 target row (single-row dump bug). 1/4 = 0.25 < 0.30."""
    ctx = _make_ctx_with_source(
        source_rows=["a", "b", "c", "d"],
        target_rows=["DUMP", "", "", ""],
    )
    with pytest.raises(EngineReturnedEmptyError) as exc_info:
        assert_translation_present(ctx)
    assert "too few" in str(exc_info.value).lower()


def test_translation_failure_subclasses_share_base():
    assert issubclass(EmptyDocxError, TranslationFailure)
    assert issubclass(EngineReturnedEmptyError, TranslationFailure)


# ─────────────────────────────────────────────────────────────────────
# Sanity bound on the ratio constant — if someone bumps it above 0.5
# the phrase-grouped DeepL/Google baseline will start tripping on
# normal output.
# ─────────────────────────────────────────────────────────────────────


def test_min_nonempty_ratio_is_below_phrase_grouped_baseline():
    # Phrase-grouped runs hit ~ 0.45 (18/40 in the smoke fixture).
    # The threshold must stay strictly below that or every successful
    # DeepL/Google run will be flagged as engine_empty.
    assert MIN_NONEMPTY_RATIO < 0.45
