# CHANGES — machine-translate-docx

> این فایل چکیده تمام تغییرات مهم پروژه است.
> برای شروع سریع سشن بعدی، **فقط همین فایل را بخوانید** — نیازی به خواندن کد از ابتدا نیست.

---

## معماری کلی پروژه

```
src/
  machine-translate-docx.py   ← نقطه ورود اصلی (CLI)
  openai_tools/
    translator.py             ← کلاس OpenAITranslator
    polisher.py               ← کلاس OpenAIPolisher (پاس ویرایش فارسی)
    aligner_per.py            ← کلاس FASubtitleAligner (توزیع مجدد دوبل فارسی)
prompts/
  translate_PER.txt           ← پرامپت ترجمه فارسی (بسیار تفصیلی) [قبلاً translate_fa.txt]
  translate_universal.txt     ← پرامپت ترجمه عمومی (fallback)
  polish_PER.txt              ← پرامپت ویرایش فارسی [قبلاً polish_fa.txt]
server.js.txt                 ← سرور Express (فایل اصلی — نام .txt دارد)
index.ejs                     ← فرانت‌اند EJS
local_launcher.py             ← سرور محلی Python (بدون Node.js) برای تست UI
CHANGES.md                    ← همین فایل — منبع اصلی برای سشن بعدی
```

### نام‌گذاری فایل خروجی (وضعیت فعلی)

```
ورودی:   filename.docx
خروجی ترجمه+پولیش:      filename_PER_TranslatePolish.docx   → filename  (job)
خروجی تقسیم کلاسیک:     filename_PER_Classic.docx           → filename3 (job)
خروجی الاینر دوبل:      filename_PER_Double.docx            → filename2 (job)
لاگ JSON:                filename_PER_TranslatePolish_log.json
```

**دانلود:** Classic بلافاصله، Double بعد از ۱۸۰۰ms — بدون ZIP، بدون multi-download prompt.
**AIAlign حذف شد** — سه فایل به دو فایل کاهش یافت.

---

## تغییرات — از ابتدا تا آخر

---

### سشن ۲۰۲۶-۰۵-۰۸ (بخش دوم) — refactor + bugfix

#### S1. دو فایل خروجی به‌جای چهار فایل

AIAlign حذف شد. دانلود از ZIP به sequential 1800ms تغییر کرد تا Chrome
multi-download prompt ظاهر نشود. ZIP endpoint با توضیح انگلیسی غیرفعال شد
(کد باقی ماند برای مرجع). تغییرات:

- `local_launcher.py` — `filename4` و `_find_ai_align_file()` حذف شدند
- `index.ejs` — ZIP endpoint کامنت شد؛ دانلود: Classic بلافاصله، Double بعد از 1800ms
- `src/machine-translate-docx.py` — Pass 3 (AIAlign) حذف شد

---

#### S2. فیکس B1 — `split=True` اشتباه برای fa+chatgpt-polish

**مشکل:** `engineChecker()` بعد از restore از localStorage صدا نمی‌شد → checkbox
`splitTranslate` چک می‌ماند → backend با `split_translate=True` اجرا می‌شد با
اینکه aligner توزیع را انجام می‌دهد.

**فیکس دو لایه:**

```python
# local_launcher.py — B1-guard
if translation_engine == "chatgpt-polish" and target_language.lower().startswith("fa"):
    split_translate = False
```

```javascript
// index.ejs — loadLanguagePrefs()
engineChecker();  // ← بعد از restore engine
```

---

#### S3. نوار پیشرفت برای Google/DeepL

`machine-translate-docx.py` — در block loop، بعد از هر بلوک:

```python
_blk_pct = int(((i + 1) / _n_blks) * 100)
for _m in (25, 50, 75):
    if _blk_pct >= _m and _m not in _progress_blk_emitted:
        print(f"PROGRESS:{_m}", flush=True)
        _progress_blk_emitted.add(_m)
```

label‌های `_progressLabel()` engine-agnostic شدند.

---

#### S4. بازنویسی کامل `aligner_per.py` — Mechanical v2.0

فایل از ۱۵۶۵ خط به ~۳۸۰ خط کاهش یافت. پایه: `fa_aligner.py` از اسکیل v7.5.

**چه چیزی ماند:** `_display_len`، RTL markers، protected bigrams، shaded cell، cross-group sentinel

**چه چیزی حذف شد:** B4 weight tables، discourse-marker alignment، LLM integration stubs، quality scoring

**ساختار جدید — توابع module-level:**
- `_find_break(text, target, bad_bigrams)` — 3 priority: ،/؛ → space+safe → space
- `_split_for_n_rows(text, n_rows)` — کمترین chunk اول → doubles را maximize می‌کند
- `_distribute_to_rows(chunks, n_rows)` — proportional، cap 2 per chunk
- `_enforce_no_triple(rows)` — logical[] parallel برای suppress slots

**فیکس مهم در `_parse_groups`:** ردیف‌های FA خالی بعد از جمله را به همان گروه اضافه می‌کند.
این برای خروجی single-call که FA فقط در سطر اول است ضروری بود.

---

#### S5. بازنویسی `_simple_split_docx` — Classic بدون insert/double

**مشکل قدیمی:** با `deepcopy(_row._tr)` ردیف جدید INSERT می‌کرد → EN و شماره
ردیف هم دوبل می‌شدند (خط قرمز).

**پیاده‌سازی جدید:**
- از `_parse_groups()` الاینر برای گروه‌بندی استفاده می‌کند
- `_split_for_n_rows(text, n_rows)` → حداکثر n_rows تکه
- هر ردیف یک تکه، ردیف‌های باقیمانده `''` — **هرگز تکرار نمی‌شود**
- فقط `_set_fa_cell()` صدا می‌شود → فقط cells[2] تغییر می‌کند

---

#### S6. فیکس prompt caching — Responses API برای gpt-5.x

**مشکل:** `gpt-5.5` در شرط `if "pro" in self.model` match نمی‌کرد → از
`chat.completions.create` استفاده می‌کرد که caching برای گروه GPT-5 broken است
(باگ شناخته‌شده OpenAI).

