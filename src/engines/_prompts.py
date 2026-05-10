"""Prompt builders shared by web-Selenium engines.

The web-LLM engines (``chatgpt_web``, ``perplexity_web``) need a
multi-line "translate this exactly line-by-line" prompt that tells the
host model what to do with the text. The legacy
``translation-robot/main`` lived in a single file with hyphens in the
filename, so the helper sat next to its callers as a module global.
After the engine modules were extracted (phase 8), the helper became
unreachable — every call to either web engine would NameError on the
``build_translation_prompt`` invocation and the wrapper would silently
return ``(False, "")``.

This module is the new home. The entry script
``src/machine-translate-docx.py`` re-exports
:func:`build_translation_prompt` for backward compatibility with any
caller that still goes through the old name.
"""
from __future__ import annotations


def build_translation_prompt(source_lang: str, dest_lang: str, text: str) -> str:
    """Build a numbered-line translation prompt for an LLM.

    Each input line is prefixed with ``Line N: `` so the model can keep
    a stable mapping; the post-processing splits on ``\\n`` and strips
    the ``Line N:`` prefix back off.

    The prompt content is preserved verbatim from the legacy entry
    script (commit ``upstream-old/main``) so behavioural parity is
    guaranteed for downstream subtitle alignment.
    """
    lines = text.split("\n")
    numbered_lines = [f"Line {i + 1}: {line}" for i, line in enumerate(lines)]
    numbered_text = "\n".join(numbered_lines)

    prompt = (
        f"You are a professional subtitling translator.\n"
        f"Your task is to translate {source_lang} into {dest_lang}.\n\n"
        f"Overall context and style:\n"
        f"- Read all lines first so you understand the full context.\n"
        f"- Treat the entire input as one coherent text when choosing tone and terminology.\n"
        f"- Ensure consistent translations for recurring terms, names, and concepts across all lines.\n"
        f"- If part of the text to translate is already in {dest_lang}, treat it as a translation memory and keep it literal.\n"
        f"Line-by-line constraints:\n"
        f"- Translate line by line: produce exactly one output line for each input line.\n"
        f"- Do NOT merge, split, add, remove, or repeat lines.\n"
        f"- Use formal, standard and natural {dest_lang} (non-colloquial);preserve all information.\n"
        f"- But the wording inside each line is allowed to become a bit shorter or longer in order to produce natural {dest_lang}.\n"
        f"- Preserve the input line order.\n"
        f"- Parentheses and multiple sentences within a line belong to that same line.\n"
        f"- Only translate lines that start with 'Line ' followed by a number and a semicolon.\n"
        f"- For each such line, translate only the TEXT after the first semicolon.\n"
        f"- After translation, do NOT include 'Line N:' in the output; only output the translated TEXT.\n"
        f"- Output only {dest_lang} text, with no explanations or comments.\n"
        f"- Produce exactly {len(lines)} output lines, in the same order as the input, there should be no blank lines.\n"
        f"- End each output line with a single newline character also known as line feed or LF (do not add extra blank lines between translated lines in the output).\n"
    )

    if dest_lang.lower() == "persian":
        prompt += (
            "- When writing decimal numbers in Persian, use a dot as the decimal separator, e.g. write «۱۲.۵» not «۱۲/۵» (and not «۱۲,۵»).\n"
            "- Do NOT add diacritics (no short vowels or tashkeel such as َ ِ ُ ّ ٌ ً ٍ),  unless a rare word would be ambiguous without them.\n"
            "- Apply the following fixed terminology rules whenever these English forms appear:\n"
            "  - \"animal-person\" / \"animal-people\"  →  «شخص-حیوان» / «اشخاص-حیوان»\n"
            "  - \"tiger-person\" / \"tiger-people\"    →  «شخص-ببر»   / «اشخاص-ببر»\n"
            "  - \"cow-person\" / \"cow-people\"        →  «شخص-گاو»   / «اشخاص-گاو»\n"
            "  (Do NOT translate them as ordinary “animal(s) / tiger(s) / cow(s)”.)\n"
        )

    prompt += f"Here is the text to translate:\n{numbered_text}\n"

    return prompt


__all__ = ["build_translation_prompt"]
