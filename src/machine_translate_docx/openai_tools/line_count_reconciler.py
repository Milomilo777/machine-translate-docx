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


# Per-1M-token rates for the reconciler model. Kept in this file
# rather than reaching back into polisher / translator because the
# reconciler is the only consumer; the constants are read-only.
_RECONCILER_PRICES_PER_1M = {
    "gpt-5.4-mini": {"input": 0.75, "cached": 0.075, "output": 4.50},
}


def _log_reconciler_cost(resp, attempt: int) -> None:
    """Print a single ``[reconciler-cost]`` line summarising one call.

    C-3 (2026-05-11): the reconciler runs only on line-count mismatch
    so volume is naturally low, but its cost still belonged in the run
    totals. We log it inline (the chatgpt-polish sidecar doesn't have
    a slot for reconciler calls today — adding one would require a
    schema bump). The launcher's stdout parser captures the printed
    line, so it lands in the failure archive's `stdout.log` even on
    error paths.
    """
    usage = getattr(resp, "usage", None)
    if usage is None:
        return
    # SDK returns either an object with attributes or a dict; support both.
    def _g(name: str, default: int = 0) -> int:
        if isinstance(usage, dict):
            return int(usage.get(name, default) or default)
        return int(getattr(usage, name, default) or default)

    prompt_tok     = _g("prompt_tokens")
    completion_tok = _g("completion_tokens")
    # cached_tokens nests under prompt_tokens_details
    details = getattr(usage, "prompt_tokens_details", None) or (
        usage.get("prompt_tokens_details") if isinstance(usage, dict) else None
    )
    cached_tok = 0
    if details is not None:
        if isinstance(details, dict):
            cached_tok = int(details.get("cached_tokens", 0) or 0)
        else:
            cached_tok = int(getattr(details, "cached_tokens", 0) or 0)

    price = _RECONCILER_PRICES_PER_1M.get(RECONCILER_MODEL)
    if not price:
        return
    non_cached = max(0, prompt_tok - cached_tok)
    cost = (
        (non_cached  / 1_000_000) * price["input"]
        + (cached_tok / 1_000_000) * price.get("cached", price["input"])
        + (completion_tok / 1_000_000) * price["output"]
    )
    print(
        f"[reconciler-cost] attempt {attempt}: "
        f"prompt {prompt_tok} (cached {cached_tok}), "
        f"completion {completion_tok}, "
        f"cost ${cost:.5f}",
        flush=True,
    )


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
            # C-3 (2026-05-11): capture the cost of the reconciler call.
            # Volume is small (only runs on line-count mismatch) but
            # invisibility makes the chatgpt-polish sidecar's
            # `total_cost_usd` look ~5–10 % too cheap on noisy days.
            try:
                _log_reconciler_cost(resp, attempt)
            except Exception:
                # Cost capture is decorative; never break the
                # reconcile path on an unfamiliar response shape.
                pass

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
