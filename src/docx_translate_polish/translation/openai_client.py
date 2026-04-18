"""OpenAI API client for translation."""
import re
import os
import json
import time
import uuid
import mysql.connector
from typing import List, Tuple, Optional
from openai import OpenAI
from ..core.config import DEFAULT_MODEL
from ..core.utils import calculate_openai_cost, estimate_tokens
from ..core.logger import TranslationLogger
from .prompt_builder import build_translation_prompt

class OpenAITranslator:
    """Handles interaction with the OpenAI API for translation."""

    def __init__(self, model: str = DEFAULT_MODEL, filename: Optional[str] = None):
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        self.client = OpenAI(api_key=self.api_key)
        self.logger = TranslationLogger()

        # DB config from environment
        self.db_config = {
            "host": os.environ.get("MARIADB_HOST", "localhost"),
            "user": os.environ.get("MARIADB_USER", "root"),
            "password": os.environ.get("MARIADB_PASSWORD", ""),
            "database": os.environ.get("MARIADB_DB", "translation")
        }
        self.doc_id = None
        self.filename = filename
        if filename:
            self.set_filename(filename)

    def set_filename(self, filename: str):
        """Sets the current filename and generates a new doc_id, logging to DB."""
        self.filename = filename
        self.doc_id = str(uuid.uuid4())
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (doc_id, filename) VALUES (%s, %s)",
                (self.doc_id, self.filename)
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            self.logger.warn(f"Failed to save document info to DB: {e}")

    def set_model(self, model: str):
        """Updates the model to be used for translation."""
        self.model = model

    def translate(self, src_lang: str, dest_lang: str, text: str) -> Tuple[bool, str]:
        """Calls the OpenAI API to translate text."""
        prompt = build_translation_prompt(src_lang, dest_lang, text)
        input_tokens = estimate_tokens(prompt)

        start_time = time.time()
        try:
            if "pro" in self.model:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": "You are a professional translator."},
                        {"role": "user", "content": prompt}
                    ]
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a professional translator."},
                        {"role": "user", "content": prompt}
                    ]
                )

            elapsed_time = time.time() - start_time
            response_json = response.model_dump()
            cost_info = calculate_openai_cost(response_json)
            self.logger.log_cost(cost_info)

            translated_text = response.choices[0].message.content.strip()

            # Basic validation: remove numbering if LLM kept it
            lines = translated_text.split("\n")
            clean_lines = []
            for line in lines:
                clean_lines.append(re.sub(r'^\d+\.\s*', '', line))
            translated_text = "\n".join(clean_lines)

            # Integrity check
            success = len(translated_text.split("\n")) == len(text.split("\n"))

            # DB logging
            self._log_query_to_db(prompt, response_json, elapsed_time, cost_info)

            return success, translated_text
        except Exception as e:
            self.logger.error(f"API Call failed: {e}")
            return False, ""

    def _log_query_to_db(self, prompt, response_json, elapsed_time, cost_info):
        if not self.doc_id: return
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO queries
                (doc_id, model_name, prompt_json, response_json, execution_time_sec,
                 input_tokens, output_tokens, total_tokens, cost_usd)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self.doc_id, self.model, json.dumps(prompt), json.dumps(response_json),
                    elapsed_time, cost_info["prompt_tokens"], cost_info["completion_tokens"],
                    cost_info["total_tokens"], cost_info["total_cost_usd"]
                )
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            self.logger.warn(f"Failed to log query to DB: {e}")

    def translate_with_retry(self, lines: List[str], src_lang: str, dest_lang: str) -> str:
        """Implements recursive block-splitting for robust translation."""
        text = "\n".join(lines)
        success, translated = self.translate(src_lang, dest_lang, text)

        if success:
            return translated

        # If block fails and has more than 1 line, split and retry
        if len(lines) > 1:
            self.logger.warn(f"Block failed ({len(lines)} lines). Splitting in half...")
            mid = len(lines) // 2
            left = self.translate_with_retry(lines[:mid], src_lang, dest_lang)
            right = self.translate_with_retry(lines[mid:], src_lang, dest_lang)
            return left + "\n" + right

        # Single line fallback
        self.logger.error(f"Single line failed translation: {lines[0]}")
        return "Unable to get translation."