**فیکس:**
```python
_use_responses_api = (
    "pro" in self.model.lower()
    or self.model.lower().startswith("gpt-5")
)
```

**نرمال‌سازی response JSON:** Responses API از `input_tokens`/`input_tokens_details`
استفاده می‌کند؛ بعد از `model_dump()` به `prompt_tokens`/`prompt_tokens_details`
نرمال می‌شود تا کد cost calc دست‌نخورده بماند.

**استخراج متن:**
```python
if _use_responses_api and hasattr(response, "output_text"):
    text = response.output_text.strip()
else:
    text = response.choices[0].message.content.strip()
```

تغییرات در `translator.py` و `polisher.py`.

---

#### S7. localStorage — فقط زبان ذخیره شود

**قبل:** زبان + موتور + مدل AI ذخیره می‌شدند → بار بعدی موتور سطح‌پایین
برای همیشه می‌ماند.

**بعد:** فقط زبان ذخیره می‌شود. موتور همیشه default زبان را می‌گیرد.

```javascript
const saveLanguagePrefs = () => {
    _lsSet('savedSourceLang', sourceSelector.value);
    _lsSet('savedTargetLang',  targetSelector.value);
    _lsDel('savedEngine');   // کلیدهای قدیمی پاک می‌شوند
    _lsDel('savedAiModel');
};
```

Helper‌های `_lsSet/_lsGet/_lsDel` با try/catch — silent no-op در private mode.

---

#### S8. فیکس engine lock — guard همه `.selected` پشت `setDefault`

**مشکل:** `deeplOption.selected = true` و `googleOption.selected = true`
در `engineChecker()` بدون guard بودند → هر بار کاربر موتور عوض می‌کرد،
`engineChecker(false)` اجرا و موتور را برمی‌گرداند.

**فیکس:** همه default selection ها در یک block `if (setDefault)` جمع شدند:
```javascript
if (setDefault && engineSel) {
  if (targetLanguage === 'fa' && ...) engineSel.value = 'chatgpt-polish';
  else if (deeplOption && !deeplOption.disabled) engineSel.value = 'deepl';
  else engineSel.value = 'google';
}
```

---

#### S9. قیمت‌گذاری رسمی gpt-5.5 (آوریل ۲۰۲۶)

```
Input:        $5.00 / 1M tokens
Cached Input: $0.50 / 1M tokens
Output:       $30.00 / 1M tokens
```

محاسبه هزینه در هر دو `translator.py` و `polisher.py` اصلاح شد تا توکن‌های کش‌شده
با نرخ cached price محاسبه شوند:

```python
input_cost = (non_cached_tokens / 1M) * price["input"]
           + (cached_tokens     / 1M) * price["cached"]
```

---

#### S10. ابزار تست مستقل الاینر

**فایل جدید:** `tests/test_aligner_only.py`

```bash
python tests/test_aligner_only.py FILE_PER_TranslatePolish.docx [--verbose]
```

خروجی: `FILE_PER_TranslatePolish_Double_TEST.docx`
Exit 0: بدون triple یا over-48. Exit 1: مشکل یافت شد (فایل باز هم ذخیره می‌شود).

---

### ۰-ح. server.js و package.json [2026-05-09]

**یافته:** فایل `server.js.txt` در ریشه پروژه دیگر وجود ندارد — قبلاً به
`server.js` (با پسوند صحیح) تغییر نام یافته بوده. CLAUDE.md درست است.
ارجاعات تاریخی در CHANGES.md (بخش‌های قدیمی) همچنان نام `server.js.txt`
را دارند که برای آن مقطع زمانی صحیح است؛ تغییری روی تاریخ نمی‌دهیم.

**اقدام:** فایل `package.json` که تا الان غایب بود اضافه شد. `server.js`
این پکیج‌های npm را require می‌کند:
- express ^4.19
- multer ^1.4
- cross-spawn ^7.0
- body-parser ^1.20
- cron ^3.1
- iconv-lite ^0.6
- ps-list ^8.1

با `package.json` می‌توان `npm install && npm start` اجرا کرد و سرور
production را برپا کرد. قبلاً نصب وابستگی‌ها دستی بود و reproducible
نبود. `engines.node = ">=18"` ست شد.

local_launcher.py (Python alternative) مستقل از این است و بدون Node
کار می‌کند.

---

### ۰-ز. تحقیق آنلاین + پیاده‌سازی [2026-05-09]

#### Persian normalizer — fa_postprocess.py
**فایل جدید:** `src/openai_tools/fa_postprocess.py`

`hazm.Normalizer` با تنظیمات پیش‌فرض W3 TECH_LOCK پروژه را می‌شکست
(`GPT-4o` → `GPT- ۴ o`) و quote `"..."` را به `«...»` تبدیل می‌کرد
(نقض HL-11). به‌جای آن، یک normalizer سفارشی ≤۵۰ خط که فقط زیرمجموعه
ایمن انجام می‌دهد:
- `ي` (U+064A) → `ی` (U+06CC)
- `ك` (U+0643) → `ک` (U+06A9)
- ارقام `٠-٩` (U+0660+) → `۰-۹` (U+06F0+)

ASCII، quote، ZWNJ، harakat، spacing — همگی دست‌نخورده. `polisher.polish`
بعد از residue check آن را اعمال می‌کند. تست در
`tests/test_polisher_parse.py::test_fa_postprocess_normalize_safe_subset`.

#### Aligner discourse cues expansion
**فایل:** `src/openai_tools/aligner_per.py`

۴ category جدید به `_BUILTIN_CUES` اضافه شد بر اساس بررسی
`docs/aligner-research.md`: addition، sequence، example، emphasis.
~۲۰ خط افزایش، همان ساختار، ریسک نزدیک به صفر.

#### RTL helpers با API صحیح python-docx
**فایل:** `src/openai_tools/aligner_per.py`

`_ensure_rtl_paragraph` و `_ensure_rtl_run` به جای `find()` دستی،
از `get_or_add_pPr()` و `get_or_add_rPr()` (روش رسمی python-docx)
استفاده می‌کنند. schema-correct insertion، کوتاه‌تر، idempotent.

#### تحقیق محض (بدون پیاده‌سازی)
- `docs/batch-api-analysis.md` — Batch API نه برای UI تعاملی فعلی، بله
  برای bulk translation در آینده. پیشنهاد out-of-scope.
- `docs/aligner-research.md` — مقایسه با Gale-Church، DP، embeddings،
  ASR. ۳ ایده برای آینده مستند شد.
- `docs/rtl-rendering.md` — توضیح why و how برای E10 fix؛ چرا
  python-bidi / arabic-reshaper استفاده نشد.

---

### ۰-و. Progress Bar روی polling موجود [2026-05-09]

**فایل‌ها:** `local_launcher.py`، `src/machine-translate-docx.py`، `index.ejs`

پیاده‌سازی بدون SSE — از همان polling هر ۴ ثانیه `/status/:jobId` استفاده
می‌شود.

- `Job` dataclass فیلد `progress: int = 0` گرفت.
- `local_launcher._process_job` در دو نقطه `progress=5` (job ثبت شد) و
  `progress=10` (semaphore acquired) ست می‌کند.
- در `_run_real_backend`، loop خواندن stdout subprocess قبل از log کردن
  هر خط، prefix `PROGRESS:` را تشخیص می‌دهد و `update_job(progress=...)`
  می‌زند. خود خط چاپ نمی‌شود (نویز نیست).
- `machine-translate-docx.py` در ۵ نقطه `print("PROGRESS:N", flush=True)`
  می‌زند: `15` قبل از translate، `30` بعد از translate، `65` بعد از polish،
  `75` قبل از aligner (Classic+Double)، `100` بعد از Double.
- `/status/:jobId` فیلد `progress` را برمی‌گرداند.
- `index.ejs` یک `<progress>` HTML5 + label و درصد دارد. `pollJobStatus`
  هر بار `_updateProgress(data.progress)` می‌زند. label از `_progressLabel(pct)`
  می‌آید (`Translating…` / `Polishing…` / `Aligning subtitles…` / ...).

---

### ۰-ه. Phase 5 (review-rewrite-opus-4.7) — اختیاری [2026-05-08]

#### 0.14 Prompt hash در log JSON
**فایل‌ها:** `src/openai_tools/_retry.py` (تابع جدید)،
`translator.py`، `polisher.py`، `aligner_per.py`، `tests/test_translator_utils.py`

`prompt_hash(text)` → ۸ کاراکتر اول `sha256(text)`. در:
- `OpenAITranslator.last_call_data["prompt_hash"]`
- `OpenAIPolisher.last_call_data["prompt_hash"]`
- `FASubtitleAligner.last_stats["prompt_hash"]`

ثبت می‌شود. وقتی پرامپت تغییر می‌کند، می‌توان از روی hash تشخیص داد که
کدام نسخه پرامپت در یک log قدیمی استفاده شده — برای reproducibility و
debug ضروری وقتی پرامپت‌های ۲۰۰+ خطی به‌مرور ویرایش می‌شوند.

#### 0.13/0.15 — Skip شدند
- **Progress bar:** نیاز به تغییر state Job و SSE/polling expansion داشت → خارج از scope ۵
- **virastar:** در PyPI نسخه‌ای موجود نیست (`pip install virastar` fail شد) → skip طبق شرط user

---

### ۰-د. Phase 4 (review-rewrite-opus-4.7) — کیفیت کد و تست [2026-05-08]

#### 0.10 ۱۰ unit test و pytest setup
**فایل‌های جدید:** `pytest.ini`، `requirements-test.txt`، `tests/conftest.py`،
`tests/test_aligner_split.py` (۶ تست)، `tests/test_polisher_parse.py` (۳ تست)،
`tests/test_translator_utils.py` (۱ تست)

`conftest.py` فقط `src/` را به `sys.path` اضافه می‌کند تا
`import openai_tools.*` کار کند. تست‌ها با `__new__` آبجکت می‌سازند تا
بدون OPENAI_API_KEY و بدون network call اجرا شوند. اجرا:
`pip install -r requirements-test.txt && pytest` → 10 passed in <۲s.

#### 0.11 DB connection guard
**فایل:** `src/openai_tools/translator.py`

`self.db_enabled = bool(os.environ.get("MARIADB_HOST"))` در `__init__`. اگر
False است، هیچ MariaDB connection تلاش نمی‌شود — `set_filename` و block
"Save query record" هر دو early-return با لاگ INFO. این ۲ تلاش connection
retry در هر API call را در حالت بدون DB حذف می‌کند.

#### 0.12 Concurrent job semaphore
**فایل:** `local_launcher.py`

`_job_semaphore = threading.Semaphore(int(os.environ.get("MTD_MAX_CONCURRENT_JOBS", "2")))`
ماژول-سطح. `_process_job` قبل از کار `acquire()` می‌کند و در `finally` رها
می‌کند → cap concurrent backend subprocesses (هر کدام ۲۵۰-۵۰۰MB حافظه).
job‌های اضافی در حالت `pending` می‌مانند و فرانت‌اند به polling ادامه می‌دهد.
از طریق env var قابل override.

---

### ۰-ج. Phase 3 (review-rewrite-opus-4.7) — کیفیت aligner [2026-05-08]

#### 0.7 `_display_len` — حذف ZWNJ از شمارش طول
**فایل:** `src/openai_tools/aligner_per.py`

ZWNJ (U+200C) در نمایش Word zero-width است ولی در `len()` شمرده می‌شد →
chunkهای حاوی نیم‌فاصله از حد نمایشی واقعی کوتاه‌تر می‌شدند. تابع جدید
`_display_len(text)` این را اصلاح می‌کند. تمام مقایسه‌های `len(...) > MAX_CHARS`
که برای validation/safety هستند به `_display_len(...) > MAX_CHARS` تبدیل شدند:
`_recursive_split`، `_emergency_split`، `_split_distinct`، `_split_by_budget`،
`_should_preserve_existing_segmentation`، `_mechanical_align` (fallback safety)،
`_try_marker_align` (left/left_ch/right_ch)، `_quality_score`، `_validate`،
`align()` stats. عملیات slicing (`text[:MAX_CHARS]`) همان len راو می‌ماند —
نتیجه‌اش conservative است.

#### 0.8 Cross-group triple guard با sentinel
**فایل:** `src/openai_tools/aligner_per.py`

Bridge rowها در flat list ظاهر نمی‌شوند، پس وقتی گروه N با "X" تمام و
گروه N+1 با "X" شروع می‌شد، در flat list یک run "X X" دیده می‌شد و در
ادامه‌ی واقعی پنجم سرکوب می‌کرد. حل: قبل از flatten بین گروه‌ها sentinel
`'\x00GROUP_BOUNDARY\x00'` تزریق می‌شود. این رشته در `_enforce_no_triple`
به‌صورت طبیعی run را reset می‌کند (چون با هیچ chunk واقعی برابر نیست).
re-chunk هم با pos += 1 sentinel slot را skip می‌کند.

#### 0.9 BREAK_RATIO per content type
**فایل:** `src/openai_tools/aligner_per.py`

به‌جای `BREAK_RATIO_MEDIAN=0.45` یکنواخت، dict `_BREAK_RATIO_BY_TYPE` بر اساس
نوع محتوا:
- `narration` و `spiritual` → 0.45 (verb-final فارسی)
- `news_attr` → 0.55 (front-loaded subject/event)
- `dialogue` و `ingredient` → 0.50 (متعادل)

`_split_distinct(text, n, content_type=None)` پارامتر اختیاری گرفت — اگر
None بود همان `BREAK_RATIO_MEDIAN` استفاده می‌شود (backward compat). در
`_mechanical_align` content_type گروه به `_split_distinct` پاس می‌شود.

---

### ۰-ب. Phase 2 (review-rewrite-opus-4.7) — مشکلات قابل دیدن [2026-05-08]

#### 0.4 ZIP package برای دانلود (E9 fix)
**فایل‌ها:** `local_launcher.py`، `index.ejs`

به‌جای ۳ تا setTimeout که Chrome آن‌ها را پشت permission gate قرار می‌دهد:
- endpoint جدید `GET /download-zip/:jobId` همه فایل‌های موجود job را در یک
  `_PER_package.zip` بسته‌بندی می‌کند و یک‌جا stream می‌کند.
- Frontend وقتی `filename2 || filename3` وجود داشت، به‌جای ۳ دانلود سریال،
  یک کلیک به ZIP می‌زند.
- پیغام موفقیت بعد از دانلود به این حالت محتوای ZIP را نشان می‌دهد.

#### 0.5 Cleanup خودکار job store
**فایل:** `local_launcher.py`

`LocalState.cleanup_old_jobs(max_age_sec=3600)` job‌های `done`/`error` که
بیش از یک ساعت از created_at آن‌ها گذشته را حذف می‌کند. یک thread با نام
`job-cleanup` هر ۱۰ دقیقه این تابع را فراخوانی می‌کند (`start_cleanup_thread`).
در `main()` بعد از `state.boot()` راه می‌افتد.

#### 0.6 Retry با backoff برای OpenAI calls
**فایل‌ جدید:** `src/openai_tools/_retry.py`
**فایل‌های ویرایش‌شده:** `translator.py`، `polisher.py`، `aligner_per.py`

`call_with_retry(fn, *, label)`:
- transient: `RateLimitError`، `APIConnectionError`، `APITimeoutError`
  → ۳ تلاش با backoff ۱s، ۲s، ۴s
- non-retryable: `BadRequestError` → فوری raise
- بقیه exceptionها → فوری raise (هیچ silent swallow نیست)

هر سه caller (translator chat/responses، polisher chat، aligner batch) از
این helper مشترک استفاده می‌کنند تا رفتار retry یکدست بماند.

---

### ۰-الف. Phase 1 (review-rewrite-opus-4.7) — رفع‌های بحرانی [2026-05-08]

**هدف:** بستن سه باگ بحرانی که مستقیماً در خروجی نهایی دیده می‌شوند یا امنیت را تهدید می‌کنند.

#### 0.1 RTL/bidi در سلول‌های FA (متن آینه‌ای fix)
**فایل:** `src/openai_tools/aligner_per.py`

`_set_fa_cell` فقط `run.text` را ست می‌کرد. اگر سلول template DOCX
مارکر `<w:bidi/>` نداشت، Word متن FA را با direction LTR رندر می‌کرد →
کاربر "آینه‌ای/معکوس" می‌دید. حالا دو helper جدید:
- `_ensure_rtl_paragraph(p)` — `<w:bidi/>` به `pPr` اضافه می‌کند
- `_ensure_rtl_run(run)` — `<w:rtl/>` به `rPr` اضافه می‌کند

و در پایان `_set_fa_cell` هر دو فراخوانی می‌شوند. idempotent — اگر markup
از قبل وجود دارد دست نمی‌زند.

#### 0.2 تشخیص English residue در پولیش
**فایل:** `src/openai_tools/polisher.py`

تابع جدید `_detect_en_residue(text)` — اگر بیش از ۴۰٪ نویسه‌ها latin باشند و
کلمه > ۵ → خط را untranslated می‌داند. بعد از `_parse_output`، خطوط مشکوک
با خروجی translator (قبل از پولیش) جایگزین می‌شوند. لیست تغییرات در
`last_call_data["en_residue"]` ثبت می‌شود تا در log JSON ظاهر شود.

#### 0.3 Server-side validation فایل
**فایل:** `local_launcher.py`

تابع جدید `_validate_docx_payload(payload)`:
1. **Magic bytes:** payload باید با `PK\x03\x04` (ZIP local header) شروع شود
2. **Zip-bomb cap:** مجموع `file_size` تمام entryها ≤ ۵۰ MB

قبل از `write_bytes` در `do_POST` فراخوانی می‌شود. روی client-side validation
در `index.ejs` تکیه نمی‌کند.

