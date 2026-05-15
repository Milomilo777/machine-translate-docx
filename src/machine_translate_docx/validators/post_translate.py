"""Post-translation deterministic checks.

Run AFTER the translator returns and the response is parsed into a
line list, BEFORE the docx is written. Each check examines one
invariant and appends a :class:`ValidatorIssue` on violation.

Current check set (v1 — intentionally small; expand here as new
failure modes are found):

- ``LINE_COUNT_MISMATCH``      document-level: output line count ≠ input.
- ``BLANK_POSITION_MISMATCH``  per-line: blank lines at different indices.
- ``LATIN_LEAKAGE``            per-line: A-Z run outside protected spans
                               (FA target only — the universal prompt's
                               target can legitimately be Latin-script).
- ``PROTECTED_SPAN_MISSING``   per-line: URL / @handle / #hashtag / tech
                               code present in source but absent from output.
- ``LITERAL_BACKSLASH_N_LOST`` per-line: source has literal ``\\n`` but
                               output does not (placeholder lost).
- ``PERSIAN_BASHE``            per-line, FA only: output contains "باشه".
- ``PERSIAN_SEMICOLON_OUTSIDE_QUOTE`` per-line, FA only: "؛" present
                               outside any " ... " span.
- ``TOOSAT_PASSIVE``           per-line, FA only: warning, output has "توسط".
- ``FORBIDDEN_GLYPH``          per-line: output contains "⚠️" / "⚠".

The check set is small on purpose. We catch the highest-frequency
invariant violations and leave subtle linguistic checks (modality
drift, scope-attachment, ontological repair) to the polish pass.
"""
from __future__ import annotations

import re

from . import ValidatorIssue, ValidatorReport

# ── Protected-span regexes (W1, W3, ACRONYM-IN-PARENS) ───────────────────────

# W1: URL / @handle / #hashtag
_URL_RX     = re.compile(r"https?://\S+")
_HANDLE_RX  = re.compile(r"(?<!\w)@[A-Za-z0-9_]+")
# Allow Persian/Arabic letters in hashtags too — the prompt's W1 is permissive.
_HASHTAG_RX = re.compile(r"(?<!\w)#[A-Za-z0-9_؀-ۿ]+")

# W3: tech codes. Conservative pattern — wide enough to cover the known
# whitelist (v2.1, GPT-4o, F-16, H5N1, NaCl, S01E05, ISO-9001) but not
# greedy enough to swallow ordinary text.
_TECH_RX = re.compile(
    r"\b(?:"
    r"v\d+(?:\.\d+)*"                          # v2.1, v2.3.1
    r"|GPT-\d+(?:[a-z]+)?"                      # GPT-4o, GPT-5
    r"|F-\d+|MIG-\d+|B-\d+"                     # F-16, F-22, MIG-29, B-52
    r"|H\d+N\d+"                                # H5N1, H1N1
    r"|NaCl|H2O|CO2|HCl|MgSO4|H2SO4"            # common formulas
    r"|S\d{2}E\d{2}"                            # S01E05
    r"|ISO-\d+"                                 # ISO-9001
    r")\b"
)

# ACRONYM-IN-PARENS: "Full Name (ACRONYM)" — the parenthesized acronym
# is part of ALLOWED_LATIN. Used to mask before the Latin-leakage scan.
_ACRONYM_PAREN_RX = re.compile(r"\([A-Z]{2,}\)")

# Latin run that suggests untranslated source-language residue.
# Threshold ≥2 so single capital letters (vitamin codes per W3) don't
# false-positive — those should already be transliterated by the prompt
# but the prompt explicitly allows ambiguity here.
_LATIN_RUN_RX = re.compile(r"[A-Za-z]{2,}")

# ── Forbidden-output regexes ─────────────────────────────────────────────────

_FORBIDDEN_GLYPHS = ("⚠️", "⚠")
_BASHE_RX  = re.compile(r"(?<!\w)(?:باشه|باشهٔ)(?!\w)")
_TOOSAT_RX = re.compile(r"(?<!\w)توسط(?!\w)")

# Quote pair for "is this semicolon inside a quote?" stripping.
_QUOTE_RX = re.compile(r'"[^"]*"')


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_protected_spans(line: str) -> list[str]:
    """Return every protected-span token (URL, handle, hashtag, tech code)."""
    spans: list[str] = []
    spans += _URL_RX.findall(line)
    spans += _HANDLE_RX.findall(line)
    spans += _HASHTAG_RX.findall(line)
    spans += _TECH_RX.findall(line)
    return spans


