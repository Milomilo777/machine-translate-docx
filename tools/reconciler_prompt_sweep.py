"""
Reconciler prompt sweep — FLYIN-1646 F5 investigation, 2026-05-13.

Goal: find a prompt that converges gpt-5.4-mini on the line-count
reconciliation for a hard real document (1387 src lines vs 1403
translator output lines). 4× attempts with the current production
prompt all returned 1403 lines.

We try up to 10 distinct prompts, each ONCE. Stop on the first one
that returns exactly 1387 lines.

If all 10 fail, escalate to gpt-5.5 (up to 2 attempts), under the
explicit user authorisation of 2026-05-13.

Usage:
    PYTHONPATH=src python tools/reconciler_prompt_sweep.py
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
from openai import OpenAI

# ── data ──────────────────────────────────────────────────────────────────
TEMP = Path(os.environ.get("TEMP", "C:/Users/Owner/AppData/Local/Temp"))
SRC_FILE = TEMP / "recon" / "src.txt"
TR_FILE  = TEMP / "recon" / "tr.txt"

src_lines = SRC_FILE.read_text(encoding="utf-8").split("\n")
tr_lines  = TR_FILE.read_text(encoding="utf-8").split("\n")

N_SRC = len(src_lines)
N_TR  = len(tr_lines)
print(f"src = {N_SRC} lines, translator output = {N_TR} lines, delta = {N_TR - N_SRC}")

# ── client ────────────────────────────────────────────────────────────────
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def call(model: str, system: str, user: str) -> tuple[str, dict]:
    """Single Responses-API call. Returns (text, usage_dict)."""
    t0 = time.time()
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        extra_body={"prompt_cache_retention": "24h"},
        reasoning={"effort": "low" if "mini" in model else "none"},
        timeout=600,
    )
    elapsed = time.time() - t0
    text = resp.output_text if hasattr(resp, "output_text") else resp.choices[0].message.content
    usage = (resp.model_dump() or {}).get("usage") or {}
    return text, {"elapsed_s": elapsed, **usage}


def build_user_payload(src, tr, hint=""):
    """The user message that all prompts share. Hint can be empty."""
    numbered_src = "\n".join(f"SRC[{i+1}]: {l}" for i, l in enumerate(src))
    numbered_tr  = "\n".join(f"TR[{i+1}]: {l}" for i, l in enumerate(tr))
    parts = [
        f"Number of source lines (target N): {len(src)}",
        f"Number of current translator-output lines: {len(tr)}",
    ]
    if hint:
        parts.append(hint)
    parts.extend([
        "",
        "── SOURCE (English) ──",
        numbered_src,
        "",
        "── CURRENT TRANSLATION (Persian) ──",
        numbered_tr,
    ])
    return "\n".join(parts)


# ── 10 candidate system prompts ───────────────────────────────────────────
PROMPTS = [
    # P1 — current production prompt (control)
    (
        "P1 — production baseline",
        "You are a line-count reconciler. The user gives you an English "
        "source with N lines and its Persian translation with M lines. "
        "Re-emit the Persian translation so it has exactly N lines, in the "
        "same order. Do not change words. Combine or split lines as needed "
        "to match line N to source line N. Output Persian only, one line "
        "per source line, no numbering, no preamble.",
    ),
    # P2 — explicit delta + merge instruction
    (
        "P2 — delta-aware merge",
        "ROLE: Persian subtitle re-aligner.\n\n"
        "TASK: The translator produced 1403 lines for a 1387-line source. "
        "Find the 16 extra Persian lines and MERGE each into the line "
        "above. Do not delete content; do not change wording. The output "
        "must have EXACTLY 1387 lines, one Persian line per source line, "
        "in original order.\n\n"
        "OUTPUT FORMAT: 1387 Persian lines separated by single \\n. No "
        "numbering. No labels. No explanation. Plain text only.",
    ),
    # P3 — line-by-line zip
    (
        "P3 — zip and merge stragglers",
        "Walk through the source and translation together, line by line. "
        "For each SRC[i], assign the corresponding TR[i] as its Persian. "
        "If a Persian line clearly belongs to the previous source line "
        "(e.g. continuation of the same sentence, attribution like "
        "'(Master)', short tag), merge it into the previous output line. "
        "Goal: exactly 1387 output lines. Output Persian only, no markers.",
    ),
    # P4 — tag-format output
    (
        "P4 — tagged output for parsing",
        "Emit 1387 Persian lines. Each line MUST start with ⟨⟨N⟩⟩ where "
        "N is the source line number (1..1387). Tags are machine-parsed; "
        "omitting them silently discards your work. If a source line has "
        "no natural Persian text, emit ⟨⟨N⟩⟩ alone (empty after the tag). "
        "Never emit 1403 lines. Never skip a number. No preamble.",
    ),
    # P5 — chain of thought before answer
    (
        "P5 — silent reasoning + commitment",
        "Step 1 (silent): identify which lines in the Persian translation "
        "are extras (i.e. lines that should be merged into the previous "
        "Persian line). There should be exactly 16 extras since src=1387 "
        "and tr=1403. Step 2 (silent): plan the merges. Step 3 (output): "
        "emit exactly 1387 Persian lines in source order, no preamble, no "
        "numbering, plain text only. Output ONLY step-3 text.",
    ),
    # P6 — strict template
    (
        "P6 — strict count assertion",
        "ASSERTION: Your response MUST contain EXACTLY 1387 newline-"
        "separated Persian lines. Any other count is a failure and the "
        "downstream pipeline will discard your work. Do not over-count. "
        "Do not under-count. Read the source carefully, walk line by "
        "line, and consolidate the Persian fragments accordingly. Output "
        "Persian only.",
    ),
    # P7 — empty-line awareness
    (
        "P7 — preserve blank source lines",
        "The source has 1387 lines. Some source lines are intentionally "
        "blank (empty rows between sentence groups). Your Persian output "
        "must mirror EXACTLY: blank source line → blank Persian line. "
        "Non-blank source line → exactly one Persian line. Total: 1387. "
        "If your draft has 1403, you have 16 extra non-blank lines that "
        "belong to adjacent groups — merge them. Output plain Persian.",
    ),
    # P8 — show me which lines extra
    (
        "P8 — diff-driven repair",
        "INPUT: 1387 numbered source lines + 1403 numbered Persian lines. "
        "Some Persian lines are continuations of earlier ones. STEP A "
        "(silent): identify the 16 continuation lines by checking if "
        "merging each Persian line into the previous gives a complete "
        "Persian sentence. STEP B (output): emit 1387 lines. Persian "
        "only, plain text, no preamble, no tags.",
    ),
    # P9 — example-driven
    (
        "P9 — worked-example template",
        "Re-align the Persian translation to match the source line count.\n\n"
        "EXAMPLE (small):\n"
        "SRC[1]: Hello there.\nSRC[2]: How are you?\n\n"
        "TR[1]: سلام\nTR[2]: به شما\nTR[3]: حالتان چطور است؟\n\n"
        "Aligned (2 lines):\n"
        "سلام به شما\nحالتان چطور است؟\n\n"
        "Now do the same for the input below. Target: 1387 lines. Persian "
        "only, no numbering, no preamble.",
    ),
    # P10 — high-pressure / final
    (
        "P10 — high-pressure final-resort",
        "This is your FINAL attempt. The pipeline has called you 9 times "
        "and you keep returning the wrong count. Make this attempt "
        "different. The source has 1387 lines. The Persian output you "
        "give MUST have 1387 lines, not one more, not one less. The 16 "
        "extra lines in the current draft are continuations — merge each "
        "into the line above. Count your output before finalising. "
        "Persian text only.",
    ),
]


# ── runner ────────────────────────────────────────────────────────────────
def try_prompt(label, system, model="gpt-5.4-mini", hint=""):
    print(f"\n── {label} (model={model}) ──")
    user = build_user_payload(src_lines, tr_lines, hint=hint)
    try:
        text, usage = call(model, system, user)
    except Exception as e:
        print(f"  ERROR: {e!r}")
        return None
    out_lines = text.strip().split("\n")
    n_out = len(out_lines)
    delta = n_out - N_SRC
    cost_in  = usage.get("input_tokens", usage.get("prompt_tokens", 0))
    cost_out = usage.get("output_tokens", usage.get("completion_tokens", 0))
    elapsed  = usage.get("elapsed_s", 0)
    status   = "✓ MATCH" if n_out == N_SRC else f"✗ delta {delta:+d}"
    print(f"  {status}  out={n_out} in_tok={cost_in} out_tok={cost_out} time={elapsed:.1f}s")
    return n_out, text


# ── main ──────────────────────────────────────────────────────────────────
def main():
    print(f"\n=== Sweep: 10 prompts with gpt-5.4-mini ===")
    winner = None
    for label, sysp in PROMPTS:
        result = try_prompt(label, sysp)
        if result and result[0] == N_SRC:
            winner = (label, sysp, result[1])
            print(f"\n→ {label} WORKS. Stopping sweep.")
            break

    if winner:
        print(f"\n✓ DONE: '{winner[0]}' converged. No need to escalate.")
        return 0

    print(f"\n=== Mini failed all 10; escalating to gpt-5.5 (×2) ===")
    best_prompt = ("P2 — delta-aware merge", PROMPTS[1][1])   # best-shaped task spec
    for i in (1, 2):
        result = try_prompt(f"5.5 attempt {i} ({best_prompt[0]})", best_prompt[1], model="gpt-5.5")
        if result and result[0] == N_SRC:
            print(f"\n→ gpt-5.5 converged on attempt {i}.")
            return 0
    print("\n✗ all attempts (10 mini + 2 main) failed. Manual review needed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
