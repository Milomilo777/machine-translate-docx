# ADR 004: Resilience and Performance

## Context
Translation jobs often involve 100+ page documents. API rate limits (HTTP 429), partial timeouts, memory leaks from token counting, and OS file locking are critical risks.

## Decision
1. **Network Resilience:** External API calls are wrapped in a 3-attempt loop with Thread sleep fallbacks to absorb temporary HTTP 429/timeout spikes. (Future optimization: Spring Retry or Resilience4j).
2. **Graceful Degradation:** If the LLM returns fewer or more lines than requested (Line Mismatch), the system aborts 1:1 mapping but saves the raw text output to the document with a `[SMTV_REVIEW_NEEDED]` flag rather than crashing the job.
3. **Memory:** Token counting via `JTokkit` uses static `EncodingRegistry` instances to prevent heap exhaustion.
4. **I/O Safety:** All Apache POI streams (`FileInputStream`, `FileOutputStream`) are managed via strict `try-with-resources` to guarantee file handle release, preventing Windows "File in Use" errors.
