# Playbook: Fix a Bug

---

## Steps

1. **Identify failing behavior**
   - Check `docs/error-catalog.md` — is this a known recurring issue?
   - Reproduce the bug with minimal input

2. **Find root cause**
   - Inspect relevant files and logs
   - Write root cause in **one sentence** before coding anything

3. **Implement fix**
   - Minimal change — fix the root cause, not symptoms
   - Do not refactor unrelated code in the same commit

4. **Add to error catalog**
   - Open `docs/error-catalog.md`
   - Add entry using the template at the bottom of that file
   - If the bug was already listed, update its status to `Fixed {date}`

5. **Update PROJECT_MEMORY.md** if the fix reveals a reusable learning

6. **Commit and push**
   ```bash
   git add <specific files>
   git commit -m "Fix: <root cause in one sentence>"
   git push origin master
   ```
