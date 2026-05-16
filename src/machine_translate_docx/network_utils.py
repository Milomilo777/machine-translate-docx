"""Network connectivity + region / mirror helpers.

Extracted from `cli.py` on 2026-05-16 as part of the 3-phase shrink
(phase 2). These helpers are stateless utilities — every dependency
(timeout values, restricted-country list, mirror URL) is passed as
an explicit argument rather than read from a module global.

Used by the entry script during startup:

* :func:`test_internet` — TCP probe against Google's public DNS,
  used as the "is the host actually online?" fallback when the
  online configuration JSON fetch fails.
* :func:`fetch_country_data` / :func:`check_mirror_url` /
  :func:`set_se_driver_mirror_url_if_needed` — region detection +
  Selenium driver mirror routing for users whose country blocks
  Google's CDN.

These functions are deliberately import-light (only `socket`, `os`,
`json`, and `requests`) so importing them at the top of the entry
script costs almost nothing.
"""
from __future__ import annotations

import json
import os
import socket
from typing import Iterable

import requests


__all__ = [
    "test_internet",
    "fetch_country_data",
    "check_mirror_url",
    "set_se_driver_mirror_url_if_needed",
]


def test_internet(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
    """Return True iff a TCP socket to ``host:port`` opens within ``timeout``.

    The default (8.8.8.8:53) targets Google Public DNS — small, globally
    routable, and not blocked by any major censorship regime. Used as the
    "is the box actually online?" fallback when our config-JSON fetch
    over HTTPS fails for a reason other than connectivity (DNS, TLS, …).
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        print(ex)
        return False


def fetch_country_data(url: str, *, http_timeout: int = 3) -> str | None:
    """GET ``url`` and return ``data["country"]`` when the response is OK.

    The endpoint convention is ``ip-api.com``-style: a JSON object with
    a ``status`` field that must equal ``"success"`` and a ``country``
    field that carries the ISO country name.
    """
    try:
        response = requests.get(url, timeout=http_timeout)
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
    """
    try:
        response = requests.get(url, timeout=http_timeout)
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