---

### ۱. فرمت خروجی پولیشر: تگ‌های `⟨⟨N⟩⟩`

**فایل:** `src/openai_tools/polisher.py` + `prompts/polish_PER.txt`

قبلاً پولیشر از فرمت `Line N: text` استفاده می‌کرد که با محتوای متن تداخل داشت.
تگ جدید `⟨⟨N⟩⟩` (U+27E8/U+27E9) منحصربه‌فرد است و در متن عادی ظاهر نمی‌شود.

`_parse_output()` با ۴ استراتژی به‌ترتیب اولویت بازنویسی شد:
1. **⟨⟨N⟩⟩ tag** (اصلی) — regex با `re.DOTALL` برای محتوای چندخطی
2. **Legacy `Line N:`** — برای مدل‌هایی که فرمت قدیمی برمی‌گردانند
3. **Plain line-for-line** — اگر تعداد خطوط دقیقاً برابر N باشد
4. **Pass-through** — raw output به downstream می‌رود (طول چک می‌کند و لاگ می‌زند)

```python
# regex اصلی
re.findall(r"⟨⟨(\d+)⟩⟩\s*(.*?)(?=⟨⟨\d+⟩⟩|$)", raw, re.DOTALL)
```

---

### ۲. جلوگیری از تداخل نام فایل خروجی

**فایل:** `src/machine-translate-docx.py`

اگر فایل خروجی از قبل وجود داشت، پایتون کرش می‌کرد. حالا suffix `_1`, `_2`, `_3` اضافه می‌شود:

```python
if os.path.exists(word_file_to_translate_save_as_path):
    stem = re.sub(r'(?i)\.docx$', '', word_file_to_translate_save_as_path)
    idx = 1
    while os.path.exists(f"{stem}_{idx}.docx"):
        idx += 1
    word_file_to_translate_save_as_path = f"{stem}_{idx}.docx"
```

---

### ۳. معماری Polling در سرور

**فایل:** `server.js.txt`

قبلاً `/upload` کل پروسه را sync اجرا می‌کرد — اگر connection قطع می‌شد، فایل خروجی گم می‌شد.

حالا:
- `/upload` فوری `{ ok: true, jobId }` برمی‌گرداند
- پروسه Python در background اجرا می‌شود
- فرانت‌اند هر ۴ ثانیه `GET /status/:jobId` را poll می‌کند
- Job store در memory: `const jobs = new Map()`
- Job cleanup: completed jobs بعد از ۲ ساعت پاک می‌شوند؛ pending بعد از ۵۰ دقیقه timeout

```javascript
// ساختار هر job
{ status: "pending" | "done" | "error", filename?, error?, createdAt }
```

---

### ۴. موتور جدید «OpenAI Translation + Polish»

**فایل‌ها:** `server.js.txt`, `index.ejs`, `src/machine-translate-docx.py`

موتور `chatgpt-polish` اضافه شد — **فقط برای زبان فارسی فعال** است.

در سرور:
```javascript
if (translationEngine === 'chatgpt-polish') {
    fullCommand += ` --with-polish `;
}
```

در CLI پایتون flag `--with-polish` باعث می‌شود `OpenAIPolisher` هم instantiate شود.

---

### ۵. اصلاحات فرانت‌اند (index.ejs)

**فایل:** `index.ejs`

- **Loading overlay**: کلاس Tailwind `hidden` از HTML حذف شد (با `.visible { display: flex }` تداخل داشت)؛ حالا فقط `classList.add/remove('visible')` استفاده می‌شود
- **`engineChecker()`**: کاملاً بازنویسی شد — کد duplicate و متناقض حذف، منطق enable/disable تمیز شد
- **localStorage**: زبان مبدأ، زبان مقصد، و موتور انتخابی در localStorage ذخیره و بازیابی می‌شوند
- **Polling**: `sendToServer()` با `pollJobStatus(jobId)` جایگزین شد — ۴۰ دقیقه max wait، retry روی network error

---

### ۶. Single-call mode برای OpenAI

**فایل:** `src/machine-translate-docx.py`

قبلاً کل فایل به بلوک‌های کوچک تقسیم می‌شد و هر بلوک جداگانه به API می‌رفت.
حالا در حالت OpenAI:
- **یک API call** برای کل فایل (ترجمه)
- **یک API call** برای کل فایل (پولیش — اگر `--with-polish` فعال باشد)

```python
_single_call_done = False
if translation_engine == "chatgpt" and engine_method == "api" and oai_translator is not None:
    full_source = "\n".join(blocks_nchar_max_to_translate_array)
    _, full_translated = oai_translator.translate(src_lang_name, dest_lang_name, full_source)
    if oai_polisher is not None:
        full_translated = oai_polisher.polish(full_source, full_translated)
    translated_blocks.append(full_translated)
    _single_call_done = True
if not _single_call_done:
    for i, block in enumerate(blocks_nchar_max_to_translate_array):
        # loop اصلی برای موتورهای دیگر — دست‌نخورده
```

---

### ۷. `timeout=1800` روی API call‌ها

**فایل‌ها:** `translator.py`, `polisher.py`

برای جلوگیری از hang بی‌نهایت، هر دو API call حالا `timeout=1800` دارند.

---

### ۸. حذف `reasoning_effort` از ترجمه‌گر + اصلاح کش

**فایل‌ها:** `translator.py`, `polisher.py`, تمام prompt فایل‌ها

**مشکل کندی:** `reasoning_effort: "high"` روی مدل mini باعث شد برای ۹۵ خط زیرنویس،
مدل ۳۸٬۹۹۷ توکن «فکر» کرد و فقط ۲٬۳۷۵ توکن واقعی ترجمه تولید شد (۹۴٪ reasoning).

**مشکل کش:** `{N}` در system prompt تزریق می‌شد — هر فایل با تعداد خط متفاوت،
system prompt متفاوت = cache key متفاوت = کش هرگز نمی‌خورد.

