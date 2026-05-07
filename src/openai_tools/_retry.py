"""Shared retry helper for OpenAI API calls.

Behaviour:
- RateLimitError, APIConnectionError, APITimeoutError -> retry up to MAX_RETRIES
  with exponential backoff (1 s, 2 s, 4 s, ...).
- BadRequestError, AuthenticationError, PermissionDeniedError -> raise immediately.
- Any other Exception subclass not in the openai hierarchy is also raised
  immediately (do not silently swallow unknown failures).

Used by translator.py, polisher.py, and aligner_per.py so retry behaviour
stays consistent across the three OpenAI callers.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        BadRequestError,
        RateLimitError,
    )
    _RETRYABLE: tuple = (RateLimitError, APIConnectionError, APITimeoutError)
    _NON_RETRYABLE: tuple = (BadRequestError,)
except ImportError:                               # openai not installed in this env
    _RETRYABLE = ()
    _NON_RETRYABLE = ()


T = TypeVar("T")

MAX_RETRIES   = 3       # total attempts: 1 initial + (MAX_RETRIES - 1) retries
BASE_DELAY_S  = 1.0


def call_with_retry(fn: Callable[[], T], *, label: str = "openai") -> T:
    """Invoke `fn` and retry transient OpenAI failures with exponential backoff.

    `fn` must be a zero-argument callable that performs exactly one API call
    and returns its result. Wrap your client call in a lambda or local def.

    Raises:
        BadRequestError (and other non-retryable openai errors) immediately.
        Any other exception type also bubbles up immediately.
        The last RateLimitError / APIConnectionError / APITimeoutError if all
        retries are exhausted.
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
            delay = BASE_DELAY_S * (2 ** attempt)  # 1 s, 2 s, 4 s
            print(
                f"[RETRY] {label}: {type(exc).__name__} on attempt "
                f"{attempt + 1}/{MAX_RETRIES} — sleeping {delay:.0f}s"
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc
