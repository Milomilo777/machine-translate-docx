"""Shared helpers for the four OpenAI Responses-API stream loops.

Centralised so a future SDK change to event names only requires one edit
in this file instead of touching translator.py / polisher.py / splitting.py
/ persian_double_lines.py individually.

Two public surfaces:

  - ``force_non_stream()`` — read the ``MTD_FORCE_NON_STREAM`` env var.
    When set, callers degrade to non-streaming Responses API. Reserved
    for emergency rollback if a future openai-python SDK change breaks
    the stream parse path. Note: non-streaming brings back the
    openai-python #2725 hang risk on gpt-5.x with large (>25K-token)
    payloads — use only if streaming itself is broken.

  - ``maybe_log_unknown_event(role, event_type)`` — log SSE event types
    we don't recognise. Cheap early-warning system: if OpenAI renames
    an event type the stream loop would otherwise return empty text
    with no visible error.

Added 2026-05-18 per the stream-hardening note in
``notes/2026-05-18_09-45_stream-hardening-suggestions.md``.
"""
from __future__ import annotations

import os
import sys


# SSE event types we expect during a Responses-API stream but do not
# act on. The four handled types (output_text.delta, completed, failed,
# incomplete) are filtered by the caller's if/elif chain BEFORE this
# helper is invoked — only truly unrecognised types reach
# ``maybe_log_unknown_event``.
#
# This set covers the full Responses-API event catalogue as of
# openai-python 2.30 (2026-05-18). Anything outside it triggers a
# stderr warning so SDK upstream changes are visible immediately.
KNOWN_NOISE_EVENTS = frozenset({
    # Lifecycle
    "response.created",
    "response.in_progress",
    "response.queued",
    # Output items / content parts
    "response.output_item.added",
    "response.output_item.done",
    "response.content_part.added",
    "response.content_part.done",
    "response.output_text.done",
    # Refusal channel
    "response.refusal.delta",
    "response.refusal.done",
    # Reasoning channel (gpt-5.x with effort != "none")
    "response.reasoning.delta",
    "response.reasoning.done",
    "response.reasoning_summary_text.delta",
    "response.reasoning_summary_text.done",
    "response.reasoning_summary_part.added",
    "response.reasoning_summary_part.done",
    # Audio channel (not used by this project but listed for completeness)
    "response.audio.delta",
    "response.audio.done",
    "response.audio.transcript.delta",
    "response.audio.transcript.done",
    "response.audio_transcript.delta",
    "response.audio_transcript.done",
    # Function-call channel (tool-use, not used here)
    "response.function_call_arguments.delta",
    "response.function_call_arguments.done",
    # Misc
    "response.error",
})


def force_non_stream() -> bool:
    """Return True when the operator has set ``MTD_FORCE_NON_STREAM=1``.

    Callers in translator / polisher / splitting / aligner check this
    flag and route to a non-streaming ``client.responses.create(...)``
    instead of the stream loop. The non-stream path is otherwise dead
    code on gpt-5.x — it exists solely as an emergency rollback.

    Use case: if openai-python ships a fix for #2725 and we want to
    A/B test stream vs non-stream without redeploying code.
    """
    return os.environ.get("MTD_FORCE_NON_STREAM") == "1"


def maybe_log_unknown_event(role: str, event_type: str) -> None:
    """Emit a stderr warning for an unrecognised SSE event type.

    The four handled types are filtered out by the caller's if/elif
    chain BEFORE this helper is invoked; the known-noise set above
    covers the rest of the current SDK catalogue. Only truly unknown
    types reach this code path.

    Parameters
    ----------
    role : str
        Short identifier for the call site — ``translator`` /
        ``polisher`` / ``splitter`` / ``aligner``. Helps grep-debugging.
    event_type : str
        The ``getattr(event, "type", "")`` value from the SSE event.
        Empty strings are ignored.
    """
    if event_type and event_type not in KNOWN_NOISE_EVENTS:
        print(
            f"[STREAM-UNKNOWN] role={role} type={event_type}",
            file=sys.stderr,
            flush=True,
        )
