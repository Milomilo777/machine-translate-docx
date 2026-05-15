"""Post-translation and post-polish validator layer.

Deterministic checks that run AFTER the OpenAI call returns, before the
result is written to disk. These checks catch invariant violations the
LLM occasionally produces — line count mismatch, Latin residue outside
ALLOWED_LATIN, missing protected spans (URLs / placeholders / tech codes),
forbidden output markers (⚠️, emoji), Persian "باشه" residue, "؛" outside
quoted spans, and a few more.

The whole layer is gated by ONE env var: ``MTD_VALIDATOR_ENABLED``.
When unset or set to "0"/"false"/"no"/"off", the validator is a no-op
and the caller sees an always-pass :class:`ValidatorReport`. This keeps
the contract on the caller side trivial — always call ``validate_*``,
read ``.passed``, the disabled path costs almost nothing (only the env
read).

Usage in caller code::

    from machine_translate_docx.validators import (
        validate_translate_output,
        is_validator_enabled,
    )

    report = validate_translate_output(
        source_lines=src,
        translate_output=lines,
        target_lang="fa",
    )
    if not report.passed:
        for issue in report.errors():
            print(f"[validator] {issue.code} @ line {issue.line_no}: {issue.message}")
        # caller chooses: retry, fail-job, or pass through with warnings.

Design notes:
- v1 is REPORT-ONLY: no auto-fix, no model re-prompt. The caller decides.
- Submodules (``post_translate`` / ``post_polish``) are imported lazily so
  disabled mode pays zero import cost beyond a single env-var read.
- Adding a new check is one function in the relevant submodule plus an
  entry in the issues list — no contract change for callers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "is_validator_enabled",
    "ValidatorIssue",
    "ValidatorReport",
    "validate_translate_output",
    "validate_polish_output",
]

# Single source of truth for the on/off switch. Read once per call; the
# value is checked lazily so changing the env var between runs is honored.
_ENV_VAR = "MTD_VALIDATOR_ENABLED"


def is_validator_enabled() -> bool:
    """Return True iff ``MTD_VALIDATOR_ENABLED`` is set to a truthy value.

    Truthy strings (case-insensitive): ``1`` / ``true`` / ``yes`` / ``on``.
    Anything else (including the env var being unset) → False.

    The validator is OPT-IN by design — packaged builds and CI smoke tests
    should not run it unless an operator explicitly turns it on.
    """
    v = os.environ.get(_ENV_VAR, "").strip().lower()
    return v in {"1", "true", "yes", "on"}


@dataclass
class ValidatorIssue:
    """A single invariant violation surfaced by the validator.

    ``line_no`` is 1-based for per-line issues; 0 marks document-level
    issues (line-count mismatch, blank-position drift on the whole file).
    """
    line_no: int
    code: str
    severity: Literal["error", "warning"]
    message: str


@dataclass
class ValidatorReport:
    """Result of running the validator on a translation or polish output.

    Attributes
    ----------
    enabled : bool
        Whether the validator actually ran. When False, ``passed`` is
        always True regardless of any ``issues`` list.
    issues : list[ValidatorIssue]
        All detected violations. Empty when disabled or when no issues.
    """
    enabled: bool
    issues: list[ValidatorIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True iff no ``error``-severity issues. Warnings are tolerated."""
        if not self.enabled:
            return True
        return not any(i.severity == "error" for i in self.issues)

    def errors(self) -> list[ValidatorIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> list[ValidatorIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def summary(self) -> str:
        if not self.enabled:
            return f"validator disabled ({_ENV_VAR} not set)"
        err = len(self.errors())
        warn = len(self.warnings())
        return f"validator: {err} errors, {warn} warnings"


def _disabled_report() -> ValidatorReport:
    return ValidatorReport(enabled=False)


# Public entry points. Submodules imported lazily so the disabled path
# is cheap (just the env read).

def validate_translate_output(
    source_lines: list[str],
    translate_output: list[str],
    target_lang: str = "fa",
) -> ValidatorReport:
    """Run post-translation checks. Returns a disabled report if the env
    var is not set (no-op fast path)."""
    if not is_validator_enabled():
        return _disabled_report()
    from .post_translate import run_checks  # noqa: PLC0415
    return run_checks(source_lines, translate_output, target_lang)


def validate_polish_output(
    source_lines: list[str],
    fa_input_lines: list[str],
    polish_output: list[str],
    target_lang: str = "fa",
) -> ValidatorReport:
    """Run post-polish checks. Returns a disabled report if the env var
    is not set (no-op fast path).

    Args:
        source_lines:    source-language lines (one per pair).
        fa_input_lines:  the FA/target lines the polisher RECEIVED.
        polish_output:   what the polisher RETURNED.
        target_lang:     short locale code (default "fa").
    """
    if not is_validator_enabled():
        return _disabled_report()
    from .post_polish import run_checks  # noqa: PLC0415
    return run_checks(source_lines, fa_input_lines, polish_output, target_lang)
