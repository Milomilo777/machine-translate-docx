"""Chrome WebDriver lifecycle helpers.

  - ``set_chrome_window_2_3_screen``  — resize + place to ~5/7 of screen
  - ``create_webdriver``              — build a fresh Chrome onto ctx
  - ``minimize_browser``              — minimize for real-engine runs
  - ``clean_up_previous_chrome_selenium_drivers`` — purge stale chromedriver bins
  - ``cleanup_selenium_chrome_temp_folders``      — purge stale temp dirs

The webdriver module (selenium vs undetected_chromedriver) is selected
at entry-script load time based on the requested engine; the resulting
module is stored on ``ctx.browser.webdriver_module`` so this file does
not have to re-do that conditional import.
"""
from __future__ import annotations

import glob
import os
import platform
import random
import re
import shutil
import sys
import time
import traceback

from selenium.webdriver.chrome.service import Service

from runtime import RuntimeContext

__all__ = [
    "set_chrome_window_2_3_screen",
    "create_webdriver",
    "minimize_browser",
    "clean_up_previous_chrome_selenium_drivers",
    "cleanup_selenium_chrome_temp_folders",
]


# ── window sizing ────────────────────────────────────────────────────────────

def set_chrome_window_2_3_screen(ctx: RuntimeContext) -> None:
    """Resize and position the Chrome window to roughly 5/7 of the screen.

    Reads/writes the window-position cache via
    ``ctx.browser.cached_window_pos`` and the active driver via
    ``ctx.browser.driver``.
    """
    drv = ctx.browser.driver
    try:
        screen_width  = drv.execute_script("return screen.availWidth;")
        screen_height = drv.execute_script("return screen.availHeight;")

        width  = min(int(screen_width  * 5 / 7), 1200)
        height = min(int(screen_height * 5 / 7), 900)

        if ctx.browser.cached_window_pos is None:
            max_x_offset = int(screen_width  / 15)
            max_y_offset = int(screen_height / 15)
            x_pos = random.randint(0, max_x_offset)
            y_pos = random.randint(0, max_y_offset)
            ctx.browser.cached_window_pos = (x_pos, y_pos)
        else:
            x_pos, y_pos = ctx.browser.cached_window_pos

        drv.set_window_size(width, height)
        drv.set_window_position(x_pos, y_pos)
    except Exception as e:
        print(f"[Warning] Could not set Chrome window size/position: {e}")
        print("[Info] Falling back to 850x750 at (0,0)")
        drv.set_window_size(850, 750)
        drv.set_window_position(0, 0)


# ── driver creation ──────────────────────────────────────────────────────────

def create_webdriver(ctx: RuntimeContext) -> None:
    """Create a fresh Chrome WebDriver and store it on ``ctx.browser.driver``.

    The driver is the single source of truth for the active Selenium
    session — every engine and helper reads it from ``ctx.browser.driver``.

    The webdriver module to use (selenium.webdriver vs
    undetected_chromedriver) lives on ``ctx.browser.webdriver_module``.
    """
    webdriver = ctx.browser.webdriver_module

    if not ctx.flags.splitonly:
        print("\nStarting translation using engine : %s" % (ctx.engine.engine.title()))

    ctx.browser.driver_path = ""

    print("Starting Chrome browser\n")
    service = Service()

    if webdriver is not None and webdriver.__name__ == "undetected_chromedriver":
        try:
            from selenium import webdriver as selenium_webdriver
            options_manager = selenium_webdriver.ChromeOptions()
            options_manager.add_argument('--headless')
            manager = selenium_webdriver.Chrome(options=options_manager)
            ctx.browser.driver_path = manager.service.path
            manager.quit()
            print(f"Using selenium chrome driver path : {ctx.browser.driver_path}")
        except Exception:
            pass

    try:
        if ctx.browser.driver_path != "":
            ctx.browser.driver = webdriver.Chrome(
                service=service,
                options=ctx.browser.chrome_options,
                driver_executable_path=ctx.browser.driver_path,
            )
        else:
            ctx.browser.driver = webdriver.Chrome(
                service=service,
                options=ctx.browser.chrome_options,
            )
    except Exception:
        var = traceback.format_exc()
        print(var)
        print("An error occured during launching chrome. This may happen during google chrome automatic updates or if Google Chrome is not installed.")
        print("You may start google chrome and open the menu Help -> About Google Chrome to see if there is an update running and retry machine translation after the update.")
        print("Exiting, please retry.")
        if not ctx.flags.exitonsuccess:
            try:
                input("Enter to close program")
            except EOFError:
                pass
        sys.exit(12)

    print("\nChrome started using driver at %s\n" % (ctx.browser.driver.service.path))

    if ctx.engine.engine == 'deepl':
        ctx.browser.driver.set_window_position(0, 100)
        set_chrome_window_2_3_screen(ctx)
    else:
        set_chrome_window_2_3_screen(ctx)

    ctx.browser.numerrors_deepl = 0


