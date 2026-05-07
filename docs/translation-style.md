# Translation Style Guide — Persian Broadcast Subtitles

Quality target: broadcast-ready Persian TV subtitle quality.

---

## Register & Tone

- Use **formal Persian** (رسمی / ادبی), not colloquial
- Maintain original speaker's tone: authoritative = formal, casual = semi-formal
- Avoid calques from English — find the natural Persian equivalent

## Line Constraints

- Maximum **50 characters** per subtitle line (hard limit, enforced by aligner)
- No dangling prepositions at line end: `به` / `از` / `در` / `برای` / `با` / `که` / `تا` / `بر`
- Compound verbs must not be split across lines: `استفاده می‌کند`, `انجام داد`, etc.
- `را` must stay with its noun phrase

## Text Preservation Rules

- All numbers, digits (including Persian-script digits), proper nouns, and quoted strings
  must appear in the corresponding output line — never dropped or moved to a different line
- Do not add information that was not in the source
- Do not remove any semantic content from the source

## Half-Space (ZWNJ)

- U+200C (ZWNJ / نیم‌فاصله) must be preserved byte-for-byte
- Examples: `می‌کند`, `نمی‌توان`, `کتاب‌ها`
- Never replace with a regular space or remove entirely

## Double-Line (Aligner) Output

- Each FA chunk: ≤ 50 characters
- Doubling ratio target: 25 – 55 %
- No triple-line repetition (never 3× same text in consecutive rows)
- Named entity alignment: if EN row N has a number/proper noun, FA row N must contain it

## Polisher Behavior

- Polisher receives the raw translation and corrects grammar, naturalness, and broadcast register
- It does **not** re-translate; it refines only
- Output format uses `⟨⟨N⟩⟩` line markers — do not alter the parser in `polisher.py`

## System Prompt Files

| File | Purpose |
|------|---------|
| `prompts/translate_PER.txt` | Translation instructions for Persian |
| `prompts/polish_PER.txt` | Polish/refinement instructions for Persian |
| `prompts/translate_universal.txt` | Fallback for non-Persian languages |

To add a new language: create `prompts/translate_{ISO639_2B}.txt` and add the code
to `_PROMPT_FILE_MAP` in `translator.py`.
