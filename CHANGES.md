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

### نام‌گذاری فایل خروجی

```
ورودی:   filename.docx
خروجی ترجمه+پولیش:   filename_PER_TranslatePolish.docx
خروجی الاینر کلاسیک: filename_PER_Classic.docx   ← جدید
خروجی الاینر دوبل:   filename_PER_Double.docx
لاگ JSON:             filename_PER_TranslatePolish_log.json
```

**توجه:** هر سه فایل به‌صورت خودکار دانلود می‌شوند (تأخیر: 0ms / 1500ms / 3000ms).

---

## تغییرات — از ابتدا تا آخر

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
| FA Subtitle Aligner — Classic (مکانیکی خالص) | ✅ |
| FA Subtitle Aligner — Double (مکانیکی خالص) | ✅ |
| فرمت خروجی `⟨⟨N⟩⟩` | ✅ |
| Polling architecture | ✅ |
| localStorage (زبان + موتور + مدل) | ✅ |
| کش prompt (24h) | ✅ |
| مدل gpt-5.5 | ✅ پیش‌فرض |
| UI model selector | ✅ |
| local_launcher.py | ✅ سه‌فایل download |
| نام‌گذاری `_PER` / `_PER_Double` / `_PER_Classic` | ✅ |
| پرامپت‌ها با پسوند `_PER` | ✅ |
| Split section مخفی برای فارسی+polish | ✅ |
| تست end-to-end واقعی | ⚠️ کیفیت مکانیکی تأیید نشده |
| Java/Kotlin migration | ❌ توصیه نشد — Python engine نگه داشته شود |

---

## باگ‌های شناخته‌شده / کارهای باقی‌مانده

- `server.js.txt` نام عجیبی دارد — بررسی شود آیا باید `.js` باشد
- قیمت `gpt-5.5` در PRICES تخمینی است — آپدیت کن وقتی pricing رسمی شد
- متن انگلیسی در بعضی ردیف‌ها پس از ترجمه باقی می‌ماند (باگ ترجمه‌گر، نه الاینر)
- بعضی ردیف‌ها متن معکوس/آینه‌ای دارند (ممکن است RTL display artifact یا encoding باگ)
- کیفیت خروجی مکانیکی (بدون LLM) هنوز تأیید کامل نشده

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
