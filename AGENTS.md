# AGENTS.md — Standing Instructions for AI Coding Agents

## What is this project?
SMTV Translation & Localization Lab.
A Python desktop tool that processes subtitle .docx files through a 3-stage AI pipeline.

## The 3 Stages
- Stage 1: Translate (Raw) — uses gpt-5.4
- Stage 2: Polish — uses gpt-5-mini
- Stage 3: Align & Double — uses gpt-5-mini + prompt_align.txt (JSON Router)

## Key Files
| File | Role |
|---|---|
| gui_translator.py | Desktop UI (CustomTkinter). Launches subprocesses. |
| machine-translate-docx-2.py | Main backend. Contains Dual-Path logic. |
| openai_translator/translator.py | OpenAITranslator class. All API calls. |
| openai_translator/prompt_align.txt | Frozen V5 prompt. Do NOT edit without ADR. |
| openai_translator/prompt_EN2FA.txt | Persian translation prompt. |
| openai_translator/prompt_polish.txt | Polish/editing prompt. |

## Hard Rules — Never Violate
1. Never push directly to main.
2. Every PR must explain WHAT changed and WHY.
3. prompt_align.txt is frozen. Any change needs a new ADR file first.
4. align_text() output must always be validated before returning.
5. Never pass global_context to align_text(). It is a structural router, not a translator.

## How the GUI Works
- gui_translator.py launches machine-translate-docx-2.py as a subprocess.
- Each action (translate/polish/align) is a separate subprocess call.
- File handoff: the output .docx of one stage becomes the input of the next.

## Changelog Rule
After every task or PR, append to CHANGELOG.md using this format:
### [DATE] Branch: branch-name — Short Title
**What changed:** ...
**Why:** ...
**Files touched:** ...

## Architecture Decisions
See docs/adr/ folder for all decisions.
