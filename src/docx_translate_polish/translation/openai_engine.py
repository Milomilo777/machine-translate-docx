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
from .prompt_builder import build_translation_prompt

class OpenAITranslator:
    """Handles interaction with the OpenAI API for translation."""

    def __init__(self, model: str = DEFAULT_MODEL, filename: Optional[str] = None):
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
        except Exception:
            pass

    def set_model(self, model: str):
        """Updates the model to be used for translation."""
        self.model = model

    def translate(self, src_lang: str, dest_lang: str, text: str,
                  logger=None, block_index: int = 0, attempt: int = 1) -> Tuple[bool, str]:
        """Calls the OpenAI API to translate text."""
        system_prompt = "You are a professional translator."
        user_prompt = build_translation_prompt(src_lang, dest_lang, text)

        start_time = time.time()
        try:
            if "pro" in self.model:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )

            elapsed = time.time() - start_time
            response_json = response.model_dump()
            raw_response = response.choices[0].message.content.strip()

            # Log successful call
            if logger is not None:
                logger.log_call(
                    stage="translate",
                    block_index=block_index,
                    lines_sent=text.split("\n"),
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    raw_response=raw_response,
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    cached_tokens=getattr(response.usage, "prompt_tokens_details", None) and
                                  getattr(response.usage.prompt_tokens_details, "cached_tokens", 0) or 0,
                    elapsed_seconds=elapsed,
                    attempt=attempt,
                    error=None,
                )

            # Basic validation: remove numbering if LLM kept it
            lines = raw_response.split("\n")
            clean_lines = []
            for line in lines:
                clean_lines.append(re.sub(r'^\d+\.\s*', '', line))
            translated_text = "\n".join(clean_lines)

            # Integrity check
            success = len(translated_text.split("\n")) == len(text.split("\n"))

            # DB logging
            cost_info = calculate_openai_cost(response_json)
            self._log_query_to_db(user_prompt, response_json, elapsed, cost_info)

            return success, translated_text
        except Exception as exc:
            elapsed = time.time() - start_time
            if logger is not None:
                logger.log_call(
                    stage="translate",
                    block_index=block_index,
                    lines_sent=text.split("\n"),
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    raw_response="",
                    input_tokens=0, output_tokens=0, cached_tokens=0,
                    elapsed_seconds=elapsed,
                    attempt=attempt,
                    error=str(exc),
                )
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
                    cost_info["total_tokens"], cost_info.get("total_cost_usd", 0.0)
                )
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            pass

    def translate_with_retry(self, lines: List[str], src_lang: str, dest_lang: str,
                             logger=None, block_index: int = 0, attempt: int = 1) -> str:
        """Implements recursive block-splitting for robust translation."""
        text = "\n".join(lines)
        success, translated = self.translate(src_lang, dest_lang, text, logger=logger, block_index=block_index, attempt=attempt)

        if success:
            return translated

        # If block fails and has more than 1 line, split and retry
        if len(lines) > 1:
            mid = len(lines) // 2
            left = self.translate_with_retry(lines[:mid], src_lang, dest_lang, logger=logger, block_index=block_index, attempt=attempt+1)
            right = self.translate_with_retry(lines[mid:], src_lang, dest_lang, logger=logger, block_index=block_index, attempt=attempt+1)
            return left + "\n" + right

        return "Unable to get translation."
