"""Tests for machine_translate_docx.translation_log_writer.write_translation_log.

Covers all 11 specified cases:
  1.  Empty log → zero summary
  2.  One block translate-only aggregation
  3.  One block translate + polish (lines_modified path)
  4.  Legacy polish-diff fallback (input_fa_text / output_text)
  5.  Two blocks aggregate correctly
  6.  Row-count metadata reflects ctx.docx
  7.  translation_prompts populated when translator has last_system_prompt
  8.  translation_prompts absent when translator is None
  9.  output_file fallback (no ctx.flags path set)
  10. output_file uses ctx.flags when set
  11. JSON is UTF-8 with ensure_ascii=False (Persian text not escaped)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from machine_translate_docx.runtime import RuntimeContext  # noqa: E402
from machine_translate_docx.translation_log_writer import write_translation_log  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_ctx() -> RuntimeContext:
    """Return a clean RuntimeContext with an empty translation_log."""
    ctx = RuntimeContext.empty()
    ctx.openai.translation_log = {"run_info": {}, "blocks": [], "summary": {}}
    return ctx


def _one_block(
    *,
    prompt: int = 100,
    completion: int = 50,
    total: int = 150,
    cached: int = 30,
    cost_usd: float = 0.01,
    elapsed_seconds: float = 1.5,
    polish: dict | None = None,
) -> dict:
    block: dict = {
        "block_index": 0,
        "source_text": "Hello",
        "translation": {
            "tokens": {
                "prompt": prompt,
                "completion": completion,
                "total": total,
                "cached": cached,
            },
            "cost_usd": cost_usd,
            "elapsed_seconds": elapsed_seconds,
        },
    }
    if polish is not None:
        block["polish"] = polish
    return block


def _read_log(log_path: str) -> dict:
    return json.loads(Path(log_path).read_text(encoding="utf-8"))


# ── test 1: empty log → zero summary ─────────────────────────────────────────

def test_empty_log_zero_summary(tmp_path):
    ctx = _make_ctx()
    ctx.openai.translation_log = {"run_info": {}, "blocks": [], "summary": {}}
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)

    assert data["summary"]["total_blocks"] == 0
    assert data["summary"]["total_tokens"]["prompt"] == 0
    assert data["summary"]["row_count"] == 0


# ── test 2: one block translate-only aggregation ──────────────────────────────

def test_one_block_translate_only(tmp_path):
    ctx = _make_ctx()
    ctx.openai.translation_log["blocks"] = [_one_block()]
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)
    s = data["summary"]

    assert s["total_blocks"] == 1
    assert s["total_tokens"]["prompt"] == 100
    assert s["total_cost_usd"] == round(0.01, 6)


# ── test 3: translate + polish with lines_modified path ───────────────────────

def test_one_block_with_polish_lines_modified(tmp_path):
    ctx = _make_ctx()
    polish = {
        "lines_processed": 5,
        "lines_modified": 2,
        "tokens": {"prompt": 80, "completion": 40, "total": 120, "cached": 0},
        "cost_usd": 0.008,
        "elapsed_seconds": 1.0,
    }
    ctx.openai.translation_log["blocks"] = [_one_block(polish=polish)]
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)
    s = data["summary"]

    assert s["polish_lines_touched"] == 2
    assert s["polish_lines_total"] == 5


# ── test 4: legacy polish-diff fallback (no lines_modified) ───────────────────

def test_legacy_polish_diff_fallback(tmp_path):
    ctx = _make_ctx()
    polish = {
        "input_fa_text": "a\nb\nc",
        "output_text": "a\nX\nc",
        # no lines_processed / lines_modified keys
    }
    ctx.openai.translation_log["blocks"] = [_one_block(polish=polish)]
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)
    s = data["summary"]

    # Only the middle line changed ("b" → "X")
    assert s["polish_lines_touched"] == 1
    assert s["polish_lines_total"] == 3


# ── test 5: two blocks aggregate correctly ────────────────────────────────────

def test_two_blocks_aggregate(tmp_path):
    ctx = _make_ctx()
    block1 = _one_block(prompt=100, completion=50, total=150, cached=30,
                        cost_usd=0.01, elapsed_seconds=1.5)
    block2 = _one_block(prompt=200, completion=100, total=300, cached=60,
                        cost_usd=0.02, elapsed_seconds=2.0)
    ctx.openai.translation_log["blocks"] = [block1, block2]
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)
    s = data["summary"]

    assert s["total_blocks"] == 2
    assert s["total_tokens"]["prompt"] == 300        # 100 + 200
    assert s["total_tokens"]["completion"] == 150    # 50 + 100
    assert s["total_tokens"]["total"] == 450         # 150 + 300
    assert s["total_tokens"]["cached"] == 90         # 30 + 60
    assert s["total_cost_usd"] == round(0.03, 6)     # 0.01 + 0.02
    assert abs(s["elapsed_total_seconds"] - round(3.5, 3)) < 1e-9  # 1.5 + 2.0


# ── test 6: row-count metadata from ctx.docx ──────────────────────────────────

def test_row_count_metadata(tmp_path):
    ctx = _make_ctx()
    ctx.docx.from_text_table = ["one", "two", "", "three"]           # 3 nonempty
    ctx.docx.to_text_by_phrase_separator_table = ["x", "", "y", ""]  # 2 nonempty
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)
    s = data["summary"]

    assert s["row_count"] == max(4, 4)  # len of each list is 4
    assert s["source_rows_nonempty"] == 3
    assert s["target_rows_nonempty"] == 2


# ── test 7: translation_prompts populated when translator has last_system_prompt

def test_translation_prompts_populated(tmp_path):
    ctx = _make_ctx()
    ctx.openai.translator = SimpleNamespace(
        last_system_prompt="PROMPT",
        last_user_prompt="USER",
    )
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)
    ri = data["run_info"]

    assert "translation_prompts" in ri
    tp = ri["translation_prompts"]
    assert tp["system_prompt"] == "PROMPT"
    assert tp["user_prompt_sample"] == "USER"
    # prompt_hash must be exactly 8 lowercase hex chars
    assert len(tp["prompt_hash"]) == 8
    assert all(c in "0123456789abcdef" for c in tp["prompt_hash"])


# ── test 8: translation_prompts absent when translator is None ────────────────

def test_translation_prompts_absent_when_no_translator(tmp_path):
    ctx = _make_ctx()
    ctx.openai.translator = None
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)

    assert "translation_prompts" not in data["run_info"]


# ── test 9: output_file fallback when ctx.flags path is None/empty ────────────
#
# Implementation note: the code does
#   _out_docx = ctx.flags.word_file_to_translate_save_as_path or ""
# so when the flag is None the field is stored as "". The docx-path fallback
# (log_path.replace("_log.json", ".docx")) only fires when accessing the flag
# attribute raises an Exception. We test the None → "" path here, which is
# what a fresh RuntimeContext.empty() produces.

def test_output_file_fallback(tmp_path):
    ctx = _make_ctx()
    ctx.flags.word_file_to_translate_save_as_path = None
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)

    # None flag → stored as "" (the `or ""` branch, not the except branch)
    assert data["run_info"]["output_file"] == ""


# ── test 10: output_file uses ctx.flags when set ─────────────────────────────

def test_output_file_from_flags(tmp_path):
    ctx = _make_ctx()
    ctx.flags.word_file_to_translate_save_as_path = "/foo/bar.docx"
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    data = _read_log(log_path)

    assert data["run_info"]["output_file"] == "/foo/bar.docx"


# ── test 11: UTF-8 with ensure_ascii=False (Persian not escaped) ──────────────

def test_utf8_persian_not_escaped(tmp_path):
    ctx = _make_ctx()
    block = _one_block()
    block["source_text"] = "سلام"
    ctx.openai.translation_log["blocks"] = [block]
    log_path = str(tmp_path / "run_log.json")

    write_translation_log(ctx, log_path)
    raw_bytes = Path(log_path).read_bytes()
    raw_text = raw_bytes.decode("utf-8")

    # The Persian word must appear literally, not as \u escape sequences
    assert "سلام" in raw_text
    assert "\\u" not in raw_text or "سلام" in raw_text  # belt-and-suspenders
    # More precise: the actual UTF-8 bytes for س (U+0633) must be present
    assert "سلام".encode("utf-8") in raw_bytes
