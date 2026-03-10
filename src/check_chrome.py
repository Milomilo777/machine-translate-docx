"""
ChromeDriver availability check.
Run before launching web-based engines to give clear error messages.
/ بررسی در دسترس بودن ChromeDriver قبل از اجرای موتورهای وب
"""
import shutil
import subprocess
import sys


def check_chrome() -> bool:
    """
    Returns True if Chrome is available, False otherwise.
    Prints a clear, actionable message in both cases.
    """
    chrome_names = ["google-chrome", "chromium-browser",
                    "chromium", "chrome"]

    # Check via PATH
    for name in chrome_names:
        if shutil.which(name):
            print(f"[OK] Chrome found: {shutil.which(name)}")
            return True

    # Windows-specific check
    if sys.platform == "win32":
        win_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for path in win_paths:
            import os
            if os.path.exists(path):
                print(f"[OK] Chrome found: {path}")
                return True

    print("[ERROR] Google Chrome not found on this system.")
    print("        Web engines (chatgpt-web, perplexity-web,")
    print("        google, deepl) require Chrome to be installed.")
    print("        Download from: https://www.google.com/chrome/")
    return False


if __name__ == "__main__":
    ok = check_chrome()
    sys.exit(0 if ok else 1)