**راه‌حل:**
- `reasoning_effort` از `translator.py` کاملاً حذف شد
- پولیشر: `reasoning_effort: "high"` فقط اگر `"mini"` در نام مدل باشد (`if "mini" in self.model.lower()`)
- `{N}` از system prompt حذف شد — حالا اول user message می‌آید:
  - ترجمه‌گر: `"Lines to translate: N\n\n..."` 
  - پولیشر: `"Lines to polish: N\n\n..."`

**نتیجه:** از call دوم به بعد با همان زبان، system prompt کش می‌خورد.

---

### ۹. ارتقاء مدل به gpt-5.5 + بهبود پرامپت‌ها

**فایل‌ها:** `translator.py`, `polisher.py`, `machine-translate-docx.py`, `translate_PER.txt`, `polish_PER.txt`

**تغییرات کد:**
- `translator.py`: مدل پیش‌فرض → `gpt-5.5`؛ مدل mini به‌صورت comment غیرفعال موجود است
- `polisher.py`: مدل پیش‌فرض → `gpt-5.5`؛ مدل mini به‌صورت comment غیرفعال موجود است
- `machine-translate-docx.py`: default CLI model → `gpt-5.5`
- `aligner_per.py`: همیشه `gpt-5.4-mini` — مستقل از `--aimodel` (تصمیم آگاهانه)

**تغییرات پرامپت:**
1. `translate_PER.txt` — `<OUT>`: افزودن `[FORMAT]` — خروجی فقط خطوط فارسی خام، بدون پیشوند `Line N:` یا tag/markdown/json/متا
2. `polish_PER.txt` — `HL-11`: رفع تناقض با ترجمه‌گر — هر دو حالا `" "` (نه `«»`)؛ دلیل: در محیط subtitle فضای بیشتری می‌گیرد

**نکته:** قیمت `gpt-5.5` در PRICES تخمینی است — آپدیت کن وقتی pricing رسمی شد.

---

### ۱۰. FA Subtitle Aligner — تشخیص bridge و سلول‌های خاکستری

**فایل:** `src/openai_tools/aligner_per.py`

**مشکل:** الاینر سلول‌های خاکستری (metadata) و سطرهای timecode را در گروه‌های جمله می‌گذاشت و متن اشتباه توزیع می‌کرد.

**راه‌حل — سه لایه:**

**لایه ۱: تشخیص رنگ سلول از XML:**
```python
def _cell_has_shading(cell) -> bool:
    tcPr = cell._tc.find(_qn('w:tcPr'))
    if tcPr is None: return False
    shd = tcPr.find(_qn('w:shd'))
    if shd is None: return False
    fill = shd.get(_qn('w:fill'))
    return fill and fill.lower() not in ('auto', 'ffffff', '')
```

**لایه ۲: BRIDGE_PATTERNS جدید اضافه شد:**
```python
re.compile(r'^\d+:\d+'),            # timecodes: "0:34 ~ 0:44"
re.compile(r'^[A-Z][A-Z\s]{2,}:\s*$'),  # ALL-CAPS labels: "YOUR LANGUAGE:"
re.compile(r'^ONSCREEN', re.I),
re.compile(r'^VO\s*[&:]', re.I),
```

**لایه ۳: سلول EN خالی:**
```python
def _is_bridge(en: str) -> bool:
    if not en.strip(): return True   # ← سلول خالی → bridge
    return any(p.search(en) for p in BRIDGE_PATTERNS)
```

**نحوه write-back (مهم — این درست است):**
الاینر `row_indices` هر گروه را نگه می‌دارد و `_write_docx` فقط به همان سطرهای اصلی می‌نویسد. سلول‌های bridge/خاکستری هرگز وارد `row_indices` نمی‌شوند → هرگز لمس نمی‌شوند.

```python
def _write_docx(self, input_path, output_path, groups, final_chunks):
    for group, chunks in zip(groups, final_chunks):
        for ri, chunk in zip(group['row_indices'], chunks):  # ← exact row index
            self._set_fa_cell(table, ri, chunk)
```

---

### ۱۱. UI Model Selector — انتخاب مدل OpenAI از فرانت‌اند

**فایل‌ها:** `index.ejs`, `server.js.txt`

**مشکل:** مدل OpenAI در Python hardcode بود — کاربر نمی‌توانست از UI تغییر دهد.

**راه‌حل:**

`index.ejs` — dropdown جدید (فقط وقتی OpenAI engine انتخاب شده نمایش داده می‌شود):
```html
<div id="aiModelRow" style="display:none;">
  <select id="aiModel" name="aiModel">
    <option value="gpt-5.5" selected>GPT-5.5 — Recommended</option>
    <option value="gpt-5.4">GPT-5.4</option>
    <option value="gpt-5.4-mini">GPT-5.4-mini — Faster, cheaper</option>
  </select>
</div>
```

`index.ejs` — `aiModel` به formData اضافه شد:
```javascript
const aiModel = document.getElementById('aiModel')?.value;
if (aiModel) formData.append('aiModel', aiModel);
```

`server.js.txt` — `--aimodel` به CLI command اضافه شد:
```javascript
const resolvedModel = aiModel || 'gpt-5.5';
fullCommand += ` --aimodel ${shellEscape(resolvedModel)} `;
```

**نکته:** انتخاب مدل در localStorage ذخیره می‌شود.

---

### ۱۲. local_launcher.py — سرور محلی Python

**فایل:** `local_launcher.py`

سرور محلی کامل برای تست UI بدون Node.js. توسط Codex ساخته شد، سپس بازبینی و اصلاح شد.

**معماری:**
- `ThreadingHTTPServer` — pure Python، بدون Express
- دو حالت: `--backend real` (اجرای واقعی پایتون) و `--backend mock` (DOCX placeholder)
- `_inject_client_patch()`: JS inject می‌کند که `aiModel`, `enableSound`, `soundSelect` را به FormData اضافه کند
- `_parse_multipart()`: multipart parser سفارشی با `email.parser`
- `_run_real_backend()`: subprocess اجرا می‌کند، "Saved file name:" از stdout می‌خواند

