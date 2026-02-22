# 🇮🇷 سیستم حرفه‌ای ترجمه خودکار فایل‌های ورد (نسخه ۱.۲.۴)

![Release v1.2.4](https://img.shields.io/badge/Release-v1.2.4-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal)
![RTL Support](https://img.shields.io/badge/RTL-Persian%20%7C%20Arabic-orange)

یک برنامه مدرن و قدرتمند تحت وب برای ترجمه فایل‌های DOCX با استفاده از مرورگر گوگل کروم بدون هد (Headless). طراحی شده برای مترجمان حرفه‌ای که با حجم بالای اسناد و سیستم‌هایی مانند **Dell Vostro 3590** کار می‌کنند.

## 🚀 ویژگی‌ها

- **معماری کامل (Full-Stack):**
  - **فرانت‌اند:** داشبورد مدرن وب با قابلیت "کشیدن و رها کردن" (Drag & Drop) و حالت تاریک.
  - **بک‌اند:** فریم‌ورک سریع FastAPI + صف‌بندی با Celery + ردیس (Redis).
  - **موتور ترجمه:** گوگل کروم هدلس با قابلیت دور زدن سیستم‌های ضدربات (undetected_chromedriver).
- **پشتیبانی از هوش مصنوعی پیشرفته:**
  - **Whisper & NLTK:** پشتیبانی از پردازش گفتار و متن با استفاده از کتابخانه‌های `whisper` و `nltk`.
  - **OpenAI:** یکپارچگی کامل با API‌های هوش مصنوعی.
- **پشتیبانی پیشرفته از زبان فارسی (RTL):**
  - ادغام کتابخانه‌های `hazm`, `parsivar`, `khoshnevis`, `python-bidi`, و `arabic-reshaper`.
  - نمایش صحیح متون ترکیبی فارسی/انگلیسی و جداول پیچیده.
  - نصب فونت‌های فارسی استاندارد (`fonts-noto-core`, `fonts-arphic-ukai`) داخل داکر.

## 🛠️ پیش‌نیازها

- **سیستم عامل:** ویندوز ۱۰/۱۱ (ترجیحاً با WSL2) یا لینوکس (Ubuntu/Debian).
- **داکر:** برنامه Docker Desktop باید نصب و در حال اجرا باشد.
- **سخت‌افزار:** بهینه شده برای پردازنده‌های ۴ هسته‌ای و رم ۸ گیگابایت به بالا.

## 📦 راهنمای سریع (داکر)

1. **دانلود مخزن کد:**
   ```bash
   git clone https://github.com/Milomilo777/machine-translate-docx.git
   cd machine-translate-docx
   ```

2. **اجرا با داکر کامپوز:**
   ```bash
   docker-compose up --build -d
   ```
   *نکته: در اولین اجرا ممکن است دانلود ایمیج ۱.۵ گیگابایتی داکر چند دقیقه طول بکشد.*

3. **دسترسی به داشبورد:**
   مرورگر خود را باز کنید و به آدرس زیر بروید: **[http://localhost:8000](http://localhost:8000)**

## 🔧 نصب دستی (حالت توسعه‌دهنده)

اگر نیاز دارید برنامه را بدون داکر اجرا کنید، مطمئن شوید پایتون ۳.۱۱+ دارید و تمام پیش‌نیازها را نصب کنید:

```bash
pip install -r requirements.txt
pip install -r requirements-server.txt
sudo apt-get install google-chrome-stable redis-server
```

**سرویس‌های مورد نیاز:**
- شروع ردیس: `redis-server`
- شروع ورکر: `celery -A server.celery_app worker --loglevel=info`
- شروع API سرور: `uvicorn server.api:app --reload`

## ❓ عیب‌یابی (Troubleshooting)

### 🔴 خطای 500 / "Internal Server Error"
- **علت:** معمولاً به دلیل نبودن کتابخانه‌هایی مثل `json5` یا `hazm` در محیط ورکر است.
- **راه حل:** ما این مشکل را در نسخه ۱.۲.۳ حل کردیم. دستور `docker-compose build --no-cache` را اجرا کنید.

### 🔴 خطای "Connection Refused" در localhost:8000
- **علت:** کانتینر داکر هنوز کامل بالا نیامده یا ردیس مشکل دارد.
- **راه حل:** لاگ‌ها را چک کنید: `docker-compose logs -f`. منتظر پیام "Application startup complete" بمانید.

### 🔴 خطای "ModuleNotFoundError: No module named 'bidi'"
- **علت:** نام اشتباه پکیج.
- **راه حل:** مطمئن شوید در `requirements.txt` نام پکیج `python-bidi` باشد، نه `bidi`.

## 📜 مجوز

MIT License.

## ⚠️ هشدار حجم بالا (نسخه ۱.۲.۵)
این نسخه شامل کتابخانه‌های سنگین **PyTorch, SciPy, Scikit-Learn** می‌باشد. حجم ایمیج داکر بیش از **۵ گیگابایت** خواهد بود.
لطفاً قبل از اجرا از داشتن حداقل ۱۰ گیگابایت فضای خالی اطمینان حاصل کنید.
