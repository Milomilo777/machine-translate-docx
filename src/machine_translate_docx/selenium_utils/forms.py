"""Form-field helpers for Selenium-driven engines."""
from __future__ import annotations

import traceback

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..runtime import RuntimeContext

__all__ = ["browser_fill_form_field_value"]


def browser_fill_form_field_value(
    ctx: RuntimeContext,
    field_css_id: str,
    field_value: str,
) -> None:
    """Locate a form field by CSS id and ``send_keys`` the value.

    Uses ``ctx.browser.driver``. Errors are caught + traced — callers
    treat this as a best-effort hint, not a hard guarantee.
    """
    try:
        input_field = WebDriverWait(ctx.browser.driver, 1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, field_css_id))
        )
        input_field.send_keys(field_value)
    except Exception:
        var = traceback.format_exc()
        print(var)
