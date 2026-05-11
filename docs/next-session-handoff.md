# Next-session handoff — 2026-05-11 end-of-day (final)

> Read this first. Then [`../CHANGELOG.md`](../CHANGELOG.md) (most
> recent first), [`../PROJECT_MEMORY.md`](../PROJECT_MEMORY.md) for
> the C1–C22 invariants, and the README hero diagram in
> [`../README.md`](../README.md) for the high-level picture.

---

## Status snapshot

```
date          2026-05-11 end-of-day
master tip    355eca2     merge: announcements + sound + weekly + legacy F-1
unit tests    113 / 113 pass
                          + 8 live-marked deselected
real-file     DeepL en→fr smoke ~27 s, 0 / 42 mismatches
                          (verified live at end of session)
branches      master only on origin (every next/* and `w` deleted
              after merge). 14 archive/* tags carry every landing.
```

---

## What the 2026-05-11 push contains

Chronological summary; full per-commit detail in
[`../CHANGELOG.md`](../CHANGELOG.md).

### Refactor + structure

  - **G1 – G3 docx_io extraction** — `docxdoc`, `use_html`,
    `get_cell_data`, `read_and_parse_docx_document` all moved into
    `docx_io/`. The package now owns every docx-shaped operation.
  - **Full `src/` layout migration** — flat `src/*.py` files +
    `src/<subpkg>/` directories moved into
    `src/machine_translate_docx/`. Every `from runtime import …`
    rewritten to absolute / relative form. CLI is now
    `python -m machine_translate_docx.cli`. `pip install -e .`
    ships a working `mtd` console script.
  - **Comprehensive audit** — `docs/audit-2026-05-11.md`. 14 fixes
    applied; 11 parked items subsequently drained
    (R-1/2/6/7/8 + F-6/8 + C-3 + H-2/5 + T-2).

### New invariants (C18 → C22)

  - C18 — model id validation against `config.VALID_AI_MODELS`.
  - C19 — empty / no-translation runs exit 20 with
    `[FAIL] reason=<token>`.
  - C20 — `runtime_dir/failures/<job_id>__<ts>/` archive +
    email / webhook / Telegram alerting (all env-gated, all
    best-effort).
  - C21 — v2 announcement surfaces driven exclusively by
    `web/v2/content.json` (slots: `pinned`, `modal`,
    `announcements`, `stories`).
  - C22 — weekly Telegram export of `subscribers.txt` (Saturday
    12:00 Europe/Paris by default; state-persisted; boot-time
    pending-warning).

### v2 frontend

  - smch.ir three-column layout (announcements | translator +
    stories | info + history). Anthropic warm palette light + dark.
    Auto-RTL on fa / ar / he / ur.
  - **Run-summary card** under results: model, elapsed, tokens,
    cache-hit %, cost (label always visible — value `—` until the
    operator flips `showCost` in Display Prefs), cache savings,
    cache expiry, rows translated, polish lines touched.
  - **Quality warnings** (toggleable): `polish_over_rewrite`,
    `output_short`, `cache_miss_unexpected`.
  - **Run history** sidebar (last 10 in localStorage) + CSV export.
  - **ETA + throughput** under progress bar.
  - **Cancel button** (POSTs to `/cancel/<id>`).
  - **Offline banner**.
  - **Display Preferences modal** with six toggles
    (`showCost`, `showCacheSavings`, `showCacheExpiry`,
    `showWarnings`, `showEta`, `playSound`).
  - **Pinned banner** — sticky top, single slot, dismissable per
    `id`.
  - **Welcome modal** — cinematic fade + spring + clay glow pulse,
    one-time per `id`, optional CTA. Honours
    `prefers-reduced-motion`.
  - **Sound notification** — Web Audio C5 → E5 chime, tab-title
    flash when document is hidden, opt-in Notifications API ping.

### Operations + alerting

  - Telegram failure alerts (text + ≤ 20 MB docx attachment),
    multi-recipient via comma-separated env var.
  - Weekly Telegram export of subscribers.txt.
  - Setup + threat model: `docs/telegram-alerts-setup.md`.
  - `/pricing` endpoint feeds the v2 pre-flight cost estimator.

