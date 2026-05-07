# Playbook: Update Project Memory

---

When to update which file:

| Trigger | Update |
|---------|--------|
| Architectural decision made | `docs/decisions-2026.md` — add entry |
| New recurring bug fixed | `docs/error-catalog.md` — add entry |
| Active constraint added/changed | `PROJECT_MEMORY.md` — Active Constraints table |
| Terminology changed | `PROJECT_MEMORY.md` — Terminology table |
| Pipeline diagram changed | `docs/architecture.md` |
| New language added | `docs/architecture.md` + `PROJECT_MEMORY.md` quick links |
| Quality rule learned | `docs/translation-style.md` |
| Aligner threshold changed | `docs/subtitle-syncing.md` + `PROJECT_MEMORY.md` |

## Rules

- Keep `PROJECT_MEMORY.md` concise — summary only, link to `docs/` for depth
- Do not paste raw logs or full conversations into any memory file
- Each `PROJECT_MEMORY.md` entry: one line + date
- Each `docs/decisions-2026.md` entry: decision + alternatives + rationale
- Each `docs/error-catalog.md` entry: use the template at the bottom of the file