**باگ‌های اصلاح‌شده:**

1. **فیلد engine (بحرانی):** فرم JS با `formData.append('translationEngine', ...)` ارسال می‌کند — launcher باید `fields.get("translationEngine", "google")` بخواند (نه `"engine"`)

2. **پارامتر تکراری:** `ai_model` دو بار به thread args پاس می‌شد (پارامتر ۹ و ۱۲). پارامتر ۱۲ (`ui_ai_model`) حذف شد.

3. **پیشوند timestamp در نام خروجی:** upload با `{timestamp}-filename` ذخیره می‌شد و خروجی هم همان پیشوند را داشت. تابع `_strip_timestamp()` اضافه شد:
```python
def _strip_timestamp(self, path: Path) -> Path:
    clean = re.sub(r'^\d{10,}-', '', path.name)
    if clean != path.name:
        clean_path = path.with_name(clean)
        path.rename(clean_path)
        return clean_path
    return path
```

4. **پسوند `_FA` به‌جای `_PER`:** fallback از `target_language.upper()` استفاده می‌کرد → `FA`. حالا `_LANG_ALPHA3B` map اضافه شد:
```python
_LANG_ALPHA3B = {'fa': 'PER', 'ar': 'ARA', 'de': 'GER', 'fr': 'FRE', ...}
```

---

### ۱۳. تغییر نام فایل‌های پرامپت: `_fa` → `_PER`

**فایل‌ها:** `prompts/`, `translator.py`, `polisher.py`

**تغییر نام:**
- `prompts/translate_fa.txt` → `prompts/translate_PER.txt`
- `prompts/polish_fa.txt` → `prompts/polish_PER.txt`

**مکانیزم lookup — تابع جدید `_prompt_lang_code()`:**
```python
# در translator.py
_PROMPT_FILE_MAP = {'fa': 'PER', 'ar': 'ARA'}

def _prompt_lang_code(dest_lang: str) -> str:
    code = _normalize_lang(dest_lang)
    return _PROMPT_FILE_MAP.get(code, code)
```

هر دو `translator.py` و `polisher.py` از `_prompt_lang_code()` برای lookup استفاده می‌کنند.
`_normalize_lang()` دست‌نخورده ماند — فقط برای prompt lookup عوض شد.

---

### ۱۴. نام‌گذاری فایل خروجی — قرارداد نهایی

**فایل:** `src/machine-translate-docx.py`, `local_launcher.py`

| خروجی | الگوی نام |
|-------|-----------|
| ترجمه + پولیش | `filename_PER_TranslatePolish.docx` |
| الاینر (دوبل) | `filename_PER_Double.docx` |
| لاگ JSON | `filename_PER_TranslatePolish_log.json` |

**تغییر کد الاینر:**
```python
# قبل: _aligned_path = re.sub(r'\.docx$', '_aligned.docx', word_file_to_translate_save_as_path)
# بعد:
_aligned_path = re.sub(r'(?i)\.docx$', '_PER_Double.docx', word_file_to_translate)
# ← از نام فایل اصلی (نه polish output) مشتق می‌شود
```

**`_fallback_output_path` در local_launcher:**
```python
def _fallback_output_path(self, source_file, target_language):
    suffix = _lang_suffix(target_language) or "OUT"
    stem = re.sub(r'^\d{10,}-', '', source_file.stem)  # حذف timestamp
    return source_file.with_name(f"{stem}_{suffix}.docx")
```

---

---

### ۱۷. سه روش تقسیم متفاوت — Classic / Double / AIAlign [2026-05-08]

**مشکل:** `_PER_Classic.docx` و `_PER_Double.docx` هر دو از `FASubtitleAligner(llm_threshold=0)`
تولید می‌شدند — عیناً یکسان بودند؛ هیچ ارزش مقایسه‌ای نداشتند.

**راه‌حل:** هر سه فایل خروجی اکنون روش تقسیم **واقعاً متفاوت** دارند:

| فایل | روش | کد |
|------|-----|-----|
| `_PER_Classic.docx` | تقسیم ساده الگوریتمی — بدون AI، بدون منطق فارسی‌محور | `_simple_split_docx()` (تابع جدید) |
| `_PER_Double.docx` | الاینر فارسی‌محور مکانیکی — بدون LLM | `FASubtitleAligner(llm_threshold=0)` |
| `_PER_AIAlign.docx` | الاینر فارسی‌محور + بازبینی LLM تمام گروه‌ها | `FASubtitleAligner(llm_threshold=100)` |

**تابع `_simple_split_docx`:** برای هر سلول FA با طول > 48 کاراکتر، در آخرین
مرز کلمه تقسیم می‌کند و یک ردیف جدید با باقیمانده زیر ردیف اصلی می‌گذارد.
حداکثر یک تقسیم per row (double، نه triple).

**`filename4`:** فیلد جدید در `Job` dataclass → `_PER_AIAlign.docx`.
`_find_ai_align_file()` با 3 استراتژی آن را پیدا می‌کند (mirrors `_find_classic_file`).

**ZIP:** شامل همه ۴ فایل (TranslatePolish + Classic + Double + AIAlign).
Guard صریح: `hasMultiple = !!(filename2 || filename3 || filename4)` — فقط fa+chatgpt-polish.

**فایل‌های تغییریافته:**
- `src/machine-translate-docx.py` — تابع `_simple_split_docx` + بلوک aligner بازنویسی شد
- `local_launcher.py` — `filename4`، `_find_ai_align_file()`, آپدیت `/status/:jobId` و ZIP
- `index.ejs` — `filename4` در poll, ZIP trigger, و alert message

---

### ۱۵. سه‌فایل خروجی — Classic + Double + TranslatePolish

**فایل‌ها:** `local_launcher.py`, `index.ejs`, `src/machine-translate-docx.py`

پایپ‌لاین فارسی حالا سه فایل تولید می‌کند:

