import os
import uuid
import json
import time
import tiktoken
# 2026-05-13 (feat/exe-packaging): mysql.connector lazy-loaded inside
# get_db_connection — see translator.py for rationale.
from openai import OpenAI
import re

class OpenAISubtitleSplitter:
    def __init__(self, model="gpt-5.4-mini", filename=None, doc_id=None):
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

        if doc_id:
            self.doc_id = doc_id
        else:
            self.doc_id = str(uuid.uuid4())
            
        self.filename = None
        if filename:
            self.filename = filename

    def set_model(self, model):
        """Change openai model for this object."""
        self.model = model
        
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
            except Exception: pass

    def get_db_connection(self):
        import mysql.connector  # noqa: WPS433 — lazy optional import
        return mysql.connector.connect(**self.db_config)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    @staticmethod
    def calculate_openai_cost(response_json):
        """Calculate per-call OpenAI spend, including the 90% prompt-cache
        discount on cached tokens.

        C-2 (2026-05-11 audit): the splitter's price table previously
        had only ``input`` and ``output`` rates; on a cache hit the
        full prompt was charged at the un-cached rate, overstating the
        bill by ~10×. Added a ``cached`` column and split
        ``prompt_tokens`` into ``prompt_tokens - cached_tokens`` (full
        rate) + ``cached_tokens`` (10% rate). Also added ``gpt-5.5``
        (the project default per ``config.DEFAULT_AI_MODEL``) so the
        on-by-default model has a real number rather than the
        ``[WARN] No known pricing`` zero.
        """
        model = response_json.get("model", "")
        usage = response_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cached_tokens = (usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens", 0
        )

        # 2026-05-16 (P2.8): pricing consolidated to
        # openai_tools._pricing.PRICES.
        from ._pricing import get_price

        # Find matching model price tier (partial match supported).
        price = get_price(model)

        if price is None:
            print(f"[WARN] No known pricing for model '{model}'. Cost will be set to 0.")
            return {
                "model":           model,
                "prompt_tokens":   prompt_tokens,
                "cached_tokens":   cached_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens":    prompt_tokens + completion_tokens,
                "input_cost_usd":  0.0,
                "output_cost_usd": 0.0,
                "total_cost_usd":  0.0,
            }

        non_cached = max(0, prompt_tokens - cached_tokens)
        input_cost = (
            (non_cached / 1_000_000) * price["input"]
            + (cached_tokens / 1_000_000) * price.get("cached", price["input"])
        )
        output_cost = (completion_tokens / 1_000_000) * price["output"]
        total_cost = input_cost + output_cost

        print("Total cost in USD:", round(total_cost, 6))

        return {
            "model":             model,
            "prompt_tokens":     prompt_tokens,
            "cached_tokens":     cached_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens":      prompt_tokens + completion_tokens,
            "input_cost_usd":    round(input_cost, 6),
            "output_cost_usd":   round(output_cost, 6),
            "total_cost_usd":    round(total_cost, 6),
        }

    # Static instructional block — placed in the `system` message so the
    # 24-hour prompt cache picks it up. Source/target language names and the
    # required N value travel via the `user` message; the system half stays
    # byte-identical across all calls. (A2 fix, 2026-05-12.)
    _SYSTEM_PROMPT = (
        "You are an elite video subtitle editor and line-splitter. You will\n"
        "receive a subtitle source text in one language and its translation\n"
        "in another, and you must re-emit the translation broken into the\n"
        "exact number of lines requested.\n\n"

        "Rules:\n"
        "1. Top priority: each output line of the translation aligns with the\n"
        "   matching source line when viewed side by side.\n"
        "2. Each source line maps to exactly one output line.\n"
        "3. Do not change any words, punctuation, or symbols in the\n"
        "   translation. Preserve emails, URLs, symbols, and emojis verbatim.\n"
        "4. Only if strict alignment is impossible due to grammar / phrasing,\n"
        "   apply professional subtitle line-splitting rules in the target\n"
        "   language:\n"
        "     - Keep grammatical units together (pronoun+verb, subject+verb,\n"
        "       auxiliary+main verb, verb+object, article+noun, prep+object).\n"
        "     - Prefer breaks at natural pauses, commas, conjunctions, or\n"
        "       between clauses.\n"
        "     - Do not split fixed expressions, names, phrasal verbs, idioms.\n"
        "     - Avoid leaving short function words alone.\n"
        "     - Maintain readability; keep line lengths roughly balanced,\n"
        "       but prioritise meaning and alignment.\n"
        "5. Output format:\n"
        "     - Output only the translation text in the target language.\n"
        "     - Use exactly N lines (N is given in the user message).\n"
        "     - Insert line breaks only — no paraphrasing, numbering,\n"
        "       labels, or extra formatting.\n\n"

        "CRITICAL:\n"
        "- You MUST emit exactly N lines.\n"
        "- If natural splitting is impossible, duplicate or break\n"
        "  arbitrarily — never return fewer or more lines.\n\n"

        "Worked example (English → French, N=2):\n"
        "  English source:\n"
        "    I really enjoyed the movie\n"
        "    and the amazing soundtrack.\n"
        "  French translation (single line):\n"
        "    J'ai vraiment apprécié le film et la bande-son incroyable.\n"
        "  Correct 2-line output:\n"
        "    J'ai vraiment apprécié le film\n"
        "    et la bande-son incroyable.\n"
    )

    @staticmethod
    def build_subtitle_splitter_prompt(source_lang, dest_lang, source_text, translation):
        """Return *only the user-message payload* — all static instructional
        text now lives in :data:`OpenAISubtitleSplitter._SYSTEM_PROMPT`.

        Kept as a static method so external callers (and the per-line counter
        below) keep their old API; nothing should rely on the previous
        single-string return shape (it was only consumed by ``split_phrase``).
        """
        lines = source_text.split("\n")
        numbered_lines = [f"Input line {i+1}: {line}" for i, line in enumerate(lines)]
        numbered_text = "\n".join(numbered_lines)

        return (
            f"Source language: {source_lang}\n"
            f"Target language: {dest_lang}\n"
            f"N = {len(lines)}  (emit exactly this many lines)\n\n"
            f"{source_lang} source ({len(lines)} lines):\n"
            f"{numbered_text}\n\n"
            f"{dest_lang} translation:\n"
            f"{translation}\n"
        )

    def split_phrase(self, source_lang, dest_lang, source_text, translation):
        # Auto-create doc ID & filename if missing
        if not self.doc_id:
            print("[INFO] No document context. Generating new doc_id and using filename 'inline_text'.")
            #self.set_filename("inline_text")

        prompt = self.build_subtitle_splitter_prompt(source_lang, dest_lang, source_text, translation)
        input_tokens = self.estimate_tokens(prompt)
        # C2 (internal audit 2026-05-13): payload logging gated like
        # translator.py + polisher.py. Default = summary only; full
        # prompt requires MTD_DEBUG_PAYLOADS=1.
        import os as _os
        if _os.environ.get("MTD_DEBUG_PAYLOADS") == "1":
            print("prompt:")
            print(prompt)
        else:
            _lc = source_text.count("\n") + 1
            print(
                f"[INFO] Splitter input: ~{_lc} source lines, "
                f"est. {input_tokens} tokens"
            )
        print(f"Estimated number of input tokens: {input_tokens}")

        _cache_extra = {
            "prompt_cache_retention": "24h",
            "prompt_cache_key": "mtd-splitter-v7",
        }
        start_time = time.time()
        _messages = [
            {"role": "system", "content": self._SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ]
        # 2026-05-16 (P2.4): wrap with call_with_retry so a single transient
        # 5xx / rate-limit doesn't kill an entire split pass. The two prior
        # OpenAI callers (translator, polisher) already use this helper;
        # splitting was the lone outlier.
        from ._retry import call_with_retry
        if "pro" in self.model or self.model.lower().startswith("gpt-5"):
            # 2026-05-18 stream-parity fix: same openai-python #2725
            # hang risk on Responses API + gpt-5.x as translator/polisher.
            # Stream the deltas and reassemble to keep this code path
            # safe under any input size, even though the default Split
            # Method is `persian_double_lines` so this rarely fires.
            def _stream_call():
                s = self.client.responses.create(
                    model=self.model,
                    input=_messages,
                    extra_body=_cache_extra,
                    stream=True,
                )
                _chunks: list[str] = []
                _final = None
                for event in s:
                    et = getattr(event, "type", "")
                    if et == "response.output_text.delta":
                        _chunks.append(getattr(event, "delta", "") or "")
                    elif et == "response.completed":
                        _final = getattr(event, "response", None)
                    elif et in ("response.failed", "response.incomplete"):
                        _final = getattr(event, "response", None)
                        raise RuntimeError(
                            f"splitter stream ended with type={et}: {_final}"
                        )
                return {"text": "".join(_chunks), "final": _final}

            _sr = call_with_retry(_stream_call, label="splitter.responses(stream)")
            from types import SimpleNamespace
            _final = _sr["final"]
            response = SimpleNamespace(
                output_text=_sr["text"],
                model_dump=(lambda f: (lambda: f.model_dump()))(_final) if _final else (lambda: {}),
            )
        else:
            response = call_with_retry(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=_messages,
                    extra_body=_cache_extra,
                ),
                label="splitter.chat",
            )
        elapsed_time = time.time() - start_time
        response_json = response.model_dump()

        # C2 (internal audit 2026-05-13): same env-gate as translator.
        if _os.environ.get("MTD_DEBUG_PAYLOADS") == "1":
            print("response:")
            print(json.dumps(response_json, indent=4))
            print("--end of response--")
        else:
            _u = response_json.get("usage") or {}
            print(
                f"[INFO] Splitter response: model={response_json.get('model', self.model)}, "
                f"prompt={_u.get('prompt_tokens', '?')}, "
                f"completion={_u.get('completion_tokens', '?')}"
            )

        cost_info = self.calculate_openai_cost(response_json)

        splitted_text = response.choices[0].message.content.strip()
        
        # Remove duplicate new lines if any
        splitted_text = re.sub(r'\n+', '\n', splitted_text)
        print(splitted_text)

        # Validate line counts
        in_lines = source_text.split("\n")
        out_lines = splitted_text.split("\n")
        num_in_lines = 0
        num_newlines = 0
        num_in_lines = source_text.count("\n") + 1
        num_newlines = splitted_text.count("\n") + 1

        if num_in_lines != num_newlines:
            print("[WARNING] Line count mismatch!")
            print(f"Input lines: {len(in_lines)}, Output lines: {len(out_lines)}")
            out_lines = "\n".join(out_lines)
            if len(out_lines) > len(in_lines):
                print("Error in openai line splitting, too many lines")
            else:
                print("Error in openai line splitting, too few lines")
            translated_text = out_lines

         # Save query record
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO queries
                (doc_id, type, model_name, prompt_json, response_json, execution_time_sec, input_tokens, output_tokens, total_tokens, cost_usd)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self.doc_id,
                    "split",
                    self.model,
                    json.dumps(prompt),
                    json.dumps(response_json),
                    elapsed_time,
                    cost_info["prompt_tokens"],
                    cost_info["completion_tokens"],
                    cost_info["total_tokens"],
                    cost_info["total_cost_usd"]
                )
            )
            conn.commit()
        except Exception as e:
            print(f"[Warning] Failed to save query info: {e}")
        finally:
            try: cursor.close(); conn.close()
            except Exception: pass

        return response, out_lines