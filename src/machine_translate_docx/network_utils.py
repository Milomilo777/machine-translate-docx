"""Network connectivity + region / mirror helpers.

Extracted from `cli.py` on 2026-05-16 as part of the 3-phase shrink
(phase 2). These helpers are stateless utilities — every dependency
(timeout values, restricted-country list, mirror URL) is passed as
an explicit argument rather than read from a module global.

Used by the entry script during startup:

* :func:`probe_internet` — TCP probe against Google's public DNS,
  used as the "is the host actually online?" fallback when the
  online configuration JSON fetch fails. The historical name
  ``test_internet`` is re-exported as a deprecated alias; pytest
  was collecting it as a test function (returned non-None) and
  emitting a warning.
* :func:`fetch_country_data` / :func:`check_mirror_url` /
  :func:`set_se_driver_mirror_url_if_needed` — region detection +
  Selenium driver mirror routing for users whose country blocks
  Google's CDN.

SSRF defence — :data:`_SAFE_HOSTNAMES` allowlists every hostname the
helpers are willing to dial. Add new hosts here as JSON config
evolves; an unknown host triggers a warning + early-return None/False
rather than a `requests.get` of attacker-supplied targets like the
cloud-metadata endpoint at 169.254.169.254. ``MTD_NETWORK_ALLOW_HOSTS``
(comma-separated env var) extends the list for operators with custom
deployments.

These functions are deliberately import-light (only `socket`, `os`,
`json`, and `requests`) so importing them at the top of the entry
script costs almost nothing.
"""
from __future__ import annotations

import json
import os
import socket
from typing import Iterable
from urllib.parse import urlparse

import requests


__all__ = [
    "probe_internet",
    "fetch_country_data",
    "check_mirror_url",
    "set_se_driver_mirror_url_if_needed",
]


# ── SSRF allowlist ───────────────────────────────────────────────────────────

_SAFE_HOSTNAMES_BASE: frozenset[str] = frozenset({
    # Region detection — public IP lookup services
    "ip-api.com",
    "ipapi.co",
    "www.contactdirectavecdieu.net",
    # Selenium WebDriver mirrors
    "chromedriver.storage.googleapis.com",
    "googlechromelabs.github.io",
    "edgedl.me.gvt1.com",
    "storage.googleapis.com",
    # Public-DNS connectivity probe (port 53; not HTTP but listed for parity)
    "8.8.8.8",
    "1.1.1.1",
})


def _allowed_hosts() -> frozenset[str]:
    """Return the active allowlist — base + ``MTD_NETWORK_ALLOW_HOSTS``."""
    extra = os.environ.get("MTD_NETWORK_ALLOW_HOSTS", "")
    if not extra:
        return _SAFE_HOSTNAMES_BASE
    parsed = {h.strip() for h in extra.split(",") if h.strip()}
    return _SAFE_HOSTNAMES_BASE | frozenset(parsed)


def _hostname_is_safe(url: str) -> bool:
    """Return True iff ``url``'s hostname is in the allowlist.

    Empty or unparseable URLs are unsafe by default — caller treats
    that as "do not dial".
    """
    try:
        host = urlparse(url).hostname
    except Exception:
        return False
    if not host:
        return False
    return host in _allowed_hosts()


# ── Public helpers ───────────────────────────────────────────────────────────


def probe_internet(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
    """Return True iff a TCP socket to ``host:port`` opens within ``timeout``.

    The default (8.8.8.8:53) targets Google Public DNS — small, globally
    routable, and not blocked by any major censorship regime. Used as the
    "is the box actually online?" fallback when our config-JSON fetch
    over HTTPS fails for a reason other than connectivity (DNS, TLS, …).
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
        return True
    except socket.error as ex:
        print(f"[network] connectivity probe failed: {ex}")
        return False


def fetch_country_data(url: str, *, http_timeout: int = 3) -> str | None:
    """GET ``url`` and return ``data["country"]`` when the response is OK.

    The endpoint convention is ``ip-api.com``-style: a JSON object with
    a ``status`` field that must equal ``"success"`` and a ``country``
    field that carries the ISO country name.

    SSRF defence: ``url``'s hostname must be in :func:`_allowed_hosts`
    (configurable via ``MTD_NETWORK_ALLOW_HOSTS``). Redirects are NOT
    followed — a redirect-chain to an internal address would otherwise
    bypass the allowlist.
    """
    if not _hostname_is_safe(url):
        print(f"[network] fetch_country_data: host not in allowlist: {url!r} (skip)")
        return None
    try:
        response = requests.get(url, timeout=http_timeout, allow_redirects=False)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            return data.get("country")
        print(f"Failed to retrieve IP information: {data.get('message')}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"HTTP request failed: {e}")
    except json.JSONDecodeError:
        print("Failed to parse the JSON response.")
    return None


def check_mirror_url(url: str, *, http_timeout: int = 3) -> bool:
    """Return True iff ``url`` responds with HTTP 200 or 400.

    Selenium's driver-cache CDN returns 400 for HEAD-on-root requests
    while still being functional, so both codes count as "alive".

    SSRF defence: see :func:`fetch_country_data`.
    """
    if not _hostname_is_safe(url):
        print(f"[network] check_mirror_url: host not in allowlist: {url!r} (skip)")
        return False
    try:
        response = requests.get(url, timeout=http_timeout, allow_redirects=False)
        return response.status_code in (200, 400)
    except requests.exceptions.RequestException as e:
        print(f"Mirror URL check failed: {e}")
        return False


def set_se_driver_mirror_url_if_needed(
    country_name: str | None,
    mirror_url: str | None,
    *,
    restricted_countries: Iterable[str],
    http_timeout: int = 3,
) -> None:
    """Set ``SE_DRIVER_MIRROR_URL`` env var when the host is in a region
    that blocks Google's CDN and the configured mirror responds.

    Only mutates ``os.environ``; never raises. Callers in the entry
    script invoke this exactly once during startup, before
    Selenium's webdriver manager fetches the chrome driver binary.
    """
    if country_name in restricted_countries:
        print(
            f"The host country ({country_name}) is restricted from "
            "downloading Google Chrome Driver, using proxy to bypass "
            "restrictions..."
        )
        if mirror_url and check_mirror_url(mirror_url, http_timeout=http_timeout):
            os.environ["SE_DRIVER_MIRROR_URL"] = mirror_url
            print(f"SE_DRIVER_MIRROR_URL set to: {os.environ['SE_DRIVER_MIRROR_URL']}")
        else:
            print(f"Mirror URL ({mirror_url}) did not respond with HTTP 200 or 400.")
    else:
        print(f"Using Google Chrome Driver from {country_name}...")
