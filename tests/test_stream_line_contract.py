"""TEST-D-1 (2026-05-18 audit) — [STREAM] line-shape contract (C39 invariant).

Commit 549539f (2026-05-17) wrapped the translator + polisher Responses-
API calls with stream=True and emits `[STREAM] role=<role> chunks=<N>`
every 50 deltas. Commit bcc8b28 (2026-05-18, B3) added a
launcher-side stdout pattern matcher that nudges `job.progress` on each
tick (capped at 29 for translator, 64 for polisher so PROGRESS:30 /
PROGRESS:65 milestones still take precedence).

The two sides agree on a single line shape. A cosmetic rename
(`role: translator`, `chunks: 50`, `role=Translator`, etc.) on either
side silently breaks the UI progress bar — the launcher reader would
fall through to the normal stdout pipe and the bar would jump in
three steps instead of advancing smoothly.

These tests pin the contract at the byte level so any future
refactor that renames either side fails CI.
"""
from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def test_translator_emits_stream_line_with_exact_prefix() -> None:
    """`translator.py` must contain the exact `[STREAM] role=translator
    chunks=` substring that the launcher startswith-matches."""
    src = (_ROOT / "src" / "machine_translate_docx" / "openai_tools"
           / "translator.py").read_text(encoding="utf-8")
    assert "[STREAM] role=translator chunks=" in src, (
        "C39 broken: translator.py no longer emits "
        "'[STREAM] role=translator chunks='. The launcher progress-bar "
        "nudge logic depends on this exact prefix."
    )


def test_polisher_emits_stream_line_with_exact_prefix() -> None:
    src = (_ROOT / "src" / "machine_translate_docx" / "openai_tools"
           / "polisher.py").read_text(encoding="utf-8")
    assert "[STREAM] role=polisher chunks=" in src, (
        "C39 broken: polisher.py no longer emits "
        "'[STREAM] role=polisher chunks='."
    )


def test_launcher_consumes_both_role_prefixes() -> None:
    """`local_launcher.py` must startswith-match the exact translator
    and polisher prefixes (including the trailing space). The space
    keeps a future role token like `translator_v2` from piggybacking
    on substring matching."""
    src = (_ROOT / "local_launcher.py").read_text(encoding="utf-8")
    assert '"[STREAM] role=translator "' in src, (
        "Launcher stdout reader must startswith-match "
        "'[STREAM] role=translator ' exactly. See CODE-C-20 audit fix."
    )
    assert '"[STREAM] role=polisher "' in src, (
        "Launcher stdout reader must startswith-match "
        "'[STREAM] role=polisher ' exactly."
    )


def test_launcher_caps_match_documented_milestones() -> None:
    """The translator nudge cap (29) sits one below PROGRESS:30; the
    polisher cap (64) sits one below PROGRESS:65. Either drift means
    the stream-tick can overshoot the explicit PROGRESS marker."""
    src = (_ROOT / "local_launcher.py").read_text(encoding="utf-8")
    # translator: cap at 29 to leave PROGRESS:30 untouched
    assert "cur_p < 29" in src, "Translator stream-cap drifted from 29"
    # polisher: cap at 64 to leave PROGRESS:65 untouched
    assert "cur_p < 64" in src, "Polisher stream-cap drifted from 64"
