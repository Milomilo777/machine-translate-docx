# Jules Briefing — Machine Translate DOCX

## Stack
- Python + customtkinter GUI
- OpenAI API (gpt-5.4 / gpt-5-mini)
- Selenium for browser engines

## Active Branch
feature/ai-localization-lab-10415451625341488816

## Architecture
- gui_translator.py → machine-translate-docx.py → translator.py
- Prompts: /prompts/*.txt (loaded by _get_prompt())
- 4 pipeline stages: translate → polish → split_double → (map TBD)

## Prompt Files
- prompt_Persian.txt      → Stage 1 (FA translation)
- prompt_Universal.txt    → Stage 1 (other languages)
- prompt_polish.txt       → Stage 2
- prompt_split_double.txt → Stage 3

## Conventions
- temperature=0 on all AI calls
- ensure_ascii=False on all json.dumps()
- system role = prompt, user role = data only
- repair_lines() handles line count mismatch
