"""Phrase and token chunking logic."""
from typing import List, Dict
from ..core.utils import estimate_tokens
from ..docx_io.reader import DocxReader

class Chunker:
    """Groups cells into phrases and token-limited blocks."""

    def build_phrases(self, cells: List[Dict]) -> List[Dict]:
        """Groups cells into phrase blocks based on punctuation."""
        phrases = []
        if not cells:
            return phrases

        current_phrase = None

        for i, cell in enumerate(cells):
            text = cell['clean_text']
            if not text:
                continue

            # Check if this cell starts a new phrase
            is_start = DocxReader.is_beginning_of_line(text) or current_phrase is None

            if is_start and current_phrase:
                phrases.append(current_phrase)
                current_phrase = None

            if current_phrase is None:
                current_phrase = {
                    "start_row": cell['row_n'],
                    "end_row": cell['row_n'],
                    "text": text,
                    "nb_lines": cell['nb_lines_in_cell'],
                    "rows": [cell['row_n']]
                }
            else:
                current_phrase["text"] += " " + text
                current_phrase["end_row"] = cell['row_n']
                current_phrase["nb_lines"] += cell['nb_lines_in_cell']
                current_phrase["rows"].append(cell['row_n'])

            # Check if this cell ends a phrase
            if DocxReader.is_end_of_line(text):
                phrases.append(current_phrase)
                current_phrase = None

        if current_phrase:
            phrases.append(current_phrase)

        return phrases

    def split_into_token_blocks(self, phrases: List[Dict], max_tokens: int) -> List[List[Dict]]:
        """Groups phrases into API-safe blocks under max_tokens limit."""
        blocks = []
        current_block = []
        current_tokens = 0

        for phrase in phrases:
            phrase_tokens = estimate_tokens(phrase['text'])
            if current_tokens + phrase_tokens > max_tokens and current_block:
                blocks.append(current_block)
                current_block = []
                current_tokens = 0

            current_block.append(phrase)
            current_tokens += phrase_tokens

        if current_block:
            blocks.append(current_block)

        return blocks
