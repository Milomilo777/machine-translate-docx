"""Server-side configuration loader.

Single source of truth for the server deployment. Reads a TOML file
(default `runtime_dir/config.toml`), populates the corresponding
`MTD_*` environment variables so the rest of the codebase keeps
working unchanged, and exposes a typed accessor for the launcher.

Resolution priority (highest wins):
    1. Real environment variable (set by systemd / shell / Docker)
    2. Value from config.toml
    3. Built-in default

This is intentional: an operator running `MTD_TELEGRAM_TOKEN=... mtd …`
on the command line for a one-off debug session should always beat the
config file. Conversely, on a long-running server the config file is
the single edit point and survives restarts.

Schema (config.toml):
    [openai]
    api_key = "sk-..."

    [auth]
    username      = "admin"
    password_hash = "$2b$12$..."
    session_secret = "<hex>"

    [server]
    host                 = "127.0.0.1"
    port                 = 3000
    max_concurrent_jobs  = 1

    [telegram]
    token             = ""
    chat_id           = ""
    no_attachment     = false
    scheduler_tz      = "Europe/Paris"

    [smtp]
    host      = ""
    port      = 25
    user      = ""
    password  = ""
    from_addr = ""

    [failure_alerts]
    email   = ""
    webhook = ""

The setup wizard writes this file with `chmod 0600` on POSIX systems
so only the owning user can read the API key.
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - we target 3.11+
    import tomli as tomllib  # type: ignore


CONFIG_FILENAME = "config.toml"

# Mapping: (toml_section, toml_key) → env var that the rest of the
# codebase already reads. When we load config.toml we push every
# present value into os.environ (only if the env var wasn't already
# set by the operator), so legacy code paths keep working untouched.
_ENV_MAP: dict[tuple[str, str], str] = {
    ("openai",        "api_key"):            "OPENAI_API_KEY",
    ("telegram",      "token"):              "MTD_TELEGRAM_TOKEN",
    ("telegram",      "chat_id"):            "MTD_TELEGRAM_CHAT_ID",
    ("telegram",      "no_attachment"):      "MTD_TELEGRAM_NO_ATTACHMENT",
    ("telegram",      "scheduler_tz"):       "MTD_SCHEDULER_TZ",
    ("smtp",          "host"):               "MTD_SMTP_HOST",
    ("smtp",          "port"):               "MTD_SMTP_PORT",
    ("smtp",          "user"):               "MTD_SMTP_USER",
    ("smtp",          "password"):           "MTD_SMTP_PASS",
    ("smtp",          "from_addr"):          "MTD_SMTP_FROM",
    ("failure_alerts","email"):              "MTD_FAILURE_EMAIL",
    ("failure_alerts","webhook"):            "MTD_FAILURE_WEBHOOK",
    ("server",        "max_concurrent_jobs"): "MTD_MAX_CONCURRENT_JOBS",
}


def default_config_path() -> Path:
    """Resolve where ``config.toml`` lives.

    Order:
      1. ``MTD_CONFIG_PATH`` env var (absolute or relative path)
      2. ``$MTD_RUNTIME_DIR/config.toml`` when set
      3. ``./runtime_dir/config.toml`` next to the launcher
    """
    explicit = os.environ.get("MTD_CONFIG_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    runtime_dir = os.environ.get("MTD_RUNTIME_DIR", "").strip()
    if runtime_dir:
        return Path(runtime_dir).expanduser().resolve() / CONFIG_FILENAME
    # Repo-relative default
    return Path.cwd() / "runtime_dir" / CONFIG_FILENAME


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Read and return the TOML config as a nested dict.

    Returns an empty dict if the file is missing. Raises a clear
    ``RuntimeError`` on parse failure so the launcher's startup log
    surfaces the line / column.
    """
    path = path or default_config_path()
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to parse {path}: {exc!r}. Re-run the setup wizard "
            f"(`python -m machine_translate_docx.scripts.setup_wizard`) "
            f"or fix the file manually."
        ) from exc


def apply_to_environment(cfg: dict[str, Any]) -> int:
    """Push config values into ``os.environ`` (env var wins if set).

    Returns the number of variables newly populated. Boolean values
    are converted to ``"1"``/``""`` (empty string = false-y). Integers
    are stringified.
    """
    count = 0
    for (section, key), env_name in _ENV_MAP.items():
        # Real env var already set → respect it (operator override).
        if os.environ.get(env_name, "").strip():
            continue
        section_data = cfg.get(section, {}) or {}
        if key not in section_data:
            continue
        value = section_data[key]
        if value is None:
            continue
        if isinstance(value, bool):
            env_value = "1" if value else ""
        else:
            env_value = str(value).strip()
        if not env_value:
            continue
        os.environ[env_name] = env_value
        count += 1
    return count


def get_auth(cfg: dict[str, Any]) -> dict[str, str]:
    """Return the auth subsection with defaults."""
    auth = (cfg.get("auth") or {}).copy()
    return {
        "username":       str(auth.get("username", "")).strip(),
        "password_hash":  str(auth.get("password_hash", "")).strip(),
        "session_secret": str(auth.get("session_secret", "")).strip(),
    }


def get_server(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return the server subsection with defaults."""
    server = (cfg.get("server") or {}).copy()
    return {
        "host": str(server.get("host", "127.0.0.1")).strip() or "127.0.0.1",
        "port": int(server.get("port", 3000)),
        "max_concurrent_jobs": int(server.get("max_concurrent_jobs", 1)),
    }


def write_config(cfg: dict[str, Any], path: Path | None = None) -> Path:
    """Persist the config to disk, restricting to 0600 on POSIX.

    Returns the resolved path. Caller is responsible for not passing
    secrets that shouldn't land on disk.
    """
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for section, values in cfg.items():
        if not isinstance(values, dict) or not values:
            continue
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key} = {value}")
            else:
                escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
                lines.append(f'{key} = "{escaped}"')
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # POSIX permission lock-down. Windows ignores chmod here; the
    # docs note that on Windows the file inherits the parent ACL,
    # which is usually fine for a single-user workstation.
    if os.name == "posix":
        try:
            os.chmod(path, 0o600)
        except Exception as exc:  # pragma: no cover - defensive
            print(
                f"[server_config] WARNING: chmod 0600 on {path} failed: {exc!r}",
                file=sys.stderr,
            )
    return path


def generate_session_secret() -> str:
    """Cryptographically strong hex string for cookie / token signing."""
    return secrets.token_hex(32)


def bootstrap() -> dict[str, Any]:
    """Convenience: load config + push to environment, return the dict.

    Idempotent. Safe to call multiple times. If the config file is
    missing, returns ``{}`` and prints a one-line breadcrumb.
    """
    path = default_config_path()
    cfg = load_config(path)
    if cfg:
        n = apply_to_environment(cfg)
        if n:
            print(
                f"[server_config] loaded {path} → {n} env var(s) populated."
            )
    return cfg
