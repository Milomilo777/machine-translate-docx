"""Line-count reconciler — phase 11 of the persian-double-lines roadmap.

When the LLM translator returns a translation whose line count does
not match the source line count, the legacy fallback was either to
fail the block (forcing a recursive split) or to silently pad with
empty strings. This reconciler instead asks ``gpt-5.4-mini`` for an
exact re-emission with one line per source line, retrying up to
``max_attempts`` times before falling back to padding / truncation.

Public API
----------
:func:`reconcile_line_count` — the only entry point. The signature is
fixed by the phase-11 contract; do not parameterise the model away.

Hardcoded constants
-------------------
``RECONCILER_MODEL`` is always ``gpt-5.4-mini`` so the reconciler is
fast and cheap. Every API call sets ``prompt_cache_retention=24h``
per the project-wide rule (C4).
"""
from __future__ import annotations

import os
from typing import Final

from openai import OpenAI


RECONCILER_MODEL:        Final[str] = "gpt-5.4-mini"
PROMPT_CACHE_RETENTION:  Final[str] = "24h"

__all__ = [
    "RECONCILER_MODEL",
    "reconcile_line_count",
]


def _pad_or_truncate(translated: list[str], target_len: int) -> list[str]:
    if target_len <= 0:
        return []
    if len(translated) > target_len:
        return list(translated[:target_len])
    if len(translated) < target_len:
        return list(translated) + [""] * (target_len - len(translated))
    return list(translated)


def _build_messages(
    source_lines:    list[str],
    candidate_lines: list[str],
    src_lang_name:   str,
    dest_lang_name:  str,
) -> list[dict]:
    """Assemble the chat-completion messages for one reconcile call."""
    system = (
        "You are a line-count reconciler. The user gives you a "
        f"{src_lang_name} source and a candidate {dest_lang_name} "
        "translation. The translation has the wrong number of lines. "
        "Re-emit the translation so that it has EXACTLY one line per "
        "source line, in the same order, preserving meaning. Output "
        "the lines only — no commentary, no numbering, no surrounding "
        "fences, no leading or trailing blank lines."
    )
    user = (
        f"Source ({len(source_lines)} lines):\n"
        + "\n".join(source_lines)
        + f"\n\nCandidate translation "
        f"({len(candidate_lines)} lines, must become {len(source_lines)}):\n"
        + "\n".join(candidate_lines)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]


def reconcile_line_count(
    source_lines:    list[str],
    translated_lines: list[str],
    src_lang_name:   str,
    dest_lang_name:  str,
    *,
    max_attempts: int = 2,
    client:       OpenAI | None = None,
) -> list[str]:
    """Re-emit ``translated_lines`` so its length equals ``len(source_lines)``.

    No-op fast path: if the lengths already match, return a copy of
    ``translated_lines`` unchanged. Otherwise call ``gpt-5.4-mini`` up to
    ``max_attempts`` times asking for a line-for-line re-emission. On
    final failure, pad with empty strings or truncate so the returned
    list always has exactly ``len(source_lines)`` entries.

    Parameters
    ----------
    source_lines, translated_lines
        Lists of strings already split on ``\\n``.
    src_lang_name, dest_lang_name
        Human-readable language names used in the prompt
        (e.g. ``"English"``, ``"Persian"``).
    max_attempts
        How many times to ask the LLM before falling back. Default 2.
    client
        Optional pre-built ``OpenAI`` client; injected by tests so the
        function can be exercised without a live API.
    """
    if len(translated_lines) == len(source_lines):
        return list(translated_lines)
    if not source_lines:
        return []

    if client is None:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    last_attempt = list(translated_lines)
    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.chat.completions.create(
                model=RECONCILER_MODEL,
                messages=_build_messages(
                    source_lines, last_attempt, src_lang_name, dest_lang_name,
                ),
                extra_body={"prompt_cache_retention": PROMPT_CACHE_RETENTION},
            )
            text = (resp.choices[0].message.content or "")
            lines = text.split("\n")
            if len(lines) == len(source_lines):
                return lines
            last_attempt = lines
            print(
                f"[reconciler] attempt {attempt} returned {len(lines)} lines "
                f"(want {len(source_lines)}); retrying"
            )
        except Exception as exc:
            print(f"[reconciler] attempt {attempt} failed: {exc}")

    print(
        f"[reconciler] giving up after {max_attempts} attempt(s); "
        f"padding/truncating to {len(source_lines)} lines"
    )
    return _pad_or_truncate(last_attempt, len(source_lines))
