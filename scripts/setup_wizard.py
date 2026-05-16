#!/usr/bin/env python3
"""First-run setup wizard for the machine-translate-docx server.

Interactive prompts collect every secret + setting the launcher needs
and write a single `config.toml` file. Designed to run on a freshly-
provisioned Ubuntu / Debian VPS with nothing more than Python 3.11.

Usage:
    python scripts/setup_wizard.py
    python scripts/setup_wizard.py --config /opt/mtd/config.toml
    python scripts/setup_wizard.py --non-interactive --values key=val,...

Idempotent: re-running on an existing config asks whether to update
each section. The operator can skip any optional section by hitting
Enter at the prompt.

Outputs (POSIX): file mode 0600 so only the owning user can read the
API key on disk.
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Allow running from a clone without `pip install -e .`
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from machine_translate_docx.server_config import (  # noqa: E402
    default_config_path,
    generate_session_secret,
    load_config,
    write_config,
)


# ── tiny prompt helpers ──────────────────────────────────────────────────────

def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    """Read a single line from stdin, with an optional default + secret mask."""
    suffix = f" [{default}]" if default and not secret else ""
    full = f"{label}{suffix}: "
    if secret:
        answer = getpass.getpass(full).strip()
    else:
        answer = input(full).strip()
    return answer or default


def _prompt_bool(label: str, default: bool = False) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    raw = input(f"{label} {hint}: ").strip().lower()
    if not raw:
        return default
    return raw.startswith("y")


def _section(title: str) -> None:
    print()
    print(f"━━━ {title} ━━━")


def _validate_openai_key(key: str) -> tuple[bool, str]:
    if not key:
        return False, "empty"
    if not re.match(r"^sk-[A-Za-z0-9_\-]{20,}$", key):
        return False, "doesn't match the `sk-...` format"
    return True, ""


def _validate_telegram_token(token: str) -> tuple[bool, str]:
    if not token:
        return True, ""  # optional
    if not re.match(r"^\d{6,}:[A-Za-z0-9_\-]{30,}$", token):
        return False, "doesn't match the `<digits>:<chars>` format from @BotFather"
    return True, ""


def _telegram_test_message(token: str, chat_id: str) -> tuple[bool, str]:
    """Send one test message; return (ok, error_text)."""
    if not token or not chat_id:
        return False, "token or chat_id empty"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": "✅ mtd setup wizard — Telegram alert plumbing works.",
    }).encode("utf-8")
    try:
        with urllib.request.urlopen(url, data=data, timeout=10) as resp:
            if resp.status == 200:
                return True, ""
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:200]
        return False, f"HTTP {exc.code}: {body}"
    except Exception as exc:
        return False, repr(exc)


def _hash_password(password: str) -> str:
    """Return a bcrypt hash, or a salted PBKDF2 hash if bcrypt is absent.

    bcrypt is preferred. If the operator hasn't installed it on a
    fresh VPS, fall back to stdlib PBKDF2-SHA256 (1M iterations) so
    the wizard never crashes for want of a dep. The auth check in the
    launcher tries both algorithms.
    """
    try:
        import bcrypt  # type: ignore
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    except ImportError:
        import hashlib
        import secrets as _secrets
        salt = _secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, 1_000_000
        )
        return f"pbkdf2_sha256$1000000${salt.hex()}${digest.hex()}"


# ── interactive sections ─────────────────────────────────────────────────────

def section_openai(existing: dict[str, Any]) -> dict[str, str]:
    _section("OpenAI API key (REQUIRED)")
    print(
        "Get this from https://platform.openai.com/api-keys. It's the\n"
        "single biggest secret on the box; the wizard chmod 0600s the\n"
        "config file so only this user can read it."
    )
    cur = (existing.get("openai") or {}).get("api_key", "")
    if cur:
        if not _prompt_bool("Replace existing OpenAI API key?", default=False):
            return {"api_key": cur}
    while True:
        key = _prompt("OpenAI API key", secret=True)
        ok, why = _validate_openai_key(key)
        if ok:
            return {"api_key": key}
        print(f"  ✗ rejected: {why}. Try again or Ctrl+C to abort.")


def section_auth(existing: dict[str, Any]) -> dict[str, str]:
    _section("Web UI credentials (REQUIRED)")
    print(
        "These guard every route except /health and /static/*. Use a\n"
        "long passphrase; bcrypt hashing happens locally."
    )
    cur = existing.get("auth") or {}
    username = _prompt("Username", default=cur.get("username", "admin"))
    while True:
        pwd = _prompt("Password", secret=True)
        if len(pwd) < 8:
            print("  ✗ at least 8 characters required.")
            continue
        confirm = _prompt("Confirm", secret=True)
        if pwd != confirm:
            print("  ✗ passwords don't match. Retry.")
            continue
        break
    return {
        "username":       username,
        "password_hash":  _hash_password(pwd),
        "session_secret": cur.get("session_secret") or generate_session_secret(),
    }


def section_server(existing: dict[str, Any]) -> dict[str, Any]:
    _section("Server binding")
    print(
        "Default 127.0.0.1:3000 means only local connections — pair\n"
        "with Caddy / nginx for HTTPS. Use 0.0.0.0 only if you don't\n"
        "have a reverse proxy."
    )
    cur = existing.get("server") or {}
    host = _prompt("Bind host", default=str(cur.get("host", "127.0.0.1")))
    port_s = _prompt("Bind port", default=str(cur.get("port", 3000)))
    try:
        port = int(port_s)
    except ValueError:
        print(f"  ✗ '{port_s}' isn't a number; defaulting to 3000.")
        port = 3000
    max_jobs_s = _prompt(
        "Max concurrent translation jobs",
        default=str(cur.get("max_concurrent_jobs", 1)),
    )
    try:
        max_jobs = max(1, int(max_jobs_s))
    except ValueError:
        max_jobs = 1
    return {"host": host, "port": port, "max_concurrent_jobs": max_jobs}


def section_telegram(existing: dict[str, Any]) -> dict[str, Any] | None:
    _section("Telegram failure alerts (OPTIONAL)")
    print(
        "When a translation job fails, the launcher posts to Telegram.\n"
        "Get a bot token from @BotFather and the chat id from\n"
        "@userinfobot. Skip with Enter to disable."
    )
    cur = existing.get("telegram") or {}
    if not _prompt_bool(
        "Enable Telegram alerts?",
        default=bool(cur.get("token")),
    ):
        return None
    while True:
        token = _prompt("Bot token", default=str(cur.get("token", "")))
        ok, why = _validate_telegram_token(token)
        if ok:
            break
        print(f"  ✗ {why}")
    chat_id = _prompt("Chat id (comma-separated for multi)", default=str(cur.get("chat_id", "")))
    no_attachment = _prompt_bool(
        "Suppress docx attachment in alerts? (text only)",
        default=bool(cur.get("no_attachment", False)),
    )
    tz = _prompt(
        "Scheduler timezone for weekly newsletter (IANA)",
        default=str(cur.get("scheduler_tz", "Europe/Paris")),
    )
    if token and chat_id and _prompt_bool("Send a test message now?", default=True):
        ok, err = _telegram_test_message(token, chat_id)
        if ok:
            print("  ✓ test message delivered.")
        else:
            print(f"  ✗ test failed: {err}")
            if not _prompt_bool("Save these values anyway?", default=False):
                return section_telegram(existing)
    return {
        "token":           token,
        "chat_id":         chat_id,
        "no_attachment":   no_attachment,
        "scheduler_tz":    tz,
    }


def section_smtp(existing: dict[str, Any]) -> dict[str, Any] | None:
    _section("Email failure alerts (OPTIONAL)")
    print(
        "SMTP relay for plain-email failure notifications. Skip with\n"
        "Enter — Telegram alerts cover the same ground."
    )
    cur = existing.get("smtp") or {}
    if not _prompt_bool("Configure SMTP?", default=bool(cur.get("host"))):
        return None
    return {
        "host":      _prompt("SMTP host",     default=str(cur.get("host",      "localhost"))),
        "port":      int(_prompt("SMTP port", default=str(cur.get("port",      25)))),
        "user":      _prompt("SMTP user",     default=str(cur.get("user",      ""))),
        "password":  _prompt("SMTP password", default=str(cur.get("password",  "")), secret=True),
        "from_addr": _prompt("From address",  default=str(cur.get("from_addr", ""))),
    }


def section_failure_alerts(existing: dict[str, Any]) -> dict[str, str] | None:
    _section("Generic failure-alert sinks (OPTIONAL)")
    print(
        "An email RECIPIENT (delivered via SMTP from the previous\n"
        "section) and / or a Discord / Slack-shaped webhook URL.\n"
        "Skip with Enter."
    )
    cur = existing.get("failure_alerts") or {}
    if not _prompt_bool(
        "Configure failure-alert sinks?",
        default=bool(cur.get("email") or cur.get("webhook")),
    ):
        return None
    email   = _prompt("Email recipient",        default=str(cur.get("email",   "")))
    webhook = _prompt("Webhook URL",            default=str(cur.get("webhook", "")))
    if not email and not webhook:
        return None
    return {"email": email, "webhook": webhook}


# ── main flow ────────────────────────────────────────────────────────────────

def run_wizard(config_path: Path, *, force_replace: bool = False) -> Path:
    print()
    print("━" * 60)
    print(" mtd setup wizard")
    print(f" target: {config_path}")
    print("━" * 60)

    existing = load_config(config_path) if config_path.exists() and not force_replace else {}
    if existing:
        print(f"\nFound existing config at {config_path}.")
        print("Each section will offer to keep or replace its values.")

    cfg: dict[str, Any] = {}

    # Required sections
    cfg["openai"] = section_openai(existing)
    cfg["auth"]   = section_auth(existing)
    cfg["server"] = section_server(existing)

    # Optional sections — store only if the operator opted in
    tg = section_telegram(existing)
    if tg:
        cfg["telegram"] = tg
    smtp = section_smtp(existing)
    if smtp:
        cfg["smtp"] = smtp
    alerts = section_failure_alerts(existing)
    if alerts:
        cfg["failure_alerts"] = alerts

    written = write_config(cfg, config_path)

    print()
    print("━" * 60)
    print(f" ✓ wrote {written}")
    if os.name == "posix":
        print(f"   permissions: 0600 (this user only)")
    print("━" * 60)
    print()
    print("Next steps:")
    print("  · Start the server:   python local_launcher.py")
    print("  · Or via systemd:     sudo systemctl start mtd-server")
    print("  · Logs:               journalctl -u mtd-server -f")
    print()
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="mtd server setup wizard")
    ap.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"path to config.toml (default: {default_config_path()})",
    )
    ap.add_argument(
        "--force-replace",
        action="store_true",
        help="ignore existing config; start fresh",
    )
    args = ap.parse_args()
    path = args.config or default_config_path()
    try:
        run_wizard(path, force_replace=args.force_replace)
    except (KeyboardInterrupt, EOFError):
        print("\n[setup_wizard] aborted by user; nothing written.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
