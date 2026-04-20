import os
import uuid
import json
import time
import tiktoken
import mysql.connector
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
            print(f"[INFO] Created document for splitting: {self.filename} ({self.doc_id})")
        except Exception as e:
            print(f"[Warning] Failed to save document info for splitting: {e}")
        finally:
            try: cursor.close(); conn.close()
            except: pass

    def get_db_connection(self):
        return mysql.connector.connect(**self.db_config)

    @staticmethod
    def calculate_openai_cost(response_json):
        model = response_json.get("model", "")
        usage = response_json.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        PRICES = {
            "gpt-5.4": {"input": 2.50, "output": 15.00},
            "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60}
        }

        price = next((v for k, v in PRICES.items() if k in model), {"input": 0, "output": 0})

        input_cost = (prompt_tokens / 1_000_000) * price["input"]
        output_cost = (completion_tokens / 1_000_000) * price["output"]

        return {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "total_cost_usd": input_cost + output_cost
        }

    def split_phrase(self, source_lang, target_lang, source_text, translation, logger=None):
        """AI-powered line splitting to match source lines."""
        lines = source_text.split("\n")
        numbered_lines = [f"Input line {i+1}: {line}" for i, line in enumerate(lines)]
        numbered_text = "\n".join(numbered_lines)

        prompt = (
            f"You are an elite video subtitle editor. You are given a subtitle text in {source_lang} (source language) and its translation in {target_lang} (target language).\n\n"
            f"Task:\n"
            f"1. Your top priority is that each line in the {target_lang} translation matches the {source_lang} source line-by-line as closely as possible when viewed side by side.\n"
            f"2. Each line in the {source_lang} source must correspond to exactly one line in the {target_lang} output.\n"
            f"3. Do not change any words, punctuation, or symbols in the {target_lang} translation.\n"
            f"4. Preserve all elements such as emails, URLs, symbols, or emojis exactly as they appear in the original {target_lang} translation.\n\n"
            f"5. Only if strict alignment is impossible due to grammar or phrasing differences, apply professional subtitle line-splitting rules for {target_lang}:\n"
            f"   - Keep grammatical units together.\n"
            f"   - Maintain readability and natural flow.\n\n"
            f"6. Output requirements:\n"
            f"   - Use exactly {len(lines)} lines.\n"
            f"CRITICAL: You MUST output exactly {len(lines)} lines.\n\n"
            f"{source_lang} source ({len(lines)} lines):\n"
            f"{numbered_text}\n\n"
            f"{target_lang} translation:\n"
            f"{translation}\n"
        )

        try:
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional subtitle editor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
            )
            elapsed_time = time.time() - start_time

            response_json = response.model_dump()
            splitted_text = response.choices[0].message.content.strip()

            # Clean up: remove multiple newlines
            splitted_text = re.sub(r'\n+', '\n', splitted_text)
            out_lines = splitted_text.split("\n")

            if logger:
                logger.log_split(
                    block_index=0,
                    mode="ai",
                    lines_in=lines,
                    lines_out=out_lines,
                    elapsed_seconds=elapsed_time,
                )

            # Log to DB
            cost_info = self.calculate_openai_cost(response_json)
            self.log_query_to_db(prompt, response_json, elapsed_time, cost_info)

            # If mismatch, fallback to classic split
            if len(out_lines) != len(lines):
                print(f"[Warning] Splitter failed to match line count ({len(out_lines)} vs {len(lines)}). Using classic fallback.")
                return self.classic_split(translation, len(lines))

            return out_lines

        except Exception as e:
            print(f"[Error] AI splitting failed: {e}")
            return self.classic_split(translation, len(lines))

    def classic_split(self, translation, expected_lines):
        """Fallback deterministic split."""
        lines = [line.strip() for line in translation.split("\n") if line.strip()]
        if len(lines) == expected_lines:
            return lines

        if len(lines) > expected_lines:
            # Merge extra lines into the last one
            main_lines = lines[:expected_lines-1]
            extra = " ".join(lines[expected_lines-1:])
            main_lines.append(extra)
            return main_lines
        else:
            # Pad with empty lines
            while len(lines) < expected_lines:
                lines.append("")
            return lines

    def log_query_to_db(self, prompt, response_json, execution_time, cost_info):
        """Log splitting interaction to database."""
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
            print(f"[Warning] Failed to log splitting query: {e}")
        finally:
            try: cursor.close(); conn.close()
            except: pass