| فایل | الگوریتم | LLM |
|------|-----------|-----|
| `_PER_TranslatePolish.docx` | ترجمه + پولیش | gpt-5.5 |
| `_PER_Classic.docx` | الاینر مکانیکی خالص | ❌ هیچ |
| `_PER_Double.docx` | الاینر مکانیکی خالص | ❌ هیچ |

**توجه:** Classic و Double هر دو `llm_threshold=0, token_budget=0` دارند — هیچ API call از الاینر نمی‌زند.

**تغییرات `local_launcher.py`:**
```python
@dataclass
class Job:
    filename2: str | None = None   # _PER_Double.docx
    filename3: str | None = None   # _PER_Classic.docx

def _find_classic_file(self, main_output: Path) -> Path | None:
    # Strategy 1: replace _TranslatePolish → _Classic
    # Strategy 2: timestamped variant
    # Strategy 3: glob by clean stem
```

**تغییرات `index.ejs`:**
```javascript
const { filename, filename2, filename3 } = await pollJobStatus(uploadData.jobId);
triggerDownload(filename);
if (filename2) setTimeout(() => triggerDownload(filename2), 1500);
if (filename3) setTimeout(() => triggerDownload(filename3), 3000);
```

**نکته Chrome:** اولین بار که ۳ فایل دانلود می‌شود، Chrome notification «Allow multiple downloads» نشان می‌دهد — باید یک‌بار Allow بزنی.

---

### ۱۶. حذف تعارض Split/Aligner — مخفی‌سازی Split section

**فایل:** `index.ejs`

**مشکل کشف‌شده:** وقتی موتور `chatgpt-polish` با زبان فارسی انتخاب می‌شد، Split Method هم روشن بود (پیش‌فرض: OpenAI API). این باعث می‌شد:
1. یک API call به‌ازای هر phrase برای splitting
2. Aligner هم همان توزیع را دوباره انجام می‌داد — کار دوگانه

**راه‌حل:**
```javascript
// در engineChecker():
const isAlignerPipeline = (targetLanguage === 'fa' && engineSel.value === 'chatgpt-polish');
if (splitSection) {
  splitSection.style.display = isAlignerPipeline ? 'none' : '';
  if (isAlignerPipeline) splitTranslateCheckbox.checked = false;
}
```

- کل `#splitSection` از دید پنهان می‌شود
- `splitTranslate=false` → سرور هیچ splitting انجام نمی‌دهد
- هر بار که engine یا زبان تغییر کند، بررسی مجدد می‌شود

---

## وضعیت فعلی

| بخش | وضعیت |
|-----|--------|
| ترجمه OpenAI (single-call) | ✅ |
| پولیش OpenAI (single-call) | ✅ |
| Classic split (بدون insert، بدون double، فقط FA column) | ✅ |
| Double aligner (FA-based grouping، maximize doubles) | ✅ |
| فرمت خروجی `⟨⟨N⟩⟩` | ✅ |
| Polling architecture | ✅ |
| localStorage (فقط زبان) | ✅ |
| کش prompt — Responses API برای gpt-5.x | ✅ |
| مدل gpt-5.5 | ✅ پیش‌فرض |
| UI model selector | ✅ |
| دانلود ۲ فایل با ۱۸۰۰ms فاصله | ✅ |
| engineChecker بدون lock | ✅ |
| قیمت‌گذاری gpt-5.5 رسمی + cached cost | ✅ |
| نام‌گذاری `_PER` / `_PER_Double` / `_PER_Classic` | ✅ |
| پرامپت‌ها با پسوند `_PER` | ✅ |
| Split section مخفی برای فارسی+polish | ✅ |
| تست مستقل الاینر (`test_aligner_only.py`) | ✅ |
| تست end-to-end با فایل واقعی | ⚠️ در حال تست |

---

## کارهای باقی‌مانده

- تأیید کیفیت خروجی الاینر با فایل‌های واقعی زیرنویس

---

## راهنمای سشن بعدی

### روش خواندن سریع (کمترین توکن)

```
1. همین فایل (CHANGES.md)                          ← ۵ دقیقه، کل تصویر
2. src/openai_tools/translator.py                   ← اگر روی ترجمه کار می‌کنید
3. src/openai_tools/polisher.py                     ← اگر روی پولیش کار می‌کنید
4. src/openai_tools/aligner_per.py                  ← اگر روی aligner کار می‌کنید
5. src/machine-translate-docx.py (جستجوی _single_call_done) ← اگر روی CLI کار می‌کنید
6. server.js.txt (بخش job store + /status)          ← اگر روی سرور کار می‌کنید
7. local_launcher.py                                ← اگر روی تست محلی کار می‌کنید
```

### سوالات احتمالی سشن بعدی

- «کدام مدل برای چه؟» → ترجمه+پولیش: `gpt-5.5` | aligner: `gpt-5.4-mini` (همیشه)
- «کش چطور کار می‌کند؟» → system prompt ثابت است؛ N در user message است؛ از call دوم کش می‌خورد
- «single-call کجاست؟» → جستجوی `_single_call_done` در `machine-translate-docx.py`
- «فرمت خروجی پولیشر؟» → `⟨⟨N⟩⟩ متن` — regex در `polisher.py`
- «الاینر چطور کار می‌کند؟» → صرفاً مکانیکی (llm_threshold=0) — mechanical 3 pass — در `aligner_per.py`
- «چرا الاینر سلول‌های خاکستری را درست می‌شناسد؟» → `_cell_has_shading()` از DOCX XML می‌خواند
- «پرامپت فارسی کجاست؟» → `prompts/translate_PER.txt` و `prompts/polish_PER.txt`
- «local_launcher چطور engine را می‌خواند؟» → `fields.get("translationEngine")` — همان key که JS ارسال می‌کند
- «چرا Split section مخفی است؟» → برای فارسی+chatgpt-polish، aligner جایگزین splitter است — تعارض برطرف شد
- «چرا سه فایل دانلود می‌شود؟» → TranslatePolish + Classic + Double، هر ۱.۵ ثانیه یکی
- «آیا باید به Java/Kotlin مهاجرت کرد؟» → خیر — bottleneck API است نه Python؛ python-docx جایگزین ندارد
