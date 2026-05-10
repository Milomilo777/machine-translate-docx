from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import shutil
import tempfile
import threading
import time
import uuid
import webbrowser
import sys
from dataclasses import dataclass, asdict
from email.parser import BytesParser
from email.policy import default as email_policy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlparse


import re as _re

# Windows console (cp1252) crashes when print() emits ▶ ✓ ✗ — that the
# job-progress logs use. Force stdout/stderr to UTF-8 so the _process_job
# thread does not die on the first decoration. (Audit finding F-013.)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "index.ejs"
WEB_V2_DIR = ROOT / "web" / "v2"
SUBSCRIBERS_FILE = ROOT / "subscribers.txt"

# 36-hour cache for API-translated files (sha256(payload) + lang + engine
# + ai_model). Cache key + paths held in memory; payloads themselves stay on
# disk under runtime_dir/cache/<hash>/. Pruned by start_cleanup_thread().
CACHE_TTL_SEC = 36 * 60 * 60
_API_ENGINES = frozenset({"chatgpt", "chatgpt-polish"})  # only API engines cache

# ISO 639-2/B codes matching what machine-translate-docx.py produces via langcodes
_LANG_ALPHA3B = {
    'fa': 'PER', 'ar': 'ARA', 'de': 'GER', 'fr': 'FRE',
    'zh-hans': 'CHI', 'zh-hant': 'CHI', 'zh-cn': 'CHI', 'zh-tw': 'CHI',
    'ko': 'KOR', 'ja': 'JPN', 'ru': 'RUS', 'es': 'SPA',
    'it': 'ITA', 'pt': 'POR', 'nl': 'DUT', 'pl': 'POL',
    'tr': 'TUR', 'sv': 'SWE', 'no': 'NOR', 'da': 'DAN',
    'fi': 'FIN', 'he': 'HEB', 'uk': 'UKR', 'cs': 'CZE',
    'ro': 'RUM', 'hu': 'HUN', 'vi': 'VIE', 'th': 'THA',
}


def _lang_suffix(target_language: str) -> str:
    return _LANG_ALPHA3B.get(target_language.lower(), target_language.replace('-', '').upper())


def _double_lines_output_path(base_path: Path) -> Path:
    """Return the Persian Double Lines variant of a translated docx path.

    Phase 6 contract: the suffix is `_Double_Lines` and is appended after
    the engine suffix, just before `.docx`. Examples:

        sample_PER_Polish.docx  → sample_PER_Polish_Double_Lines.docx
        sample_PER_chatGPT.docx → sample_PER_chatGPT_Double_Lines.docx
    """
    stem = _re.sub(r"(?i)\.docx$", "", base_path.name)
    return base_path.with_name(f"{stem}_Double_Lines.docx")


def _engine_suffix_for(translation_engine: str | None) -> str:
    """Filename suffix appended after the lang code, per engine.

    Mirrors the table in `save_docx_file._engine_suffix(ctx)` on the
    backend side. Used by `_fallback_output_path` when the launcher
    has to guess the output filename because the subprocess never
    printed `Saved file name:`.
    """
    return {
        'google':         '_Google',
        'deepl':          '_Deepl',
        'chatgpt':        '_chatGPT',
        'chatgpt-polish': '_Polish',
        'chatgpt-web':    '_web_chatGPT',
        'perplexity-web': '_web_Perplexity',
    }.get((translation_engine or '').lower().strip(), '')


def _sanitize_filename(name: str) -> str:
    name = Path(name).name
    name = name.replace("\x00", "")
    name = name.replace("（", "(").replace("）", ")")
    name = name.replace("&", "")
    return name.strip() or "upload.docx"


# ── 36-hour cache for API-translated outputs ─────────────────────────────────

