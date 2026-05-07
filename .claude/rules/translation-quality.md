# Translation Quality Rules

Quick reference for enforcing broadcast-quality Persian output.

Full style guide: `docs/translation-style.md`

---

## Hard checks (block output if violated)

- [ ] No FA chunk > 50 characters
- [ ] No triple-line repetition in aligner output
- [ ] All named entities (numbers, proper nouns) preserved in corresponding row
- [ ] ZWNJ (U+200C) unchanged in all FA text
- [ ] Compound verbs not split across lines (`می‌کند`, `انجام داد`, etc.)
- [ ] `را` not separated from its noun phrase

## Soft checks (warn, do not block)

- [ ] No dangling preposition at line end
- [ ] Doubling ratio between 25 % and 55 %
- [ ] Chunk length balance within a group (avoid 8-char next to 48-char)
- [ ] No orphan line starters (`و`, `که` alone at start of chunk)

## Prompt file coverage

- Persian: `prompts/translate_PER.txt` + `prompts/polish_PER.txt`
- All others: `prompts/translate_universal.txt`
- New language needs its own `translate_{ISO639_2B}.txt` + entry in `_PROMPT_FILE_MAP`

## When polisher output line count mismatches input

- Check `docs/error-catalog.md` E5
- The 4-strategy parser in `polisher.py` handles most cases
- If count is still wrong, log the raw response and add to error catalog
