"""JS-click helper.

``safe_click`` issues a JavaScript click which avoids overlay /
intercepted-click issues common in modern web translators. The driver
is taken as an explicit argument rather than read from ctx — every
call site already has a driver in hand.
"""
from __future__ import annotations

from selenium.common.exceptions import WebDriverException

__all__ = ["safe_click"]


def safe_click(driver, element) -> None:
    """JavaScript-click ``element`` via ``driver``. Swallows WebDriverException.

    Falls back silently if the click fails — every caller is wrapped in
    its own retry/timeout machinery, so a propagated exception here would
    just confuse the upper layers.
    """
    try:
        driver.execute_script("arguments[0].click();", element)
    except WebDriverException:
        # The original code printed an undefined ``e`` here — ignore.
        pass
