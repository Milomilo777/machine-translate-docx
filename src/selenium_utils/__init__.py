"""Selenium utility helpers shared across active and inactive engines.

Public API:
  - safe_click           — robust JS-click on an element
  - browser_fill_form_field_value — locate by CSS id and ``send_keys``
  - set_chrome_window_2_3_screen — resize+place to ~5/7 of screen
  - create_webdriver     — build a fresh Chrome WebDriver onto ctx
  - minimize_browser     — minimize when running a real engine
  - clean_up_previous_chrome_selenium_drivers — purge old chromedriver bins
  - cleanup_selenium_chrome_temp_folders      — purge old temp dirs

The new active engine modules (``engines.google``, ``engines.deepl``)
import from this package. The entry script also imports back from here
to keep its remaining helpers wired.
"""
from __future__ import annotations

from .click  import safe_click
from .forms  import browser_fill_form_field_value
from .driver import (
    set_chrome_window_2_3_screen,
    create_webdriver,
    minimize_browser,
    clean_up_previous_chrome_selenium_drivers,
    cleanup_selenium_chrome_temp_folders,
)

__all__ = [
    "safe_click",
    "browser_fill_form_field_value",
    "set_chrome_window_2_3_screen",
    "create_webdriver",
    "minimize_browser",
    "clean_up_previous_chrome_selenium_drivers",
    "cleanup_selenium_chrome_temp_folders",
]
