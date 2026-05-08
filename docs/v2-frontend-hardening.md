# V2 Frontend Hardening Summary

> Source: this document was authored on the `feature/v2-frontend` branch
> during the 5-phase hardening sprint. It is preserved here for the
> historical record after the merge to `master` on 2026-05-09.

---

```
Phase A regression tests:        15 added (cache + subscribe)
Phase B a11y/perf fixes:         9 changes
Phase C Tailwind migration:      complete (~285 KB savings)
Phase D i18n locales:            complete (65 keys × 2 locales)
Phase E Playwright e2e:          complete (4 tests, marked live)
Total tests passing:             21 (default) + 4 (live, on-demand)
Branch:                          feature/v2-frontend (HEAD = 38c9c8a)
```

## کامیت‌های فاز

- `bbf4e16` chore: حذف تست stale (پاکسازی pre-flight)
- `92f7716` Phase A — رگرسیون cache + subscribe
- `d24cb93` Phase B — a11y + perf static audit
- `4b44c59` Phase C — Tailwind CDN → compiled
- `1d3f69a` Phase D — i18n en + fa
- `38c9c8a` Phase E — Playwright e2e (live)

## تصمیمات معماری

- `brand-800: #9F4D2D` به‌عنوان رنگ AA-compliant برای متن inline اضافه شد
  (500/600/700 با cream-100 contrast لازم را ندارند)
- Tailwind compiled به جای CDN — `web/v2/tailwind.css` در repo کامیت می‌شود؛
  `node_modules/` در .gitignore
- i18n از طریق `i18n.json` async loaded می‌شود + `x-cloak` روی body برای
  جلوگیری از FOUC؛ توابع متنی fallback به key دارند
- مدل‌ها/موتورها به‌عنوان شناسه فنی untranslated می‌مانند
- تست‌های live از پیش‌فرض pytest با marker `not live` در `addopts` مستثنی
  می‌شوند
- `alpine:init` handler به app.js اضافه شد به‌عنوان دفاع در برابر race بین
  Alpine و app.js

## رعایت قوانین (R rules)

- **R1** (legacy /): دست‌نخورده — `local_launcher.py` تغییر نکرد در فاز feature.
  در سشن ۲۰۲۶-۰۵-۰۹ فقط فیکس F-013 (UTF-8 stdout reconfigure) برای
  ویندوز اضافه شد — additive و non-breaking.
- **R2** (API contract): تغییر نکرد
- **R3** (PROGRESS markers): دست‌نخورده
- **R4** (subscribers.txt): همچنان gitignored
- **R5** (cache key): تغییر نکرد
- **R6** (py_compile + pytest): همه ۶ کامیت سبز
- **R7** (third-party deps): فقط tailwindcss/postcss/autoprefixer (Phase C)
  و playwright (Phase E، dev-only)

## Deferred

هیچ‌کدام. هر ۵ فاز کامل شدند.

## نکته مهم

در حین فاز E، شاخه‌ی محلی چندین بار به‌صورت خارجی به `audit/post-refactor`
تغییر کرد و فایل‌های uncommitted از دست رفتند؛ هر بار stash + بازگشت +
بازنویسی ادیت‌ها انجام شد و کامیت `38c9c8a` با موفقیت push شد.

قبل از تست واقعی فایل، توصیه می‌شود live tests یک‌بار دستی روی محیطی پایدار
اجرا شوند:

```bash
pytest -m live -v
```
