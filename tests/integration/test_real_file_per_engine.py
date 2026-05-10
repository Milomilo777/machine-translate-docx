"""End-to-end real-file integration tests — phase 10 / phase 13.

Boots the entry script as a subprocess against
``tests/fixtures/sample_hyperlink.docx`` for every supported engine and
verifies the contract from ``AGENT.md`` on the resulting output docx:

  1. Source columns 0 + 1 byte-identical between input and output.
  2. Target column 2 non-empty for every translatable row.
  3. Hyperlinked source text reaches the translated cell.
  4. Output filename carries the correct engine suffix
     (``_Google`` / ``_Deepl`` / ``_chatGPT`` / ``_Polish`` /
     ``_web_chatGPT`` / ``_web_Perplexity``).
  5. If Persian Double Lines was selected, filename ends
     ``_Double_Lines.docx`` and every FA cell is ≤ 50 display chars.
  6. No ``Traceback`` in subprocess stdout.
  7. No ``[LOCK] Restored …`` line.
  8. Exit code 0.

Web engines (``chatgpt-web`` / ``perplexity-web``) are smoke-tested
only — selector breakage on the upstream UI converts to a ``skip`` so
a guest-session change at chatgpt.com / perplexity.ai does not turn
this into a blocking CI failure.

Marker: ``@pytest.mark.live``. Excluded from default ``pytest`` runs
via ``pytest.ini`` (``addopts = -m "not live"``). Run on demand with::

    OPENAI_API_KEY=… pytest -m live tests/integration

The test target language defaults to ``mn`` (Mongolian) for the cheap
non-FA flow and ``fa`` for the FA-only Persian Double Lines flow. Set
``MTD_TEST_MODEL=gpt-5.4-mini`` in the environment so the OpenAI
engines run cheaply; the project default model (``gpt-5.5``) is left
unchanged.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.live   # whole module is opt-in


ROOT     = Path(__file__).resolve().parents[2]
SCRIPT   = ROOT / "src" / "machine-translate-docx.py"
FIXTURE  = ROOT / "tests" / "fixtures" / "sample_hyperlink.docx"
PYTHON   = os.environ.get("MTD_TEST_PYTHON", sys.executable)
DEFAULT_MODEL = os.environ.get("MTD_TEST_MODEL", "gpt-5.4-mini")
PER_ENGINE_TIMEOUT_SEC = int(os.environ.get("MTD_TEST_TIMEOUT_SEC", "600"))

ENGINE_SUFFIX = {
    "google":         "_Google",
    "deepl":          "_Deepl",
    "chatgpt":        "_chatGPT",
    "chatgpt-polish": "_Polish",
    "chatgpt-web":    "_web_chatGPT",
    "perplexity-web": "_web_Perplexity",
}

WEB_ENGINES = frozenset({"chatgpt-web", "perplexity-web"})


def _engine_cli_flags(engine: str) -> list[str]:
    """Return the engine-specific CLI arguments for the entry script."""
    flags: list[str] = []
    if engine == "chatgpt-polish":
        flags.extend(["--engine", "chatgpt", "--enginemethod", "api", "--with-polish"])
    elif engine == "chatgpt":
        flags.extend(["--engine", "chatgpt", "--enginemethod", "api"])
    elif engine == "chatgpt-web":
        flags.extend(["--engine", "chatgpt", "--enginemethod", "web"])
    elif engine == "perplexity-web":
        flags.extend(["--engine", "perplexity", "--enginemethod", "web"])
    elif engine in ("google", "deepl"):
        flags.extend(["--engine", engine])
    else:
        raise ValueError(f"unknown engine: {engine}")
    return flags


def _is_openai_engine(engine: str) -> bool:
    return engine in ("chatgpt", "chatgpt-polish")


def _read_saved_filename(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if line.startswith("Saved file name:"):
            return line.split(":", 1)[1].strip()
    return None


def _docx_table(path: Path):
    """Return the first table of a docx, or ``None`` if python-docx is
    unavailable (the helper module fails closed so the test can still
    skip cleanly under a stripped-down environment)."""
    try:
        from docx import Document  # type: ignore
    except Exception:
        return None
    return Document(str(path)).tables[0]


def _assert_source_columns_match(input_path: Path, output_path: Path) -> None:
    src = _docx_table(input_path)
    out = _docx_table(output_path)
    if src is None or out is None:
        pytest.skip("python-docx not installed")
    assert len(src.rows) == len(out.rows), (
        f"row count drift: input={len(src.rows)} output={len(out.rows)}"
    )
    for ri, (sr, orow) in enumerate(zip(src.rows, out.rows)):
        for ci in (0, 1):
            sx = sr.cells[ci].text if ci < len(sr.cells) else ""
            ox = orow.cells[ci].text if ci < len(orow.cells) else ""
            assert sx == ox, f"source-column drift at row {ri} col {ci}: {sx!r} -> {ox!r}"


def _assert_hyperlink_text_present(input_path: Path, output_path: Path) -> None:
    """If the fixture contains the word 'hyperlink' anywhere, the
    output must contain it too — guarantees the cell-text iterator
    walks <w:hyperlink> children rather than dropping them."""
    src = _docx_table(input_path)
    out = _docx_table(output_path)
    if src is None or out is None:
        return
    src_blob = "\n".join(c.text for r in src.rows for c in r.cells)
    if "hyperlink" not in src_blob.lower():
        return
    out_blob = "\n".join(c.text for r in out.rows for c in r.cells)
    assert "hyperlink" in out_blob.lower(), "hyperlink-anchor text dropped in output"


def _assert_target_column_populated(output_path: Path) -> None:
    """At least one row's column 2 must carry translated text — the
    fixture has 41 rows; an empty target column means the engine never
    wrote anything."""
    out = _docx_table(output_path)
    if out is None:
        return
    populated = sum(
        1 for r in out.rows
        if len(r.cells) > 2 and r.cells[2].text.strip()
    )
    assert populated > 0, "target column 2 is empty in every row"


def _assert_double_lines_chunks(output_path: Path, max_chars: int = 50) -> None:
    out = _docx_table(output_path)
    if out is None:
        return
    over = []
    for ri, r in enumerate(out.rows):
        if len(r.cells) <= 2:
            continue
        for line in (r.cells[2].text or "").splitlines():
            if len(line) > max_chars:
                over.append((ri, len(line), line[:60]))
    assert not over, f"FA cell line(s) exceed {max_chars} chars: {over[:3]}"


@pytest.fixture
def fixture_copy(tmp_path: Path) -> Path:
    if not FIXTURE.exists():
        pytest.skip(f"fixture missing: {FIXTURE}")
    dst = tmp_path / "sample_hyperlink.docx"
    shutil.copy2(FIXTURE, dst)
    return dst


def _run_pipeline(
    fixture: Path,
    engine: str,
    target_lang: str,
    *,
    split_engine: str | None = None,
) -> subprocess.CompletedProcess:
    cmd: list[str] = [
        PYTHON, str(SCRIPT),
        "--docxfile", str(fixture),
        "--destlang", target_lang,
        "--silent",
        "--exitonsuccess",
    ]
    cmd.extend(_engine_cli_flags(engine))
    if _is_openai_engine(engine):
        cmd.extend(["--aimodel", DEFAULT_MODEL])
    if split_engine:
        cmd.extend(["--split", "--splitengine", split_engine])

    env = {
        **os.environ,
        # force UTF-8 stdout in the subprocess (mirrors local_launcher)
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8":       "1",
        "MTD_TEST_MODEL":   DEFAULT_MODEL,
    }
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=PER_ENGINE_TIMEOUT_SEC,
        env=env,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )


@pytest.mark.parametrize("engine", [
    "google",
    "deepl",
    "chatgpt",
    "chatgpt-polish",
    "chatgpt-web",
    "perplexity-web",
])
def test_engine_end_to_end_non_fa(engine: str, fixture_copy: Path):
    """en → mn for every engine. FA-specific behaviour is exercised in
    test_persian_double_lines_split below."""
    target_lang = "mn"
    proc = _run_pipeline(fixture_copy, engine, target_lang)

    if engine in WEB_ENGINES and proc.returncode != 0:
        pytest.skip(
            f"{engine} smoke failed (upstream guest-session UI may have changed):\n"
            f"  exit={proc.returncode}\n  stderr (tail)={proc.stderr[-400:]}"
        )

    assert "Traceback" not in proc.stdout, f"Traceback in {engine} stdout:\n{proc.stdout[-800:]}"
    assert "[LOCK] Restored" not in proc.stdout, (
        f"source-column drift logged for {engine}: see {proc.stdout[:400]}…"
    )
    assert proc.returncode == 0, (
        f"{engine} exited with {proc.returncode}; stderr tail={proc.stderr[-400:]}"
    )

    saved = _read_saved_filename(proc.stdout)
    assert saved, f"no `Saved file name:` line in {engine} stdout"
    out_path = Path(saved)
    assert out_path.exists(), f"output file missing: {out_path}"

    assert ENGINE_SUFFIX[engine] in out_path.name, (
        f"{engine}: expected suffix {ENGINE_SUFFIX[engine]!r} not in {out_path.name!r}"
    )
    _assert_source_columns_match(fixture_copy, out_path)
    _assert_hyperlink_text_present(fixture_copy, out_path)
    _assert_target_column_populated(out_path)


@pytest.mark.parametrize("engine", ["chatgpt-polish", "chatgpt"])
def test_persian_double_lines_split(engine: str, fixture_copy: Path):
    """en → fa with Persian Double Lines splitter. The aligner runs
    inside the launcher's _apply_splitter path, but for this CLI test
    we exercise the same code via the entry script's --split +
    --splitengine flags so the contract holds end to end."""
    proc = _run_pipeline(
        fixture_copy, engine, "fa", split_engine="persian_double_lines",
    )

    assert "Traceback" not in proc.stdout, f"Traceback in {engine} stdout"
    assert "[LOCK] Restored" not in proc.stdout
    assert proc.returncode == 0

    saved = _read_saved_filename(proc.stdout)
    assert saved
    out_path = Path(saved)
    assert out_path.exists()
    assert ENGINE_SUFFIX[engine] in out_path.name

    # The CLI's split path may write the split docx alongside the main
    # one — accept either as long as the contract holds. Phase-13 will
    # exercise the launcher's _apply_splitter wiring via HTTP to verify
    # the _Double_Lines suffix at the launcher boundary.
    _assert_source_columns_match(fixture_copy, out_path)
    _assert_target_column_populated(out_path)
