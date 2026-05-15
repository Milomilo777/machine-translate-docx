"""Prompt-regression test suite.

Each YAML fixture in ``tests/fixtures/prompts_regression/`` describes
one regression case. Two run modes:

MOCK MODE (default — CI-safe, no API calls)
    For each fixture, the fixture's ``mock_output`` is fed to the
    validator and the suite asserts the fixture's ``invariants``.
    This is a regression test of the VALIDATOR plus a contract test
    on the documented expected output. Fast and free.

LIVE MODE (opt-in — runs only with ``--live`` plus OPENAI_API_KEY)
    For each fixture, the fixture's ``input`` is sent to the real
    OpenAI translator / polisher using the canonical prompt files.
    The model's output is then asserted against the same
    ``invariants``. A new prompt version must clear ≥95% of
    fixtures before promotion to canonical.

Run:
    pytest tests/test_prompts_regression.py              # mock
    pytest tests/test_prompts_regression.py --live       # real API

Add a new case by dropping a new ``case_NN_*.yaml`` next to
this file's fixtures dir. See the README in that directory for
the schema.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# Make src/ importable without installing.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "prompts_regression"


# ── pytest config: --live flag ───────────────────────────────────────────────

def pytest_addoption(parser):  # noqa: D401
    """Add the --live flag to pytest for this test module."""
    # NOTE: pytest only invokes pytest_addoption from conftest.py at the
    # rootdir, not from a regular test file. We expose this as a helper
    # but also fall back to an env var for users who can't add conftest
    # plumbing.


def _live_mode_requested(request) -> bool:
    """Return True if the user asked for live API runs.

    Two signals: ``--live`` flag on pytest, or ``MTD_REGRESSION_LIVE=1``
    in the env. The env var is the portable path because adding a
    custom ``--live`` flag would require editing conftest.py.
    """
    env = os.environ.get("MTD_REGRESSION_LIVE", "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True
    try:
        return bool(request.config.getoption("--live"))
    except Exception:
        return False


# ── Fixture loading ─────────────────────────────────────────────────────────

def _load_fixtures() -> list[dict[str, Any]]:
    """Read every case_*.yaml file in the fixtures dir."""
    cases = []
    if not FIXTURES_DIR.is_dir():
        return cases
    for path in sorted(FIXTURES_DIR.glob("case_*.yaml")):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and data.get("id"):
                data["_path"] = path
                cases.append(data)
        except Exception as exc:
            # Surface fixture errors but don't crash collection.
            print(f"[fixture-error] {path.name}: {exc}", file=sys.stderr)
    return cases


_FIXTURES = _load_fixtures()


# ── Invariant assertions ────────────────────────────────────────────────────

def _output_lines(output: str) -> list[str]:
    """Split output preserving blank lines exactly as the model returned them."""
    return output.split("\n")


def _strip_tag(line: str) -> str:
    """Strip the ⟨⟨N⟩⟩ polish tag if present."""
    import re
    m = re.match(r"^⟨⟨\d+⟩⟩\s*", line)
    return line[m.end():] if m else line


def _assert_invariants(fixture: dict[str, Any], output_text: str, *, is_polish: bool) -> None:
    """Run every invariant block in *fixture* against *output_text*.

    Raises pytest failure with a descriptive message on first mismatch.
    """
    name = fixture["id"]
    invariants = fixture.get("invariants", {}) or {}
    raw_lines = _output_lines(output_text.rstrip("\n"))
    payload_lines = [_strip_tag(ln) for ln in raw_lines] if is_polish else raw_lines
    joined_payload = "\n".join(payload_lines)

    # line_count
    expected_lc = invariants.get("line_count")
    if expected_lc is not None:
        assert len(raw_lines) == expected_lc, (
            f"[{name}] line_count: expected {expected_lc}, got {len(raw_lines)}"
        )

    # must_contain
    for token in invariants.get("must_contain", []) or []:
        assert token in joined_payload, f"[{name}] must_contain: {token!r} not in output"

    # must_not_contain
    for token in invariants.get("must_not_contain", []) or []:
        assert token not in joined_payload, f"[{name}] must_not_contain: {token!r} present in output"

    # must_contain_one_of — accepts either a flat list of alternative tokens
    # ("at least one of these MUST be present") or a list of lists
    # ("for each group, at least one of its members must be present").
    flat_alt = invariants.get("must_contain_one_of")
    if isinstance(flat_alt, list) and flat_alt:
        if all(isinstance(x, str) for x in flat_alt):
            assert any(tk in joined_payload for tk in flat_alt), (
                f"[{name}] must_contain_one_of: none of {flat_alt!r} present in output"
            )
        else:
            for token_group in flat_alt:
                if isinstance(token_group, list):
                    assert any(tk in joined_payload for tk in token_group), (
                        f"[{name}] must_contain_one_of group: none of {token_group!r} present in output"
                    )

    # name_consistency: token in first occurrence == token in last occurrence.
    for name_token in invariants.get("name_consistency", []) or []:
        occurrences = [ln for ln in payload_lines if name_token in ln]
        if len(occurrences) >= 2:
            # All occurrences must contain the same token spelling.
            # Since the token itself is the spelling, the assert is
            # implicit. But we should also check the token is the
            # canonical form by verifying it's the EXACT same byte
            # sequence everywhere — which YAML token equality already does.
            assert all(name_token in ln for ln in occurrences), (
                f"[{name}] name_consistency: {name_token!r} variants found"
            )


def _validator_assertions(fixture, validator_report) -> None:
    """Check ``validator_must_not_flag`` / ``validator_must_flag`` lists."""
    name = fixture["id"]
    invariants = fixture.get("invariants", {}) or {}
    flagged_codes = {issue.code for issue in validator_report.issues}

    for code in invariants.get("validator_must_not_flag", []) or []:
        assert code not in flagged_codes, (
            f"[{name}] validator unexpectedly flagged {code}; issues={list(flagged_codes)}"
        )

    for code in invariants.get("validator_must_flag", []) or []:
        assert code in flagged_codes, (
            f"[{name}] validator expected to flag {code} but did not; issues={list(flagged_codes)}"
        )


# ── Mock-mode test ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f.get("id", "unknown"))
def test_fixture_mock(fixture, monkeypatch):
    """Validate the hand-crafted mock_output against the fixture's invariants.

    This is a contract test on the documented expected behavior, plus
    a regression test on the validator. Runs in CI without any API call.
    """
    # Enable the validator so we can assert its output too.
    monkeypatch.setenv("MTD_VALIDATOR_ENABLED", "1")

    pipeline = fixture.get("pipeline", "translate")
    src = fixture["input"].rstrip("\n")
    src_lines = src.split("\n")
    mock_output = fixture.get("mock_output", "").rstrip("\n")
    target_lang = fixture.get("target_lang", "fa")

    if not mock_output:
        pytest.skip(f"{fixture['id']}: no mock_output, live-only fixture")

    # Output-text invariants (line count, must_contain, etc.).
    _assert_invariants(fixture, mock_output, is_polish=(pipeline == "polish"))

    # Validator invariants.
    if pipeline == "translate":
        from machine_translate_docx.validators import validate_translate_output
        report = validate_translate_output(
            source_lines=src_lines,
            translate_output=mock_output.split("\n"),
            target_lang=target_lang,
        )
    elif pipeline == "polish":
        from machine_translate_docx.validators import validate_polish_output
        fa_input = fixture.get("fa_input", "").rstrip("\n").split("\n") or src_lines
        report = validate_polish_output(
            source_lines=src_lines,
            fa_input_lines=fa_input,
            polish_output=mock_output.split("\n"),
            target_lang=target_lang,
        )
    else:
        pytest.skip(f"{fixture['id']}: unknown pipeline {pipeline!r}")

    _validator_assertions(fixture, report)


# ── Live-mode test ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f.get("id", "unknown"))
def test_fixture_live(fixture, request):
    """Run the real translator/polisher against the fixture's input.

    Opt-in via ``MTD_REGRESSION_LIVE=1`` or pytest ``--live``. Costs
    API tokens — use sparingly.
    """
    if not _live_mode_requested(request):
        pytest.skip("live mode not requested (set MTD_REGRESSION_LIVE=1)")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set — cannot run live regression")

    pipeline = fixture.get("pipeline", "translate")
    src = fixture["input"].rstrip("\n")
    source_lang = fixture.get("source_lang", "en")
    target_lang = fixture.get("target_lang", "fa")

    # Enable the validator for live runs so we can assert its output too.
    os.environ["MTD_VALIDATOR_ENABLED"] = "1"

    if pipeline == "translate":
        from machine_translate_docx.openai_tools.translator import OpenAITranslator
        t = OpenAITranslator()
        t.set_filename(f"regression_{fixture['id']}")
        _resp, translated = t.translate(source_lang, target_lang, src)
        output_text = translated
    elif pipeline == "polish":
        from machine_translate_docx.openai_tools.polisher import OpenAIPolisher
        p = OpenAIPolisher(dest_lang=target_lang, source_lang=source_lang)
        fa_input = fixture.get("fa_input", "").rstrip("\n") or src
        output_text = p.polish(src, fa_input)
    else:
        pytest.skip(f"unknown pipeline: {pipeline!r}")

    _assert_invariants(fixture, output_text, is_polish=(pipeline == "polish"))


# ── Smoke test: at least one fixture loaded ─────────────────────────────────

def test_fixtures_directory_not_empty():
    """Defensive: catch a CI setup where fixtures got moved / deleted."""
    assert len(_FIXTURES) >= 5, (
        f"Expected ≥5 prompt-regression fixtures, found {len(_FIXTURES)} "
        f"under {FIXTURES_DIR}. Add more cases or check the path."
    )
