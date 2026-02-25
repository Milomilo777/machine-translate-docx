code = r'''
import json
import datetime
import traceback

def report_crash(exception, context_text=""):
    """
    Writes a fatal error report to last_fatal_error.json for frontend telemetry.
    """
    error_report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "error_type": type(exception).__name__,
        "message": str(exception),
        "traceback": traceback.format_exc(),
        "current_text_chunk_at_crash": str(context_text)[:500], # Truncate for sanity
        "engine": globals().get("translation_engine", "Unknown")
    }

    try:
        with open("last_fatal_error.json", "w", encoding="utf-8") as f:
            json.dump(error_report, f, indent=4, ensure_ascii=False)
        print("\n[CRITICAL] Fatal error logged to last_fatal_error.json")
    except Exception as e:
        print(f"\n[CRITICAL] Failed to write error report: {e}")

    # Aggressive RAM Rescue
    try:
        cleanup_selenium_chrome_temp_folders()
        if 'driver' in globals() and driver:
            driver.quit()
    except:
        pass
'''

with open('src/machine-translate-docx.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Insert after imports (e.g., after 'from bidi.algorithm import get_display')
# Or closer to top.
# Let's verify where imports end.
# I'll insert it after  or similar.
target = 'import platform'
if target in content:
    content = content.replace(target, target + '\n' + code)
else:
    # Fallback
    content = code + '\n' + content

with open('src/machine-translate-docx.py', 'w', encoding='utf-8') as f:
    f.write(content)
