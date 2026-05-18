"""Tests for src/machine_translate_docx/openai_tools/_stream_circuit.py.

Covers the 3-state circuit breaker:

  CLOSED --[N consecutive failures]--> OPEN
  OPEN --[cooldown expires]--> HALF_OPEN
  HALF_OPEN --[probe success]--> CLOSED
  HALF_OPEN --[probe failure]--> OPEN (cooldown restart)

Plus persistence to disk (state survives module reload), defensive
fallback (corrupt state file resets to CLOSED), and the integration
with ``_stream_helper.use_non_stream()`` combined check.

No network, no OpenAI key required.
"""
from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolated_state_file(tmp_path, monkeypatch):
    """Each test gets its own state file via the override env var.

    Also reload the module so the env-var-driven TRIP_THRESHOLD / COOLDOWN
    constants are re-read from a clean state. Yield the module reference
    so tests can use it directly.
    """
    state_file = tmp_path / "_stream_circuit.json"
    monkeypatch.setenv("MTD_STREAM_CIRCUIT_STATE_FILE", str(state_file))
    # Default to short cooldown so cooldown-expiry tests run fast.
    monkeypatch.setenv("MTD_STREAM_TRIP_THRESHOLD", "3")
    monkeypatch.setenv("MTD_STREAM_COOLDOWN_SECONDS", "3600")

    # Re-import to pick up env vars.
    from machine_translate_docx.openai_tools import _stream_circuit as mod
    importlib.reload(mod)
    yield mod


# ── CLOSED → CLOSED on success ───────────────────────────────────────────────

def test_fresh_state_is_closed(_isolated_state_file):
    mod = _isolated_state_file
    assert mod.should_use_non_stream() is False
    s = mod.snapshot()
    assert s["state"] == "CLOSED"
    assert s["consecutive_failures"] == 0


def test_single_failure_does_not_trip(_isolated_state_file):
    mod = _isolated_state_file
    mod.record_stream_failure("translator", "test")
    s = mod.snapshot()
    assert s["state"] == "CLOSED"
    assert s["consecutive_failures"] == 1
    assert mod.should_use_non_stream() is False


def test_two_failures_does_not_trip(_isolated_state_file):
    mod = _isolated_state_file
    mod.record_stream_failure("translator", "test")
    mod.record_stream_failure("translator", "test")
    s = mod.snapshot()
    assert s["state"] == "CLOSED"
    assert s["consecutive_failures"] == 2
    assert mod.should_use_non_stream() is False


# ── CLOSED → OPEN on 3rd failure ─────────────────────────────────────────────

def test_three_failures_trips_to_open(_isolated_state_file):
    mod = _isolated_state_file
    mod.record_stream_failure("translator", "test")
    mod.record_stream_failure("translator", "test")
    mod.record_stream_failure("translator", "test")
    s = mod.snapshot()
    assert s["state"] == "OPEN"
    assert s["consecutive_failures"] == 3
    assert mod.should_use_non_stream() is True


def test_success_resets_failures_to_zero(_isolated_state_file):
    """A success between failures must reset the counter — only
    CONSECUTIVE failures count."""
    mod = _isolated_state_file
    mod.record_stream_failure("translator", "test")
    mod.record_stream_failure("translator", "test")
    mod.record_stream_success("translator")
    s = mod.snapshot()
    assert s["state"] == "CLOSED"
    assert s["consecutive_failures"] == 0

    # Now two more failures should still NOT trip — counter is at 2 not 4.
    mod.record_stream_failure("translator", "test")
    mod.record_stream_failure("translator", "test")
    s = mod.snapshot()
    assert s["state"] == "CLOSED"
    assert s["consecutive_failures"] == 2


# ── OPEN behaviour ───────────────────────────────────────────────────────────

def test_open_state_keeps_using_non_stream_within_cooldown(_isolated_state_file):
    mod = _isolated_state_file
    for _ in range(3):
        mod.record_stream_failure("translator", "test")
    # Within the 1-hour cooldown, repeated reads stay OPEN.
    for _ in range(5):
        assert mod.should_use_non_stream() is True
    s = mod.snapshot()
    assert s["state"] == "OPEN"
    assert "cooldown_remaining_seconds" in s


def test_open_promotes_to_half_open_when_cooldown_expired(
    _isolated_state_file, monkeypatch,
):
    """Use a tiny cooldown so we can let it expire without sleeping
    real seconds. Reload the module so the env override takes effect."""
    monkeypatch.setenv("MTD_STREAM_COOLDOWN_SECONDS", "0")
    from machine_translate_docx.openai_tools import _stream_circuit as mod
    importlib.reload(mod)
    for _ in range(3):
        mod.record_stream_failure("translator", "test")
    s = mod.snapshot()
    assert s["state"] == "OPEN"

    # Sleep 1s to be sure ``now - opened_at >= 0``.
    time.sleep(0.05)

    # Next check should promote to HALF_OPEN and let stream through.
    assert mod.should_use_non_stream() is False
    s = mod.snapshot()
    assert s["state"] == "HALF_OPEN"


