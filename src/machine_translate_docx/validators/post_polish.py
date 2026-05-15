"""Post-polish deterministic checks.

The polish output uses tagged format — every line begins with
``⟨⟨N⟩⟩`` where N is the 1-based line number. This module verifies tag
integrity in addition to running the standard translation-output checks
on the payload (the text after the tag).

Checks beyond what ``post_translate`` does:

- ``TAG_FORMAT_INVALID``       per-line: output line has no ``⟨⟨N⟩⟩`` prefix.
- ``TAG_NUMBER_MISMATCH``      per-line: tag number ≠ position in list.
- ``UNEXPECTED_BLANK_OUTPUT``  per-line: polisher emitted blank where the
                               [TGT] input was nonblank.

All ``post_translate`` checks (LINE_COUNT_MISMATCH, LATIN_LEAKAGE,
PROTECTED_SPAN_MISSING, PERSIAN_BASHE, …) run on the payload after the
tag is stripped.
"""
from __future__ import annotations

import re

from . import ValidatorIssue, ValidatorReport
from .post_translate import (
    _BASHE_RX,
    _FORBIDDEN_GLYPHS,
    _LATIN_RUN_RX,
    _TOOSAT_RX,
    _extract_protected_spans,
    _has_semicolon_outside_quotes,
    _is_persian_target,
    _strip_protected,
)

# ``⟨⟨N⟩⟩`` tag at the very start of the line. ASCII digits only.
_TAG_RX = re.compile(r"^⟨⟨(\d+)⟩⟩")


def run_checks(
    source_lines: list[str],
    fa_input_lines: list[str],
    polish_output: list[str],
    target_lang: str,
) -> ValidatorReport:
    """Execute every polish-output check and return a ValidatorReport.

    Args:
        source_lines:    EN/source-language lines (one per pair).
        fa_input_lines:  FA/target lines the polisher RECEIVED as [TGT].
        polish_output:   what the polisher RETURNED.
        target_lang:     short locale code, used for FA-specific checks.

    Caller guarantees ``is_validator_enabled() is True``.
    """
    issues: list[ValidatorIssue] = []

    # ── Document-level: pair count vs output count ─────────────────────────
    n_pairs, n_out = len(fa_input_lines), len(polish_output)
    if n_pairs != n_out:
        issues.append(ValidatorIssue(
            line_no=0, code="LINE_COUNT_MISMATCH", severity="error",
            message=f"input pairs={n_pairs}, output lines={n_out}",
        ))
        return ValidatorReport(enabled=True, issues=issues)

    is_fa = _is_persian_target(target_lang)

    # Some callers don't pass source_lines (mock paths). Be defensive.
    src_aligned: list[str] = (
        list(source_lines) if source_lines else [""] * n_pairs
    )
    if len(src_aligned) < n_pairs:
        src_aligned += [""] * (n_pairs - len(src_aligned))

    for i, (src, fa_in, out) in enumerate(zip(src_aligned, fa_input_lines, polish_output), 1):
        # ── Tag format ─────────────────────────────────────────────────────
        m = _TAG_RX.match(out)
        if not m:
            issues.append(ValidatorIssue(
                line_no=i, code="TAG_FORMAT_INVALID", severity="error",
                message=f"line missing ⟨⟨N⟩⟩ prefix: {out[:40]!r}",
            ))
            payload = out
        else:
            n_tag = int(m.group(1))
            if n_tag != i:
                issues.append(ValidatorIssue(
                    line_no=i, code="TAG_NUMBER_MISMATCH", severity="error",
                    message=f"tag says {n_tag}, position is {i}",
                ))
            payload = out[m.end():].lstrip()

        # ── Blank-line consistency ────────────────────────────────────────
        if not payload:
            if fa_in.strip():
                issues.append(ValidatorIssue(
                    line_no=i, code="UNEXPECTED_BLANK_OUTPUT", severity="error",
                    message="polisher emitted blank where [TGT] was nonblank",
                ))
            continue

        # ── Per-line lexical / orthographic checks ────────────────────────
        for g in _FORBIDDEN_GLYPHS:
            if g in payload:
                issues.append(ValidatorIssue(
                    line_no=i, code="FORBIDDEN_GLYPH", severity="error",
                    message=f"output contains forbidden glyph {g!r}",
                ))
                break

        if is_fa:
            if _BASHE_RX.search(payload):
                issues.append(ValidatorIssue(
                    line_no=i, code="PERSIAN_BASHE", severity="error",
                    message="output contains 'باشه' — polish should have normalized it",
                ))
            if _TOOSAT_RX.search(payload):
                issues.append(ValidatorIssue(
                    line_no=i, code="TOOSAT_PASSIVE", severity="warning",
                    message="output contains 'توسط' — prefer active or prepositional form",
                ))
            if _has_semicolon_outside_quotes(payload):
                issues.append(ValidatorIssue(
                    line_no=i, code="PERSIAN_SEMICOLON_OUTSIDE_QUOTE",
                    severity="error",
                    message="'؛' present outside a quoted span",
                ))

            # Latin leakage outside protected spans.
            stripped = _strip_protected(payload)
            latin_runs = _LATIN_RUN_RX.findall(stripped)
            if latin_runs:
                issues.append(ValidatorIssue(
                    line_no=i, code="LATIN_LEAKAGE", severity="error",
                    message=f"unexpected Latin runs in FA output: {latin_runs[:3]}",
                ))

        # Protected-span presence — every URL/handle/hashtag/tech code in
        # the source pair MUST appear byte-id in the polish output.
        for span in _extract_protected_spans(src):
            if span not in payload:
                issues.append(ValidatorIssue(
                    line_no=i, code="PROTECTED_SPAN_MISSING", severity="error",
                    message=f"protected span {span!r} missing from polish output",
                ))

        # Literal "\n" preservation.
        if "\\n" in src and "\\n" not in payload:
            issues.append(ValidatorIssue(
                line_no=i, code="LITERAL_BACKSLASH_N_LOST", severity="error",
                message="source has literal '\\n' but polish output does not",
            ))

    return ValidatorReport(enabled=True, issues=issues)
