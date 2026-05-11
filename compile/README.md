# compile/

Build artefacts and the **frozen requirements set** for the project.
The canonical metadata + direct dependencies live in
[`../pyproject.toml`](../pyproject.toml); the files here are byte-
identical reproducibility aids for production deploys.

## Files

| File | Purpose |
|---|---|
| `requirements.txt` | Full transitive pin set (Python 3.11, Linux + Windows). 53 packages at exact versions. Use this for deploy: `pip install -r compile/requirements.txt`. |
| `requirements.p311.mac.freeze.txt` | Same shape as above, but produced on macOS — some packages (mostly chromedriver wrappers) pull different transitive deps on Mac. Use this on Mac targets only. |
| `../requirements-test.txt` | The single dev/test dep (`pytest>=8.0`). Kept at repo root for muscle memory. |

## Which file should I install?

For **CI, dev, and Linux deploys**:
```bash
pip install -r compile/requirements.txt
```

For **macOS development**:
```bash
pip install -r compile/requirements.p311.mac.freeze.txt
```

For **modern tooling** (`uv`, `poetry`, `hatch`, IDE auto-resolve):
```bash
pip install -e .
# resolves from pyproject.toml's [project].dependencies with >= floors
```

The `pip install -e .` route is the fastest to iterate; the
`-r requirements.txt` route is the safest reproducible build.

## Why both?

Direct deps in `pyproject.toml` (~25 lines) carry permissive
`>=` floors so modern resolvers can pick fresh transitive versions.
The frozen `requirements.txt` (53 lines, exact pins) carries the
exact graph that the maintainers tested against — useful for
reproducing a production bug or for a clean-room rebuild months
later.

## Refreshing the freeze

```bash
# In a fresh venv:
pip install -e .
pip freeze > compile/requirements.txt
```

Strip the `-e ...` line from the top before committing.

## What's NOT here

- The Windows installer build scripts live under
  [`../src/installer/`](../src/installer/).
- The mac service template lives under
  [`../src/mac_service_template/`](../src/mac_service_template/).
- The compiled Tailwind CSS for the v2 frontend lives at
  [`../web/v2/tailwind.css`](../web/v2/tailwind.css) (regenerated
  via `npm run build:css` in `web/v2/`).
