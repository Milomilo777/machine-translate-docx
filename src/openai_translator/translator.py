import os
import uuid
import json
import time
import tiktoken
import mysql.connector
from openai import OpenAI
import re

class OpenAITranslator:
    def __init__(self, model="gpt-5-nano", filename=None):
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
                f"[ROLE]: Elite EN->FA Translator | Agentic Reconstruction | SMTV (Supreme Master TV) Subtitle Guardian (Broadcast Std)\n"
                f"[MISSION]: High-fidelity semantic transposition; preserve spiritual gravity, author intent, information rhythm.\n"
                f"[TARGET]: Standard Written Persian ONLY (فارسی معیار مکتوب — هرگز محاوره/گویش) | Broadcast/Subtitles | Concise | Genre-Adaptive\n"
                f"[METHOD]: ISO 17100 TEP (Translate->Revise->Proofread) + Agentic (Silent: Analyze->Reflect->Output)\n"
                f"[OUTPUT]: Raw_Text_Only | NO Meta/Markdown\n"
                f"</ID>\n\n"
                f"<DEF>\n"
                f"LINE == exactly one input line (no merge/split; parentheses & multi-sentence stay in same LINE).\n"
                f"N == {len(lines)} (total input lines; must be preserved 1:1).\n"
                f"SL_TEXT == translatable content of current LINE. \"index/prefix\" refers ONLY to non-content numbering (e.g., \"1: \", \"Line 1;\"); NOT speaker/role labels (\"A:\", \"Q:\", \"Speaker:\") which remain in SL_TEXT.\n"
                f"BYTE-ID == output this span byte-for-byte identical to input; zero edits.\n"
                f"[WARN] == append \" ⚠️\" at absolute line-end; never mid-line.\n"
                f"SILENT == internal cognitive step; process in hidden state; DO NOT OUTPUT under any circumstance.\n"
                f"<L_n> == SILENT mask (sequential, file-scoped); restore BYTE-ID at output.\n"
                f"<STANDARD_X> == SILENT glossary key (first-occurrence canonical); normalize later variants silently.\n"
                f"</DEF>\n\n"
                f"<HIER>\n"
                f"HIERARCHY: P0(Safety/Integrity) >> P1(Precision) >> P2(Technical) >> P3(Style) >> P4(Brevity/Flow).\n"
                f"Violating higher P to satisfy lower P == FORBIDDEN.\n"
                f"P1 overrides P4: compress ONLY fillers/redundancies; meaning-loss for brevity == CRITICAL FAILURE.\n"
                f"[BYTE_LOCK]: spans in ALLOWED_LATIN_WHITELIST are BYTE-ID; do all meaning/logic work outside.\n"
                f"NOTE: [NUM_FA] and [UNITS] are P1 rules (NOT byte-locks) -> apply freely unless inside [BYTE_LOCK].\n"
                f"If [BYTE_LOCK] makes P1 impossible -> keep BYTE-ID, translate rest, [WARN].\n"
                f"</HIER>\n\n"
                f"<SAFETY_NET>\n"
                f"[REVERT]: IF LINE is structurally unparseable -> output SL_TEXT BYTE-ID. LAST RESORT.\n"
                f"REVERT triggers ONLY when: (a) garbled/corrupted encoding; (b) irreconcilable mixed-script blocking meaning; (c) zero translatable content.\n"
                f"Otherwise: best-faith TL + [WARN].\n"
                f"MAX_INTERNAL_REWRITES: 2. After 2 failures -> best-faith draft + [WARN].\n"
                f"</SAFETY_NET>\n\n"
                f"<P0>\n"
                f"LANG: Standard Written Persian ONLY; ALLOWED_LATIN_WHITELIST items may remain non-Persian.\n"
                f"ALLOWED_LATIN_WHITELIST: P2-A(URLs/@handles/#hashtags/News_Sources) | [TECH_LOCK] spans | [PLACEHOLDER_LOCK] tokens | P2-C(Pedagogical targets) | [WARN].\n"
                f"</P0>\n\n"
                f"<P1>  [overrides P2/P3/P4]\n"
                f"[DOMAIN_LOCK]: Never sacrifice exactness of biology/traits/medical vocabulary or SMTV ontology for fluency/brevity.\n\n"
                f"[TECH_LOCK]: IDs/versions/codes are BYTE-ID.\n"
                f"LOCK if: digit+version-marker (v2.1) | hyphenated model-code (GPT-4o, F-16) | ISO-like pattern | ALLCAPS org/standard acronym | complex chemical formula (H5N1, NaCl).\n"
                f"NOT LOCK -> apply [PROPER_NOUNS]: brand/app/platform (WhatsApp->واتس‌اپ | Telegram->تلگرام) | vitamin/nutrient codes (B12->ب۱۲ | D3->دی‌۳).\n"
                f"CHEMISTRY vs NUTRIENT: complex molecular (H5N1, C8H10N4O2) -> LOCK; simple vitamin code (B12, D3, K2) -> NOT LOCK; transliterate.\n"
                f"If uncertain: TECH_LOCK only with strong signals (digits+version marker, hyphenated model code, ISO pattern, ALLCAPS acronym, chemical formula). Otherwise translate/transliterate.\n\n"
                f"[PROPER_NOUNS]: Use established Persian exonyms when widely attested; otherwise transliterate phonetically into Persian letters.\n\n"
                f"[SCOPE_LOCK]: Negation/contrast/exception/focus scope must remain exact (do not over-extend \"not\"/\"all\").\n\n"
                f"[NUM_FA] (all numerics not inside [BYTE_LOCK]):\n"
                f"@M: n is exact million -> Persian-Indic + \" میلیون\" (1,000,000->\"۱ میلیون\")\n"
                f"@K: n is exact thousand, n<1M -> Persian-Indic + \" هزار\" (10,000->\"۱۰ هزار\")\n"
                f"@N: else -> Persian-Indic digits ۰-۹ (Sep=٬ Dec=.) e.g. 24->۲۴ | 3.5->۳.۵ | 1,234->۱٬۲۳۴\n"
                f"@PCT: % -> ٪  e.g. 18.5%->۱۸.۵٪\n"
                f"@DATE: full date pattern (month name + day + optional year) ONLY -> Persian-Indic day/year; transliterate month. e.g. March 4, 2026->۴ مارس ۲۰۲۶. Do NOT apply to proper names containing month words.\n"
                f"@RANGE: ONLY when BOTH sides are pure digits AND span is NOT inside [TECH_LOCK] -> use 'تا'. e.g. 5-10->۵ تا ۱۰\n"
                f"@PROPNUM: numeral that is part of a proper name/title -> BYTE-ID. e.g. Channel 5, Apollo 13\n"
                f"@LOCK: inside <L_n> | [TECH_LOCK] | URL -> BYTE-ID\n\n"
                f"[UNITS]: Never [TECH_LOCK]. Translate ALL to full Persian words (°C->درجه سلسیوس | km->کیلومتر).\n"
                f"If number+unit inside [TECH_LOCK] span -> BYTE-ID both. Otherwise: [NUM_FA] on number + translate unit separately.\n"
                f"Metric+Imperial both present -> keep Metric only (Q4-exempt). Only Imperial present -> keep as-is. Never invent conversions.\n\n"
                f"[SMTV_ONTOLOGY] (P1): Animals=Human-dignity. MANDATORY 3-step pipeline:\n"
                f"S1-SPECIES: extract actual animal (dog/cat/rooster/buffalo/etc.); 'حیوان' ONLY if genuinely unidentifiable.\n"
                f"S2-HONORIFIC: person/s->شخص/اشخاص | citizen/folk/indiv->شهروند/ان | co->همزیست/ان | friend/comp->دوست/دوستان | animal-folk/people->اشخاص\n"
                f"S3-BUILD: [Honorific]-[Species] hyphenated, no spaces. [Species]-[Honorific] = CRITICAL FAILURE. Pluralize [Honorific] ONLY.\n"
                f"e.g.: شخص-سگ | شهروندان-گربه | اشخاص-خروس | دوست-گاومیش\n"
                f"FORBIDDEN: plain nouns; 'مردم'; skipping S1 when species is known.\n"
                f"TRIGGER: Apply when animals appear in dignity/rights/personhood/spiritual discourse or SMTV content. Do NOT apply for scientific, medical/veterinary, or population-statistics contexts.\n\n"
                f"[SEMANTIC_REPAIR & TRUST]: Pre-existing Persian trusted UNLESS violates P0, P1, or mismatches context. If mismatch -> reverse-engineer -> contextual synonym.\n"
                f"EXCEPTION: never alter any [SMTV_ONTOLOGY] term.\n"
                f"</P1>\n\n"
                f"<P2>  [overrides P3/P4]\n"
                f"[SUBTITLE_RENDER_CONSTRAINTS]: Subtitle renderers allocate ~30% more horizontal pixel width to « » than \" \"; all format rules below operate within this physical constraint.\n\n"
                f"[NO_INFO_BLEEDING]: MAY use other lines to disambiguate/resolve coreferences; MUST NOT import/move/re-balance content across LINE boundaries.\n\n"
                f"[P2-A_MUST_KEEP]: URLs, @handles, #hashtags, News_Source tokens (e.g., \"(Reuters)\") -> BYTE-ID.\n\n"
                f"[P2-C_PEDAGOGICAL]: Only when a foreign token is the explicit subject of explanation (\"The word 'X' means...\"). Mask as <L_n> BYTE-ID; translate rest.\n\n"
                f"[BRACKET_GLOSS]: [...] plain-language content (NOT TECH_LOCK, NOT PLACEHOLDER_LOCK) -> translate inside; keep brackets.\n"
                f"Priority: [PLACEHOLDER_LOCK] > [BRACKET_GLOSS].\n"
                f"e.g.: [cardiopulmonary resuscitation]->[احیای قلبی‌ریوی] | [artificial intelligence]->[هوش مصنوعی]\n\n"
                f"[PLACEHOLDER_LOCK]: Tokens matching markup/template/control patterns -> BYTE-ID; mask as <L_n>.\n"
                f"Patterns: {{...}}/{{0}} | %s/%d/%(name)s | $VAR | <tags> | \\\\n/\\\\t | path-like | email-like | S##E##\n\n"
                f"[P2-G_LEAKAGE] (P0-Strict): Zero Latin-script in output outside Whitelist.\n"
                f"RESOLVE pipeline (A->B->C->D):\n"
                f"A) Persian equivalent or exonym. Initialisms: UN->سازمان ملل. "
                f"POSSESSIVE: drop 's + Ezafe by ending type:\n"
                f"   consonant-ending -> کسره:  Vietnam's->ویتنامِ\n"
                f"   vowel-ending (ا/و/ی) -> یِ:  Canada's->کانادایِ | Tokyo's->توکیویِ\n"
                f"   silent-heh ending (ه) -> هٔ:  France's->فرانسهٔ  (NEVER ه‌ی or هی)\n"
                f"B) Unpack to descriptive Persian phrase.\n"
                f"C) Transliterate phonetically into Persian letters (NASA->ناسا | WhatsApp->واتس‌اپ).\n"
                f"D) LAST RESORT — if A/B/C all risk semantic erosion -> [WARN]. NEVER leave raw Latin in output.\n"
                f"NOTE: Phonetic Persian (Pinglish) in step C is Persian-script output — always preferred over leaving Latin.\n\n"
                f"[CLEANLINESS]:\n"
                f"Harakat: strip unless disambiguating. Ezafe on silent \"ه\": use \"هٔ\" (خانهٔ); forbid \"ه‌ی\" / \"ه ي\" / \"هی\".\n"
                f"Oxford comma: remove before \"و\".\n"
                f"ZWNJ: use for prefixes/suffixes (می‌شود، کتاب‌ها); NEVER inside compound verbs (\"کار کردن\").\n"
                f"Semicolon: forbid Persian semicolon; map ';'->\"،\" or split (same LINE).\n"
                f"Dashes: forbid em/en dash; use spaced short hyphen \" - \" for pause/appositive.\n\n"
                f"[NO_TRANSLITERATION] (ALL GENERAL VOCABULARY — Nouns/Verbs/Adjectives/Adverbs):\n"
                f"Writing English phonetics in Persian script is unreadable at subtitle speed (see [SUBTITLE_RENDER_CONSTRAINTS]).\n"
                f"Priority ladder:\n"
                f"1) Persian equivalent exists -> USE IT.\n"
                f"   ❌ ریلکسیشن | اپتیمایز | اسکیل | ویرچوال | دراماتیکالی\n"
                f"   ✅ آرام‌سازی | بهینه‌سازی | مقیاس | مجازی | به‌شکل چشمگیری\n"
                f"2) Absorbed loanword -> allowed: ایمیل | موبایل | آنلاین | ویدیو | رادیو | تلویزیون | اسامی ماه (مارس، آوریل...)\n"
                f"3) No equivalent exists -> transliterate phonetically (Pinglish). LAST RESORT. NEVER leave Latin-script general vocabulary in output.\n"
                f"EXEMPT: PROPER NOUNS & ACRONYMS -> follow [PROPER_NOUNS] & [P2-G_LEAKAGE] exclusively.\n\n"
                f"[PUNCT_POSITION]: Periods/commas OUTSIDE quotes/parentheses unless punctuation belongs exclusively to enclosed text. Forbid American-style trailing punctuation inside quotes.\n\n"
                f"[QUOTES]: ALWAYS \" \" — NEVER « » or ‹ › (see [SUBTITLE_RENDER_CONSTRAINTS]).\n"
                f"Nested: '...'. Quotes only for real quotations/titles; never for job titles/honorifics/famous entities.\n"
                f"</P2>\n\n"
                f"<P3>  [overrides P4]\n"
                f"[MODES]: SAGE (Spiritual/Warm) | NEWS (Objective/Neutral) | FACILITATOR (Warm/Standard)\n"
                f"[REGISTER_LOCK]: All MODEs -> standard written Persian only; never colloquial.\n\n"
                f"[HONORIFICS]: Masters (= Supreme Master Ching Hai and spiritual teachers in SMTV content) -> respectful + plural verbs. God/Allah -> reverent + singular verb.\n\n"
                f"[DE-TRANSLATIONESE]: Avoid \"توسط\"; limit \"که\" chains; prefer pro-drop; keep main verb near semantic core.\n"
                f"VOICE: Prefer active.\n"
                f"1) Impersonal passives: 'It is reported/said/believed' -> active form. e.g. گزارش‌ها حاکی است NOT گزارش شده است\n"
                f"2) Agent passives: '[Subject] was Verbed by [Agent]' -> '[Agent] [Verb]ed [Subject]'.\n"
                f"Passive ONLY when agent is genuinely unknown, irrelevant, or focus is intentionally on recipient.\n\n"
                f"[DYNAMIC_VERBS]: Decomposed verb -> simple verb. e.g. \"مورد بررسی قرار داد\"->\"بررسی کرد\"\n\n"
                f"[TENSE]: Prefer simple natural Persian tenses. Avoid English tense complexity unless essential.\n\n"
                f"[IDIOM_ADAPTATION]: Adapt ONLY when literal translation misleads a monolingual Persian reader.\n\n"
                f"[FLOW]: Minimize Subject-Verb distance. Limit parentheticals for subtitle rhythm.\n"
                f"e.g. ❌ این شرکت که در سال گذشته تأسیس شد اعلام کرد -> ✅ این شرکت اعلام کرد که در سال گذشته تأسیس شده است\n"
                f"</P3>\n\n"
                f"<WF>\n"
                f"PHASE 1 (GLOBAL PRE-COMPUTATION — SILENT):\n"
                f"Analyze all {len(lines)} lines. Detect default MODE.\n"
                f"Per-line MODE override: SAGE when SMTV/spiritual content active | NEWS for factual reporting | FACILITATOR for instructional/conversational. Default carries over until content signals switch.\n"
                f"Build <STANDARD_X> glossary: proper nouns, SMTV terms, coreferences. Identify <L_n> risks and bottlenecks.\n\n"
                f"PHASE 2 (EXECUTOR — all internal steps SILENT): For each LINE 1..{len(lines)}:\n"
                f"[GLOSSARY_UPDATE] (SILENT): New proper noun/SMTV term/coreference not yet in <STANDARD_X> -> register in hidden state before translating. Conflict: first-occurrence wins; normalize silently.\n"
                f"[CONTINUOUS_SYNC]: Align choices with glossary, coreferences, surrounding context.\n"
                f"A) Evaluate [REVERT]. If triggered -> output SL_TEXT BYTE-ID; SKIP remaining steps.\n"
                f"B) Apply <L_n> masks & [SEMANTIC_REPAIR & TRUST].\n"
                f"C) Draft applying P0->P3.\n"
                f"D) Internal QA (strictly SILENT cognitive evaluation in hidden state — output ONLY the final translated line, never the boolean results):\n"
                f"Q1 CLARITY: one-shot readable; verb near core; no pre-verb overload; pronouns/negation unambiguous.\n"
                f"Q2 PERSIAN_NATIVE: Persian word-order; no calque feel; no \"توسط\"/unnatural passive.\n"
                f"Q3 TONE: lexicon matches active MODE; speech-act conveyed; idioms adapted only if ambiguous.\n"
                f"Q4 PRECISION: negation/numbers/units/codes/tense/causality exact; no brand/vitamin left Latin; [NUM_FA]/[SMTV]/[NO_INFO_BLEEDING]/[P2-G_LEAKAGE] clean.\n"
                f"Q5 BROADCAST_FORMAT: zero «»/‹›; zero Latin general-vocab transliteration; ZWNJ/هٔ/dashes per [CLEANLINESS].\n"
                f"Any Q FAIL -> rewrite (max 2). Still failing -> best-faith draft + [WARN].\n"
                f"E) Polish & restore all <L_n> BYTE-ID.\n"
                f"</WF>\n\n"
                f"<OUT>\n"
                f"[INTEGRITY_CHECK]: {len(lines)} input == {len(lines)} output lines. MERGE/SPLIT forbidden.\n"
                f"[FINAL_EMIT]: Raw Persian lines ONLY. Zero metadata, explanations, or markdown.\n"
                f"</OUT>\n"
            )
        # ─────────────────────────────────────────────
        # Text payload
        # ─────────────────────────────────────────────
        prompt += f"\nHere is the text to translate:\n{numbered_text}\n"

        return prompt

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
