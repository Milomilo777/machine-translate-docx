"""Regression test for the _get_ctx() snapshot-ordering bug fixed in commit 4c36183.

Bug summary
-----------
``oai_translator``, ``oai_polisher``, and ``translation_log`` were declared in
``cli.py`` *after* the first runtime ``_get_ctx()`` call at line ~1078.  The
lazy snapshot inside ``_get_ctx()`` tries to read those names from module scope
and silently catches ``NameError`` when they are absent, so
``ctx.openai.translation_log`` ended up pointing at the dataclass empty-dict
default instead of the module-level ``translation_log`` dict.  The divergence
was masked in production by ``_sync_globals_from_ctx``, but any code path that
called ``_get_ctx()`` before ``main()`` (or inspected the snapshot directly)
would see a stale ``{}`` instead of the live seed dict.

The fix moved the three declarations *above* the ``_get_ctx()`` call.  This
test guards against that ordering being accidentally reversed in a future edit.

Import strategy
---------------
``cli.py`` runs argparse, file-existence checks, and a docx open at module
level — it cannot be imported in a neutral state.  We therefore set ``sys.argv``
to a minimal valid invocation (``--splitonly`` with the existing fixture docx)
*before* import so the module-level code completes without prompting or exiting.

Because pytest reuses the same process across the test session, a second import
of ``machine_translate_docx.cli`` is a no-op (Python caches modules in
``sys.modules``).  If another test has already imported it, we reuse that
cached module — the invariant we check is idempotent: once the fix is in place,
``cli.translation_log is cli._get_ctx().openai.translation_log`` must be True
regardless of whether the snapshot was built now or earlier in the session.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Absolute path to the fixture so the module-level os.path.exists() check
# passes regardless of the current working directory when pytest is invoked.
_FIXTURE_DOCX = str(Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sample_hyperlink.docx")


def _import_cli():
    """Import machine_translate_docx.cli with a safe sys.argv.

    Sets sys.argv before the import so argparse does not exit.

    Handles two test-isolation pitfalls:

    1. If a previous test in the session (e.g. test_docx_io_parse.py)
       installed a STUB module under the same name to avoid the heavy
       cli.py top-level — the stub will be missing ``_get_ctx`` and the
       module-level globals we want to inspect. We detect this by
       checking for ``_get_ctx`` on the cached module; if it's missing,
       evict the stub and import the real module.
    2. If the real module is already imported (cached), reuse it —
       Python guarantees a single module instance per process, so the
       identity invariant remains valid.
    """
    cached = sys.modules.get("machine_translate_docx.cli")
    if cached is not None and hasattr(cached, "_get_ctx"):
        return cached
    if cached is not None:
        # A stub is sitting in our slot. Evict it so the real import runs.
        del sys.modules["machine_translate_docx.cli"]

    _original_argv = sys.argv[:]
    sys.argv = [
        "cli",
        "--docxfile", _FIXTURE_DOCX,
        "--destlang", "fa",
        "--engine", "chatgpt",
        "--enginemethod", "api",
        "--aimodel", "gpt-5.4-mini",
        "--silent",
        "--splitonly",
    ]
    try:
        import machine_translate_docx.cli as cli
        return cli
    finally:
        sys.argv = _original_argv


def test_translation_log_identity_after_import():
    """After importing cli, ctx.openai.translation_log must be the same object
    as the module-level cli.translation_log global.

    The fix (commit 4c36183) moved the module-level declarations of
    ``oai_translator``, ``oai_polisher``, and ``translation_log`` above the
    first ``_get_ctx()`` call so the lazy snapshot picks them up on first
    invocation.  A regression that re-ordered them would silently desync the
    two references — the module-level dict would diverge from the one stored
    on ctx, and any mutation of ctx.openai.translation_log would not be
    reflected in cli.translation_log (or vice versa).
    """
    cli = _import_cli()
    ctx = cli._get_ctx()

    assert cli.translation_log is ctx.openai.translation_log, (
        "Snapshot-ordering regression: ctx.openai.translation_log "
        "diverged from cli.translation_log. "
        "Likely cause: module-level `translation_log = ...` was moved "
        "back below the first `_get_ctx()` call. See commit 4c36183."
    )


def test_oai_translator_identity_after_import():
    """ctx.openai.translator must be the same object as cli.oai_translator.

    Part of the same snapshot-ordering fix as translation_log.  When the
    name was not yet bound at snapshot time, the try/except NameError block
    silently left ctx.openai.translator as the dataclass default (None from
    RuntimeContext.empty()), which happened to match — but for the wrong
    reason: the fix ensures they are the same *binding*, not just the same
    value.
    """
    cli = _import_cli()
    ctx = cli._get_ctx()

    assert ctx.openai.translator == cli.oai_translator, (
        "ctx.openai.translator diverged from cli.oai_translator. "
        "See commit 4c36183 for context."
    )


def test_oai_polisher_identity_after_import():
    """ctx.openai.polisher must be the same object as cli.oai_polisher.

    Symmetric to test_oai_translator_identity_after_import.
    """
    cli = _import_cli()
    ctx = cli._get_ctx()

    assert ctx.openai.polisher == cli.oai_polisher, (
        "ctx.openai.polisher diverged from cli.oai_polisher. "
        "See commit 4c36183 for context."
    )
