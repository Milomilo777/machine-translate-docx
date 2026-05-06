import os
import re
import time
import json
from pathlib import Path
from openai import OpenAI

from .translator import _normalize_lang, _find_prompts_dir, _prompt_lang_code


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
    def __init__(self, model: str = "gpt-5.5", dest_lang: str = "fa",
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

        if specific.exists():
            return specific.read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"No polish prompt for language '{lang_code}' "
            f"(looked for {specific}). "
            f"Create prompts/polish_{lang_code}.txt (or pass an explicit prompt_path)."
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
            _extra["reasoning_effort"] = "high"

        t0 = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user_content},
                ],
                extra_body=_extra,
                timeout=1800,
            )
        except Exception as e:
            print(f"[ERROR] Polisher API call failed: {e} — returning original translation.")
            self.last_call_data = {"error": str(e)}
            return translated_text

        elapsed       = time.time() - t0
        response_json = response.model_dump()
        raw           = response.choices[0].message.content

        polished_lines = self._parse_output(raw, fa_lines)

        if len(polished_lines) != n:
            print(
                f"[WARN] Polisher: output line count {len(polished_lines)} != {n} "
                f"— returning original translation."
            )
            return translated_text

        usage = response_json.get("usage") or {}
        ptd   = usage.get("prompt_tokens_details") or {}

        self.last_call_data = {
            "type":           "polish",
            "model":          self.model,
            "system_prompt":  system,
            "user_prompt":    user_content,
            "response_raw":   response_json,
            "input_fa_text":  translated_text,
            "output_text":    "\n".join(polished_lines),
            "tokens": {
                "prompt":     usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total":      usage.get("total_tokens", 0),
                "cached":     ptd.get("cached_tokens", 0),
            },
            "cost_usd":        self._estimate_cost(response_json),
            "elapsed_seconds": round(elapsed, 3),
        }

        print(f"[INFO] Polisher: {n} lines refined in {elapsed:.1f}s (model={self.model})")
        return "\n".join(polished_lines)

    def _estimate_cost(self, response_json: dict) -> float:
        PRICES = {
            "gpt-5.5":      {"input": 3.00,  "output": 15.00},  # estimate — update when pricing confirmed
            "gpt-5.4":      {"input": 2.50,  "output": 15.00},
            "gpt-5.4-mini": {"input": 0.75,  "output": 4.50},
            "gpt-5.4-nano": {"input": 0.20,  "output": 1.25},
            "gpt-4o":       {"input": 2.50,  "output": 10.00},
            "gpt-4o-mini":  {"input": 0.15,  "output": 0.60},
        }
        model = response_json.get("model", self.model)
        usage = response_json.get("usage") or {}
        price = next((v for k, v in PRICES.items() if k in model), None)
        if not price:
            return 0.0
        p_tok = usage.get("prompt_tokens", 0)
        c_tok = usage.get("completion_tokens", 0)
        return round(
            (p_tok / 1_000_000) * price["input"] +
            (c_tok / 1_000_000) * price["output"],
            6
        )
