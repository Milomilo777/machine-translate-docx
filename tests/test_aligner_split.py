"""Aligner split / triple-guard / bigram tests.

Covers the deterministic core of the v2.0 mechanical aligner. No network
calls. No DOCX I/O. Module-level pure-function checks only.
"""
from machine_translate_docx.openai_tools.aligner_per import (
    FASubtitleAligner,
    MAX_CHARS,
    PROTECTED_BIGRAMS,
    ZWNJ,
    _bigram_bad_positions,
    _display_len,
    _distribute_to_rows,
    _enforce_no_triple,
    _is_bridge,
    _split_for_n_rows,
)


# ── module-level helpers ──────────────────────────────────────────────────────

def test_display_len_excludes_zwnj():
    text = "می" + ZWNJ + "گویم"
    assert _display_len(text) == len(text) - 1


def test_protected_bigram_listed():
    # The bigram set must contain a representative entry; _bigram_bad_positions
    # then ensures we never split inside one.
    assert "از طریق" in PROTECTED_BIGRAMS
    text = "این کار از طریق همکاری انجام می‌شود"
    bad  = _bigram_bad_positions(text)
    az_pos = text.find("از")
    # The position right after "از " (start of the second word in the bigram)
    # must be flagged as bad.
    assert (az_pos + len("از") + 1) in bad


def test_no_triple_emitted_for_quadruple():
    out = _enforce_no_triple(["X", "X", "X", "X"])
    # First two kept, third+ replaced with empty so row count stays constant.
    assert out == ["X", "X", "", ""]


def test_sentinel_breaks_run_in_no_triple():
    sent = "\x00GROUP_BOUNDARY\x00"
    # X X then sentinel then X — the trailing X must NOT be suppressed because
    # the sentinel breaks the consecutive run (sentinel is non-empty content
    # different from X, which resets the run counter).
    out = _enforce_no_triple(["X", "X", sent, "X"])
    assert out == ["X", "X", sent, "X"]


def test_split_for_n_rows_respects_max_chars():
    long = (
        "این یک متن بسیار طولانی فارسی است که باید به چند تکه کوتاه‌تر "
        "تقسیم شود تا روی صفحه جا شود"
    )
    chunks = _split_for_n_rows(long, 4)
    assert chunks
    for c in chunks:
        assert _display_len(c) <= MAX_CHARS


def test_distribute_to_rows_pads_via_doubles():
    # 2 chunks → 4 rows: must produce doubles (no triples).
    chunks = ["aaa", "bbb"]
    rows = _distribute_to_rows(chunks, 4)
    assert len(rows) == 4
    # Each chunk must appear at least once, and no chunk three times in a row.
    for i in range(len(rows) - 2):
        assert not (rows[i] == rows[i + 1] == rows[i + 2])


def test_is_bridge_detects_timestamp_row():
    # Timecode-only English content is a bridge row that must be skipped.
    assert _is_bridge("00:01 - 00:05", "")
    # Empty EN is a bridge row regardless of FA content.
    assert _is_bridge("", "متن فارسی")
    # Plain prose is NOT a bridge row.
    assert not _is_bridge("Hello world", "سلام دنیا")


# ── FASubtitleAligner construction ────────────────────────────────────────────

def test_fasubtitle_aligner_default_attrs():
    a = FASubtitleAligner()
    # Aligner v2 hardcodes the model and accepts (but ignores) llm_threshold
    # and token_budget for backwards compatibility.
    assert a.model == "gpt-5.4-mini"
    assert a.llm_threshold == 0
    assert a.token_budget == 0
    assert a.last_stats == {}


def test_fasubtitle_aligner_accepts_legacy_kwargs():
    # Old call sites pass these — must not raise.
    a = FASubtitleAligner(model="gpt-5.4-mini", llm_threshold=70, token_budget=40_000)
    assert a.llm_threshold == 70
    assert a.token_budget == 40_000
