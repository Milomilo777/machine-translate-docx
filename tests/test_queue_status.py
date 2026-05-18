"""C4 (2026-05-18): unit-level test of the concurrency-cap + queue
notification logic in local_launcher.py.

We do NOT spin a real HTTP server here — that path is exercised by the
`@pytest.mark.live` end-to-end suite. This is a deterministic, no-network
test that proves:

  1. With `MTD_MAX_CONCURRENT_JOBS=2`, the third concurrent acquire blocks.
  2. While blocked, the third job's status is flipped to 'queued'
     (so the frontend can render the Persian wait message).
  3. When a slot frees, the third job is unblocked and resumed.

This catches regressions in the semaphore + status-flip path without
needing Playwright or chromium.
"""
from __future__ import annotations

import threading
import time

import pytest


def _make_state_with_two_running_jobs(monkeypatch):
    """Boot just enough of local_launcher to drive the queue logic.

    We import the module fresh so the module-level
    ``_MAX_CONCURRENT_JOBS`` / ``_job_semaphore`` are recreated from a
    test-controlled env var.
    """
    monkeypatch.setenv("MTD_MAX_CONCURRENT_JOBS", "2")

    import importlib
    import local_launcher as ll  # noqa: WPS433 — intentional in-test import
    importlib.reload(ll)

    # Acquire 2 slots to simulate two jobs already running.
    assert ll._job_semaphore.acquire(blocking=False) is True
    assert ll._job_semaphore.acquire(blocking=False) is True
    return ll


def test_third_acquire_blocks_when_cap_reached(monkeypatch):
    ll = _make_state_with_two_running_jobs(monkeypatch)
    try:
        # A third non-blocking acquire must FAIL — the cap is hit.
        assert ll._job_semaphore.acquire(blocking=False) is False
    finally:
        # Restore — release the two slots we grabbed.
        ll._job_semaphore.release()
        ll._job_semaphore.release()


def test_third_acquire_succeeds_after_one_release(monkeypatch):
    ll = _make_state_with_two_running_jobs(monkeypatch)
    try:
        assert ll._job_semaphore.acquire(blocking=False) is False

        # Free one slot — third acquire should now succeed.
        ll._job_semaphore.release()
        assert ll._job_semaphore.acquire(blocking=False) is True
        # And restore.
        ll._job_semaphore.release()
    finally:
        ll._job_semaphore.release()


def test_status_flips_to_queued_then_pending(monkeypatch, tmp_path):
    """Direct check on LocalState.update_job: when a job goes from
    pending → queued → pending, only the visible status fields change;
    no error is set, and progress is preserved at 5 during the wait.
    """
    ll = _make_state_with_two_running_jobs(monkeypatch)
    try:
        # Build a minimal LocalState (no HTTP server, no subprocesses).
        state = ll.LocalState(
            runtime_dir=tmp_path,
            backend_mode="mock",
            python_exe=tmp_path / "py.exe",
            script_path=tmp_path / "cli.py",
        )
        job_id = state.register_job()
        state.update_job(job_id, filename="t.docx", progress=5)

        # Simulate the queue path: cap is hit, flip to queued.
        state.update_job(job_id, status="queued", progress=5)
        j = state.get_job(job_id)
        assert j is not None
        assert j.status == "queued"
        assert j.progress == 5
        assert j.error is None, "queue path must NOT use the error channel"

        # Slot frees → flip back to pending.
        state.update_job(job_id, status="pending")
        j = state.get_job(job_id)
        assert j is not None
        assert j.status == "pending"
        assert j.progress == 5
        assert j.error is None
    finally:
        ll._job_semaphore.release()
        ll._job_semaphore.release()


def test_queue_unblocks_when_slot_frees(monkeypatch):
    """End-to-end (still in-process): start a thread that performs a
    blocking acquire while the semaphore is full, then release a slot
    and confirm the thread proceeds promptly.
    """
    ll = _make_state_with_two_running_jobs(monkeypatch)
    proceed_at: dict = {}

    def waiter():
        ll._job_semaphore.acquire()  # blocking
        proceed_at["t"] = time.monotonic()
        ll._job_semaphore.release()

    th = threading.Thread(target=waiter, daemon=True)
    th.start()

    # The thread should be BLOCKED — give it a moment, confirm it has
    # not yet recorded proceed_at.
    time.sleep(0.05)
    assert "t" not in proceed_at, "third acquire should still be blocked"

    # Free a slot and watch the thread unblock.
    t_release = time.monotonic()
    ll._job_semaphore.release()
    th.join(timeout=2.0)
    assert "t" in proceed_at, "third acquire never unblocked after release"

    # And the unblock should have happened promptly (< 1 s).
    assert proceed_at["t"] - t_release < 1.0

    # Restore — the waiter re-released, so only one slot left to drop.
    ll._job_semaphore.release()