def _cache_key(payload: bytes, target_lang: str, engine: str,
               ai_model: str | None) -> str:
    """SHA-256 over payload + lang + engine + ai_model.

    Two requests collide ONLY when the uploaded bytes are byte-identical AND
    the language/engine/model triple matches. A one-byte difference in the
    docx zip (e.g. different metadata, different timestamp) yields a
    different key — by design.
    """
    h = hashlib.sha256()
    h.update(payload)
    h.update(b"\x00")
    h.update(target_lang.encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update(engine.encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update((ai_model or "").encode("utf-8", errors="replace"))
    return h.hexdigest()


# ── Newsletter subscriber list ───────────────────────────────────────────────

_RE_EMAIL = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _append_subscriber(email: str) -> tuple[bool, str]:
    """Append `email` to subscribers.txt if it validates and is new.

    Returns (ok, message). The file is line-delimited UTF-8; existing
    duplicates are silently ignored so re-submission is idempotent.
    """
    email = (email or "").strip().lower()
    if not _RE_EMAIL.match(email):
        return False, "invalid email format"
    if len(email) > 254:
        return False, "email too long"

    try:
        existing: set[str] = set()
        if SUBSCRIBERS_FILE.exists():
            with SUBSCRIBERS_FILE.open("r", encoding="utf-8") as f:
                existing = {line.strip().lower() for line in f if line.strip()}
        if email in existing:
            return True, "already subscribed"
        with SUBSCRIBERS_FILE.open("a", encoding="utf-8") as f:
            f.write(email + "\n")
        return True, "subscribed"
    except Exception as exc:
        return False, f"server error: {exc}"


# Server-side upload limits
_MAX_DOCX_UNCOMPRESSED = 50 * 1024 * 1024   # 50 MB total uncompressed entries
_DOCX_MAGIC_PK         = b"PK\x03\x04"      # ZIP local file header (DOCX is a ZIP)

# Concurrency cap on real-backend subprocesses. Each subprocess loads
# python-docx + openai client + tiktoken (≈250-500 MB). Two slots is a
# safe default for a workstation; increase via MTD_MAX_CONCURRENT_JOBS env var.
_MAX_CONCURRENT_JOBS = int(os.environ.get("MTD_MAX_CONCURRENT_JOBS", "2"))
_job_semaphore       = threading.Semaphore(_MAX_CONCURRENT_JOBS)


def _validate_docx_payload(payload: bytes) -> str | None:
    """Return None when payload is a safe DOCX, otherwise an error message.

    Two layers:
      1. Magic bytes — first four bytes must be ZIP local-file header (PK\\x03\\x04).
      2. Decompressed-size cap — sum of all entries' file_size must stay under
         _MAX_DOCX_UNCOMPRESSED. Defends against zip-bomb DOCX uploads.
    """
    if not payload or not payload.startswith(_DOCX_MAGIC_PK):
        return "File does not look like a DOCX (missing ZIP header)."

    import io
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            total = 0
            for zi in zf.infolist():
                total += zi.file_size
                if total > _MAX_DOCX_UNCOMPRESSED:
                    return (
                        f"DOCX uncompressed size exceeds the "
                        f"{_MAX_DOCX_UNCOMPRESSED // (1024 * 1024)} MB limit."
                    )
    except zipfile.BadZipFile:
        return "DOCX file is corrupted or not a valid ZIP archive."
    return None


def _load_index_html() -> str:
    return INDEX_FILE.read_text(encoding="utf-8", errors="replace")


def _inject_client_patch(html: str) -> str:
    patch = """
<script>
(function () {
  const originalFetch = window.fetch.bind(window);
  window.fetch = async function (input, init) {
    try {
      const url = typeof input === 'string' ? input : (input && input.url) ? input.url : '';
      const body = init && init.body;
      if (url.includes('/upload') && body instanceof FormData) {
        const aiModel = document.getElementById('aiModel');
        const enableSound = document.getElementById('enableSound');
        const soundSelect = document.getElementById('soundSelect');

        if (aiModel && !body.has('aiModel')) body.append('aiModel', aiModel.value);
        if (enableSound && !body.has('enableSound')) body.append('enableSound', enableSound.checked ? 'on' : 'off');
        if (soundSelect && !body.has('soundSelect')) body.append('soundSelect', soundSelect.value);
      }
    } catch (err) {
      console.warn('Local launcher patch failed:', err);
    }
    return originalFetch(input, init);
  };
})();
</script>
"""
    if "</body>" in html:
        return html.replace("</body>", patch + "\n</body>", 1)
    return html + patch


def _read_int(path: Path, default: int = 0) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return default


def _write_int(path: Path, value: int) -> None:
    path.write_text(str(int(value)), encoding="utf-8")


def _build_placeholder_docx(
    output_path: Path,
    *,
    job_id: str,
    original_name: str,
    source_file: str,
    source_language: str,
    target_language: str,
    translation_engine: str,
    split_translate: bool,
    split_engine: str | None,
    ai_model: str | None,
    enable_sound: str | None,
    sound_select: str | None,
) -> None:
    # python-docx is available in this environment, so we can generate a
    # visible DOCX instead of returning a byte-for-byte copy.
    from docx import Document

    doc = Document()
    doc.add_heading("Local Test Output", level=0)
    doc.add_paragraph(
        "This document was generated by local_launcher.py as a local UI test placeholder."
    )
    doc.add_paragraph(f"Job ID: {job_id}")
    doc.add_paragraph(f"Original upload name: {original_name}")
    doc.add_paragraph(f"Stored source file: {source_file}")
    doc.add_paragraph(f"Source language: {source_language}")
    doc.add_paragraph(f"Target language: {target_language}")
    doc.add_paragraph(f"Translation engine: {translation_engine}")
    doc.add_paragraph(f"Split translation: {'yes' if split_translate else 'no'}")
    doc.add_paragraph(f"Split engine: {split_engine or '(not sent)'}")
    doc.add_paragraph(f"AI model: {ai_model or '(not sent)'}")
    doc.add_paragraph(f"Sound enabled: {enable_sound or '(not sent)'}")
    doc.add_paragraph(f"Sound selection: {sound_select or '(not sent)'}")
    doc.add_paragraph(
        "If you want a real end-to-end translation run, the current machine still needs the missing Python dependencies used by src/machine-translate-docx.py."
    )
    doc.save(output_path)


@dataclass
class Job:
    status: str
    filename: str | None
    error: str | None
    created_at: float
    progress: int = 0             # 0-100; updated by PROGRESS:N markers from backend


class LocalState:
    def __init__(self, runtime_dir: Path, backend_mode: str, python_exe: Path, script_path: Path):
        self.runtime_dir = runtime_dir
        self.uploads_dir = runtime_dir / "uploads"
        self.logs_dir = runtime_dir / "logs"
        self.views_dir = runtime_dir / "views"
        self.ssl_dir = runtime_dir / "ssl"
        self.cache_dir = runtime_dir / "cache"
        self.count_file = runtime_dir / "count.txt"
        self.index_file = self.views_dir / "index.ejs"
        self.backend_mode = backend_mode
        self.python_exe = python_exe
        self.script_path = script_path
        self.lock = threading.Lock()
        self.jobs: dict[str, Job] = {}
        self.total_uploads = 0
        # cache_key → (timestamp, payload_dict). The dict carries:
        #   main_path:                Path  — engine output, no splitter
        #   source_path:              Path  — original upload bytes
        #   translation_array:        list[str] — for line-aware splitters
        #   phrase_separator_table:   list[str]
        #   engine, ai_model, src_lang, dest_lang: str | None
        # The cache key intentionally excludes the splitter so a re-upload
        # with a different Split Method reuses the cached translation and
        # only re-runs the splitter (phase 4 of the persian-double-lines
        # roadmap). Pre-phase-4 (timestamp, list-of-tuples) entries are
        # evicted on access.
        self.cache: dict[str, tuple[float, dict]] = {}

    def boot(self) -> None:
        for directory in [
            self.runtime_dir,
            self.uploads_dir,
            self.logs_dir,
            self.views_dir,
            self.ssl_dir,
            self.cache_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        self.index_file.write_text(_inject_client_patch(_load_index_html()), encoding="utf-8")
        _write_int(self.count_file, 0)

        # The original server expects these files to exist during startup.
        # Their contents are not used in mock mode, so placeholders are fine.
        (self.ssl_dir / "private.key").write_text("LOCAL-MOCK-KEY", encoding="utf-8")
        (self.ssl_dir / "certificate.crt").write_text("LOCAL-MOCK-CERT", encoding="utf-8")
        (self.ssl_dir / "ca_bundle.crt").write_text("LOCAL-MOCK-CA", encoding="utf-8")

    def register_job(self) -> str:
        job_id = uuid.uuid4().hex
        with self.lock:
            self.jobs[job_id] = Job(
                status="pending",
                filename=None,
                error=None,
                created_at=time.time(),
            )
            self.total_uploads += 1
        return job_id

    def update_job(self, job_id: str, **changes) -> None:
        with self.lock:
            job = self.jobs[job_id]
            self.jobs[job_id] = Job(**{**asdict(job), **changes})

    def get_job(self, job_id: str) -> Job | None:
        with self.lock:
            return self.jobs.get(job_id)

    def job_snapshot(self) -> dict[str, Job]:
        with self.lock:
            return dict(self.jobs)

    def cleanup_old_jobs(self, max_age_sec: int = 3600) -> int:
        """Remove finished jobs older than `max_age_sec`. Returns count removed."""
        now = time.time()
        removed = 0
        with self.lock:
            for jid in [
                j for j, job in self.jobs.items()
                if job.status in ("done", "error") and (now - job.created_at) > max_age_sec
            ]:
                del self.jobs[jid]
                removed += 1
        return removed

    # ── 36-hour cache ────────────────────────────────────────────────────────

    def cache_lookup(self, key: str) -> dict | None:
        """Return the cache payload dict if a fresh entry exists, else None.

        Stale entries (older than CACHE_TTL_SEC) are evicted on access, as
        are entries whose `main_path` has disappeared from disk. Pre-phase-4
        entries (the legacy (timestamp, list-of-tuples) shape) are also
        evicted on access so the next upload re-runs the engine cleanly.
        """
        with self.lock:
            entry = self.cache.get(key)
        if not entry:
            return None
        ts, data = entry
        if not isinstance(data, dict):
            self._evict(key)
            return None
        if time.time() - ts > CACHE_TTL_SEC:
            self._evict(key)
            return None
        main_path = data.get("main_path")
        if not main_path or not Path(main_path).exists():
            self._evict(key)
            return None
        return data

    def cache_store(
        self,
        key: str,
        *,
        main_path: Path,
        source_file: Path | None = None,
        translation_array: list[str] | None = None,
        phrase_separator_table: list[str] | None = None,
        engine: str | None = None,
        ai_model: str | None = None,
        src_lang: str | None = None,
        dest_lang: str | None = None,
    ) -> None:
        """Persist a cached translation under `runtime/cache/<key>/`.

        Stores the engine's main output docx and a copy of the source
        upload (so a future request with a different splitter can apply
        it without needing the original upload to still be on disk).
        Optional translation arrays are kept for line-aware splitters and
        the line-count reconciler; either may be empty in early phases.
        """
        if not main_path.exists():
            return
        try:
            entry_dir = self.cache_dir / key
            entry_dir.mkdir(parents=True, exist_ok=True)
            dst_main = entry_dir / main_path.name
            if not dst_main.exists() or dst_main.stat().st_size != main_path.stat().st_size:
                shutil.copy2(main_path, dst_main)
            dst_src: Path | None = None
            if source_file and source_file.exists():
                dst_src = entry_dir / "_source.docx"
                if not dst_src.exists() or dst_src.stat().st_size != source_file.stat().st_size:
                    shutil.copy2(source_file, dst_src)
            data: dict = {
                "main_path": dst_main,
                "source_path": dst_src,
                "translation_array": list(translation_array or []),
                "phrase_separator_table": list(phrase_separator_table or []),
                "engine": engine,
                "ai_model": ai_model,
                "src_lang": src_lang,
                "dest_lang": dest_lang,
            }
            with self.lock:
                self.cache[key] = (time.time(), data)
        except Exception as exc:
            print(f"[cache] store failed for {key[:12]}…: {exc}")

    def _evict(self, key: str) -> None:
        """Remove cache entry + its on-disk copies. Quiet on missing files."""
        with self.lock:
            entry = self.cache.pop(key, None)
        if not entry:
            return
        entry_dir = self.cache_dir / key
        try:
            if entry_dir.exists():
                shutil.rmtree(entry_dir, ignore_errors=True)
        except Exception:
            pass

    def cleanup_stale_cache(self, max_age_sec: int = CACHE_TTL_SEC) -> int:
        """Evict cache entries older than `max_age_sec`. Returns count evicted."""
        now = time.time()
        with self.lock:
            stale = [k for k, (ts, _) in self.cache.items()
                     if now - ts > max_age_sec]
        for k in stale:
            self._evict(k)
        return len(stale)

    def start_cleanup_thread(self, interval_sec: int = 600, max_age_sec: int = 3600) -> None:
        """Spawn a daemon thread that periodically prunes finished jobs and
        stale cache entries (independent TTLs)."""
        def _loop():
            while True:
                time.sleep(interval_sec)
                try:
                    n = self.cleanup_old_jobs(max_age_sec=max_age_sec)
                    if n:
                        print(f"[cleanup] pruned {n} finished job(s) older than {max_age_sec}s")
                    c = self.cleanup_stale_cache()
                    if c:
                        print(f"[cleanup] evicted {c} cache entr(ies) older than {CACHE_TTL_SEC}s")
                except Exception as exc:
                    print(f"[cleanup] error: {exc}")
        threading.Thread(target=_loop, daemon=True, name="job-cleanup").start()


def _parse_multipart(headers, body: bytes) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    content_type = headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        return {}, {}

    raw = (
        f"Content-Type: {content_type}\r\n"
        f"MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8") + body
    message = BytesParser(policy=email_policy).parsebytes(raw)

    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}

    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[name] = (filename, payload)
        else:
            charset = part.get_content_charset() or "utf-8"
            fields[name] = payload.decode(charset, errors="replace")

    return fields, files


class MockTranslatorHandler(BaseHTTPRequestHandler):
    server_version = "LocalDocxTranslator/1.0"

    @property
    def state(self) -> LocalState:
        return self.server.state  # type: ignore[attr-defined]

    @property
    def index_html(self) -> str:
        return self.server.index_html  # type: ignore[attr-defined]

    def log_message(self, fmt, *args):
        # Keep the console readable. The launcher prints its own status lines.
        print(f"[http] {self.address_string()} - {fmt % args}")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, file_path: Path, download_name: str) -> None:
        if not file_path.exists():
            self._send_text("Not found", HTTPStatus.NOT_FOUND)
            return

        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_zip_for_job(self, job_id: str) -> None:
        """[RETIRED] Multi-file ZIP packaging.

        Phase 7 of the persian-double-lines roadmap collapsed the output
        from three files (TranslatePolish + Classic + Double) to one
        single docx per job, so there is nothing left to bundle. The
        /download-zip/ route is kept to avoid 404s for any client that
        still has the URL cached, but always responds 410 GONE.
        """
        self._send_text("ZIP download is no longer active.", HTTPStatus.GONE)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, proxy-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(self.index_html.encode("utf-8"))
            return

        if path == "/count":
            self._send_json({"count": str(_read_int(self.state.count_file, 0))})
            return

        if path == "/robotscount":
            jobs = self.state.job_snapshot()
            active = sum(1 for job in jobs.values() if job.status == "pending")
            self._send_json({"count": {"all": len(jobs), "user": active}})
            return

        if path.startswith("/status/"):
            job_id = path.removeprefix("/status/")
            job = self.state.get_job(job_id)
            if not job:
                self._send_json({"ok": False, "status": "not_found"}, HTTPStatus.NOT_FOUND)
                return
            payload: dict = {
                "ok": True,
                "status": job.status,
                "filename": job.filename,
                "error": job.error,
                "progress": job.progress,
            }
            self._send_json(payload)
            return

        if path.startswith("/download/"):
            file_name = unquote(path.removeprefix("/download/"))
            self._send_file(self.state.uploads_dir / file_name, file_name)
            return

        if path.startswith("/download-zip/"):
            # ZIP download is disabled — see _send_zip_for_job() for explanation.
            job_id = unquote(path.removeprefix("/download-zip/"))
            self._send_zip_for_job(job_id)
            return

        if path == "/robots.txt":
            self._send_text("User-agent: *\nDisallow:\n")
            return

        # ── v2 frontend (Claude-inspired UI) ─────────────────────────────────
        # The legacy index.ejs continues to live at "/" untouched. v2 lives
        # alongside it under /v2 and shares the same backend endpoints.
        if path == "/v2" or path == "/v2/":
            html_file = WEB_V2_DIR / "index.html"
            if html_file.exists():
                data = html_file.read_text(encoding="utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data.encode("utf-8"))
            else:
                self._send_text("v2 frontend not deployed", HTTPStatus.NOT_FOUND)
            return

        if path.startswith("/v2/"):
            relative = path.removeprefix("/v2/").lstrip("/")
            # Reject path traversal and only serve files under web/v2/.
            if ".." in relative.split("/") or relative.startswith("/"):
                self._send_text("Not found", HTTPStatus.NOT_FOUND)
                return
            asset = (WEB_V2_DIR / relative).resolve()
            try:
                asset.relative_to(WEB_V2_DIR.resolve())
            except ValueError:
                self._send_text("Not found", HTTPStatus.NOT_FOUND)
                return
            if asset.is_file():
                ctype, _ = mimetypes.guess_type(str(asset))
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", ctype or "application/octet-stream")
                self.send_header("Content-Length", str(asset.stat().st_size))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.end_headers()
                self.wfile.write(asset.read_bytes())
                return
            self._send_text("Not found", HTTPStatus.NOT_FOUND)
            return

        self._send_text("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)

        # Newsletter subscribe endpoint — accepts JSON {"email": "..."} OR
        # multipart/form-data with field name "email". Used by the v2 UI
        # but also accessible from any client.
        if parsed.path == "/subscribe":
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            ctype = (self.headers.get("Content-Type") or "").lower()
            email = ""
            if "application/json" in ctype:
                try:
                    email = (json.loads(body or b"{}").get("email") or "").strip()
                except Exception:
                    email = ""
            elif "multipart/form-data" in ctype:
                fields, _ = _parse_multipart(self.headers, body)
                email = fields.get("email", "").strip()
            else:
                # urlencoded
                from urllib.parse import parse_qs
                qs = parse_qs(body.decode("utf-8", errors="replace"))
                email = (qs.get("email", [""])[0] or "").strip()
            ok, msg = _append_subscriber(email)
            self._send_json(
                {"ok": ok, "message": msg},
                HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST,
            )
            return

        if parsed.path != "/upload":
            self._send_text("Not found", HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        fields, files = _parse_multipart(self.headers, body)

        uploaded = files.get("file")
        if not uploaded:
            self._send_json({"ok": False, "comment": "Please upload a DOCX file."}, HTTPStatus.BAD_REQUEST)
            return

        original_name, payload = uploaded

        # Server-side validation runs *before* writing to disk.
        # Magic bytes + zip-bomb cap protect against malicious / malformed uploads
        # even when the client-side check in index.ejs is bypassed.
        validation_error = _validate_docx_payload(payload)
        if validation_error:
            self._send_json(
                {"ok": False, "comment": validation_error},
                HTTPStatus.BAD_REQUEST,
            )
            return

        safe_name = _sanitize_filename(original_name)
        saved_name = f"{int(time.time() * 1000)}-{safe_name}"
        upload_path = self.state.uploads_dir / saved_name
        upload_path.write_bytes(payload)

        job_id = self.state.register_job()

        source_language = fields.get("sourceLanguage", "Auto")
        target_language = fields.get("targetLanguage", "en")
        translation_engine = fields.get("translationEngine", "google")
        split_engine = fields.get("splitEngine")
        ai_model = fields.get("aiModel")
        enable_sound = fields.get("enableSound")
        sound_select = fields.get("soundSelect")
        split_translate = fields.get("splitTranslate", "false").lower() in {"true", "1", "on", "yes"}

        # ── 36-hour cache short-circuit ──────────────────────────────────────
        # Only API engines cache (chatgpt, chatgpt-polish). Selenium engines
        # are stateful (cookie consent, login) and not worth caching.
        cache_key: str | None = None
        if translation_engine.lower() in _API_ENGINES:
            cache_key = _cache_key(payload, target_language, translation_engine, ai_model)
            cached = self.state.cache_lookup(cache_key)
            if cached:
                # Materialise the cached engine output back into uploads/
                # and apply the requested Split Method on top. A different
                # splitter than was used last time is the whole point of
                # the phase-4 dict-shape cache.
                served = self._materialise_cached_output(
                    cached,
                    split_engine=split_engine,
                    target_language=target_language,
                )
                if served:
                    splitter_only = served.name.endswith("_Double_Lines.docx")
                    self.state.update_job(
                        job_id, status="done",
                        filename=served.name,
                        progress=100, error=None,
                    )
                    print(
                        f"[cache hit] {cache_key[:12]}… reused; "
                        f"split={split_engine or 'none'} splitter_only={splitter_only}"
                    )
                    self._send_json({
                        "ok": True, "jobId": job_id,
                        "cacheHit": True, "splitterOnly": splitter_only,
                    })
                    return

        print(f"[job {job_id}] upload={saved_name}")
        print(f"[job {job_id}] source={source_language} target={target_language} engine={translation_engine} split={split_translate}")
        print(f"[job {job_id}] splitEngine={split_engine or '(not sent)'} aiModel={ai_model or '(not sent)'} enableSound={enable_sound or '(not sent)'} soundSelect={sound_select or '(not sent)'}")

        thread = threading.Thread(
            target=self._process_job,
            args=(
                job_id,
                upload_path,
                safe_name,
                source_language,
                target_language,
                translation_engine,
                split_translate,
                split_engine,
                ai_model,
                enable_sound,
                sound_select,
                cache_key,
            ),
            daemon=True,
        )
        thread.start()

        self._send_json({"ok": True, "jobId": job_id, "cacheHit": False})

    def _process_job(
        self,
        job_id: str,
        source_file: Path,
        original_name: str,
        source_language: str,
        target_language: str,
        translation_engine: str,
        split_translate: bool,
        split_engine: str | None,
        ai_model: str | None,
        enable_sound: str | None,
        sound_select: str | None,
        cache_key: str | None = None,
    ) -> None:
        _job_t0 = time.time()
        print(f"[job {job_id}] ▶ start — file: {original_name} | lang: {target_language} | engine: {translation_engine}")
        self.state.update_job(job_id, progress=5)
        # Limit concurrent backend subprocesses to keep memory bounded.
        # When the cap is reached, a job waits here (status remains 'pending'
        # so the frontend keeps polling) until a slot frees up.
        _job_semaphore.acquire()
        self.state.update_job(job_id, progress=10)
        try:
            if self.state.backend_mode == "mock":
                time.sleep(1.2)

                stem = Path(original_name).stem
                suffix = _lang_suffix(target_language) or "OUT"
                output_name = f"{stem}_{suffix}.docx"
                output_path = self.state.uploads_dir / output_name
                _build_placeholder_docx(
                    output_path,
                    job_id=job_id,
                    original_name=original_name,
                    source_file=source_file.name,
                    source_language=source_language,
                    target_language=target_language,
                    translation_engine=translation_engine,
                    split_translate=split_translate,
                    split_engine=split_engine,
                    ai_model=ai_model,
                    enable_sound=enable_sound,
                    sound_select=sound_select,
                )

                count = _read_int(self.state.count_file, 0) + 1
                _write_int(self.state.count_file, count)

                self.state.update_job(job_id, status="done", filename=output_name, error=None)
                print(f"[job {job_id}] done -> {output_name} (placeholder DOCX)")
                return

            output_path = self._run_real_backend(
                job_id=job_id,
                source_file=source_file,
                target_language=target_language,
                translation_engine=translation_engine,
                split_translate=split_translate,
                split_engine=split_engine,
                source_language=source_language,
                ai_model=ai_model,
            )

            count = _read_int(self.state.count_file, 0) + 1
            _write_int(self.state.count_file, count)

            # Apply the requested Split Method on top of the engine's
            # raw translated output. For Persian Double Lines this runs
            # the FA mechanical aligner in-process; for any other splitter
            # (or none) the engine output is served unchanged.
            served_path = self._apply_splitter(
                output_path,
                split_engine=split_engine,
                target_language=target_language,
            )

            self.state.update_job(
                job_id,
                status="done",
                filename=served_path.name,
                error=None,
            )

            # Cache outputs for 36 hours (API engines only — `cache_key` is
            # only set for them in do_POST). The cache stores the engine's
            # *raw* translated docx (no splitter applied) so a re-upload
            # with a different Split Method can reuse it.
            if cache_key:
                self.state.cache_store(
                    cache_key,
                    main_path=output_path,
                    source_file=source_file,
                    engine=translation_engine,
                    ai_model=ai_model,
                    src_lang=source_language,
                    dest_lang=target_language,
                )

            _job_elapsed = time.time() - _job_t0
            print(f"[job {job_id}] ✓ done in {_job_elapsed:.0f}s -> {served_path.name}")
        except Exception as exc:
            _job_elapsed = time.time() - _job_t0
            self.state.update_job(job_id, status="error", filename=None, error=str(exc))
            print(f"[job {job_id}] ✗ error after {_job_elapsed:.0f}s: {exc}")
        finally:
            _job_semaphore.release()

    def _map_engine(self, translation_engine: str) -> tuple[str, list[str]]:
        engine = translation_engine.lower().strip()
        extra: list[str] = []

        if engine == "chatgpt-polish":
            engine = "chatgpt"
            extra.extend(["--enginemethod", "api", "--with-polish"])
        elif engine == "chatgpt-web":
            engine = "chatgpt"
            extra.extend(["--enginemethod", "web"])
        elif engine == "perplexity-web":
            engine = "perplexity"
            extra.extend(["--enginemethod", "web"])
        elif engine == "perplexity":
            extra.extend(["--enginemethod", "webservice"])
        elif engine == "chatgpt":
            extra.extend(["--enginemethod", "api"])

        return engine, extra

    def _run_real_backend(
        self,
        *,
        job_id: str,
        source_file: Path,
        target_language: str,
        translation_engine: str,
        split_translate: bool,
        split_engine: str | None,
        source_language: str,
        ai_model: str | None,
    ) -> Path:
        engine, extra_flags = self._map_engine(translation_engine)

        # B1-guard: fa + chatgpt-polish pipeline never uses basic split —
        # the aligner handles line distribution. Force off regardless of
        # what the frontend sent (e.g. stale localStorage checkbox state).
        if translation_engine == "chatgpt-polish" and target_language.lower().startswith("fa"):
            split_translate = False

        cmd = [
            str(self.state.python_exe),
            str(self.state.script_path),
            "--docxfile",
            str(source_file),
            "--destlang",
            target_language,
            "--silent",
            "--exitonsuccess",
            "--engine",
            engine,
        ]

        if ai_model:
            cmd.extend(["--aimodel", ai_model])
        else:
            cmd.extend(["--aimodel", "gpt-5.5"])

        if source_language and source_language.lower() != "auto":
            cmd.extend(["--srclang", source_language])
        if split_translate:
            cmd.append("--split")
        if split_engine in ("openai", "persian_double_lines"):
            cmd.extend(["--splitengine", split_engine])
        if engine == "google":
            cmd.append("--showbrowser")

        cmd.extend(extra_flags)

        print(f"[job {job_id}] running real backend via: {self.state.python_exe}")
        print(f"[job {job_id}] command: {' '.join(cmd)}")

        # bufsize=1 → line-buffered. Without this, Python pipes default to
        # full-buffering (~8 KB), so PROGRESS:N markers emitted by the
        # backend can be held back for many seconds before the launcher
        # sees them — making the UI bar jump from 10 % straight to 100 %.
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env={
                **{k: v for k, v in os.environ.items() if k.upper() not in {
                    "HTTP_PROXY",
                    "HTTPS_PROXY",
                    "ALL_PROXY",
                    "NO_PROXY",
                    "http_proxy",
                    "https_proxy",
                    "all_proxy",
                    "no_proxy",
                }},
                # Force UTF-8 stdout/stderr in the subprocess so aligner
                # print() calls containing non-ASCII chars (e.g. arrows, dashes)
                # don't crash with UnicodeEncodeError on Windows CP1252 consoles.
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            },
        )

        saved_filename: str | None = None
        if proc.stdout is not None:
            for line in proc.stdout:
                stripped = line.rstrip()
                # Parse PROGRESS:N lines into job.progress without printing
                # them as noise — they are tiny status pings, not log content.
                if stripped.startswith("PROGRESS:"):
                    try:
                        pct = int(stripped.split(":", 1)[1].strip())
                        pct = max(0, min(100, pct))
                        self.state.update_job(job_id, progress=pct)
                    except ValueError:
                        pass
                    continue
                if stripped:
                    print(f"[job {job_id}] {stripped}")
                if "Saved file name:" in stripped:
                    _, _, part = stripped.partition("Saved file name:")
                    candidate = part.strip()
                    if candidate:
                        saved_filename = candidate

        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"Backend exited with code {code}")

        output_path = Path(saved_filename) if saved_filename else self._fallback_output_path(source_file, target_language, translation_engine)
        deadline = time.time() + 120
        while time.time() < deadline:
            if output_path.exists():
                output_path = self._strip_timestamp(output_path)
                return output_path
            time.sleep(0.5)

        raise FileNotFoundError(f"Output file not found: {output_path}")

    def _strip_timestamp(self, path: Path) -> Path:
        """Rename file to remove leading timestamp prefix (e.g. 1778036666789-)."""
        clean = _re.sub(r'^\d{10,}-', '', path.name)
        if clean == path.name:
            return path
        clean_path = path.with_name(clean)
        if not clean_path.exists():
            path.rename(clean_path)
            return clean_path
        path.unlink()  # duplicate — remove timestamped copy, clean already exists
        return clean_path

    def _apply_splitter(
        self,
        base_path: Path,
        *,
        split_engine: str | None,
        target_language: str,
    ) -> Path:
        """Apply the requested Split Method to a translated docx.

        For ``persian_double_lines`` (FA target only): run the FA mechanical
        aligner in-process — no API call, no extra subprocess — and emit
        ``{stem}_Double_Lines.docx`` next to the input. For any other
        splitter or target language, return ``base_path`` unchanged.

        Falls back to the input path on any aligner error so the user
        always receives at least the engine's translated docx.
        """
        if split_engine != "persian_double_lines":
            return base_path
        if not (target_language or "").lower().startswith("fa"):
            return base_path
        try:
            out_path = _double_lines_output_path(base_path)
            if out_path.exists():
                return out_path
            src_dir = str(ROOT / "src")
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
            # Lazy import — keeps the launcher's start-up cheap and avoids
            # loading python-docx until a Persian Double Lines job arrives.
            from openai_tools.persian_double_lines import FASubtitleAligner
            aligner = FASubtitleAligner(
                model="gpt-5.4-mini",   # aligner is hardcoded mini (C1)
                llm_threshold=0,        # purely mechanical; no LLM call
                token_budget=0,
            )
            aligner.align(str(base_path), str(out_path))
            return out_path
        except Exception as exc:
            print(f"[splitter] persian_double_lines failed: {exc}")
            return base_path

    def _materialise_cached_output(
        self,
        cached: dict,
        *,
        split_engine: str | None,
        target_language: str,
    ) -> Path | None:
        """Copy the cached engine output back into uploads/, applying the
        requested splitter (Phase 4: Persian Double Lines re-runs the FA
        aligner against the cached translation in <2 s — no engine call).
        """
        main_src = cached.get("main_path")
        if not main_src:
            return None
        main_src = Path(main_src)
        if not main_src.exists():
            return None
        uploads_dir = self.state.uploads_dir
        base_dst = uploads_dir / main_src.name
        if not base_dst.exists():
            try:
                shutil.copy2(main_src, base_dst)
            except Exception as exc:
                print(f"[cache] copy-back failed: {exc}")
                return None
        return self._apply_splitter(
            base_dst,
            split_engine=split_engine,
            target_language=target_language,
        )

    def _fallback_output_path(
        self,
        source_file: Path,
        target_language: str,
        translation_engine: str | None = None,
    ) -> Path:
        suffix     = _lang_suffix(target_language) or "OUT"
        engine_tag = _engine_suffix_for(translation_engine)
        stem       = _re.sub(r'^\d{10,}-', '', source_file.stem)
        return source_file.with_name(f"{stem}_{suffix}{engine_tag}.docx")


def _find_free_port(start_port: int) -> int:
    import socket

    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free port found.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local browser-ready simulator for the DOCX translator UI.")
    parser.add_argument("--port", type=int, default=3000, help="Preferred port to use. Falls back to the next free port if busy.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--backend", choices=["real", "mock"], default="real", help="Use the real Python backend or the local placeholder mode.")
    parser.add_argument("--python-exe", default="", help="Python interpreter to use for the real backend. Defaults to the current interpreter.")
    args = parser.parse_args()

    runtime_dir = Path(tempfile.gettempdir()) / "machine_translate_docx_local"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir, ignore_errors=True)

    python_exe = Path(args.python_exe) if args.python_exe else Path(sys.executable)
    if args.backend == "real" and not python_exe.exists():
        raise FileNotFoundError(f"Python executable not found: {python_exe}")

    script_path = ROOT / "src" / "machine-translate-docx.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Backend script not found: {script_path}")

    state = LocalState(runtime_dir, args.backend, python_exe, script_path)
    state.boot()

    # Periodically prune finished jobs older than 1 h so the in-memory job
    # store does not grow unbounded across long-running sessions.
    state.start_cleanup_thread(interval_sec=600, max_age_sec=3600)

    port = _find_free_port(args.port)
    server = ThreadingHTTPServer((args.host, port), MockTranslatorHandler)
    server.state = state  # type: ignore[attr-defined]
    server.index_html = _inject_client_patch(_load_index_html())  # type: ignore[attr-defined]

    url = f"http://{args.host}:{port}/"
    print(f"Local launcher ready: {url}")
    print(f"Runtime dir: {runtime_dir}")
    print("Press Ctrl+C to stop.")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url, new=2)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