def _strip_protected(line: str) -> str:
    """Remove protected spans so the Latin-residue scan doesn't false-fire.

    Returns the line with every URL, handle, hashtag, tech code, and
    acronym-in-parens replaced by a single space.
    """
    s = _URL_RX.sub(" ", line)
    s = _HANDLE_RX.sub(" ", s)
    s = _HASHTAG_RX.sub(" ", s)
    s = _TECH_RX.sub(" ", s)
    s = _ACRONYM_PAREN_RX.sub(" ", s)
    return s


def _has_semicolon_outside_quotes(line: str) -> bool:
    """True iff a Persian semicolon (``؛``) exists outside any " ... " span."""
    stripped = _QUOTE_RX.sub(" ", line)
    return "؛" in stripped


def _is_persian_target(target_lang: str) -> bool:
    return target_lang.strip().lower() in {"fa", "per", "persian", "farsi"}


# ── Public entry point ──────────────────────────────────────────────────────

def run_checks(
    source_lines: list[str],
    translate_output: list[str],
    target_lang: str,
) -> ValidatorReport:
    """Execute every check and return a ValidatorReport.

    Caller guarantees ``is_validator_enabled() is True`` (the public
    ``validate_translate_output`` wrapper enforces this).
    """
    issues: list[ValidatorIssue] = []

    # ── Document-level: line count + blank positions ───────────────────────
    n_in, n_out = len(source_lines), len(translate_output)
    if n_in != n_out:
        issues.append(ValidatorIssue(
            line_no=0,
            code="LINE_COUNT_MISMATCH",
            severity="error",
            message=f"input has {n_in} lines, output has {n_out}",
        ))
        # Bail out of per-line checks — indices would be meaningless.
        return ValidatorReport(enabled=True, issues=issues)

    for i, (src, out) in enumerate(zip(source_lines, translate_output), 1):
        if (not src.strip()) != (not out.strip()):
            issues.append(ValidatorIssue(
                line_no=i,
                code="BLANK_POSITION_MISMATCH",
                severity="error",
                message=f"source blank={not src.strip()}, output blank={not out.strip()}",
            ))

    # ── Per-line checks ────────────────────────────────────────────────────
    is_fa = _is_persian_target(target_lang)

    for i, (src, out) in enumerate(zip(source_lines, translate_output), 1):
        if not out.strip():
            continue

        # Forbidden glyphs (warning marker, emoji)
        for g in _FORBIDDEN_GLYPHS:
            if g in out:
                issues.append(ValidatorIssue(
                    line_no=i, code="FORBIDDEN_GLYPH", severity="error",
                    message=f"output contains forbidden glyph {g!r}",
                ))
                break

        # Persian-specific lexical checks
        if is_fa:
            if _BASHE_RX.search(out):
                issues.append(ValidatorIssue(
                    line_no=i, code="PERSIAN_BASHE", severity="error",
                    message="output contains 'باشه' — should normalize to 'بله' / 'حتماً' / 'درست است'",
                ))
            if _TOOSAT_RX.search(out):
                issues.append(ValidatorIssue(
                    line_no=i, code="TOOSAT_PASSIVE", severity="warning",
                    message="output contains 'توسط' — prefer active or prepositional form",
                ))
            if _has_semicolon_outside_quotes(out):
                issues.append(ValidatorIssue(
                    line_no=i, code="PERSIAN_SEMICOLON_OUTSIDE_QUOTE",
                    severity="error",
                    message="'؛' present outside a quoted span — should be '،' or clause split",
                ))

            # Latin leakage outside protected spans
            stripped = _strip_protected(out)
            latin_runs = _LATIN_RUN_RX.findall(stripped)
            if latin_runs:
                issues.append(ValidatorIssue(
                    line_no=i, code="LATIN_LEAKAGE", severity="error",
                    message=f"unexpected Latin runs in FA output: {latin_runs[:3]}",
                ))

        # Universal (any target): protected-span preservation. Every URL,
        # handle, hashtag, and tech code present in the source MUST appear
        # byte-id in the corresponding output line.
        for span in _extract_protected_spans(src):
            if span not in out:
                issues.append(ValidatorIssue(
                    line_no=i, code="PROTECTED_SPAN_MISSING", severity="error",
                    message=f"protected span {span!r} missing from output",
                ))

        # Universal: literal "\n" preservation (W4 placeholder).
        if "\\n" in src and "\\n" not in out:
            issues.append(ValidatorIssue(
                line_no=i, code="LITERAL_BACKSLASH_N_LOST", severity="error",
                message="source has literal '\\n' but output does not",
            ))

    return ValidatorReport(enabled=True, issues=issues)
