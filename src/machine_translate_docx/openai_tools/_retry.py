"""Shared helpers for the OpenAI tool modules.

Currently exposes:
- `call_with_retry(fn, *, label)` — retry transient OpenAI failures.
- `prompt_hash(text)` — short reproducibility marker for system prompts.


Behaviour:
- RateLimitError, APIConnectionError -> retry up to MAX_RETRIES
  with exponential backoff (1 s, 2 s, 4 s, ...).
- BadRequestError, AuthenticationError, PermissionDeniedError -> raise immediately.
- APITimeoutError -> raise immediately (2026-05-17 policy change). The
  server keeps generating output even after the SDK times out (openai-
  python #2725), so a retry on timeout BILLS the same output again —
  in the FLYIN incident, a single hung call paid for 6 attempts × ~25K
  output tokens each before finally surrendering. We now treat timeout
  as a fatal request error: surface to the caller and let it decide
  (smaller block, stream=True, or model switch). With the stream=True
  fix in translator/polisher this path should rarely fire.
- Any other Exception subclass not in the openai hierarchy is also raised
  immediately (do not silently swallow unknown failures).

Used by translator.py, polisher.py, and aligner_per.py so retry behaviour
stays consistent across the three OpenAI callers.
"""
from __future__ import annotations

import hashlib
import random
import time
from typing import Callable, TypeVar


def prompt_hash(text: str) -> str:
    """Return the first 8 hex chars of sha256(text).

    Stored in the JSON log so a downstream reviewer can tell which
    revision of `translate_PER.txt` / `polish_PER.txt` was actually
    sent to the model — prompts are large and edited often, so the
    hash is the fastest way to spot drift.
    """
    if not text:
        return "00000000"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]

try:
    from openai import (
        APIConnectionError,
        APIError,
        APITimeoutError,
        BadRequestError,
        InternalServerError,
        RateLimitError,
    )
    # A4 (2026-05-12): treat transient 5xx (InternalServerError, generic
    # APIError used for 502/503) the same as connection / rate errors —
    # they recover on retry. BadRequestError stays non-retryable (a bug
    # in our request, not the server).
    # 2026-05-17: APITimeoutError MOVED to non-retryable. See module
    # docstring — silent server-side billing on timeout retries was
    # observed to spiral cost ~6× per hung call. Better to fail fast and
    # let the caller decide whether to shrink payload / enable stream.
    _RETRYABLE: tuple = (
        RateLimitError,
        APIConnectionError,
        InternalServerError,
        APIError,
    )
    _NON_RETRYABLE: tuple = (BadRequestError, APITimeoutError)
except ImportError:                               # openai not installed in this env
    _RETRYABLE = ()
    _NON_RETRYABLE = ()


T = TypeVar("T")

# Total attempts = 1 initial + (MAX_RETRIES - 1) retries.
# 5 (audit B4, 2026-05-13): bumped from 3 to give transient 5xx more
# room — a 30-minute polish was failing on a 7-second 502 blip.
MAX_RETRIES   = 5
BASE_DELAY_S  = 1.0
MAX_DELAY_S   = 30.0


def call_with_retry(fn: Callable[[], T], *, label: str = "openai") -> T:
    """Invoke `fn` and retry transient OpenAI failures with exponential backoff
    + full jitter.

    `fn` must be a zero-argument callable that performs exactly one API call
    and returns its result. Wrap your client call in a lambda or local def.

    Backoff (B3, 2026-05-13): full jitter — ``delay = uniform(0, base * 2^n)``
    capped at MAX_DELAY_S. Prevents retry-herd collisions when several jobs
    hit a rate-limit window simultaneously.

    Raises:
        BadRequestError (and other non-retryable openai errors) immediately.
        Any other exception type also bubbles up immediately.
        The last retryable error if all attempts are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except _NON_RETRYABLE:
            raise                                  # bug in our request — never retry
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt == MAX_RETRIES - 1:
                break
            # Full jitter — uniform between 0 and the exponential ceiling.
            ceiling = min(BASE_DELAY_S * (2 ** attempt), MAX_DELAY_S)
            delay   = random.uniform(0, ceiling)
            print(
                f"[RETRY] {label}: {type(exc).__name__} on attempt "
                f"{attempt + 1}/{MAX_RETRIES} — sleeping {delay:.1f}s "
                f"(jittered ceiling {ceiling:.0f}s)"
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def normalize_usage(response_json: dict) -> dict:
    """Rewrite ``response_json["usage"]`` from Responses-API → Chat-Completions shape.

    The Responses API (the new ``client.responses.create`` endpoint) reports
    usage as ``input_tokens`` / ``output_tokens`` / ``input_tokens_details``.
    Every downstream piece of code in this project (cost calculation,
    cached-token logging, JSON sidecar) was written against the Chat
    Completions shape ``prompt_tokens`` / ``completion_tokens`` /
    ``prompt_tokens_details``. To avoid rewriting all of that, we
    re-label the keys in place.

    Returns the (possibly-rewrapped) response dict. Idempotent: if
    ``usage`` already carries ``prompt_tokens``, the dict is returned
    unchanged. Never mutates the input dict — caller-safe.

    2026-05-16 (P2.8 / P2.9 from master audit): extracted from two
    byte-identical copies in translator.py:373-386 and
    polisher.py:352-362 so future Responses-API schema changes are a
    one-line edit.
    """
    raw_usage = response_json.get("usage") or {}
    if "input_tokens" in raw_usage and "prompt_tokens" not in raw_usage:
        rewrapped = dict(response_json)
        rewrapped["usage"] = {
            "prompt_tokens":             raw_usage.get("input_tokens", 0),
            "completion_tokens":         raw_usage.get("output_tokens", 0),
            "total_tokens":              raw_usage.get("total_tokens", 0),
            "prompt_tokens_details":     raw_usage.get("input_tokens_details", {}),
            "completion_tokens_details": raw_usage.get("output_tokens_details", {}),
        }
        return rewrapped
    return response_json
