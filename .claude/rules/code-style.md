# Code Style Rules

Applies to all Python and JavaScript files in this project.

---

## Python

- Python 3.11+ — use `str | None` union syntax, `match/case` where appropriate
- Type hints on all public function signatures
- `snake_case` for variables and functions; `PascalCase` for classes
- Private helpers prefixed with `_` (e.g. `_normalize_lang`, `_strip_timestamp`)
- Constants: `UPPER_SNAKE_CASE`
- No bare `except:` — always catch specific exceptions or at minimum `Exception`
- f-strings preferred over `.format()` or `%`
- Every new API call must include `extra_body={"prompt_cache_retention": "24h"}`
- Imports: stdlib → third-party → local, separated by blank lines

## JavaScript (index.ejs)

- `const` for values that don't change; `let` for mutable bindings; never `var`
- No `const`/`let` referenced before their declaration (TDZ — temporal dead zone)
- When a function needs a DOM element, use `document.getElementById()` locally
  inside the function — do not capture outer-scope `const` in functions that run
  before the declaration is reached
- Async/await preferred over `.then()` chains
- DOM manipulation: create element → configure → appendChild → use → removeChild

## General

- Comments explain *why*, not *what* (the code shows what)
- No commented-out dead code left in production files
- File encoding: UTF-8 with LF line endings (`.gitattributes` enforces on checkout)
