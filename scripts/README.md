# scripts/

Helper scripts that don't fit at the project root. Each one is
documented inline; only entries listed here are guaranteed-supported.

## Supported

(Currently nothing — the supported runners live at the project root.
This directory exists for future scripts that don't belong on the
top level.)

## Legacy

Files under `scripts/legacy/` are kept for historical reference. They
**may or may not work** — they were valuable developer scratch tools
at some point but have not been maintained.

| File | Origin | Status |
|---|---|---|
| `legacy/run-developer-scratch.bat` | the original `run.bat` at the project root, moved 2026-05-11 | hundreds of stale `SET DOCXFILE=…` lines; only the last line ran. Kept for reference only — use `tasks.bat smoke` or the v2 frontend instead. |

## Where the supported runners live

| You want to … | Run |
|---|---|
| Open the dev server (v2 UI) | `run_local_launcher_v2.bat` *(project root)* |
| Run unit tests | `tasks.bat test` (Windows) or `make test` (Unix) |
| Run the DeepL smoke test | `tasks.bat smoke` or `make smoke` |
| Run a live engine pass | `tasks.bat live-deepl` / `live-google` / `live-all` |
| Build the Windows installer | `compile.bat` *(project root)* |
