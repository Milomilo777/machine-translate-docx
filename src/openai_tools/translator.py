import os
import uuid
import json
import time
import tiktoken
import mysql.connector
from openai import OpenAI
from pathlib import Path
import re

from ._retry import call_with_retry

# ── language-code normalisation ───────────────────────────────────────────────
_LANG_CODE_MAP = {
    "persian": "fa",
    "farsi":   "fa",
    "fa-ir":   "fa",
    "fa_ir":   "fa",
    "arabic":  "ar",
    "french":  "fr",
    "german":  "de",
    "spanish": "es",
    "chinese": "zh",
    "russian": "ru",
    "japanese":"ja",
    "korean":  "ko",
}


def _normalize_lang(lang: str) -> str:
    lower = lang.lower().strip()
    if lower in _LANG_CODE_MAP:
        return _LANG_CODE_MAP[lower]
    return lower.split("-")[0].split("_")[0]


# Maps normalised lang code → prompt file suffix (ISO 639-2/B uppercase)
_PROMPT_FILE_MAP = {
    'fa': 'PER',
    'ar': 'ARA',
}


def _prompt_lang_code(dest_lang: str) -> str:
    code = _normalize_lang(dest_lang)
    return _PROMPT_FILE_MAP.get(code, code)


def _find_prompts_dir(anchor: Path) -> Path:
    """Walk up from *anchor* to find the project-level prompts/ directory."""
    for candidate in [
        anchor / "../../prompts",
        anchor / "../prompts",
        anchor / "prompts",
    ]:
        resolved = candidate.resolve()
        if resolved.is_dir():
            return resolved
    raise FileNotFoundError(
        f"prompts/ directory not found (searched relative to {anchor})"
    )


