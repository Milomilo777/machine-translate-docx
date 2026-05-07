"""Aligner split / triple-guard / content-type tests.

These cover the deterministic core that runs without an OpenAI client.
No network calls. No DOCX I/O. Pure-function checks only.
"""
from openai_tools.aligner_per import (
    FASubtitleAligner,
    MAX_CHARS,
    PROTECTED_BIGRAMS,
    ZWNJ,
    _BREAK_RATIO_BY_TYPE,
    _BUILTIN_CUES,
    _display_len,
)


def _make_aligner() -> FASubtitleAligner:
    """Construct an aligner without touching the OpenAI client / cues file."""
    a = FASubtitleAligner.__new__(FASubtitleAligner)
    a.model         = "gpt-5.4-mini"
    a.llm_threshold = 0
    a.token_budget  = 40_000
    a.tokens_used   = 0
    a.last_stats    = {}
    a.client        = None
    a._cues         = _BUILTIN_CUES
    return a


def test_display_len_excludes_zwnj():
    text = "می" + ZWNJ + "گویم"
    assert _display_len(text) == len(text) - 1


def test_protected_bigram_listed():
    # Sanity check the bigram set exists and contains a representative entry.
    # _bigram_bad_positions then ensures we never split inside one.
    assert "از طریق" in PROTECTED_BIGRAMS
    a = _make_aligner()
    text = "این کار از طریق همکاری انجام می‌شود"
    bad  = a._bigram_bad_positions(text)
    # Position right after "از" (i.e. the space inside "از طریق") must be marked.
    az_pos = text.find("از")
    assert (az_pos + len("از") + 1) in bad


def test_no_triple_emitted_for_quadruple():
    a = _make_aligner()
    out = a._enforce_no_triple(["X", "X", "X", "X"])
    # First two kept, third+ replaced with empty so row count stays constant.
    assert out == ["X", "X", "", ""]


def test_sentinel_breaks_run_in_no_triple():
    a = _make_aligner()
    sent = "\x00GROUP_BOUNDARY\x00"
    # X X then sentinel then X — the trailing X must NOT be suppressed because
    # the sentinel breaks the consecutive run.
    out = a._enforce_no_triple(["X", "X", sent, "X"])
    assert out == ["X", "X", sent, "X"]


def test_max_chars_hard_limit_after_split():
    a = _make_aligner()
    long = "این یک متن بسیار طولانی فارسی است که باید به چند تکه کوتاه‌تر تقسیم شود تا روی صفحه جا شود"
    chunks = a._split_distinct(long, 4)
    for c in chunks:
        assert _display_len(c) <= MAX_CHARS


def test_break_ratio_table_complete():
    # The five known content types must all have an entry. Missing one would
    # silently fall back to the default ratio.
    expected = {"narration", "spiritual", "news_attr", "dialogue", "ingredient"}
    assert set(_BREAK_RATIO_BY_TYPE.keys()) == expected
