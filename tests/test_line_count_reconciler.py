"""Unit tests for ``openai_tools.line_count_reconciler``.

The OpenAI client is injected via the ``client=`` keyword argument so
the tests run offline. A tiny stub mimics the
``client.chat.completions.create(...)`` shape used by the production
code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import pytest

from openai_tools.line_count_reconciler import (
    RECONCILER_MODEL,
    reconcile_line_count,
)


# ── stub OpenAI client ───────────────────────────────────────────────────────

@dataclass
class _StubMessage:
    content: str


@dataclass
class _StubChoice:
    message: _StubMessage


@dataclass
class _StubResponse:
    choices: list[_StubChoice]


class _StubCompletions:
    def __init__(self, scripted_responses: Iterator[str]):
        self._iter = iter(scripted_responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        try:
            text = next(self._iter)
        except StopIteration:
            text = ""
        return _StubResponse(choices=[_StubChoice(message=_StubMessage(content=text))])


class _StubChat:
    def __init__(self, completions: _StubCompletions):
        self.completions = completions


class _StubClient:
    def __init__(self, scripted_responses: list[str]):
        self.chat = _StubChat(_StubCompletions(iter(scripted_responses)))


# ── tests ─────────────────────────────────────────────────────────────────────

def test_no_op_when_lengths_match():
    src = ["a", "b", "c"]
    tr  = ["x", "y", "z"]
    client = _StubClient([])
    out = reconcile_line_count(src, tr, "English", "Persian", client=client)
    assert out == tr
    # The fast path must NOT call the API at all.
    assert client.chat.completions.calls == []


def test_empty_source_returns_empty():
    out = reconcile_line_count([], ["whatever"], "English", "Persian", client=_StubClient([]))
    assert out == []


def test_first_attempt_reconciles_successfully():
    src = ["one", "two", "three"]
    tr  = ["uno dos tres"]   # collapsed to 1 line
    # First (and only) LLM response returns the right shape.
    client = _StubClient(["α\nβ\nγ"])
    out = reconcile_line_count(src, tr, "English", "Greek", client=client)
    assert out == ["α", "β", "γ"]
    assert len(client.chat.completions.calls) == 1
    call = client.chat.completions.calls[0]
    assert call["model"] == RECONCILER_MODEL
    assert call["extra_body"] == {"prompt_cache_retention": "24h"}
    # The candidate (collapsed translation) is in the user message.
    user_msg = call["messages"][1]["content"]
    assert "uno dos tres" in user_msg


def test_retry_loop_then_pad_fallback():
    src = ["one", "two", "three", "four"]
    tr  = ["x", "y"]
    # Both attempts return the wrong line count → reconciler falls
    # back to pad/truncate the LAST attempt.
    client = _StubClient(["a\nb", "c\nd\ne"])
    out = reconcile_line_count(src, tr, "EN", "FA", client=client, max_attempts=2)
    assert len(out) == len(src)
    # The final fallback pads the *last* attempt (3 lines) to 4.
    assert out[:3] == ["c", "d", "e"]
    assert out[3] == ""
    assert len(client.chat.completions.calls) == 2


def test_truncate_fallback_when_llm_overshoots():
    src = ["one", "two"]
    tr  = ["x x x x x"]   # 1 line
    # LLM keeps returning too many lines.
    client = _StubClient(["a\nb\nc", "d\ne\nf\ng"])
    out = reconcile_line_count(src, tr, "EN", "FA", client=client, max_attempts=2)
    assert len(out) == len(src) == 2
    # Truncate from the last attempt.
    assert out == ["d", "e"]


def test_api_failure_does_not_crash():
    """An exception raised by the LLM client must not propagate; the
    reconciler logs and falls back to padding/truncating."""

    class _Boom(_StubClient):
        def __init__(self):
            class _Exploding:
                def create(self, **_):
                    raise RuntimeError("network down")
            class _Chat:
                completions = _Exploding()
            self.chat = _Chat()

    src = ["a", "b", "c"]
    tr  = ["x"]
    out = reconcile_line_count(src, tr, "EN", "FA", client=_Boom(), max_attempts=2)
    assert len(out) == 3
    assert out[0] == "x"
    assert out[1:] == ["", ""]
