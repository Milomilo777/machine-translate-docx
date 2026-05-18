"""Tests for src/machine_translate_docx/openai_tools/_stream_helper.py.

The helper centralises:

  - ``force_non_stream()`` — reads ``MTD_FORCE_NON_STREAM`` env var.
  - ``maybe_log_unknown_event(role, type)`` — stderr warning for SSE
    event types not in ``KNOWN_NOISE_EVENTS``.

Both surfaces are called by translator / polisher / splitting / aligner
stream loops. A regression that breaks either path would silently
disable the 2026-05-18 stream-hardening rollback + early-warning.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from machine_translate_docx.openai_tools._stream_helper import (
    KNOWN_NOISE_EVENTS,
    force_non_stream,
    maybe_log_unknown_event,
)


# ── force_non_stream ─────────────────────────────────────────────────────────

def test_force_non_stream_false_when_unset(monkeypatch):
    """Default (env var absent) must return False — stream stays on."""
    monkeypatch.delenv("MTD_FORCE_NON_STREAM", raising=False)
    assert force_non_stream() is False


def test_force_non_stream_true_when_set_to_one(monkeypatch):
    """The documented enable string is ``1`` (string)."""
    monkeypatch.setenv("MTD_FORCE_NON_STREAM", "1")
    assert force_non_stream() is True


def test_force_non_stream_false_for_other_values(monkeypatch):
    """Anything other than the literal ``1`` keeps stream on — no truthy
    coercion (so ``true`` / ``yes`` / ``on`` do NOT trigger rollback)."""
    for v in ["0", "true", "yes", "on", "TRUE", "True", "", "  ", "2"]:
        monkeypatch.setenv("MTD_FORCE_NON_STREAM", v)
        assert force_non_stream() is False, (
            f"Value {v!r} should not trigger rollback — only literal '1' does"
        )


# ── KNOWN_NOISE_EVENTS ───────────────────────────────────────────────────────

def test_known_noise_events_is_frozenset():
    """Immutable so callers can't accidentally mutate the set at runtime."""
    assert isinstance(KNOWN_NOISE_EVENTS, frozenset)


def test_known_noise_events_excludes_the_four_handled_types():
    """The four event types short-circuited by every caller's if/elif chain
    must NOT be in the noise set — otherwise we'd risk masking a real
    bug if a caller forgot to handle one of them."""
    handled = {
        "response.output_text.delta",
        "response.completed",
        "response.failed",
        "response.incomplete",
    }
    overlap = handled & KNOWN_NOISE_EVENTS
    assert overlap == set(), (
        f"These types are both handled and in noise set: {overlap}. "
        "Remove from KNOWN_NOISE_EVENTS so unknown-event logging fires."
    )


def test_known_noise_events_covers_lifecycle_basics():
    """Sanity check that the obvious lifecycle types are in the noise set
    so they don't pollute the [STREAM-UNKNOWN] log on every call."""
    for et in (
        "response.created",
        "response.in_progress",
        "response.output_item.added",
        "response.output_item.done",
    ):
        assert et in KNOWN_NOISE_EVENTS, f"{et} missing from noise set"


# ── maybe_log_unknown_event ──────────────────────────────────────────────────

def test_maybe_log_unknown_event_logs_truly_unknown(capsys):
    """A type not in the noise set must produce a [STREAM-UNKNOWN] line
    on stderr (so future SDK renames are visible immediately)."""
    maybe_log_unknown_event("translator", "response.something_new_2027")
    captured = capsys.readouterr()
    assert "[STREAM-UNKNOWN]" in captured.err
    assert "role=translator" in captured.err
    assert "type=response.something_new_2027" in captured.err


def test_maybe_log_unknown_event_silent_for_known_noise(capsys):
    """Known no-op events must NOT spam the log."""
    maybe_log_unknown_event("polisher", "response.created")
    maybe_log_unknown_event("polisher", "response.output_item.added")
    captured = capsys.readouterr()
    assert "[STREAM-UNKNOWN]" not in captured.err
    assert "[STREAM-UNKNOWN]" not in captured.out


def test_maybe_log_unknown_event_silent_for_empty_string(capsys):
    """Empty / missing type (e.g. malformed event) must not log."""
    maybe_log_unknown_event("splitter", "")
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""
