# Prompt Regression Fixtures

Each `*.yaml` file describes one regression case for the EN→FA
translation / polish pipeline. Tests use these fixtures in two modes:

## Mock mode (default — runs in CI, no API calls)

A hand-crafted `expected_output` is fed to the validator. The test
asserts the validator finds the expected issues (or finds nothing
when the output is clean). This is fast and free — but it tests the
validator + the documented expected behavior, not the live model.

## Live mode (opt-in — needs OPENAI_API_KEY)

Run with `pytest tests/test_prompts_regression.py --live`. Each
fixture's `input` is sent to the real translator/polisher with the
canonical prompt files. The output is then asserted against the
fixture's `invariants` (token-level checks, not exact string match —
LLMs are stochastic). A new prompt version must clear ≥95% of
invariants before promotion to canonical.

## Fixture schema

```yaml
id: 01_short_name
description: |
  One-line human-readable description.
source_lang: en          # short locale code
target_lang: fa
pipeline: translate      # or "polish"
input: |
  Welcome to Supreme Master TV.
  I'm Bounxou from Laos.

# For mock mode: a hand-crafted output to validate.
mock_output: |
  خوش آمدید به سوپریم مستر تلویزیون.
  من بانخو هستم اهل لائوس.

# Invariants checked in both modes. Each entry is independent.
invariants:
  # line count must match input
  line_count: 2

  # tokens that MUST be present anywhere in the output
  must_contain:
    - "بانخو"
    - "لائوس"

  # tokens that MUST NOT appear anywhere
  must_not_contain:
    - "Bounxou"   # source name should be transliterated
    - "Laos"      # source place should be translated

  # tokens whose first-line form must equal their last-line form
  # (catches "ایلان ماسک / الون ماسک" drift)
  name_consistency:
    - "بانخو"

  # validator issue codes that must NOT fire
  validator_must_not_flag:
    - LATIN_LEAKAGE
    - PERSIAN_BASHE
    - LINE_COUNT_MISMATCH

  # validator issue codes that MUST fire (negative test)
  validator_must_flag: []
```

## Current coverage

Each fixture covers ONE prompt rule or invariant. The aim is for
every numbered v7 rule (PRE_EMIT_CHECK C1–C6, MN-1..MN-10, LS-1..LS-13,
SA-1..SA-13) to have at least one fixture by the time we reach
v8 or v7.x stability.
