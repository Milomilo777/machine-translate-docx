# ADR 002: SMTV Tag and Unicode Preservation

## Context
Translation output must adhere strictly to internal SMTV broadcast subtitle rules, which rely on invisible structural metadata (`<ID:XXX>`, `<SMTV>`) and precise typography (e.g., Persian Zero-Width Non-Joiner / ZWNJ / `\u200C`).

## Decision
We enforce a strict non-corruption policy in the Java text pipelines.
- Standard "trim" or whitespace normalizations are heavily tested (via Jqwik property fuzzing) to ensure they do not obliterate ZWNJs or proprietary XML-style tags.
- The `PromptBuilderUtil` uses raw Java 17 Text Blocks to send these tags identically to the LLM.
