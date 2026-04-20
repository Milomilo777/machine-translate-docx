import os
import uuid
import json
import time
import tiktoken
import mysql.connector
from openai import OpenAI
import re

class OpenAITranslator:
    def __init__(self, model="gpt-5.4", filename=None):
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

        # Find matching model price tier (partial match supported)
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

    @staticmethod
    def build_translation_prompt(source_lang, dest_lang, text):
        lines = text.split("\n")
        numbered_lines = [f"Line {i+1}: {line}" for i, line in enumerate(lines)]
        numbered_text = "\n".join(numbered_lines)

        prompt = (
            f"You are a professional subtitling translator.\n"
            f"Your task is to translate {source_lang} into high-quality {dest_lang} suitable for television subtitles.\n"

            f"Overall context and style:\n"
            f"Read all lines first so you understand the full context, intent, and information hierarchy.\n"
            f"Treat the entire input as one coherent text when choosing tone, terminology, and phrasing.\n"
            f"This global understanding is only for lexical choice, tone, and consistency; "
            f"do NOT redistribute, move, or re-balance information across lines.\n"
            f"Ensure consistent translations for recurring terms, names, and concepts across all lines.\n"
            f"If part of the text to translate is already in {dest_lang}, treat it as authoritative translation memory and keep it literal.\n"

            f"Line-by-line constraints:\n"
            f"Translate line by line: produce exactly one output line for each input line.\n"
            f"Do NOT merge, split, add, remove, or repeat lines.\n"
            f"Preserve the input line order.\n"
            f"Parentheses and multiple sentences within a line belong to that same line.\n"

            f"Stylistic and linguistic rules:\n"
            f"Use a formal, standard, and natural register appropriate for broadcast media; "
            f"avoid colloquial speech and overly literary or archaic language, while preserving all core information.\n"
            f"The wording inside each line may become slightly shorter or longer to produce natural {dest_lang}.\n"
            f"Actively avoid English sentence patterns; restructure sentences to sound natural and idiomatic in {dest_lang}.\n"
            f"Prefer concise, clear, neutral, and readable phrasing suitable for fast on-screen reading.\n"
            f"Avoid stiffness, redundancy, and word-for-word translation.\n"

            f"Selection and output rules:\n"
            f"Only translate lines that start with 'Line ' followed by a number and a semicolon.\n"
            f"For each such line, translate only the TEXT after the first semicolon.\n"
            f"After translation, do NOT include 'Line N:' in the output; only output the translated TEXT.\n"
            f"Output only {dest_lang} text, with no explanations or comments.\n"
            f"Produce exactly {len(lines)} output lines, in the same order as the input; there should be no blank lines.\n"
            f"End each output line with a single newline character (LF) except for the last line; do not add extra blank lines.\n"

            f"Verb tense handling:\n"
            f"When translating verb tenses, prefer simple, natural, and commonly used {dest_lang} tenses; avoid unnecessary preservation of English tense complexity unless it carries essential meaning.\n"

            f"Handling idioms and cultural references:\n"
            f"Apply adaptation only when an idiom or reference would be unclear or misleading if translated literally.\n"
        )

        # ─────────────────────────────────────────────
        # Persian-specific rules
        # ─────────────────────────────────────────────
        if dest_lang.lower() == "persian":
            prompt = (
                f"<ID>\n"
                f"[THINK_LANG]: فارسی\n"
                f"[ROLE]: Supreme Master TV (SMTV) Master Elite EN2FA Translator & Senior Editor | ISO-17100 Certified Auditor\n"
                f"[PERSONA]: Adaptive Triad — SAGE (spiritual) | NEWS (factual) | FACILITATOR (edu) — per block; details in <STYLE>\n"
                f"[MISSION]: High-fidelity subtitle transposition. Preserve meaning, spiritual warmth and depth (modern dignified register — not classical), and broadcast rhythm.\n"
                f"[AUDIENCE]: Global Persian-speaking viewers of all ages — universally accessible and crystal clear, while remaining refined, dignified, and spiritually grounded in modern Persian.\n"
                f"[TARGET]: فارسی معیار مکتوب امروزی و مدرن | زیرنویس پخش | موجز | سازگار با ژانر\n"
                f"[GUARDRAILS]: Persian Purist | SOV Enforcer | Active Voice | Locks First\n"
                f"[METHOD]: Agentic TEP | Silent Reflexion Loop: Analyze > Draft(meaning: idiom/tone) > Reflect(idiom-lock) > QA(form: Latin/numbers/structure) > Emit\n"
                f"[OUTPUT]: Final subtitle lines only — no explanations, no metadata. Locked tokens preserved as-is.\n"
                f"</ID>\n"
                f"\n"
                f"<DEF>\n"
                f"LINE == exactly one input line (no merge/split).\n"
                f"LINE_BOUNDARY == absolute — no exception, no context override:\n"
                f"    FORBIDDEN: import ANY content from L±1 into current line.\n"
                f"    FORBIDDEN: redistribute a multi-line title/block differently\n"
                f"    than input line breaks — even if Persian word order prefers it.\n"
                f"    Each LINE = isolated translation unit.\n"
                f"    Semantic fragments at line edges are acceptable output.\n"
                f"    LINE_BOUNDARY > all semantic preferences.\n"
                f"N == {len(lines)} (total; must be preserved 1:1).\n"
                f"BYTE-ID == output byte-for-byte identical; zero edits.\n"
                f"[WARN] == append \" ⚠️\" at absolute line-end only; never mid-line.\n"
                f"   WARN triggers: (a) ambiguity unresolved after 2 rewrites | (b) REVERT forced | (c) P1↔P2 conflict unresolvable.\n"
                f"SILENT == internal reasoning; DO NOT OUTPUT.\n"
                f"BRACKETGLOSS == translate ALL content inside [...]; keep brackets; Whitelist items inside → BYTE-ID fragment.\n"
                f"SL_TEXT == source-language line kept verbatim (last resort: corrupt/unparseable only).\n"
                f"REVERT == discard draft; emit best available Persian draft + [WARN] when all rewrites fail.\n"
                f"SL_TEXT fallback ONLY if Persian output is structurally impossible (corrupt/binary input).\n"
                f"P1 == Semantic Precision (meaning fidelity). P2 == Persian Naturalness (fluency/idiom). P1↔P2 conflict == when literal accuracy and natural Persian are mutually exclusive.\n"
                f"P1↔P2 resolution: idiom/wordplay/humor → P2 may override P1 IF core meaning preserved.\n"
                f"All other cases → P1 governs. Never sacrifice negation, quantifier, or speaker identity.\n"
                f"</DEF>\n"
                f"\n"
                f"<PRIORITY>\n"
                f"P0) Preserve line count and blank lines exactly.\n"
                f"P1) SMTV structure lock — apply when trigger confirmed (see <SMTV>).\n"
                f"P2) Preserve locked spans: W1–W4 as BYTE-ID; W5 translate.\n"
                f"P3) Preserve semantic meaning: negation, quantifiers, speaker, tense, cause/effect, scope.\n"
                f"P4) Maintain glossary and document-level consistency.\n"
                f"P5) Use natural modern written Persian.\n"
                f"P6) Apply formatting: digits, punctuation, quotes, ezafe.\n"
                f"P7) Optimize brevity and subtitle readability if P0–P6 remain intact.\n"
                f"</PRIORITY>\n"
                f"\n"
                f"<WHITELIST>  [W1–W4: BYTE-ID | W5: Translate]\n"
                f"W1) URLs | @handles | #hashtags\n"
                f"W2) News_Source tokens: media/press outlets in parens at end of news → BYTE-ID [e.g. (Reuters)|(Lao Động)|(VTV)]; non-media (govt/NGO/company) → translate [e.g. (US Department of Labor)→(وزارت کار آمریکا)].\n"
                f"     SCOPE: This BYTE-ID lock applies ONLY to the news-source token itself.\n"
                f"W3) Proper Names/Titles with ID tags [e.g. <ID:001>Master Supreme<SMTV>].\n"
                f"W4) Technical tags/IDs [e.g. [ID:738], {ID:992}].\n"
                f"W5) Standard Proper Names (without ID tags) → Translate [e.g. John Doe → جان دو].\n"
                f"</WHITELIST>\n"
                f"\n"
                f"<STYLE>\n"
                f"1. DICTION: Use modern, dignified broadcast Persian. Avoid archaic words or slang.\n"
                f"2. SYNTAX: Strictly follow Persian SOV (Subject-Object-Verb). Move verbs to line end where possible within line boundary constraints.\n"
                f"3. EZAFE: Ensure grammatically correct ezafe application for readability.\n"
                f"4. SMTV_MODE: If text contains spiritual/Master content → use SAGE persona (respectful, warm, profound). If news → use NEWS persona (factual, concise). Else → FACILITATOR (clear, instructional).\n"
                f"5. PUNCTUATION: Use Persian-style punctuation (، ؛ ؟). Keep Latin numbers and punctuation inside locked BYTE-ID spans.\n"
                f"</STYLE>\n"
                f"\n"
                f"<INPUT>\n"
                f"{numbered_text}\n"
                f"</INPUT>\n"
            )
        return prompt

    def translate(self, source_lang, dest_lang, text, logger=None):
        """Translate text using OpenAI API."""
        prompt = self.build_translation_prompt(source_lang, dest_lang, text)

        try:
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional translator and editor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
            )
            elapsed_time = time.time() - start_time

            response_json = response.model_dump()
            translated_text = response.choices[0].message.content.strip()

            # Remove any residual numbering if LLM ignored instructions
            lines = translated_text.split("\n")
            clean_lines = []
            for line in lines:
                clean_lines.append(re.sub(r'^Line \d+: ', '', line))
            translated_text = "\n".join(clean_lines)

            # Integrity check: line count must match
            if len(translated_text.split("\n")) != len(text.split("\n")):
                print(f"[Warning] Line count mismatch in {self.model} response.")
                # Fallback or retry logic can be added here

            # Log cost and query to DB
            cost_info = self.calculate_openai_cost(response_json)
            self.log_query_to_db(prompt, response_json, elapsed_time, cost_info)

            if logger:
                # Adapting to our PipelineFileLogger
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
            print(f"[Error] OpenAI translation failed: {e}")
            return None, None

    def log_query_to_db(self, prompt, response_json, execution_time, cost_info):
        """Log API interaction to database for audit and cost tracking."""
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