class OpenAITranslator:
    # model="gpt-5.4-mini"  ← mini (cheaper, faster, lower quality)
    def __init__(self, model="gpt-5.5", filename=None):
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        self.client = OpenAI(api_key=self.api_key)

        # DB config from environment
        self.db_config = {
            "host": os.environ.get("MARIADB_HOST", "localhost"),
            "user": os.environ.get("MARIADB_USER", "root"),
            "password": os.environ.get("MARIADB_PASSWORD", ""),
            "database": os.environ.get("MARIADB_DB", "translation")
        }

        self.doc_id = None
        self.filename = None
        self.last_call_data = {}

        if filename:
            self.set_filename(filename)

    def set_filename(self, filename):
        """Change active document context."""
        self.filename = filename
        self.doc_id = str(uuid.uuid4())
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (doc_id, filename) VALUES (%s, %s)",
                (self.doc_id, self.filename)
            )
            conn.commit()
            print(f"[INFO] Created document: {self.filename} ({self.doc_id})")
        except Exception as e:
            print(f"[Warning] Failed to save document info: {e}")
        finally:
            try: cursor.close(); conn.close()
            except: pass

    def get_db_connection(self):
        return mysql.connector.connect(**self.db_config)

    def get_doc_id(self):
        return self.doc_id

    # ── prompt loading ─────────────────────────────────────────────────────────

    def _load_system_prompt(self, source_lang: str, dest_lang: str) -> str:
        """
        Load the translation system prompt for *dest_lang*.
        Falls back to translate_universal.txt when no language-specific file exists.
        Does NOT substitute {N} here — N goes into the user message so the system
        prompt stays identical across documents and benefits from prompt caching.
        Substitutes {SOURCE_LANG} and {DEST_LANG} only (these are stable per session).
        """
        prompts_dir = _find_prompts_dir(Path(__file__).parent)
        lang_code   = _prompt_lang_code(dest_lang)
        specific    = prompts_dir / f"translate_{lang_code}.txt"
        universal   = prompts_dir / "translate_universal.txt"
        path = specific if specific.exists() else universal
        template = path.read_text(encoding="utf-8")
        return (
            template
            .replace("{SOURCE_LANG}", source_lang)
            .replace("{DEST_LANG}", dest_lang)
        )

    @staticmethod
    def _build_user_message(text: str) -> str:
        """Return the numbered-line user payload with line count header."""
        lines = text.split("\n")
        n = len(lines)
        numbered = "\n".join(f"Line {i + 1}: {line}" for i, line in enumerate(lines))
        return f"Lines to translate: {n}\n\n{numbered}"

    # ── token / cost helpers ───────────────────────────────────────────────────

    @staticmethod
    def estimate_tokens(text: str) -> int:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    @staticmethod
    def calculate_openai_cost(response_json):
        model = response_json.get("model", "")
        usage = response_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        PRICES = {
            "gpt-5.5":      {"input": 3.00,  "output": 15.00},  # estimate — update when pricing confirmed
            "gpt-5.4":      {"input": 2.50,  "output": 15.00},
            "gpt-5.4-mini": {"input": 0.75,  "output": 4.50},
            "gpt-5.4-nano": {"input": 0.20,  "output": 1.25},
            "gpt-5.2":      {"input": 1.75,  "output": 14.00},
            "gpt-5.1":      {"input": 1.25,  "output": 10.00},
            "gpt-5":        {"input": 1.25,  "output": 10.00},
            "gpt-5-mini":   {"input": 0.25,  "output": 2.00},
            "gpt-5-nano":   {"input": 0.05,  "output": 0.40},
            "gpt-4o":       {"input": 2.50,  "output": 10.00},
            "gpt-4o-mini":  {"input": 0.15,  "output": 0.60},
        }

        price = next((v for k, v in PRICES.items() if k in model), None)

        if price is None:
            print(f"[WARN] No known pricing for model '{model}'. Cost will be set to 0.")
            return {
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "input_cost_usd": 0.0,
                "output_cost_usd": 0.0,
                "total_cost_usd": 0.0,
            }

        input_cost  = (prompt_tokens      / 1_000_000) * price["input"]
        output_cost = (completion_tokens  / 1_000_000) * price["output"]
        total_cost  = input_cost + output_cost

        print("Total cost in USD:", round(total_cost, 6))

        return {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "input_cost_usd":  round(input_cost,  6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd":  round(total_cost,  6),
        }

    # ── translation ────────────────────────────────────────────────────────────

    def translate(self, source_lang, dest_lang, text_to_translate):
        if not self.doc_id:
            print("[INFO] No document context. Generating new doc_id and using filename 'inline_text'.")
            self.set_filename("inline_text")

        lines         = text_to_translate.split("\n")
        n             = len(lines)
        system_prompt = self._load_system_prompt(source_lang, dest_lang)
        user_message  = self._build_user_message(text_to_translate)

        print("user_message:")
        print(user_message)

        input_tokens = self.estimate_tokens(system_prompt + user_message)
        print(f"Estimated number of input tokens: {input_tokens}")

        start_time = time.time()

        _messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ]

        _extra = {"prompt_cache_retention": "24h"}

        if "pro" in self.model:
            response = call_with_retry(
                lambda: self.client.responses.create(
                    model=self.model,
                    input=_messages,
                    extra_body=_extra,
                    timeout=1800,
                ),
                label="translator.responses.create",
            )
        else:
            response = call_with_retry(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=_messages,
                    extra_body=_extra,
                    timeout=1800,
                ),
                label="translator.chat.completions.create",
            )

        elapsed_time  = time.time() - start_time
        response_json = response.model_dump()

        print("response:")
        print(json.dumps(response_json, indent=4))
        print("--end of response--")

        cost_info = self.calculate_openai_cost(response_json)

        translated_text = response.choices[0].message.content.strip()
        translated_text = re.sub(r'\n+', '\n', translated_text)

        in_lines  = text_to_translate.split("\n")
        out_lines = translated_text.split("\n")

        if len(in_lines) != len(out_lines):
            print("[WARNING] Line count mismatch!")
            print(f"Input lines: {len(in_lines)}, Output lines: {len(out_lines)}")
            out_lines = "\n".join(out_lines)
            if len(out_lines) > len(in_lines):
                print("Error in openai translation, too many lines")
            else:
                print("Error in openai translation, too few lines")
            translated_text = out_lines

        # Save query record
        try:
            conn   = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO queries
                (doc_id, type, model_name, prompt_json, response_json, execution_time_sec,
                 input_tokens, output_tokens, total_tokens, cost_usd)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self.doc_id,
                    "translate",
                    self.model,
                    json.dumps({"system": system_prompt, "user": user_message}),
                    json.dumps(response_json),
                    elapsed_time,
                    cost_info["prompt_tokens"],
                    cost_info["completion_tokens"],
                    cost_info["total_tokens"],
                    cost_info["total_cost_usd"],
                )
            )
            conn.commit()
        except Exception as e:
            print(f"[Warning] Failed to save query info: {e}")
        finally:
            try: cursor.close(); conn.close()
            except: pass

        self.last_call_data = {
            "type":            "translate",
            "model":           self.model,
            "system_prompt":   system_prompt,
            "user_prompt":     user_message,
            "response_raw":    response_json,
            "output_text":     translated_text,
            "tokens": {
                "prompt":      cost_info.get("prompt_tokens", 0),
                "completion":  cost_info.get("completion_tokens", 0),
                "total":       cost_info.get("total_tokens", 0),
                "cached":      (response_json.get("usage") or {})
                               .get("prompt_tokens_details", {})
                               .get("cached_tokens", 0),
            },
            "cost_usd":        cost_info.get("total_cost_usd", 0.0),
            "elapsed_seconds": round(elapsed_time, 3),
        }

        return response, translated_text
