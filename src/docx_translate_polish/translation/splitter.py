"""Line splitting logic for translated text."""
from typing import List

class DocxLineSplitter:
    """Handles splitting translated text into the expected number of lines."""

    def split(self, mode: str, **kwargs) -> List[str]:
        """Unified entry point for splitting."""
        if mode == "ai":
            return self.split_ai(**kwargs)
        return self.split_classic(**kwargs)

    def split_ai(self, src_lang: str, dest_lang: str, source_text: str, translation: str) -> List[str]:
        """AI-powered intelligent splitting (Placeholder)."""
        # Source missing in repo, implementing skeleton/fallback
        expected_lines = len(source_text.split("\n"))
        return self.split_classic(translation, expected_lines)

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
