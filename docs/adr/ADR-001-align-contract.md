# ADR-001 — Aligner Contract V1

**Status:** ACCEPTED
**Date:** 2026-03-08

## Problem
align_text() in translator.py calls the OpenAI API and returns a JSON dict.
Currently there is no validation on the returned JSON.
If the model skips a key or returns malformed JSON, it silently corrupts data.

## Decision
1. After every align_text() API call, validate the JSON output:
   - Strip the _reasoning key before returning.
   - If any input key is missing from the result, restore it from target_dict.
   - If the result is empty or not a dict, return target_dict entirely.
2. Never pass global_context to align_text(). The aligner is a structural JSON
   router, not
