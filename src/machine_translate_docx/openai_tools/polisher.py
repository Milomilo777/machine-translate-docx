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
                 prompt_path: str = None):
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        self.client = OpenAI(api_key=self.api_key)
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
        parts = []
        for i, (en, fa) in enumerate(zip(src_lines, fa_lines), 1):
            parts.append(f"Line {i} [EN]: {en}")
            parts.append(f"Line {i} [FA]: {fa}")
        return "\n".join(parts)

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
            return translated_text

        user_content = (
            f"Lines to polish: {n}\n\n"
            + self._build_user_content(src_lines, fa_lines)
        )

        # {N}/{lines_count} removed from system prompt substitution so the prompt
        # stays identical across documents and benefits from prompt caching.
        system = self.system_prompt

        _extra = {"prompt_cache_retention": "24h"}
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
        _extra_responses = {"prompt_cache_retention": "24h"}
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
                response = call_with_retry(
                    lambda: self.client.responses.create(
                        model=self.model,
                        input=_messages_list,
                        extra_body=_extra_responses,
                        reasoning=_reasoning_param,
                        timeout=1800,
                    ),
                    label="polisher.responses.create",
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
            print(f"[ERROR] Polisher API call failed: {e} — returning original translation.")
            self.last_call_data = {"error": str(e)}
            return translated_text

        elapsed       = time.time() - t0
        response_json = response.model_dump()

        # Normalize Responses API usage fields to Chat Completions format.
        _raw_usage = response_json.get("usage") or {}
        if "input_tokens" in _raw_usage and "prompt_tokens" not in _raw_usage:
            response_json = dict(response_json)
            response_json["usage"] = {
                "prompt_tokens":             _raw_usage.get("input_tokens", 0),
                "completion_tokens":         _raw_usage.get("output_tokens", 0),
                "total_tokens":              _raw_usage.get("total_tokens", 0),
                "prompt_tokens_details":     _raw_usage.get("input_tokens_details", {}),
                "completion_tokens_details": _raw_usage.get("output_tokens_details", {}),
            }

        if _use_responses_api and hasattr(response, "output_text") and response.output_text is not None:
            raw = response.output_text
        else:
            raw = response.choices[0].message.content

        polished_lines = self._parse_output(raw, fa_lines)

        if len(polished_lines) != n:
            print(
                f"[WARN] Polisher: output line count {len(polished_lines)} != {n} "
                f"— returning original translation."
            )
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

        # Conservative FA normalization — Arabic Yeh/Kaf and Arabic-Indic
        # digits to their Persian equivalents only. Safe for TECH_LOCK
        # tokens, ASCII content, ZWNJ, quotes. See fa_postprocess.py for
        # the full list of what it does NOT touch.
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
        _lines_modified = sum(
            1 for a, b in zip(fa_lines, polished_lines) if a != b
        )

        self.last_call_data = {
            "type":           "polish",
            "model":          self.model,
            "prompt_hash":    prompt_hash(system),
            "system_prompt":  system,
            "user_prompt":    user_content,
            "response_raw":   response_json,
            "input_fa_text":  translated_text,
            "output_text":    "\n".join(polished_lines),
            "en_residue":     residue_lines,
            "lines_processed":  n,
            "lines_modified":   _lines_modified,
            "tokens": {
                "prompt":     usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total":      usage.get("total_tokens", 0),
                "cached":     ptd.get("cached_tokens", 0),
            },
            "cost_usd":        self._estimate_cost(response_json),
            "elapsed_seconds": round(elapsed, 3),
        }

        # Warn when polish was effectively a no-op on a real document.
        # Threshold 2 % of lines is generous — anything lower is unusual
        # and almost always means a prompt-content mismatch (F6).
        if n >= 20 and _lines_modified / max(n, 1) < 0.02:
            print(
                f"[WARN] Polisher: only {_lines_modified}/{n} lines changed "
                f"(<2 %) — polish pass likely ineffective for this document. "
                "Review prompts/polish_PER.txt sensitivity (F6)."
            )

        print(
            f"[INFO] Polisher: {n} lines processed, {_lines_modified} "
            f"modified, in {elapsed:.1f}s (model={self.model})"
        )
        return "\n".join(polished_lines)

    def _estimate_cost(self, response_json: dict) -> float:
        PRICES = {
            # Official API pricing — April 2026
            "gpt-5.5":      {"input": 5.00,  "cached": 0.50,  "output": 30.00},
            "gpt-5.4":      {"input": 2.50,  "cached": 0.25,  "output": 15.00},
            "gpt-5.4-mini": {"input": 0.75,  "cached": 0.075, "output": 4.50},
            "gpt-5.4-nano": {"input": 0.20,  "cached": 0.02,  "output": 1.25},
            "gpt-4o":       {"input": 2.50,  "cached": 0.25,  "output": 10.00},
            "gpt-4o-mini":  {"input": 0.15,  "cached": 0.015, "output": 0.60},
        }
        model = response_json.get("model", self.model)
        usage = response_json.get("usage") or {}
        price = next((v for k, v in PRICES.items() if k in model), None)
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
