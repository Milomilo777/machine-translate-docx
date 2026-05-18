"""Tests for src/machine_translate_docx/openai_tools/_retry.py.

Covers:
  - call_with_retry(fn, *, label="openai")
      * success on first call
      * retries on retryable error then succeeds
      * exhausts MAX_RETRIES on persistent retryable error
      * propagates non-retryable errors immediately
  - prompt_hash(text)
      * deterministic output
      * always 8 hex characters
      * different inputs → different outputs

No network, no OpenAI key, no DOCX file required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from machine_translate_docx.openai_tools._retry import (
    call_with_retry,
    prompt_hash,
    MAX_RETRIES,
    _RETRYABLE,
    _NON_RETRYABLE,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_rate_limit_error() -> Exception:
    """Build a RateLimitError that the retry loop will actually catch.

    The openai SDK requires a real httpx.Response to construct properly,
    so we build a minimal one. Falls back to a plain subclass if the SDK
    is unavailable or the constructor signature changes.
    """
    try:
        import httpx
        from openai import RateLimitError

        req = httpx.Request("GET", "https://api.openai.com")
        resp = httpx.Response(429, request=req)
        return RateLimitError("rate limit hit", response=resp, body=None)
    except Exception:
        # Fallback: create a subclass that passes isinstance checks against
        # _RETRYABLE (which itself falls back to () when openai absent).
        if _RETRYABLE:
            return type("RateLimitError", (_RETRYABLE[0],), {})("rate limit hit")
        return ValueError("rate limit hit (stub)")


# ── call_with_retry ───────────────────────────────────────────────────────────

def test_call_with_retry_success_first_try():
    """Callable returns 'ok'; no retry needed; invoked exactly once."""
    fn = MagicMock(return_value="ok")

    with patch("machine_translate_docx.openai_tools._retry.time.sleep"):
        result = call_with_retry(fn)

    assert result == "ok"
    fn.assert_called_once()


def test_call_with_retry_retries_then_succeeds():
    """Callable raises RateLimitError once, then returns 'ok'.

    Must be invoked exactly twice (1 failure + 1 success) and the
    helper must return 'ok'.
    """
    err = _make_rate_limit_error()
    fn = MagicMock(side_effect=[err, "ok"])

    with patch("machine_translate_docx.openai_tools._retry.time.sleep"), \
         patch("machine_translate_docx.openai_tools._retry.random.uniform", return_value=0.0):
        result = call_with_retry(fn)

    assert result == "ok"
    assert fn.call_count == 2


def test_call_with_retry_max_retries_exhausted_raises():
    """Callable always raises a retryable error.

    After MAX_RETRIES total attempts the helper must re-raise the last
    error. The callable is called exactly MAX_RETRIES times.
    """
    err = _make_rate_limit_error()
    fn = MagicMock(side_effect=err)

    with patch("machine_translate_docx.openai_tools._retry.time.sleep"), \
         patch("machine_translate_docx.openai_tools._retry.random.uniform", return_value=0.0):
        try:
            call_with_retry(fn)
            raised = False
        except Exception as exc:
            raised = True
            caught = exc

    assert raised, "call_with_retry should have re-raised the retryable error"
    assert type(caught) is type(err), (
        f"Expected {type(err).__name__}, got {type(caught).__name__}"
    )
    # The loop runs for range(MAX_RETRIES) — one call per iteration.
    assert fn.call_count == MAX_RETRIES, (
        f"Expected {MAX_RETRIES} total attempts, got {fn.call_count}"
    )


def test_call_with_retry_non_retryable_error_propagates_immediately():
    """Callable raises ValueError (not retryable).

    The error must propagate on the very first call — no sleep, no retry.
    """
    fn = MagicMock(side_effect=ValueError("bad request"))

    with patch("machine_translate_docx.openai_tools._retry.time.sleep") as mock_sleep:
        try:
            call_with_retry(fn)
            raised = False
        except ValueError:
            raised = True

    assert raised, "ValueError should have propagated immediately"
    fn.assert_called_once()
    mock_sleep.assert_not_called()


# ── TEST-D-2 (2026-05-18 audit): pin APITimeoutError policy ──────────────────
#
# Commit fea6115 (2026-05-17) moved APITimeoutError to _NON_RETRYABLE.
# The cost-guard motivation is in `_retry.py` lines 12-19 — a hung call
# bills ~25K output tokens per retry, observed to spiral 6× in FLYIN
# incident. These tests pin the policy so a future maintainer cannot
# silently move it back without the suite failing.

def _make_api_timeout_error() -> Exception:
    """Build an APITimeoutError instance the retry loop will actually catch.

    Falls back to a synthetic subclass if the SDK is unavailable.
    """
    try:
        import httpx  # type: ignore[import-not-found]
        from openai import APITimeoutError
        req = httpx.Request("POST", "https://api.openai.com/v1/responses")
        return APITimeoutError(req)
    except Exception:
        if _NON_RETRYABLE:
            return type("APITimeoutError", (_NON_RETRYABLE[-1],), {})("timeout")
        return RuntimeError("timeout (stub)")


def test_apitimeout_is_in_non_retryable_tuple():
    """Pin the policy at the class level — APITimeoutError MUST be in _NON_RETRYABLE."""
    try:
        from openai import APITimeoutError
    except ImportError:
        import pytest
        pytest.skip("openai SDK not installed")
    assert APITimeoutError in _NON_RETRYABLE, (
        "Policy change 2026-05-17: APITimeoutError must stay in _NON_RETRYABLE. "
        "Retrying a hung gpt-5.x call re-bills the same ~25K output tokens."
    )
    try:
        from openai import APITimeoutError as _AT
    except ImportError:
        pass
    else:
        assert _AT not in _RETRYABLE


def test_apitimeout_propagates_immediately_no_sleep():
    """A single APITimeoutError must surface on attempt #1 — never retry."""
    err = _make_api_timeout_error()
    fn = MagicMock(side_effect=err)

    with patch("machine_translate_docx.openai_tools._retry.time.sleep") as mock_sleep:
        try:
            call_with_retry(fn)
            raised = False
        except type(err):
            raised = True

    assert raised, "APITimeoutError must propagate immediately"
    fn.assert_called_once()
    mock_sleep.assert_not_called()


def test_apitimeout_does_not_consume_max_retries_budget():
    """A single APITimeoutError must NOT trigger MAX_RETRIES SDK calls."""
    err = _make_api_timeout_error()
    fn = MagicMock(side_effect=err)

    with patch("machine_translate_docx.openai_tools._retry.time.sleep"):
        try:
            call_with_retry(fn)
        except type(err):
            pass

    assert fn.call_count == 1, (
        f"APITimeoutError must not be retried — got {fn.call_count} calls "
        f"(MAX_RETRIES={MAX_RETRIES} would be the cost-spiral bug)"
    )


# ── prompt_hash ───────────────────────────────────────────────────────────────

def test_prompt_hash_deterministic():
    """Same input always produces the same 8-char output."""
    text = "translate this carefully"
    assert prompt_hash(text) == prompt_hash(text)


def test_prompt_hash_8_chars_hex():
    """Output is exactly 8 lowercase hexadecimal characters."""
    import re

    result = prompt_hash("some system prompt text")
    assert len(result) == 8, f"Expected 8 chars, got {len(result)}: {result!r}"
    assert re.fullmatch(r"[0-9a-f]{8}", result), (
        f"Not valid hex: {result!r}"
    )


def test_prompt_hash_different_inputs_different_outputs():
    """'a' and 'b' must produce distinct hashes (collision is astronomically unlikely)."""
    assert prompt_hash("a") != prompt_hash("b")
