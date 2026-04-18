# ═══════════════════════════════════════════════════
# PROTECTED FILE — Do not modify without explicit
# written approval from project owner.
# ═══════════════════════════════════════════════════

def build_translation_prompt(source_lang, dest_lang, text):
    """
    Builds the translation prompt for OpenAI.
    EXACT copy from src/openai_translator/translator.py
    """
    numbered_lines = []
    for i, line in enumerate(text.split("\n"), 1):
        numbered_lines.append(f"{i}. {line}")
    numbered_text = "\n".join(numbered_lines)

    if dest_lang.lower() == "persian" or dest_lang.lower() == "fa":
        prompt = (
            f"SYSTEM_ROLE: SENIOR_LITERARY_TRANSLATOR (English -> Persian)\n"
            f"CONTEXT: Supreme Master Television (SMTV) — High-quality spiritual/educational subtitles.\n"
            f"INPUT_SPEC: {len(numbered_lines)} numbered English lines.\n"
            f"\n"
            f"PROTOCOLS (STRICT):\n"
            f"P0: [SCRIPT]: Persian (Farsi) script only. NO Latin/English characters allowed in output.\n"
            f"P1: [Z-LOCK]: Technical terms, names of programs, and 'SMTV' remain byte-identical.\n"
            f"P2: [REFINEMENT]: Use ZWNJ (\u200c) for correct spacing. Apply Persian grammar (Syntax) over English structure.\n"
            f"P3: [HONORIFICS]: Apply spiritual/respectful register (Sage Mode) where context warrants.\n"
            f"\n"
            f"Example of line pairings:\n"
            f"\"Welcome to [X]\" -> \"خوش آمدید به [X]\"\n"
            f"\n"
            f"EXECUTION (SILENT; PER LINE; ONE-PASS; STRICT)\n"
            f"CONST MAX_RETRY = 1.\n"
            f"\n"
            f"OUTPUT CONSTRAINTS (HARD)\n"
            f"N_input_lines == N_output_lines (Strict Sequencing).\n"
            f"MERGE/SPLIT == FORBIDDEN.\n"
            f"INTEGRITY: Output line count must be {len(numbered_lines)}.\n"
            f"\n"
            f"Here is the text to translate:\n"
            f"{numbered_text}\n"
        )
    else:
        prompt = (
            f"Your task is to translate {source_lang} into high-quality {dest_lang} suitable for television subtitles.\n"
            f"Maintain the exact line structure. There are {len(numbered_lines)} lines.\n"
            f"Translate each line independently. Do not merge or split lines.\n"
            f"\n"
            f"Text to translate:\n"
            f"{numbered_text}\n"
        )

    return prompt
