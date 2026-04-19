import re
import os
import time
from typing import List, Optional
from openai import OpenAI
from ..core.config import DEFAULT_MODEL
from ..core.utils import calculate_openai_cost

class DocxLineSplitter:
    """Handles splitting translated text into the expected number of lines."""

    def __init__(self, model: str = DEFAULT_MODEL, client: Optional[OpenAI] = None):
        self.model = model
        if client:
            self.client = client
        else:
            api_key = os.environ.get("OPENAI_API_KEY")
            self.client = OpenAI(api_key=api_key) if api_key else None

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
            f"   - Keep grammatical units together.\n"
            f"   - Maintain readability and natural flow.\n\n"
            f"6. Output requirements:\n"
            f"   - Use exactly {len(lines)} lines.\n"
            f"CRITICAL: You MUST output exactly {len(lines)} lines.\n\n"
            f"{source_lang} source ({len(lines)} lines):\n"
            f"{numbered_text}\n\n"
            f"{dest_lang} translation:\n"
            f"{translation}\n"
        )
        return prompt

    def split(self, mode: str, logger=None, block_index: int = 0, **kwargs) -> List[str]:
        """Unified entry point for splitting."""
        start_time = time.time()
        if mode == "ai":
            lines_out = self.split_ai(**kwargs)
        else:
            lines_out = self.split_classic(kwargs.get("translation", ""), kwargs.get("expected_lines", 0))

        elapsed = time.time() - start_time
        if logger is not None:
            logger.log_split(
                block_index=block_index,
                mode=mode,
                lines_in=kwargs.get("source_text", "").split("\n") if "source_text" in kwargs else [],
                lines_out=lines_out,
                elapsed_seconds=elapsed,
            )
        return lines_out

    def split_ai(self, src_lang: str, dest_lang: str, source_text: str, translation: str) -> List[str]:
        """AI-powered intelligent splitting logic."""
        if not self.client:
            return self.split_classic(translation, len(source_text.split("\n")))

        prompt = self.build_subtitle_splitter_prompt(src_lang, dest_lang, source_text, translation)
        try:
            if "pro" in self.model:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": "You are a professional subtitle editor."},
                        {"role": "user", "content": prompt}
                    ]
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a professional subtitle editor."},
                        {"role": "user", "content": prompt}
                    ]
                )

            splitted_text = response.choices[0].message.content.strip()
            splitted_text = re.sub(r'\n+', '\n', splitted_text)
            out_lines = splitted_text.split("\n")
            expected_count = len(source_text.split("\n"))

            if len(out_lines) != expected_count:
                return self.split_classic(translation, expected_count)
            return out_lines
        except Exception:
            return self.split_classic(translation, len(source_text.split("\n")))

    def split_classic(self, translation: str, expected_lines: int) -> List[str]:
        """Deterministic splitting by newline with padding/trimming."""
        lines = [line.strip() for line in translation.split("\n") if line.strip()]
        if len(lines) == expected_lines:
            return lines
        if len(lines) > expected_lines:
            main_lines = lines[:expected_lines-1]
            extra = " ".join(lines[expected_lines-1:])
            main_lines.append(extra)
            return main_lines
        else:
            while len(lines) < expected_lines:
                lines.append("")
            return lines
