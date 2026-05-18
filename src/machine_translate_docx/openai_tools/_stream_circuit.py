"""Stream-mode circuit breaker.

Auto-degrades Responses-API calls from streaming to non-streaming after N
consecutive stream failures, then probes recovery after a cooldown window.
This makes the stream / non-stream choice **self-healing**: an operator
no longer has to notice the failure pattern and set ``MTD_FORCE_NON_STREAM=1``
manually.

State machine:

    CLOSED          normal operation, stream-mode active
       │
       │  3 consecutive failures
       ▼
    OPEN            non-stream forced for the cooldown window
       │
       │  cooldown expires
       ▼
    HALF_OPEN       next stream call is a probe
       │           ┌──── probe succeeds ──► back to CLOSED
       └──── probe fails ──► back to OPEN (cooldown restarts)

Definitions of "stream failure" used by the callers:

    - ``_final is None`` after the stream loop exits — i.e., the call
      ended without a ``response.completed`` event. This is the symptom
      a future SDK change to SSE event names would produce.
    - Assembled text is empty when the source clearly was not — handled
      by the caller; we just expose ``record_stream_failure``.

State persists in ``<runtime_dir>/_stream_circuit.json`` so the breaker
survives process restarts and is shared between the launcher and CLI
subprocesses.

Public surface (the only things callers should touch):

    should_use_non_stream() -> bool      # check before firing a call
    record_stream_success(role: str)     # call after a clean stream
    record_stream_failure(role: str,
                          reason: str)   # call after a degraded stream

Added 2026-05-18 per proposal #5 in
``notes/2026-05-18_15-57_self-healing-error-tracking-survey-and-proposals.md``.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


# ── tuning knobs (override via env vars for tests / hot-fix) ─────────────────

TRIP_THRESHOLD: int = int(os.environ.get("MTD_STREAM_TRIP_THRESHOLD", "3"))
"""Consecutive failures required to trip the breaker open. Default 3."""

COOLDOWN_SECONDS: int = int(os.environ.get("MTD_STREAM_COOLDOWN_SECONDS", "3600"))
"""How long the breaker stays open before promoting to HALF_OPEN. Default 1h."""

_STATE_FILE_NAME = "_stream_circuit.json"


# ── state file location ──────────────────────────────────────────────────────

def _state_path() -> Path:
    """Path to the shared state file.

    Uses the same ``<temp>/machine_translate_docx_local`` location the
    launcher uses for its runtime_dir, so launcher + CLI subprocess
    agree on the file even when env vars aren't threaded through.
    """
    override = os.environ.get("MTD_STREAM_CIRCUIT_STATE_FILE")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "machine_translate_docx_local" / _STATE_FILE_NAME


def _load_state() -> dict[str, Any]:
    """Return the persisted state dict (or a fresh CLOSED default)."""
    p = _state_path()
    if not p.exists():
        return {"state": "CLOSED", "consecutive_failures": 0, "opened_at": None}
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("not a dict")
        # Defensive: ensure required keys exist with sane defaults.
        data.setdefault("state", "CLOSED")
        data.setdefault("consecutive_failures", 0)
        data.setdefault("opened_at", None)
        return data
    except Exception:
        # Corrupt state → start fresh; better than crashing the run.
        return {"state": "CLOSED", "consecutive_failures": 0, "opened_at": None}


def _save_state(state: dict[str, Any]) -> None:
    """Persist the state dict, creating the parent dir if needed."""
    p = _state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        # State write failure should never crash the run — the circuit
        # just won't persist this update. Worst case: re-evaluates on
        # the next call from a stale (or default-CLOSED) state.
        pass


# ── public surface ───────────────────────────────────────────────────────────

def should_use_non_stream() -> bool:
    """Return ``True`` if the circuit is OPEN (caller should bypass stream).

    Side effect: when called and the cooldown has expired, promotes the
    state from OPEN to HALF_OPEN so the next stream call acts as a probe.
    """
    s = _load_state()
    state = s.get("state", "CLOSED")

    if state == "CLOSED":
        return False

    if state == "HALF_OPEN":
        # The probe call is allowed through in stream mode.
        return False

    # state == "OPEN" — check cooldown.
    opened_at = s.get("opened_at") or 0
    now = time.time()
    if now - opened_at >= COOLDOWN_SECONDS:
        # Cooldown expired — promote to HALF_OPEN, let this caller probe.
        s["state"] = "HALF_OPEN"
        _save_state(s)
        return False

    return True  # OPEN and still within cooldown


def record_stream_success(role: str) -> None:
    """Record a clean stream result (received ``response.completed``).

    If the breaker was HALF_OPEN, this success closes it. Counters
    always reset to 0 on success.
    """
    s = _load_state()
    prev = s.get("state", "CLOSED")
    if prev == "HALF_OPEN":
        print(
            f"[CIRCUIT] healed — stream mode restored (role={role})",
            flush=True,
        )
    s["state"] = "CLOSED"
    s["consecutive_failures"] = 0
    s["opened_at"] = None
    _save_state(s)


def record_stream_failure(role: str, reason: str = "no_response_completed") -> None:
    """Record a degraded stream result.

    Two transition cases:
      - From HALF_OPEN: a failed probe restarts the cooldown (back to OPEN).
      - From CLOSED: increment failure counter; trip to OPEN once we hit
        ``TRIP_THRESHOLD``.
    """
    s = _load_state()
    prev = s.get("state", "CLOSED")
    now = time.time()

    if prev == "HALF_OPEN":
        s["state"] = "OPEN"
        s["opened_at"] = now
        # consecutive_failures already at trip threshold; leave it.
        print(
            f"[CIRCUIT] probe failed — extending non-stream window "
            f"{COOLDOWN_SECONDS}s (role={role} reason={reason})",
            flush=True,
        )
        _save_state(s)
        return

    # prev is CLOSED or OPEN. If already OPEN, leave it OPEN — the
    # cooldown timer keeps running. Just increment the counter.
    s["consecutive_failures"] = int(s.get("consecutive_failures") or 0) + 1
    cf = s["consecutive_failures"]
    if prev == "CLOSED" and cf >= TRIP_THRESHOLD:
        s["state"] = "OPEN"
        s["opened_at"] = now
        print(
            f"[CIRCUIT] tripped to OPEN — {cf} consecutive stream "
            f"failures. Falling back to non-stream for {COOLDOWN_SECONDS}s "
            f"(role={role} reason={reason})",
            flush=True,
        )
    _save_state(s)


def reset() -> None:
    """Delete the persisted state. Used by tests and (manually) for hot-recovery."""
    p = _state_path()
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass


def snapshot() -> dict[str, Any]:
    """Read the current state without mutating. For diagnostics."""
    s = _load_state()
    # Compute remaining cooldown if OPEN.
    if s.get("state") == "OPEN" and s.get("opened_at"):
        remaining = max(0, COOLDOWN_SECONDS - (time.time() - s["opened_at"]))
        s["cooldown_remaining_seconds"] = round(remaining, 1)
    return s
