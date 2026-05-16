"""Stats + reporting helpers extracted from `cli.py` (Sprint D, 2026-05-16).

Owns the end-of-run reporting cluster that does not touch the docx itself:

* :func:`local_time_offset` — small pure helper returning the local timezone
  offset (hours from UTC). Used by both the run-summary printer and the
  PHP-side usage report.
* :func:`run_statistics` (added in later commits) — driver-side statistics
  collection + opt-in submission to Google Forms or the HTML usage form.
* :func:`get_robot_usage_comment` (added in later commits) — HTML report
  builder consumed by the legacy report-back endpoint.

All helpers here are fire-and-forget: a failure inside them never aborts a
translation — the launcher only cares about the docx + sidecar landing on
disk.
"""
from __future__ import annotations

import time


__all__ = [
    "local_time_offset",
]


def local_time_offset(t: float | None = None) -> int | float:
    """Return the local timezone offset from UTC in hours.

    Handles DST + the "no DST in this region" case the way the historical
    body did (the inversion in the trailing conditional). Returns ``int``
    when the offset has no fractional part, otherwise ``float``. The
    legacy callers were tolerant of either shape.
    """
    if t is None:
        t = time.time()
    localtimezone = -time.altzone / 3600
    if (localtimezone - int(localtimezone)) == 0:
        localtimezone = int(localtimezone)
    if time.localtime(t).tm_isdst == False or time.daylight != 1:
        localtimezone = -localtimezone
    return localtimezone
