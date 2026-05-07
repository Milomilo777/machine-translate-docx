# Architectural Decisions — 2026

Log of significant design choices. Add an entry when a non-obvious approach is chosen.

Format: date, decision, alternatives considered, rationale.

---

## 2026-05-07 — Lower llm_threshold from 70 to 10

**Decision:** `FASubtitleAligner` default `llm_threshold` reduced from 70 to 10.  
**Alternatives:** Keep at 70 (faster, lower cost); raise to 100 (LLM reviews everything).  
**Rationale:** At threshold=70, only ~10 % of groups went to LLM; output quality was uneven.
At threshold=10, near-complete LLM review catches compound verb splits and poor alignments.
Cost increase is acceptable for broadcast-quality output.

---

## 2026-05-07 — Two-file download architecture

**Decision:** Job object carries `filename2`; frontend triggers two sequential downloads.  
**Alternatives:** Zip both files; separate endpoint; user manually downloads second file.  
**Rationale:** Zip requires extra library and changes UX. Separate endpoint adds complexity.
Sequential browser downloads (800 ms apart) work reliably across Chrome/Edge/Firefox.

---

## 2026-05-07 — Rename prompt files _fa → _PER

**Decision:** `translate_fa.txt` → `translate_PER.txt`; `polish_fa.txt` → `polish_PER.txt`.  
**Rationale:** Consistency with output filename convention (ISO 639-2/B codes).
New `_prompt_lang_code()` helper keeps `_normalize_lang()` untouched.

---

## 2026-03 — Single-call translation (whole file in one API request)

**Decision:** Translate the entire document in a single API call instead of block-by-block.  
**Alternatives:** Block-by-block (256-line chunks); paragraph-by-paragraph.  
**Rationale:** Block-by-block caused context loss at boundaries, inconsistent terminology, and
many round-trips. Single-call with gpt-5.5 handles large documents within context window and
produces more consistent output. Timeout set to 1800 s to accommodate large files.

---

## 2026-03 — Remove reasoning_effort from translator

**Decision:** `reasoning_effort` removed from `OpenAITranslator` API call.  
**Alternatives:** Keep it for better translation quality.  
**Rationale:** In testing, `reasoning_effort` caused 94 % of tokens to be reasoning tokens,
massively increasing cost with negligible quality improvement for translation tasks.
`reasoning_effort` remains in polisher only when model name contains `"mini"`.

---

## 2026-03 — Move {N} from system prompt to user message

**Decision:** Line count `{N}` removed from system prompt, added to user message instead.  
**Rationale:** System prompt must be identical across all requests for prompt cache to hit.
Including a per-document variable (`{N}`) in the system prompt invalidated the cache on every call.

---

## 2026-03 — Polling architecture (/upload → jobId → /status)

**Decision:** Upload returns jobId immediately; client polls `/status/:id` every 4 s.  
**Alternatives:** Long-polling; WebSocket; synchronous HTTP (wait for completion).  
**Rationale:** Translation can take 10–30 minutes for large files. Synchronous HTTP would
time out. WebSocket adds complexity. Polling is simple, reliable, and easy to debug.

---

## 2026-02 — FASubtitleAligner as separate pipeline stage

**Decision:** Aligner runs as a third stage after translate + polish, always using `gpt-5.4-mini`.  
**Alternatives:** Integrate alignment into polish step; use a deterministic algorithm only.  
**Rationale:** Alignment quality requires semantic understanding. Separating it as a distinct
stage keeps each component focused. Mini model is sufficient and cost-effective for this task.
Model is hardcoded to prevent accidental upgrade to a slower/costlier model.
