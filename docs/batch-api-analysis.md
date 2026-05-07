# OpenAI Batch API — Cost / Latency Analysis for This Pipeline

> Research-only document. No code change is proposed in this PR.
> Sources: [OpenAI Batch guide](https://developers.openai.com/api/docs/guides/batch),
> [OpenAI Pricing](https://openai.com/api/pricing/),
> [Hacker News discussion](https://news.ycombinator.com/item?id=40043845),
> [TokenMix 2026 pricing summary](https://tokenmix.ai/blog/openai-batch-api-pricing).

---

## What the Batch API offers

| Aspect | Detail |
|--------|--------|
| Discount | Flat **50 %** off both prompt and completion tokens, every model |
| Completion window | 24 h SLA; typical 1–6 h depending on size and load |
| Submission | Upload a `.jsonl` (≤ 200 MB, ≤ 50 000 requests) → poll batch status |
| Endpoints relevant to us | `/v1/chat/completions` (translator + polisher) |
| Rate-limit headroom | Substantially higher than the realtime quota — separate bucket |
| Prompt caching interaction | Not documented as guaranteed; safest to assume cache hits are best-effort within a batch |

## Where this pipeline sits today (realtime)

A typical chatgpt-polish job on a Persian DOCX makes **two synchronous API calls**:

1. **translate** — single-call, whole document, ~1 800 s timeout. Uses `gpt-5.5`.
2. **polish** — single-call, same document, ~1 800 s timeout. Uses `gpt-5.5`.

End-to-end wall time observed: typically **40 s – 5 min per file** depending on
length. Single-call mode means the user is sitting in front of the loading
overlay (now with the new progress bar) until both calls return.

## Where Batch could win

| Scenario | Realtime cost | Batch cost | Savings |
|----------|---------------|------------|---------|
| 1 doc, single-call (current) | 100 % | 50 % | ½ the bill |
| 50 docs queued together | 100 % × 50 | 50 % × 50 | ½ the bill, plus one batch round-trip |
| Doc > 1 500 lines (would benefit from chunking) | high cost, long sync wait | submitted as N chunked batch entries | ½ the bill **and** unlocks parallelism |

## Where Batch loses

| Reason | Why it hurts this product |
|--------|--------------------------|
| 24 h SLA | UI today shows a loading overlay and expects a result in minutes |
| Cannot stream / progress | The new `PROGRESS:N` markers stop being meaningful — the user just sees "submitted, check back in a few hours" |
| Re-architecting required | Job state needs `batch_id` + a poller for batch status, not subprocess stdout |
| Prompt caching unclear | Today every API call sets `prompt_cache_retention=24h`; batch behaviour is not explicitly documented as cache-friendly |
| Operationally heavier | Need result-mapping by `custom_id`, retry on partial failure, etc. |

## Decision matrix

| User intent | Recommended path |
|-------------|------------------|
| "I uploaded one DOCX and I'm waiting" — current product | **Realtime** (no change). Batch's 24 h SLA is a UX regression here. |
| "I have a folder of 200 episodes; I'll come back tomorrow" | **Batch** is a clear win — half the bill, no human waiting. |
| "I want lower cost without changing UX" | Skip Batch. Bigger lever: prompt-cache hit-rate + chunking. |

## Concrete proposal (out of scope for this PR)

1. **Add a `--batch` mode to `machine-translate-docx.py`** that, instead of
   calling `oai_translator.translate(...)` synchronously, writes a single
   JSONL line to a per-job `.batch.jsonl` file, then exits with a hint to
   the user to run `--batch-collect` later.
2. **Add a tiny `batch_collector.py`** that polls `/v1/batches/<id>`,
   downloads results, and runs the same `polisher.polish(...)` step
   realtime (since polish is half the cost and most of the latency is
   in translate).
3. **Keep realtime as the default** for the local-launcher UI.

## TL;DR

For the current single-job interactive UI, Batch API is **not** worth the
re-architecture. For a future bulk-translation use case (whole season at
once), it is the cheapest option available — half the bill, same model
quality.
