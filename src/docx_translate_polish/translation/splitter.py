import re
import os
import time
import json
from typing import List, Optional
from openai import OpenAI
from ..core.config import DEFAULT_MODEL
from ..core.utils import calculate_openai_cost, estimate_tokens
from ..core.logger import TranslationLogger

class DocxLineSplitter:
    """Handles splitting translated text into the expected number of lines."""

    def __init__(self, model: str = DEFAULT_MODEL, client: Optional[OpenAI] = None):
        self.model = model
        self.logger = TranslationLogger()
        if client:
            self.client = client
        else:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                # We only raise if split_ai is actually called, but for safety:
                self.client = None
            else:
                self.client = OpenAI(api_key=api_key)

    @staticmethod
    def build_subtitle_splitter_prompt(src_lang: str, dest_lang: str, source_text: str, translation: str) -> str:
        """
        Builds the prompt for AI-powered line splitting.
        EXACT copy from splitting.py
        """
        lines = source_text.split("\n")
        numbered_lines = [f"Input line {i+1}: {line}" for i, line in enumerate(lines)]
        numbered_text = "\n".join(numbered_lines)

        prompt = (
            f"You are an elite video subtitle editor. You are given a subtitle text in {src_lang} (source language) and its translation in {dest_lang} (target language).\n\n"

            f"Task:\n"

            f"1. Your top priority is that each line in the {dest_lang} translation matches the {src_lang} source line-by-line as closely as possible when viewed side by side.\n"
            f"2. Each line in the {src_lang} source must correspond to exactly one line in the {dest_lang} output.\n"
            f"3. Do not change any words, punctuation, or symbols in the {dest_lang} translation.\n"
            f"4. Preserve all elements such as emails, URLs, symbols, or emojis exactly as they appear in the original {dest_lang} translation.\n\n"

            f"5. Only if strict alignment is impossible due to grammar or phrasing differences, apply professional subtitle line-splitting rules for {dest_lang}:\n"
            f"   - Keep grammatical units together (pronouns + verbs, subject + verb, auxiliary + main verb, verb + object, article + noun, preposition + object).\n"
            f"   - Prefer breaking at natural pauses, commas, conjunctions, or between clauses.\n"
            f"   - Do not split fixed expressions, names, phrasal verbs, or idioms.\n"
            f"   - Avoid leaving short words alone (e.g., 'a', 'the', 'to', 'of').\n"
            f"   - Maintain readability and natural flow.\n"
            f"   - Keep line lengths roughly balanced but prioritize meaning and alignment with the source.\n\n"

            f"6. Output requirements:\n"
            f"   - Output only the {dest_lang} text.\n"
            f"   - Use exactly {len(lines)} lines, matching the {src_lang} source line count.\n"
            f"   - Insert line breaks only; no paraphrasing, numbering, labels, or extra formatting.\n\n"

            f"CRITICAL:\n"
            f"- You MUST output exactly {len(lines)} lines.\n"
            f"- If you cannot split naturally, duplicate or break arbitrarily.\n"
            f"- Never return fewer or more lines.\n"

            f"{src_lang} source ({len(lines)} lines):\n"
            f"{numbered_text}\n\n"

            f"{dest_lang} translation:\n"
            f"{translation}\n\n"

            f"Expected output:\n"
            f"Split the {dest_lang} text into {len(lines)} lines.\n"
            f"Prioritize exact line alignment with the {src_lang} source.\n"
            f"Only apply subtitle readability rules when strict alignment is impossible.\n\n"

            f"Example:\n\n"

            f"English source:\n"
            f"I really enjoyed the movie\n"
            f"and the amazing soundtrack.\n\n"

            f"French translation:\n"
            f"J'ai vraiment apprécié le film et la bande-son incroyable.\n\n"

            f"Correct 2-line output:\n"
            f"J'ai vraiment apprécié le film\n"
            f"et la bande-son incroyable."
        )
        return prompt

    def split(self, mode: str, **kwargs) -> List[str]:
        """Unified entry point for splitting."""
        if mode == "ai":
            return self.split_ai(**kwargs)
        return self.split_classic(**kwargs)

    def split_ai(self, src_lang: str, dest_lang: str, source_text: str, translation: str) -> List[str]:
        """AI-powered intelligent splitting logic."""
        if not self.client:
            self.logger.error("OpenAI client not initialized. Falling back to classic mode.")
            return self.split_classic(translation, len(source_text.split("\n")))

        prompt = self.build_subtitle_splitter_prompt(src_lang, dest_lang, source_text, translation)

        try:
            start_time = time.time()
            if "pro" in self.model:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": "You are a professional subtitle translator line splitting assistant."},
                        {"role": "user", "content": prompt}
                    ]
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a professional subtitle translator line splitting assistant."},
                        {"role": "user", "content": prompt}
                    ]
                )

            elapsed_time = time.time() - start_time
            response_json = response.model_dump()
            cost_info = calculate_openai_cost(response_json)
            self.logger.log_cost(cost_info)

            splitted_text = response.choices[0].message.content.strip()
            # Remove duplicate new lines
            splitted_text = re.sub(r'\n+', '\n', splitted_text)

            out_lines = splitted_text.split("\n")
            expected_count = len(source_text.split("\n"))

            if len(out_lines) != expected_count:
                self.logger.warn(f"AI Split count mismatch! Expected {expected_count}, got {len(out_lines)}")
                return self.split_classic(translation, expected_count)

            return out_lines
        except Exception as e:
            self.logger.error(f"AI splitting failed: {e}")
            return self.split_classic(translation, len(source_text.split("\n")))

    def split_classic(self, translation: str, expected_lines: int) -> List[str]:
        """Deterministic splitting by newline with padding/trimming."""
        lines = [line.strip() for line in translation.split("\n") if line.strip()]

        if len(lines) == expected_lines:
            return lines

        if len(lines) > expected_lines:
            # Join extra lines into the last allowed line
            main_lines = lines[:expected_lines-1]
            extra = " ".join(lines[expected_lines-1:])
            main_lines.append(extra)
            return main_lines
        else:
            # Pad with empty strings
            while len(lines) < expected_lines:
                lines.append("")
            return lines
