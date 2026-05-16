"""Single source of truth for OpenAI per-1M-token pricing.

Extracted 2026-05-16 (P2.8 from master audit) from three near-duplicate
``PRICES`` tables that lived inside ``translator._estimate_cost``,
``polisher._estimate_cost``, and ``splitting._compute_cost``. The three
copies had already drifted (polisher was missing 5 models that
translator + splitting had), and adding a new model meant editing
three files in lock-step — a recipe for cost-miscalculation bugs.

Public API:

  * :data:`PRICES` — the canonical model → {input, cached, output}
    rate table. ``cached`` is the discounted rate for tokens that
    re-used the 24-h prompt cache.
  * :func:`get_price(model)` — return the price dict for the first
    table entry whose key is a substring of ``model``, or ``None``
    if no entry matches. Lookup order matters: tables are dicts in
    Python 3.7+ which preserve insertion order, so longer/more
    specific names should come BEFORE shorter prefixes (e.g.
    ``gpt-5.5`` before ``gpt-5``). The substring match means
    ``gpt-5.5-mini`` would match ``gpt-5.5``, then ``gpt-5``; we
    rely on insertion order to pick the more specific one.

Pricing snapshot date: April 2026. Update this table when
OpenAI publishes new rates.
"""
from __future__ import annotations

from typing import Final, TypedDict


class PriceTier(TypedDict):
    input:  float
    cached: float
    output: float


PRICES: Final[dict[str, PriceTier]] = {
    # Order matters — see module docstring. Longer/more specific
    # model names come first so substring matching picks them.
    "gpt-5.5":       {"input": 5.00, "cached": 0.50,  "output": 30.00},
    "gpt-5.4-mini":  {"input": 0.75, "cached": 0.075, "output": 4.50},
    "gpt-5.4-nano":  {"input": 0.20, "cached": 0.02,  "output": 1.25},
    "gpt-5.4":       {"input": 2.50, "cached": 0.25,  "output": 15.00},
    "gpt-5.2":       {"input": 1.75, "cached": 0.175, "output": 14.00},
    "gpt-5.1":       {"input": 1.25, "cached": 0.125, "output": 10.00},
    "gpt-5-mini":    {"input": 0.25, "cached": 0.025, "output": 2.00},
    "gpt-5-nano":    {"input": 0.05, "cached": 0.005, "output": 0.40},
    "gpt-5":         {"input": 1.25, "cached": 0.125, "output": 10.00},
    "gpt-4o-mini":   {"input": 0.15, "cached": 0.015, "output": 0.60},
    "gpt-4o":        {"input": 2.50, "cached": 0.25,  "output": 10.00},
}


def get_price(model: str | None) -> PriceTier | None:
    """Return the price tier matching ``model``, or ``None``.

    Substring match against insertion-ordered :data:`PRICES`. The
    first key found inside ``model`` wins. Returns ``None`` if
    ``model`` is falsy or no key matches.
    """
    if not model:
        return None
    return next((v for k, v in PRICES.items() if k in model), None)


__all__ = ["PRICES", "PriceTier", "get_price"]
