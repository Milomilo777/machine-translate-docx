import os
import re
import time
import json
from pathlib import Path
from openai import OpenAI

from .translator import _normalize_lang, _find_prompts_dir, _prompt_lang_code
from ._retry import call_with_retry, prompt_hash
from .fa_postprocess import normalize_fa

try:
    from ..config import DEFAULT_AI_MODEL as _DEFAULT_AI_MODEL
except Exception:
    _DEFAULT_AI_MODEL = "gpt-5.5"


class OpenAIPolisher:
    """
    Post-translation Persian polish pass.
    Receives paired EN source + FA translation blocks, returns polished FA.
    One API call per block — mirrors the translator's block structure.

    Prompt lookup order:
      1. explicit prompt_path argument
      2. prompts/polish_{lang_code}.txt  (language-specific)
      3. FileNotFoundError — no universal polish fallback by design
    """

    # model="gpt-5.4-mini"  ← mini (cheaper, faster, lower quality)
    def __init__(self, model: str = _DEFAULT_AI_MODEL, dest_lang: str = "fa",
                 source_lang: str = "en", prompt_path: str = None):
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        self.client = OpenAI(api_key=self.api_key)
        self.dest_lang = _normalize_lang(dest_lang)
        # 2026-05-15 (v7 STATIC + JOB_CONFIG): source language is stored
        # at construction so polish() can build a JOB_CONFIG envelope
        # in the user message. Backwards-compatible default is "en".
        self.source_lang = source_lang
        self.system_prompt = self._load_prompt(dest_lang, prompt_path)
        self.last_call_data = {}

    # ── prompt loading ────────────────────────────────────────────────────────

    def _load_prompt(self, dest_lang: str, prompt_path: str) -> str:
        if prompt_path:
            p = Path(prompt_path)
            if p.exists():
                return p.read_text(encoding="utf-8")
            raise FileNotFoundError(f"Polish prompt not found: {prompt_path}")

        lang_code   = _prompt_lang_code(dest_lang)
        prompts_dir = _find_prompts_dir(Path(__file__).parent)
        specific    = prompts_dir / f"polish_{lang_code}.txt"
        universal   = prompts_dir / "polish_universal.txt"

        # 2026-05-12 (phase-1 prompt rewrite): for Persian, prepend the
        # shared SMTV brand lexicon so translator and polisher edit
        # the same spec. For non-PER targets, fall back to the
        # universal polish prompt (added 2026-05-12) instead of
        # raising — keeps the polish pass useful for other languages.
        if specific.exists():
            text = specific.read_text(encoding="utf-8")
            if lang_code == "PER":
                shared = prompts_dir / "_smtv_locks.txt"
                if shared.exists():
                    text = shared.read_text(encoding="utf-8") + "\n\n" + text
            return text

        if universal.exists():
            return universal.read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"No polish prompt for language '{lang_code}' "
            f"(looked for {specific} and {universal})."
        )

    # ── input / output formatting ─────────────────────────────────────────────

    def _build_user_content(self, src_lines: list, fa_lines: list) -> str:
        """Build the FA-only user content (experiment/fa-only-polish 2026-05-19).

        ARCHITECTURE CHANGE — branch experiment/fa-only-polish:
        The user message no longer carries EN source lines. The polisher
        sees ONLY the Persian target text, line-by-line. The system
        prompt body (``polish_PER.txt``) is UNCHANGED on this branch
        — the user explicitly asked for an architecture-only edit so
        the experiment isolates the effect of dropping the EN context.

        Rationale: most of the remaining quality issues are calque /
        translationese problems that a bilingual lens tends to miss
        because the model is busy verifying meaning preservation. By
        feeding only FA, we re-aim the model's attention on Persian
        fluency. Risk: it can't catch omission / negation drift / scope
        without the EN anchor; that's the trade-off being measured.

        ``src_lines`` argument is kept for signature compatibility with
        the call sites that still pass both — it's ignored here.
        """
        # Format kept as "Line N [FA]: ..." so the [FA] tag in the
        # existing system prompt still matches. This keeps the prompt
        # body byte-identical between bilingual + FA-only branches; only
        # the user-message structure differs.
        parts = []
        for i, fa in enumerate(fa_lines, 1):
            parts.append(f"Line {i} [FA]: {fa}")
        return "\n".join(parts)

    def _build_user_envelope(self, src_lines: list, fa_lines: list) -> str:
        """Return the JOB_CONFIG + FA-only user payload (branch-experiment).

        v7 STATIC + JOB_CONFIG layout, with the bilingual <PAIRS> block
        replaced by an FA-only listing inside a renamed <FA_LINES>
        block. The block-name change is a deliberate signal to the
        model that the layout is different from the cached prefix.

        2026-05-19 — branch experiment/fa-only-polish: still no edits
        to the prompt body itself, per user instruction. Only the user
        message changes.
        """
        from ._lang_descriptors import lang_descriptor
        n = len(fa_lines)
        src_desc = lang_descriptor(self.source_lang)
        tgt_desc = lang_descriptor(self.dest_lang)
        fa_block = self._build_user_content(src_lines, fa_lines)
        return (
            "<JOB_CONFIG>\n"
            f"SOURCE_LANGUAGE: {src_desc}\n"
            f"TARGET_LANGUAGE: {tgt_desc}\n"
            f"N: {n}\n"
            "</JOB_CONFIG>\n"
            "\n"
            "<FA_LINES>\n"
            f"{fa_block}\n"
            "</FA_LINES>"
        )

    @staticmethod
    def _normalize_digits(s: str) -> str:
        """Convert Persian/Arabic-Indic digits to ASCII so regex can match them."""
        for i, ch in enumerate("۰۱۲۳۴۵۶۷۸۹"):
            s = s.replace(ch, str(i))
        return s

    @staticmethod
    def _detect_en_residue(text: str) -> bool:
        """Return True when a polished FA line looks like untranslated English.

        Triggers when latin letters dominate (>40 % of characters in the line)
        AND the line carries enough words to be a real sentence (>5 tokens).
        Whitelist tokens (URLs, codes like GPT-4o, single acronyms) are short
        and pass through; this guard targets full-sentence regressions where
        the model returned the source verbatim.
        """
        if not text or not text.strip():
            return False
        latin = sum(1 for c in text if 'a' <= c.lower() <= 'z')
        word_count = len(text.split())
        return latin > len(text) * 0.4 and word_count > 5

    def _parse_output(self, raw: str, fa_lines: list) -> list:
        """
        Parse model output — tries four strategies in order:

        1. ⟨⟨N⟩⟩ tag format (primary — DOTALL, handles extra newlines in content).
        2. Legacy 'Line N: text' numbered format (ASCII or Persian digits).
        3. Plain line-for-line match when model returns exactly N lines.
        4. Pass raw output through so the downstream length check logs the mismatch.
        """
        n = len(fa_lines)

        def _build_from_dict(result: dict) -> list:
            output = []
            for i in range(1, n + 1):
                if i in result:
                    text = result[i]
                    output.append(text if (text or not fa_lines[i - 1]) else fa_lines[i - 1])
                else:
                    output.append(fa_lines[i - 1])
            return output

        # ── Strategy 1: ⟨⟨N⟩⟩ tag format ────────────────────────────────────
        matches = re.findall(r"⟨⟨(\d+)⟩⟩\s*(.*?)(?=⟨⟨\d+⟩⟩|$)", raw, re.DOTALL)
        if matches:
            result = {}
            for idx_str, content in matches:
                idx = int(idx_str)
                if 1 <= idx <= n:
                    result[idx] = content.strip()
            if result:
                return _build_from_dict(result)

        # ── Strategy 2: legacy 'Line N:' format ──────────────────────────────
        result = {}
        for line in raw.strip().split("\n"):
            normalized = self._normalize_digits(line.strip())
            m = re.match(r"^Line\s+(\d+):\s?(.*)$", normalized)
            if m:
                idx = int(m.group(1))
                if 1 <= idx <= n:
                    content = re.sub(r"^[Ll]ine\s+[\d۰-۹]+:\s?", "", line.strip())
                    result[idx] = content
        if result:
            print("[INFO] Polisher: legacy 'Line N:' format detected.")
            return _build_from_dict(result)

        # ── Strategy 3: plain line-for-line ──────────────────────────────────
        raw_lines = raw.strip().split("\n")
        if len(raw_lines) == n:
            print(
                "[INFO] Polisher: no tags found — "
                "using plain line-for-line match."
            )
            return [
                raw_lines[i] if raw_lines[i] or not fa_lines[i] else fa_lines[i]
                for i in range(n)
            ]

        # ── Strategy 4: pass raw through (downstream length check logs it) ───
        first_raw = repr(raw_lines[0][:100]) if raw_lines else "'(empty)'"
        print(
            f"[WARN] Polisher: no tags found, raw={len(raw_lines)} lines != {n}. "
            f"Passing raw output through. First line: {first_raw}"
        )
        return raw_lines

    # ── public API ────────────────────────────────────────────────────────────

    def set_model(self, model: str):
        self.model = model

    def polish(self, src_text: str, translated_text: str) -> str:
        """
        Polish a translated Persian block using its English source as guardrail.

        src_text:        English source block (N newline-separated lines)
        translated_text: Persian translation block (same N lines)
        Returns:         Polished Persian block (same N lines)
        """
        src_lines = src_text.strip().split("\n")
        fa_lines  = translated_text.strip().split("\n")
        n         = len(fa_lines)

        self.last_call_data = {}

        if len(src_lines) != n:
            print(
                f"[WARN] Polisher: line count mismatch "
                f"src={len(src_lines)} fa={n} — skipping polish, returning original."
            )
            self.last_call_data = {
                "type":           "polish",
                "model":          self.model,
                "polish_skipped": True,
                "skipped_reason": "line_count_mismatch_input",
                "lines_processed": n,
                "lines_modified":  0,
            }
            return translated_text

        # 2026-05-15 (v7 STATIC + JOB_CONFIG): the user message now
        # carries a <JOB_CONFIG> envelope (language pair + N) before
        # the bilingual <PAIRS> block. The system prompt stays
        # byte-identical across calls so OpenAI prompt cache can hit.
        user_content = self._build_user_envelope(src_lines, fa_lines)

        # The system prompt is loaded once at __init__ and reused
        # verbatim. No per-call substitution.
        system = self.system_prompt

        # 2026-05-15 (cache reliability fix): pair prompt_cache_retention with
        # a stable prompt_cache_key. See translator.py for the full rationale.
        # Bump the version suffix whenever polish_PER.txt / _smtv_locks.txt
        # change in a non-backwards-compatible way.
        _extra = {
            "prompt_cache_retention": "24h",
            "prompt_cache_key": "mtd-polisher-v7.6-faonly",
        }
        if "mini" in self.model.lower():
            _extra["reasoning_effort"] = "medium"

        # GPT-5.x models have broken prompt-caching via chat.completions (known
        # OpenAI bug).  Route them to the Responses API for working cache hits.
        _use_responses_api = (
            "pro" in self.model.lower()
            or self.model.lower().startswith("gpt-5")
        )
        # reasoning_effort is a chat.completions extra — omit it for Responses API
        # (Responses API accepts reasoning via the `reasoning` parameter, not extra_body).
        _extra_responses = {
            "prompt_cache_retention": "24h",
            "prompt_cache_key": "mtd-polisher-v7.6-faonly",
        }
        # Reasoning effort policy (per model class):
        #   mini       → medium  (was "high"; 2026-05-12 user lowered to medium
        #                          — high cost ~3× wall-clock for diminishing
        #                          quality gain on a 30 % modify-rate document.)
        #   non-mini   → none    (F3 / 2026-05-12; the main gpt-5.5 model
        #                          defaults to medium and that turned an 11K
        #                          char polish into a 64-minute run, so we
        #                          keep it explicitly "none" until the user
        #                          asks otherwise.)
        # The translator never spends reasoning tokens (C2 invariant).
        #
        # 2026-05-13: MTD_POLISH_REASONING env var overrides the default
        # for ad-hoc benchmarking (e.g. `MTD_POLISH_REASONING=low` for a
        # fast smoke test on a long document). Valid values:
        # none / low / medium / high (gpt-5.4-mini also supports xhigh).
        _user_override = os.environ.get("MTD_POLISH_REASONING", "").strip().lower()
        if _user_override in {"none", "low", "medium", "high", "xhigh"}:
            _reasoning_param = {"effort": _user_override}
        else:
            _reasoning_param = (
                {"effort": "medium"} if "mini" in self.model.lower()
                else {"effort": "none"}
            )

        _messages_list = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ]

        t0 = time.time()
        try:
            if _use_responses_api:
                # 2026-05-17 (FLYIN hang fix): streaming for gpt-5.x via
                # Responses API — non-streaming SDK path hangs on large
                # payloads (openai/openai-python#2725). Same fix as the
                # translator.
                #
                # 2026-05-18 hardening: ``MTD_FORCE_NON_STREAM=1`` falls
                # back to non-stream Responses API. Emergency rollback
                # only — the #2725 hang risk returns under non-stream.
                from ._stream_helper import (
                    use_non_stream,
                    maybe_log_unknown_event,
                )
                from ._stream_circuit import (
                    record_stream_success,
                    record_stream_failure,
                )
                if use_non_stream():
                    print(
                        "[INFO] polisher using non-stream Responses API "
                        "(rollback active: MTD_FORCE_NON_STREAM=1 or "
                        "circuit breaker OPEN); #2725 hang risk on large "
                        "gpt-5.x payloads",
                        flush=True,
                    )
                    response = call_with_retry(
                        lambda: self.client.responses.create(
                            model=self.model,
                            input=_messages_list,
                            extra_body=_extra_responses,
                            reasoning=_reasoning_param,
                            timeout=1800,
                        ),
                        label="polisher.responses.create(non-stream)",
                    )
                else:
                    def _stream_call():
                        s = self.client.responses.create(
                            model=self.model,
                            input=_messages_list,
                            extra_body=_extra_responses,
                            reasoning=_reasoning_param,
                            timeout=1800,
                            stream=True,
                        )
                        _chunks: list[str] = []
                        _final = None
                        _delta_n = 0
                        for event in s:
                            et = getattr(event, "type", "")
                            if et == "response.output_text.delta":
                                _chunks.append(getattr(event, "delta", "") or "")
                                _delta_n += 1
                                # B3 (2026-05-18): tick every 50 deltas for
                                # the launcher's UI progress bar (see
                                # local_launcher.py stdout reader).
                                if _delta_n % 50 == 0:
                                    print(f"[STREAM] role=polisher chunks={_delta_n}", flush=True)
                            elif et == "response.completed":
                                _final = getattr(event, "response", None)
                            elif et in ("response.failed", "response.incomplete"):
                                _final = getattr(event, "response", None)
                                raise RuntimeError(
                                    f"polisher stream ended with type={et}: {_final}"
                                )
                            else:
                                # 2026-05-18 hardening: surface SDK changes.
                                maybe_log_unknown_event("polisher", et)
                        return {"text": "".join(_chunks), "final": _final}

                    _sr = call_with_retry(
                        _stream_call,
                        label="polisher.responses.create(stream)",
                    )
                    from types import SimpleNamespace
                    _final = _sr["final"]
                    _text = _sr["text"]
                    # CODE-C-9 (2026-05-18 audit): mirror the translator
                    # warning — stream without response.completed leaves
                    # usage data unavailable. Also feed the outcome to
                    # the circuit breaker for auto-rollback.
                    if _final is None:
                        print(
                            "[WARN] polisher: stream ended without response.completed — "
                            "usage data unavailable, log sidecar will record zero tokens/cost",
                            flush=True,
                        )
                        record_stream_failure("polisher", "no_response_completed")
                    else:
                        record_stream_success("polisher")
                    response = SimpleNamespace(
                        output_text=_text,
                        model_dump=(lambda f: (lambda: f.model_dump()))(_final) if _final else (lambda: {}),
                    )
            else:
                response = call_with_retry(
                    lambda: self.client.chat.completions.create(
                        model=self.model,
                        messages=_messages_list,
                        extra_body=_extra,
                        timeout=1800,
                    ),
                    label="polisher.chat.completions.create",
                )
        except Exception as e:
            # B8 (audit 2026-05-13): structured failure signal. Caller and
            # sidecar JSON can now check last_call_data["polish_skipped"]
            # to know the polish pass didn't run, instead of inferring it
            # from the absence of token counts.
            print(f"[ERROR] Polisher API call failed: {e} — returning original translation.")
            self.last_call_data = {
                "type":           "polish",
                "model":          self.model,
                "error":          str(e),
                "polish_skipped": True,
                "skipped_reason": "api_error",
                "lines_processed": n,
                "lines_modified":  0,
            }
            return translated_text

        elapsed       = time.time() - t0
        response_json = response.model_dump()

        # Normalize Responses-API usage shape -> Chat-Completions shape.
        # Consolidated to _retry.normalize_usage 2026-05-16 (P2.9).
        from ._retry import normalize_usage
        response_json = normalize_usage(response_json)

        if _use_responses_api and hasattr(response, "output_text") and response.output_text is not None:
            raw = response.output_text
        else:
            raw = response.choices[0].message.content

        polished_lines = self._parse_output(raw, fa_lines)

        # 2026-05-13 (F8): count real edits BEFORE the line-shape reconciler
        # touches the output. The reconciler re-emits every line through
        # the model, which makes ~100 % of rows look "modified" downstream
        # even when the polish content barely changed. We capture the
        # honest count here on the raw polished_lines vs fa_lines pairing
        # (using min length so a mismatch still gives us a meaningful
        # number). When `was_reconciled` is True, treat the figure as a
        # lower bound — the real edit count may be higher because the
        # reconciler may have merged content from extra Persian lines.
        _pre_reconcile_modified = sum(
            1 for a, b in zip(fa_lines, polished_lines) if a != b
        )
        _was_reconciled = False

        if len(polished_lines) != n:
            # 2026-05-13 (F5 cascade): instead of dropping the polish pass
            # outright, hand the mismatched output to the line-count
            # reconciler (gpt-5.4-mini, tag-format prompt). If the
            # reconciler converges, we keep the polished content and
            # only fix the line shape. If it cannot, we still fall back
            # to the untouched translator output.
            print(
                f"[WARN] Polisher: output line count {len(polished_lines)} != {n} "
                f"— invoking reconciler to repair line shape."
            )
            try:
                from .line_count_reconciler import reconcile_line_count
                reconciled = reconcile_line_count(
                    fa_lines, polished_lines,
                    "English", "Persian",
                    max_attempts=2,    # quick attempt; failure → revert
                )
                if len(reconciled) == n:
                    polished_lines = reconciled
                    _was_reconciled = True
                    print(
                        f"[INFO] Polisher: reconciler restored {n} lines; "
                        f"keeping polished content (line-shape repaired)."
                    )
                else:
                    raise ValueError("reconciler did not converge")
            except Exception as _r:
                print(f"[WARN] Polisher: reconciler failed ({_r!r}); reverting to translator output.")
                self.last_call_data = {
                    "type":           "polish",
                    "model":          self.model,
                    "polish_skipped": True,
                    "skipped_reason": "line_count_mismatch_output",
                    "lines_processed": n,
                    "lines_modified":  0,
                }
                return translated_text

        # English-residue scan: any line that came back as English (or mostly
        # English) is replaced with the pre-polish translator output for that
        # line. Indices of replaced rows are recorded in last_call_data so the
        # caller can surface them in the run JSON log.
        residue_lines: list = []
        for i, polished in enumerate(polished_lines):
            if self._detect_en_residue(polished):
                fallback = fa_lines[i] if i < len(fa_lines) else ''
                residue_lines.append({
                    'index':      i + 1,
                    'polished':   polished,
                    'fallback':   fallback,
                })
                polished_lines[i] = fallback
        if residue_lines:
            print(
                f"[WARN] Polisher: {len(residue_lines)} line(s) flagged as "
                f"English residue — reverted to translator output."
            )

        # Conservative FA normalization — only for FA target. Arabic-Indic
        # digits + Arabic Yeh/Kaf get mapped to Persian variants. SAFETY:
        # 2026-05-13 — applying this unconditionally was actively breaking
        # Arabic output (every legitimate ي in AR became ی). Now gated by
        # dest_lang so AR / UR / etc. keep their canonical script set.
        if self.dest_lang == "fa":
            normalized_lines = [normalize_fa(line) for line in polished_lines]
            if any(a != b for a, b in zip(polished_lines, normalized_lines)):
                print("[INFO] Polisher: FA letter/digit normalization applied.")
            polished_lines = normalized_lines

        usage = response_json.get("usage") or {}
        ptd   = usage.get("prompt_tokens_details") or {}

        # A10 (2026-05-12): the prior "refined N lines" log counted lines
        # **processed**, not lines **changed** — which gave a green
        # "refined 51 lines" log on a run where the diff later showed zero
        # changes (F8). Count modifications now, and surface a quality
        # warning when the polish pass barely moved anything for a Persian
        # chatgpt-polish job.
        # F8 (audit 2026-05-13): when the reconciler ran, the post-pass
        # diff is dominated by re-emit noise (every line passed through
        # gpt-5.4-mini once more, so almost everything looks "modified").
        # Prefer the pre-reconcile honest count; expose was_reconciled
        # so callers can warn the user that the figure is a lower bound.
        if _was_reconciled:
            _lines_modified = _pre_reconcile_modified
        else:
            _lines_modified = sum(
                1 for a, b in zip(fa_lines, polished_lines) if a != b
            )

        # 2026-05-15 (log compaction): mirror the translator's lean form.
        # By default we drop system_prompt / user_prompt / response_raw /
        # input_fa_text (the last is byte-identical to translation.output_text
        # in the same block, so storing it twice doubled log size for no
        # audit benefit). Set MTD_LOG_VERBOSE=1 to restore the legacy
        # fields when debugging a single call.
        _verbose = os.environ.get("MTD_LOG_VERBOSE", "").strip() == "1"
        self.last_call_data = {
            "type":           "polish",
            "model":          self.model,
            "prompt_hash":    prompt_hash(system),
            "output_text":    "\n".join(polished_lines),
            "en_residue":     residue_lines,
            "lines_processed":  n,
            "lines_modified":   _lines_modified,
            "was_reconciled":   _was_reconciled,
            "tokens": {
                "prompt":     usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total":      usage.get("total_tokens", 0),
                "cached":     ptd.get("cached_tokens", 0),
            },
            "cost_usd":        self._estimate_cost(response_json),
            "elapsed_seconds": round(elapsed, 3),
        }
        if _verbose:
            self.last_call_data["system_prompt"] = system
            self.last_call_data["user_prompt"]   = user_content
            self.last_call_data["response_raw"]  = response_json
            self.last_call_data["input_fa_text"] = translated_text

        # Always remember the latest user envelope so the run_info section
        # of the sidecar can carry one canonical sample. self.system_prompt
        # is already populated at __init__.
        self.last_user_prompt = user_content

        # Warn when polish was effectively a no-op on a real document.
        # Threshold 2 % of lines is generous — anything lower is unusual
        # and almost always means a prompt-content mismatch (F6).
        if n >= 20 and _lines_modified / max(n, 1) < 0.02:
            print(
                f"[WARN] Polisher: only {_lines_modified}/{n} lines changed "
                f"(<2 %) — polish pass likely ineffective for this document. "
                "Review prompts/polish_PER.txt sensitivity (F6)."
            )

        _reconcile_note = " (line shape repaired by reconciler — count is a lower bound)" if _was_reconciled else ""
        print(
            f"[INFO] Polisher: {n} lines processed, {_lines_modified} "
            f"modified, in {elapsed:.1f}s (model={self.model}){_reconcile_note}"
        )

        # 2026-05-15 (v7 follow-up): post-polish validator gate.
        # Disabled by default; opt in with MTD_VALIDATOR_ENABLED=1. The
        # report only logs to stdout — we never reject the polish output
        # because of validator findings (the caller would have no fallback).
        # The validator is a diagnostic, not a hard gate; over time the
        # most common error codes can graduate into the prompt or a
        # repair loop.
        try:
            from ..validators import validate_polish_output, is_validator_enabled
            if is_validator_enabled():
                # The polisher emits ⟨⟨N⟩⟩ tags only when parsing succeeded
                # via Strategy 1; later strategies strip the tags. Build a
                # tagged form for the validator regardless so TAG_FORMAT_INVALID
                # doesn't false-fire on parser-stripped output.
                tagged_for_check = [
                    f"⟨⟨{i+1}⟩⟩ {ln}" if ln else f"⟨⟨{i+1}⟩⟩"
                    for i, ln in enumerate(polished_lines)
                ]
                report = validate_polish_output(
                    source_lines=src_lines,
                    fa_input_lines=fa_lines,
                    polish_output=tagged_for_check,
                    target_lang=self.dest_lang,
                )
                if report.issues:
                    print(f"[validator] post-polish: {report.summary()}")
                    for issue in report.errors():
                        print(
                            f"[validator] ERROR line {issue.line_no}: "
                            f"{issue.code} — {issue.message}"
                        )
                    for issue in report.warnings():
                        print(
                            f"[validator] warn  line {issue.line_no}: "
                            f"{issue.code} — {issue.message}"
                        )
        except Exception as _e:
            # The validator must never break a job. Log and move on.
            print(f"[validator] post-polish gate skipped: {_e}")

        return "\n".join(polished_lines)

    def _estimate_cost(self, response_json: dict) -> float:
        # 2026-05-16 (P2.8): pricing consolidated. The previous local
        # PRICES table here was missing 5 models (gpt-5, gpt-5-mini,
        # gpt-5-nano, gpt-5.1, gpt-5.2) compared to translator.py.
        from ._pricing import get_price

        model = response_json.get("model", self.model)
        usage = response_json.get("usage") or {}
        price = get_price(model)
        if not price:
            return 0.0
        p_tok      = usage.get("prompt_tokens", 0)
        c_tok      = usage.get("completion_tokens", 0)
        cached_tok = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        non_cached = max(0, p_tok - cached_tok)
        cached_price = price.get("cached", price["input"] * 0.1)
        return round(
            (non_cached  / 1_000_000) * price["input"]  +
            (cached_tok  / 1_000_000) * cached_price    +
            (c_tok       / 1_000_000) * price["output"],
            6
        )