# ── minimize ─────────────────────────────────────────────────────────────────

def minimize_browser(ctx: RuntimeContext) -> None:
    """Minimize the Chrome window when running with a real engine.

    Skipped in API-only and split-only modes (no browser to minimize).
    """
    if not ctx.flags.use_api and not ctx.flags.splitonly:
        try:
            ctx.browser.driver.minimize_window()
        except Exception:
            pass


# ── stale chromedriver cleanup ───────────────────────────────────────────────

def clean_up_previous_chrome_selenium_drivers(current_driver_full_path: str) -> None:
    """Delete obsolete chromedriver binaries from the selenium cache."""
    found_previous_chrome_driver = False
    try:
        if platform.system().lower() == 'windows':
            userprofile_path = os.environ.get('USERPROFILE')
            selenium_cache_folder = f"{userprofile_path}\\.cache\\selenium"
            list_driver_path = glob.glob(
                f"{selenium_cache_folder}\\**\\chromedriver.exe", recursive=True
            )
        else:
            home_path = os.environ.get('HOME')
            selenium_cache_folder = f"{home_path}/.cache/selenium"
            list_driver_path = glob.glob(
                f"{selenium_cache_folder}/*/**/chromedriver", recursive=True
            )

        for driver_path in list_driver_path:
            if driver_path == current_driver_full_path:
                continue
            if os.path.exists(driver_path):
                try:
                    if not found_previous_chrome_driver:
                        print("\nCleaning up old chrome driver files")
                        found_previous_chrome_driver = True
                    print(f"Removing previous chrome driver at {driver_path}")
                    os.remove(driver_path)
                except Exception:
                    print(f"Unable to cleanup chrome driver at {driver_path}")

        if len(list_driver_path) >= 2:
            print(f"Keeping current chrome driver at {current_driver_full_path}")
    except Exception:
        var = traceback.format_exc()
        print(var)


# ── temp folder cleanup ──────────────────────────────────────────────────────

def cleanup_selenium_chrome_temp_folders() -> None:
    """Cleans up Selenium/Chrome temporary folders older than 1 hour.

      - Windows: Program Files + TEMP/TMP
      - Linux/macOS: /tmp
    """
    system = platform.system().lower()
    cutoff_time = time.time() - 1 * 60 * 60  # 1 hour
    print("\n[INFO] Cleaning Selenium/Chrome temp folders (older than 1 hour)")

    tmp_8char_pattern = re.compile(r'^tmp[a-zA-Z0-9_]{8}$')

    if system == 'windows':
        delete_patterns = [
            r"scoped_dir\d{3,}_\d{6,}",
            r"chrome_BITS_\d{3,}_\d{6,}",
            r"chrome_PuffinComponentUnpacker_BeginUnzipping\d{3,}_\d{7,}",
            r"chrome_url_fetcher_\d{3,}_\d{7,}",
            tmp_8char_pattern.pattern,
        ]
        paths_to_check = [r"C:\Program Files"]
        for env_var in ["TEMP", "TMP"]:
            tmp_dir = os.environ.get(env_var)
            if tmp_dir and os.path.isdir(tmp_dir):
                paths_to_check.append(tmp_dir)
        for root_path in paths_to_check:
            try:
                folders = [
                    f for f in os.listdir(root_path)
                    if os.path.isdir(os.path.join(root_path, f))
                ]
            except PermissionError:
                continue
            for folder in folders:
                folder_path = os.path.join(root_path, folder)
                if any(re.fullmatch(p, folder) for p in delete_patterns):
                    try:
                        last_mod = os.path.getmtime(folder_path)
                        if last_mod < cutoff_time:
                            print(f"[INFO] Deleting: {folder_path}")
                            shutil.rmtree(folder_path, ignore_errors=True)
                    except Exception:
                        continue
    elif system in ('linux', 'darwin'):
        tmp_path = "/tmp"
        try:
            folders = [
                f for f in os.listdir(tmp_path)
                if os.path.isdir(os.path.join(tmp_path, f))
            ]
        except PermissionError:
            folders = []
        for folder in folders:
            if folder.startswith((".org.chromium.Chromium.", ".com.google.Chrome.")) \
                    or tmp_8char_pattern.fullmatch(folder):
                folder_path = os.path.join(tmp_path, folder)
                try:
                    last_mod = os.path.getmtime(folder_path)
                    if last_mod < cutoff_time:
                        print(f"[INFO] Deleting: {folder_path}")
                        shutil.rmtree(folder_path, ignore_errors=True)
                except Exception:
                    continue
    else:
        print(f"Unsupported OS: {system}")
