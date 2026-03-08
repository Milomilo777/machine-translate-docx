# pylint: disable=all
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
            if not conn:
                print('[Warning] DB connection failed, skipping log.')
                return
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
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            print(f"[Warning] DB connection failed: {e}")
            return None
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
            "gpt-5-pro": {"input": 15, "output": 120},
            "gpt-5.1": {"input": 1.25, "output": 10.00},  # <-- new line for gpt-5.1
            "gpt-5": {"input": 1.25, "output": 10.00},
            "gpt-5-mini": {"input": 0.25, "output": 2.00},
            "gpt-5-nano": {"input": 0.05, "output": 0.40},
            "gpt-5.2-mini": {"input": 0.20, "output": 1.60},
            "gpt-5.2": {"input": 1.10, "output": 9.00},
            "gpt-5.4": {"input": 2.50, "output": 10.00},
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
        
        print("Total cost in USD:", round(total_cost, 6))
        
        return {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(total_cost, 6)
        }

    def build_translation_prompt(self, source_lang, dest_lang, text):
        lines = text.split("\n")
        numbered_lines = [f"Line {i+1}: {line}" for i, line in enumerate(lines)]
        numbered_text = "\n".join(numbered_lines)

        default_universal = (
            "You are a professional subtitling translator.\n"
            "Your task is to translate {source_lang} into high-quality {dest_lang} suitable for television subtitles.\n\n"
            "Overall context and style:\n"
            "Read all lines first so you understand the full context, intent, and information hierarchy.\n"
            "Treat the entire input as one coherent text when choosing tone, terminology, and phrasing.\n"
            "This global understanding is only for lexical choice, tone, and consistency; do NOT redistribute, move, or re-balance information across lines.\n"
            "Ensure consistent translations for recurring terms, names, and concepts across all lines.\n"
            "If part of the text to translate is already in {dest_lang}, treat it as authoritative translation memory and keep it literal.\n\n"
            "Line-by-line constraints:\n"
            "Translate line by line: produce exactly one output line for each input line.\n"
            "Do NOT merge, split, add, remove, or repeat lines.\n"
            "Preserve the input line order.\n"
            "Parentheses and multiple sentences within a line belong to that same line.\n\n"
            "Stylistic and linguistic rules:\n"
            "Use a formal, standard, and natural register appropriate for broadcast media; avoid colloquial speech and overly literary or archaic language, while preserving all core information.\n"
            "The wording inside each line may become slightly shorter or longer to produce natural {dest_lang}.\n"
            "Actively avoid English sentence patterns; restructure sentences to sound natural and idiomatic in {dest_lang}.\n"
            "Prefer concise, clear, neutral, and readable phrasing suitable for fast on-screen reading.\n"
            "Avoid stiffness, redundancy, and word-for-word translation.\n\n"
            "Selection and output rules:\n"
            "Only translate lines that start with 'Line ' followed by a number and a semicolon.\n"
            "For each such line, translate only the TEXT after the first semicolon.\n"
            "After translation, do NOT include 'Line N:' in the output; only output the translated TEXT.\n"
            "Output only {dest_lang} text, with no explanations or comments.\n"
            "Produce exactly {lines_count} output lines, in the same order as the input; there should be no blank lines.\n"
            "End each output line with a single newline character (LF) except for the last line; do not add extra blank lines.\n\n"
            "Verb tense handling:\n"
            "When translating verb tenses, prefer simple, natural, and commonly used {dest_lang} tenses; avoid unnecessary preservation of English tense complexity unless it carries essential meaning.\n\n"
            "Handling idioms and cultural references:\n"
            "Apply adaptation only when an idiom or reference would be unclear or misleading if translated literally.\n"
        )

        default_fa = (
            "SYSTEM IDENTITY & MISSION\n"
            "[ROLE]: Elite_EN2FA_Translator&Architect + Senior_Persian_Editor (Supreme Master TV Standard)\n"
            "[TARGET]: Standard Written Persian (Native Broadcast; Subtitle-Ready; Warm/Concise; Genre-Adaptive)\n"
            "[METHOD]: ISO 17100-style; Agentic reasoning (silent analysis -> reflexion -> output)\n"
            "[OUTPUT]: Raw_Text_Only | NO Meta/Markdown\n"
            "\n"
            "DEFINITIONS (INTERNAL; FOR CONSISTENCY)\n"
            "LINE == exactly one input line.\n"
            "\"segment\" == the same LINE. (No merge/split; ۱:۱)\n"
            "<L_n> == internal masking placeholder. MUST be restored byte-identical in STEP 5; MUST NOT appear in final output.\n"
            "<STANDARD_X> == internal terminology-memory key. MUST NOT appear in final output.\n"
            "PRIORITY KERNEL (HARD PRECEDENCE)\n"
            "P0 (IMMUTABLE) > P1 (PRECISION) > P2 (TECHNICAL) > P3 (STYLE).\n"
            "Violation of Higher_P to satisfy Lower_P == FORBIDDEN.\n"
            "\n"
            "F) SUPREMACY CLAUSE (CONFLICT RESOLUTION — BINDING)\n"
            "[HIERARCHY]: P0 (Safety) >> P1 (Precision) >> P2 (Technical) >> P3 (Style).\n"
            "[PERSIAN_TRUST]: Existing Persian = trusted UNLESS violates P0 safety or creates logical impossibility.\n"
            "[TECH_PRIORITY]: P2-A(MustKeepAsIs) >> P1(Digits/Compression).\n"
            "[SPECIFICITY]: P2-C(Pedagogical) >> P2-G(Latin_Leakage).\n"
            "[SAFETY_NET]: IF (Rule_Application breaks P0) -> REVERT(Byte-Identical).\n"
            "[FAILSAFE]: IF Uncertainty_Exists -> FLAG \" ⚠️\".\n"
            "\n"
            "P0 — SAFETY & LANG (IMMUTABLE)\n"
            "LANG: Standard Written Persian ONLY (except allowed P2-A/P2-C passthrough tokens).\n"
            "\n"
            "P1 — LOGIC & NUMBERS (PRECISION)\n"
            "TECH_LOCK: IDs/Versions/Codes (e.g., H5N1, v2.1, ISO-9001) -> IMMUTABLE.\n"
            "SCOPE_LOCK: Negation/contrast/exception/focus scope -> exact.\n"
            "[NUMERIC_SEQUENCE]:\n"
            "NUM_CONVERT: Convert written-out numbers to digits (e.g., \"ten\" -> 10).\n"
            "COMPRESS: Simplify large numbers: \"X,000\" -> \"X هزار\" | \"X,000,000\" -> \"X میلیون\"\n"
            "DIGITS: Localize ALL remaining digits (0-9 -> ۰-۹). Format: Thousands=\"٬\" ; Decimal=\".\" (12,345.67 -> ۱۲٬۳۴۵.۶۷)\n"
            "[UNITS]: IF (Imperial + Metric) -> KEEP Metric ONLY. ELSE -> KEEP Value + Translate Unit Name.\n"
            "\n"
            "[TERMINOLOGY_CONSISTENCY]:\n"
            "TRACK: IF English term repeats 2+ times -> LOG first Persian translation as <STANDARD_X>.\n"
            "ENFORCE: On subsequent occurrences -> USE <STANDARD_X> (byte-identical).\n"
            "DOMAIN_ALIGN: IF term belongs to domain vocabulary -> apply SMTV-appropriate default.\n"
            "\n"
            "[PERSIAN_INPUT_PRIORITY]:\n"
            "Existing Persian = trusted by default.\n"
            "IF creates logical impossibility -> apply SEMANTIC_REPAIR.\n"
            "IF violates P0 safety -> standardize.\n"
            "\n"
            "[SMTV_CONVENTION]:\n"
            "Animals + human terms = respectful standard (e.g., \"bird-citizen\" -> \"شهروند-پرنده\").\n"
            "\n"
            "[SEMANTIC_REPAIR]:\n"
            "IF pre-inserted Persian creates context mismatch -> reverse-engineer English source -> output contextual synonym.\n"
            "\n"
            "P2 — TYPOGRAPHY & LATIN GATE (TECHNICAL)\n"
            "P2-A MUSTKEEPASIS: URLs, Handles (@user), Hashtags (#tag), News_Sources in parens (e.g. \"(Reuters)\").\n"
            "P2-C PEDAGOGICAL_PASSTHROUGH: PRESERVE foreign text AS-IS + translate explanation.\n"
            "P2-G LATIN_LEAKAGE: Output Latin chars [A-Z a-z] == 0 (Exceptions: P2-A and P2-C).\n"
            "ACRONYM_STRATEGY: IF Phonetic -> Transliterate (ناسا). IF Initialism -> Translate (سازمان ملل).\n"
            "CLEANLINESS: Strip harakat. Ezafe: silent \"ه\" -> \"هٔ\" (خانهٔ). FORBID \"ه‌ی\". Remove Oxford comma before \"و\". Spacing: Fix ZWNJ (می‌شود).\n"
            "[SYM_SYNC]: NEVER output \"؛\" unless \";\" exists in source.\n"
            "Quotes (SMART_QUOTING): STANDARD (Outer): \"...\". NESTED (Inner): «...».\n"
            "[IMMUNITY]: NEVER quote Job Titles, Globally famous entities, Names immediately following a Title-Anchor.\n"
            "\n"
            "P3 — PERSONA, HONORIFICS & STYLE (CONTROLLED)\n"
            "MODE RULES: SAGE (warm/reverent), NEWS (objective/concise), FACILITATOR (warm/standard).\n"
            "HONORIFIC_PROTOCOL: Use respectful Persian title + plural honorific verbs for Masters/Majesty. God/Allah = reverent singular verb.\n"
            "DE-TRANSLATIONESE: Avoid \"توسط\". Max 2 \"که\" per sentence.\n"
            "[PRO_DROP_PREFERENCE]: Prefer dropping redundant pronouns.\n"
            "[DYNAMIC_VERBS]: Aggressively compress bureaucratic compounds (\"مورد بررسی قرار داد\" -> \"بررسی کرد\").\n"
            "PATTERNS: \"I'm [X]\" -> \"من [X] هستم\". \"Welcome to [X]\" -> \"خوش آمدید به [X]\".\n"
            "\n"
            "EXECUTION (SILENT; PER LINE; ONE-PASS; STRICT)\n"
            "CONST MAX_RETRY = 1.\n"
            "OUTPUT CONSTRAINTS (HARD)\n"
            "N_input_lines == N_output_lines (Strict Sequencing).\n"
            "MERGE/SPLIT == FORBIDDEN.\n"
            "INTEGRITY: Output line count != Input line count = {lines_count} -> INVALID_RESPONSE.\n"
            "INTEGRITY_RETRY: Before emit, verify N-line sync; if mismatch, silently repair and re-check until equal.\n"
        )

        if dest_lang.lower() == "persian":
            template = self._get_prompt('prompt_EN2FA.txt', default_fa)
            prompt = template.replace("{lines_count}", str(len(lines)))
        else:
            template = self._get_prompt('prompt_universal.txt', default_universal)
            prompt = template.replace("{source_lang}", source_lang).replace("{dest_lang}", dest_lang).replace("{lines_count}", str(len(lines)))

        prompt += f"\nHere is the text to translate:\n{numbered_text}\n"

        return prompt


    def _get_prompt(self, filename, default_content):
        import os
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(default_content)
            return default_content
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()

    def polish_text(self, src_lang_name, dest_lang_name, source_dict, target_dict, global_context=""):
        prompt_content = self._get_prompt('prompt_polish.txt', f"You are an expert editor translating from {src_lang_name} to {dest_lang_name}. Polish the translation line by line. Return ONLY the polished plain text, with each line corresponding to the input lines in order. NO JSON. NO MARKDOWN.")

        payload = {
            "instructions": prompt_content,
            "global_document_context": global_context,
            "source_texts": source_dict,
            "target_texts": target_dict
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional editor. Return ONLY raw plain text. 1 input line = 1 output line."},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                ]
            )

            # Plain text line-by-line mapping logic
            res_dict = {}
            response_text = response.choices[0].message.content.strip()
            cleaned_lines = [line.strip() for line in response_text.split('\n') if line.strip()]
            source_keys = list(source_dict.keys())

            for i, key in enumerate(source_keys):
                if i < len(cleaned_lines):
                    res_dict[key] = cleaned_lines[i]
                else:
                    res_dict[key] = target_dict[key] # Safe fallback
            return res_dict
        except Exception as e:
            print(f"[Error] Polish failed: {e}")
            return target_dict

    def align_text(self, src_lang_name, dest_lang_name, source_dict, target_dict, global_context=""):
        # Load raw instructions from the prompt file
        prompt_content = self._get_prompt('prompt_align.txt', "You are a strict JSON Router for Subtitle Alignment.")

        # global_context excluded — aligner is a structural JSON router only
        payload = {
            "instructions": prompt_content,
            "source_texts": source_dict,
            "target_texts": target_dict
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": "You are a strict JSON Router for Subtitle Alignment. Always return a raw JSON object, no markdown blocks."},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                ],
                response_format={"type": "json_object"}
            )

            try:
                raw = json.loads(response.choices[0].message.content)
                if not isinstance(raw, dict) or not raw:
                    print("[Align] Warning: empty or non-dict result, using fallback.")
                    return target_dict
                raw.pop('_reasoning', None)
                for key in source_dict:
                    if key not in raw:
                        print(f"[Align] Warning: missing key '{key}', restored from target.")
                        raw[key] = target_dict.get(key, '')
                return raw
            except json.JSONDecodeError as json_err:
                print(f"[Error] Align failed due to JSON decoding error: {json_err}")
                print(f"[Fallback] Executing safe KEEP_SEPARATE bypass.")
                return target_dict

        except Exception as e:
            print(f"[Error] Align failed: {e}")
            return target_dict

    def translate(self, source_lang, dest_lang, text_to_translate):
        # Auto-create doc ID & filename if missing
        if not self.doc_id:
            print("[INFO] No document context. Generating new doc_id and using filename 'inline_text'.")
            self.set_filename("inline_text")

        prompt = self.build_translation_prompt(source_lang, dest_lang, text_to_translate)
        print("prompt:")
        print(prompt)

        input_tokens = self.estimate_tokens(prompt)
        print(f"Estimated number of input tokens: {input_tokens}")

        start_time = time.time()
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

        print("response:")
        print(json.dumps(response_json, indent=4))
        print("--end of response--")

        cost_info = self.calculate_openai_cost(response_json)

        translated_text = response.choices[0].message.content.strip()
        
        # Remove duplicate new lines if any
        translated_text = re.sub(r'\n+', '\n', translated_text)

        # Validate line counts
        in_lines = text_to_translate.split("\n")
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
            conn = self.get_db_connection()
            if not conn:
                print('[Warning] DB connection failed, skipping log.')
                return response, translated_text
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO queries
                (doc_id, model_name, prompt_json, response_json, execution_time_sec, input_tokens, output_tokens, total_tokens, cost_usd)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self.doc_id,
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
            except: pass

        return response, translated_text