### Repo first-impression

  - Real `README.md` with embedded SVG diagrams
    (`docs/diagrams/architecture-*`, `pipeline-*`,
    `failure-path-*` — 3 × 2 themes via `<picture>`).
  - `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md`.
  - `pyproject.toml` (PEP 621) with `mtd` entry-point.
  - `.github/workflows/ci.yml` (pytest on 3.11 + 3.12).
  - `.github/ISSUE_TEMPLATE/` (bug + feature + config).
  - `.github/PULL_REQUEST_TEMPLATE.md`.
  - `docs/index.md` hub for the 25 markdown files under `docs/`.
  - `docs/v2-future-ideas.md` tier-1..4 backlog.
  - `compile/README.md` clarifies pinned vs. resolved deps.
  - `scripts/` directory + legacy bat archive.
  - `CHANGES.md` renamed to `CHANGELOG.md` (stub redirect kept).
  - `pytest.ini` migrated into `[tool.pytest.ini_options]`.

### Tests

  - Baseline: **113** (was 63 at session start). +50 new tests:
    `tests/test_docx_io_cells.py` (7),
    `tests/test_post_test_hardening.py` (14),
    `tests/test_log_sidecar_pair.py` (4),
    `tests/test_fa_postprocess.py` (14),
    `tests/test_telegram_alert.py` (11).

---

## What's left for the next session

Everything the user requested is in. The remaining items are
nice-to-haves and design questions.

### Picked-from backlog ([`v2-future-ideas.md`](v2-future-ideas.md))

The next reviewer can pull the top-of-tier-1 items in any order:

  - Tab-title progress (`(45 %) SMTV Translate`)
  - Auto-detect source language from filename
  - Per-file remembered prefs (`v2.fileprefs.<basename>`)
  - Toast pattern for transient confirmations
  - Keyboard shortcuts (Esc / `?` help / Ctrl+Enter)
  - Cached-vs-fresh badge on the Run summary card

Tier-2+ items are listed with cost scores in the same doc.

### Three open operator questions (no decision needed to ship)

  1. **Telegram bot in production?** Token was leaked once in
     chat during setup and `/revoke`d. The launcher's failure
     alerter + weekly subscribers report are both ready to fire
     the moment two env vars are set
     (`MTD_TELEGRAM_TOKEN`, `MTD_TELEGRAM_CHAT_ID`).
  2. **GitHub Actions enabled?** `.github/workflows/ci.yml` ships
     but won't run until Actions is enabled on the repo settings
     page.
  3. **MIT vs. Apache-2.0?** Current `LICENSE` is MIT. Switch only
     when a patent grant is needed.

### Items intentionally NOT done

  - Full Selenium engine rewrite (R-7) — only a
    `MTD_SELENIUM_VERBOSE=1` debug-logging helper landed.
  - Legacy theme persistence (F-5 / U-6) — `index.ejs` has no
    theme toggle to persist. N/A.
  - i18n of v2 UI — deferred until non-English user feedback.
  - WebSocket-based progress — 4 s polling is cheaper on the box.

---

## How to run the test matrix (operator quick ref)

```bash
# Unit tests — fast, no network, no Chrome (default `-m "not live"`)
make test
# → 113 passed, 8 deselected (the `live` ones)

# Opt-in integration tests
make test-integration

# Everything (unit + integration)
make test-all

# DeepL en→fr smoke (real Chrome, ~30 s)
make smoke

# Live engine matrix (all four engines, all language pairs)
make live-all

# Run the v2 SPA locally
python local_launcher.py
# → http://127.0.0.1:3000/v2/
```

---

## Hand-off complete

The repo is in the best shape it's been in since the project
started. Nothing is blocked. The next session can start from any
of the backlog items in
[`docs/v2-future-ideas.md`](v2-future-ideas.md), or from one of
the three open operator questions above.

Master tip at end of session: **`355eca2`**.
This handoff doc was written on a follow-up `w` branch; merging it
bumps master to a final docs-only commit.