# ── HALF_OPEN behaviour ──────────────────────────────────────────────────────

def test_half_open_success_returns_to_closed(_isolated_state_file, monkeypatch):
    monkeypatch.setenv("MTD_STREAM_COOLDOWN_SECONDS", "0")
    from machine_translate_docx.openai_tools import _stream_circuit as mod
    importlib.reload(mod)
    for _ in range(3):
        mod.record_stream_failure("translator", "test")
    time.sleep(0.05)
    mod.should_use_non_stream()  # promote to HALF_OPEN

    # Probe call succeeds.
    mod.record_stream_success("translator")
    s = mod.snapshot()
    assert s["state"] == "CLOSED"
    assert s["consecutive_failures"] == 0
    assert s["opened_at"] is None


def test_half_open_failure_returns_to_open(_isolated_state_file, monkeypatch):
    monkeypatch.setenv("MTD_STREAM_COOLDOWN_SECONDS", "0")
    from machine_translate_docx.openai_tools import _stream_circuit as mod
    importlib.reload(mod)
    for _ in range(3):
        mod.record_stream_failure("translator", "test")
    time.sleep(0.05)
    mod.should_use_non_stream()  # promote to HALF_OPEN

    # Now: probe fails. Should go back to OPEN with cooldown restarted.
    # Bump cooldown back up so we can verify the OPEN state.
    monkeypatch.setenv("MTD_STREAM_COOLDOWN_SECONDS", "3600")
    importlib.reload(mod)
    # After reload state file still says HALF_OPEN — the prev cooldown override
    # also reloaded; the on-disk state is what we care about.
    s = mod.snapshot()
    assert s["state"] == "HALF_OPEN"

    mod.record_stream_failure("translator", "test")
    s = mod.snapshot()
    assert s["state"] == "OPEN"
    # consecutive_failures stays at the trip value or higher
    assert s["consecutive_failures"] >= 3


# ── persistence ──────────────────────────────────────────────────────────────

def test_state_persists_across_module_reload(_isolated_state_file):
    """Trip the breaker; reload the module; OPEN state must remain."""
    mod = _isolated_state_file
    for _ in range(3):
        mod.record_stream_failure("translator", "test")
    assert mod.snapshot()["state"] == "OPEN"

    # Reload — simulates a fresh subprocess that imports the module.
    from machine_translate_docx.openai_tools import _stream_circuit as mod2
    importlib.reload(mod2)
    assert mod2.snapshot()["state"] == "OPEN"
    assert mod2.should_use_non_stream() is True


# ── defensive: corrupt state file ────────────────────────────────────────────

def test_corrupt_state_file_starts_fresh(_isolated_state_file, monkeypatch):
    mod = _isolated_state_file
    # Write garbage to the state file.
    state_file = Path(mod._state_path())
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("not valid json {{{", encoding="utf-8")

    # Should NOT crash. Returns to fresh CLOSED.
    assert mod.should_use_non_stream() is False
    s = mod.snapshot()
    assert s["state"] == "CLOSED"
    assert s["consecutive_failures"] == 0


def test_missing_keys_get_safe_defaults(_isolated_state_file):
    mod = _isolated_state_file
    state_file = Path(mod._state_path())
    state_file.parent.mkdir(parents=True, exist_ok=True)
    # Write a dict that's missing required keys.
    state_file.write_text(json.dumps({"unrelated": "value"}), encoding="utf-8")
    assert mod.should_use_non_stream() is False
    s = mod.snapshot()
    assert s["state"] == "CLOSED"
    assert s["consecutive_failures"] == 0


# ── reset() ─────────────────────────────────────────────────────────────────

def test_reset_clears_state(_isolated_state_file):
    mod = _isolated_state_file
    for _ in range(3):
        mod.record_stream_failure("translator", "test")
    assert mod.snapshot()["state"] == "OPEN"

    mod.reset()
    s = mod.snapshot()
    assert s["state"] == "CLOSED"
    assert s["consecutive_failures"] == 0


# ── integration with use_non_stream() combined helper ────────────────────────

def test_use_non_stream_returns_true_when_env_var_set(_isolated_state_file, monkeypatch):
    monkeypatch.setenv("MTD_FORCE_NON_STREAM", "1")
    from machine_translate_docx.openai_tools._stream_helper import use_non_stream
    # Env var alone is enough.
    assert use_non_stream() is True


def test_use_non_stream_returns_true_when_circuit_open(_isolated_state_file, monkeypatch):
    monkeypatch.delenv("MTD_FORCE_NON_STREAM", raising=False)
    mod = _isolated_state_file
    for _ in range(3):
        mod.record_stream_failure("translator", "test")
    from machine_translate_docx.openai_tools._stream_helper import use_non_stream
    assert use_non_stream() is True


def test_use_non_stream_returns_false_in_normal_conditions(
    _isolated_state_file, monkeypatch,
):
    monkeypatch.delenv("MTD_FORCE_NON_STREAM", raising=False)
    from machine_translate_docx.openai_tools._stream_helper import use_non_stream
    assert use_non_stream() is False
