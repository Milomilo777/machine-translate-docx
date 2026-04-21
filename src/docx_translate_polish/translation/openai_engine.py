import os
import uuid
import json
import time
import tiktoken
import mysql.connector
from openai import OpenAI
import re
from typing import List, Tuple, Optional
from .prompt_template import build_translation_prompt

class OpenAITranslator:
    def __init__(self, model="gpt-5.4", filename=None, reasoning_effort="medium", api_key=None):
        self.model = model
        self.reasoning_effort = reasoning_effort

        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment or config")
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

        if filename:
            self.set_filename(filename)

    def set_filename(self, filename):
        """Change active document context."""
        self.filename = filename
        new_doc_id = str(uuid.uuid4())
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (doc_id, filename) VALUES (%s, %s)",
                (new_doc_id, self.filename)
            )
            conn.commit()
            self.doc_id = new_doc_id   # only set on success
            print(f"[INFO] Created document: {self.filename} ({self.doc_id})")
        except Exception as e:
            self.doc_id = None         # explicitly clear so log_query_to_db skips
            print(f"[INFO] DB unavailable, running without query logging: {e}")
        finally:
            try: cursor.close(); conn.close()
            except: pass

    def get_db_connection(self):
        return mysql.connector.connect(**self.db_config)

    def get_doc_id(self):
        return self.doc_id

    def set_reasoning_effort(self, reasoning_effort: str):
        """Sets the reasoning effort for the API call."""
        self.reasoning_effort = reasoning_effort

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
            "gpt-5.4": {"input": 2.50, "output": 15.00},
            "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
            "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
            "gpt-5.2": {"input": 1.75, "output": 14.00},
            "gpt-5.1": {"input": 1.25, "output": 10.00},
            "gpt-5": {"input": 1.25, "output": 10.00},
            "gpt-5-mini": {"input": 0.25, "output": 2.00},
            "gpt-5-nano": {"input": 0.05, "output": 0.40},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60}
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
                "total_cost_usd": 0.0
            }

        input_cost = (prompt_tokens / 1_000_000) * price["input"]
        output_cost = (completion_tokens / 1_000_000) * price["output"]
        total_cost = input_cost + output_cost

        return {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "total_cost_usd": total_cost
        }

    def translate(self, source_lang, dest_lang, text, logger=None):
        """Translate text using OpenAI API."""
        prompt = build_translation_prompt(source_lang, dest_lang, text)

        def _call_api(use_reasoning=True):
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a professional translator and editor."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0,
            }
            if use_reasoning:
                kwargs["reasoning_effort"] = self.reasoning_effort
            return self.client.chat.completions.create(**kwargs)

        try:
            start_time = time.time()
            try:
                response = _call_api(use_reasoning=True)
            except Exception as e:
                # If reasoning_effort is not supported by the model, retry without it
                if "reasoning_effort" in str(e).lower() or "unsupported parameter" in str(e).lower():
                    print(f"[INFO] Retrying without reasoning_effort due to error: {e}")
                    response = _call_api(use_reasoning=False)
                else:
                    raise e

            elapsed_time = time.time() - start_time

            response_json = response.model_dump()
            translated_text = response.choices[0].message.content.strip()

            # Remove any residual numbering if LLM ignored instructions
            lines = translated_text.split("\n")
            clean_lines = []
            for line in lines:
                # Matches "Line 1: ", "Line 01: ", etc.
                clean_lines.append(re.sub(r'^Line \d+:\s*', '', line))
            translated_text = "\n".join(clean_lines)

            # Integrity check: line count must match
            if len(translated_text.split("\n")) != len(text.split("\n")):
                print(f"[Warning] Line count mismatch in {self.model} response.")

            # Log cost and query to DB
            cost_info = self.calculate_openai_cost(response_json)
            self.log_query_to_db(prompt, response_json, elapsed_time, cost_info)

            if logger:
                logger.log_call(
                    stage="translate",
                    block_index=0,
                    lines_sent=text.split("\n"),
                    system_prompt="You are a professional translator and editor.",
                    user_prompt=prompt,
                    raw_response=translated_text,
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    cached_tokens=getattr(response.usage, "prompt_tokens_details", None) and
                                  getattr(response.usage.prompt_tokens_details, "cached_tokens", 0) or 0,
                    elapsed_seconds=elapsed_time,
                )

            return response_json, translated_text

        except Exception as e:
            error_msg = f"OpenAI API call failed: {type(e).__name__}: {e}"
            if logger:
                logger.log_event("ERROR", error_msg)
            print(f"[Error] {error_msg}")
            raise

    def log_query_to_db(self, prompt, response_json, execution_time, cost_info):
        """Log API interaction to database."""
        if not self.doc_id:
            return

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            query = """
                INSERT INTO queries
                (doc_id, model_name, prompt_json, response_json, execution_time_sec,
                 input_tokens, output_tokens, total_tokens, cost_usd)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(query, (
                self.doc_id,
                self.model,
                json.dumps(prompt),
                json.dumps(response_json),
                execution_time,
                cost_info["prompt_tokens"],
                cost_info["completion_tokens"],
                cost_info["total_tokens"],
                cost_info["total_cost_usd"]
            ))

            conn.commit()
        except Exception as e:
            print(f"[Warning] Failed to log query to DB: {e}")
        finally:
            try: cursor.close(); conn.close()
            except: pass
