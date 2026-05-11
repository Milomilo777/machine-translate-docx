# Playbook: Add a Feature

---

## Steps

1. **Understand scope**
   - Read `CLAUDE.md` and `PROJECT_MEMORY.md` first
   - Check `docs/architecture.md` for the component that owns the feature
   - Identify which files will change

2. **Inspect relevant files**
   - Read the target file(s) fully before editing
   - Check `CHANGELOG.md` for related prior changes

3. **Implement minimally**
   - Change only what is necessary
   - Respect all active constraints in `PROJECT_MEMORY.md`
   - Follow `.claude/rules/code-style.md`

4. **Check the review checklist** (`AGENTS.md`)
   - Model guard, cache guard, lang code, collision safety, two-file download, no TDZ

5. **Update docs if architectural knowledge changed**
   - `docs/decisions-2026.md` — if a design choice was made
   - `PROJECT_MEMORY.md` — if a constraint was added or changed
   - `docs/architecture.md` — if the pipeline diagram changed

6. **Commit and push**
   ```bash
   git add <specific files>
   git commit -m "Add: <short description>"
   git push origin master
   ```
