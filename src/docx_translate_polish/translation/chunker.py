"""
FUTURE USE — Chunking support for very large documents.

Currently disabled. Default behavior: entire document in one API call.
To enable chunking in the future:
  - Set chunk_enabled=True in TranslationConfig (config.py)
  - Set chunk_size to the desired number of lines per API call
This module is intentionally preserved for future large-file support.
"""
from typing import List, Dict
from ..core.utils import estimate_tokens

class Chunker:
    """Handles grouping cells into phrases and phrases into API-safe blocks."""

    def build_phrases(self, cells: List[Dict]) -> List[Dict]:
        """Groups cells into phrase blocks based on EOL/BOL markers."""
        phrases = []
        current_phrase = {"rows": [], "text": "", "lines_count": 0}

        for cell in cells:
            text = cell['clean_text']
            current_phrase["rows"].append(cell['row_n'])
            current_phrase["text"] += (text + " ")
            current_phrase["lines_count"] += 1

            # Very basic phrase boundary detection for now
            if text.strip().endswith(('.', '!', '?', ':', ';')):
                current_phrase["text"] = current_phrase["text"].strip()
                phrases.append(current_phrase)
                current_phrase = {"rows": [], "text": "", "lines_count": 0}

        if current_phrase["rows"]:
            current_phrase["text"] = current_phrase["text"].strip()
            phrases.append(current_phrase)

        return phrases

    def split_into_token_blocks(self, phrases: List[Dict], max_tokens: int) -> List[List[Dict]]:
        """Groups phrases into API blocks within token limits."""
        blocks = []
        current_block = []
        current_tokens = 0

        for phrase in phrases:
            tokens = estimate_tokens(phrase['text'])
            if current_tokens + tokens > max_tokens and current_block:
                blocks.append(current_block)
                current_block = []
                current_tokens = 0

            current_block.append(phrase)
            current_tokens += tokens

        if current_block:
            blocks.append(current_block)

        return blocks
