# AI Instructions — machine-translate-docx

## Active Engines (5)
GOOGLE, DEEPL, CHATGPT_API, CHATGPT_WEB, PERPLEXITY_WEB

## Disabled Engines (preserve — never delete)
YANDEX, GOOGLE_API, DEEPL_API

## GUI Policy
- Python tkinter GUI (machine_translate_gui.py) = primary desktop interface
- Web UI (index.ejs + WebController) = production server interface
- BOTH must always work
- NEVER deprecate or remove Python GUI — required for desktop testing
- Repository architecture is hybrid Python + Java, not Java-only

## Immutable stdout Contracts (never change these exact strings)
  "Saved file name: "
  "==== [ FINANCIAL REPORT ] ===="

## Anti-Bot Rules (all web engines: GOOGLE, DEEPL, CHATGPT_WEB, PERPLEXITY_WEB)
  - Random delay 2-5 seconds between each request (ThreadLocalRandom)
  - Realistic User-Agent: Chrome/Windows
  - No parallel requests — always sequential
  - On HTTP 429 or 503: wait 45 seconds, retry max 3 times
  - After 3 failures: throw RuntimeException with clear message

## Persian Text Rule
  Never corrupt or remove ZWNJ character U+200C in any text processing.

## Architecture Decisions
  See docs/decisions/ for all ADRs.
  Any new architectural decision must be a new ADR file in that folder.

---

# دستورالعمل‌های هوش مصنوعی — machine-translate-docx

## موتورهای فعال (۵ موتور)
GOOGLE، DEEPL، CHATGPT_API، CHATGPT_WEB، PERPLEXITY_WEB

## موتورهای غیرفعال (نگهداری — هرگز حذف نشوند)
YANDEX، GOOGLE_API، DEEPL_API

## سیاست رابط کاربری
- Python tkinter GUI (machine_translate_gui.py) = رابط اصلی دسکتاپ
- Web UI (index.ejs + WebController) = رابط سرور تولید
- هر دو باید همیشه کار کنند
- GUI پایتون را هرگز deprecated یا حذف نکنید

## قراردادهای ثابت stdout (هرگز تغییر نکنند)
  "Saved file name: "
  "==== [ FINANCIAL REPORT ] ===="

## قوانین ضد ربات (همه موتورهای وب)
  - تأخیر تصادفی ۲ تا ۵ ثانیه بین هر درخواست (ThreadLocalRandom)
  - User-Agent واقعی Chrome/Windows
  - بدون درخواست موازی — همیشه ترتیبی
  - خطای ۴۲۹ یا ۵۰۳: صبر ۴۵ ثانیه، حداکثر ۳ بار retry
  - بعد از ۳ شکست: RuntimeException با پیام واضح

## قانون متن فارسی
  نیم‌فاصله U+200C را در هیچ پردازش متنی خراب یا حذف نکنید.

## تصمیمات معماری
  به docs/decisions/ مراجعه کنید.
  هر تصمیم جدید = یک فایل ADR جدید در همان پوشه.
