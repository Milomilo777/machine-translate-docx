# Security Rules

---

## What must never be committed

- `.env` files of any name
- `src/configuration/configuration.json` if it contains real credentials
- API keys (`OPENAI_API_KEY`, `DEEPL_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`)
- Database passwords or connection strings
- Any file matching `*secret*`, `*apikey*`, `*password*`

These patterns are covered by `.gitignore`. Double-check `git status` before committing.

## API Key handling

- Keys come exclusively from environment variables
- `local_launcher.py` passes them via `os.environ` to the subprocess — never via CLI args
- No key material in log output

## Subprocess security

- `local_launcher.py` strips proxy environment variables (`HTTP_PROXY`, etc.) before
  spawning the backend subprocess — do not remove this behavior

## Input validation

- Uploaded file name is sanitized via `_sanitize_filename()` before saving
- File extension checked — only `.docx` accepted
- Content-Length header read to limit body size
