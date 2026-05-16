# Security policy

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Email a description of the issue to **`smtv.bot@gmail.com`** with:
- A reproduction (input file, command, expected vs actual).
- The version / commit hash you tested against.
- Your impact assessment (DoS, data exposure, RCE, etc.).

You will receive an acknowledgement within ~5 working days. Critical
issues are fixed and disclosed on a coordinated schedule.

## What's in scope

- `local_launcher.py` — the dev HTTP server. Any way to escape the
  `web/v2/` or `uploads/` directories, RCE via crafted docx, or auth
  bypass.
- `src/machine_translate_docx/openai_tools/*` — anywhere OpenAI API keys
  could leak to stdout, log files, or HTTP responses.
- The translation pipeline — anywhere user input (filename, language
  code, docx body) ends up in a shell command without escaping.
- `.docx` parsing — zip-bomb or XXE attacks (we use python-docx; known
  CVEs in that library count).

## What's out of scope

- The legacy `index.ejs` UI is preserved as-is per project policy; we
  do **not** add new XSS surfaces to it but we also do not block on
  ones that existed pre-fork. Use the v2 SPA at `/v2/` for security-
  sensitive work.
- Vulnerabilities in third-party services (OpenAI, DeepL, Google
  Translate) — those should be reported to the upstream vendor.
- `vba_macro/*.docx` — these are user-supplied office macros, not
  software we run.
- Selenium / Chrome driver issues — those are upstream.

## Active security measures

Documented in detail in `.claude/rules/security.md` and PROJECT_MEMORY's
constraint list:

- Subprocess strips `HTTP_PROXY` / `HTTPS_PROXY` env vars before
  spawning the backend.
- Uploaded filenames are sanitised via `_sanitize_filename()` (200-char
  cap, null-byte and full-width quote handling).
- Uploaded payloads must pass the magic-bytes + zip-bomb check
  (`_validate_docx_payload`, 50 MB cap).
- Failed-job archives copy the input verbatim but only into
  `runtime_dir/failures/` which is **not** served by the launcher's
  static-file route — the path traversal guard rejects anything outside
  `web/v2/`.
- OpenAI keys are passed via `os.environ` to the subprocess only, never
  via CLI args or the JSON log.
- Telegram bot tokens are masked in launcher logs (`chat {first6}…`)
  and never echoed back in HTTP responses.
- `.env`, `*secret*`, `*apikey*`, `*password*`, and `.claude/launch.json`
  are blanket-`.gitignore`d.
