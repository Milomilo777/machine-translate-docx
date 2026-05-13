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
import re
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


_RE_TAG = re.compile(r"^\s*⟨⟨\s*(\d+)\s*⟩⟩\s?")


def _build_messages(
    source_lines:    list[str],
    candidate_lines: list[str],
    src_lang_name:   str,
    dest_lang_name:  str,
) -> list[dict]:
    """Assemble the chat-completion messages for one reconcile call.

    2026-05-13 (F5 sweep): the production prompt converged on 0 of 4
    attempts for FLYIN-1646 (1387 source vs 1403 translator output).
    A 10-prompt sweep on the same data showed that asking the model to
    emit a ``⟨⟨N⟩⟩`` per-line tag forces it to count explicitly. P4
    converged in attempt 1; the other 9 prompts (including the legacy
    raw-line shape, delta-aware merge, zip-and-merge, worked examples,
    high-pressure framing) all came back wrong. The tag-format prompt
    costs ~60 % more output tokens but it actually works.

    The reconciler now requests tagged output; the caller strips the
    tags before returning.
    """
    N = len(source_lines)
    system = (
        f"You are a line-count reconciler. The user gives you a "
        f"{src_lang_name} source with N lines and its {dest_lang_name} "
        f"translation that has the WRONG line count. Re-emit the "
        f"translation so it has exactly N lines, one per source line, "
        f"in the same order, preserving meaning. Merge or split lines "
        f"as needed; do not invent new content; do not drop content.\n\n"
        f"OUTPUT FORMAT — MANDATORY. Emit EXACTLY N lines. Each line "
        f"MUST begin with ⟨⟨K⟩⟩ where K is the source line number "
        f"(1..N) in ASCII digits. The tags are machine-parsed; omitting "
        f"them silently discards your work. A blank source line gets a "
        f"tag with nothing after it (⟨⟨K⟩⟩ alone). No preamble, no "
        f"numbering outside the tags, no markdown, no JSON."
    )
    numbered_src = "\n".join(f"SRC[{i+1}]: {l}" for i, l in enumerate(source_lines))
    numbered_tr  = "\n".join(f"TR[{i+1}]: {l}"  for i, l in enumerate(candidate_lines))
    user = (
        f"Target line count N = {N}\n"
        f"Current translation has {len(candidate_lines)} lines.\n\n"
        f"── SOURCE ({src_lang_name}, {N} lines) ──\n"
        f"{numbered_src}\n\n"
        f"── CURRENT TRANSLATION ({dest_lang_name}, {len(candidate_lines)} lines) ──\n"
        f"{numbered_tr}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]


def _strip_tags(text: str, target_len: int) -> list[str] | None:
    """Parse `⟨⟨N⟩⟩ content` lines back to a plain list[str].

    Returns None if the tagged output cannot be parsed cleanly to
    exactly `target_len` lines — the caller treats None the same way
    as a line-count mismatch and retries (or pad/truncates).
    """
    out = [""] * target_len
    seen: set[int] = set()
    for raw in text.split("\n"):
        m = _RE_TAG.match(raw)
        if not m:
            continue
        idx = int(m.group(1))
        if idx < 1 or idx > target_len:
            continue
        content = raw[m.end():].rstrip("\r")
        out[idx - 1] = content
        seen.add(idx)
    if len(seen) != target_len:
        return None
    return out


def reconcile_line_count(
    source_lines:    list[str],
    translated_lines: list[str],
    src_lang_name:   str,
    dest_lang_name:  str,
    *,
    max_attempts: int = 4,   # B13 (audit 2026-05-13): bumped from 2 to give
                             # gpt-5.4-mini room to converge on dense docs.
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

    # A14 (2026-05-12): share the transient-error retry policy with
    # translator + polisher. Without this, a transient 5xx becomes
    # "attempt failed" and routes straight to pad_or_truncate, which
    # mis-aligns the subtitle column. With call_with_retry, the same
    # error class gets exponential backoff first.
    from ._retry import call_with_retry

    last_attempt = list(translated_lines)
    for attempt in range(1, max_attempts + 1):
        try:
            resp = call_with_retry(
                lambda: client.chat.completions.create(
                    model=RECONCILER_MODEL,
                    messages=_build_messages(
                        source_lines, last_attempt, src_lang_name, dest_lang_name,
                    ),
                    extra_body={"prompt_cache_retention": PROMPT_CACHE_RETENTION},
                ),
                label=f"reconciler.attempt{attempt}",
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
            # 2026-05-13 (F5 sweep result): prefer the tag-format parser
            # because the new prompt asks for ⟨⟨N⟩⟩-tagged output. Fall
            # back to plain-line parsing for backward-compat with any
            # caller that supplied a different prompt builder.
            parsed = _strip_tags(text, len(source_lines))
            if parsed is not None:
                return parsed
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
