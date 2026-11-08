# 11 — AI Guardrails (ضد‌الگوها و خطوط قرمز)

> **وضعیت:** زنده  
> **نسخه:** 1.0.0  
> **تاریخ:** 2026-11-08  
> **استفاده:** قبل از هر commit توسط انسان یا مدل خوانده شود

---

## 1. خطوط قرمز امنیتی

| ممنوع | دلیل |
|--------|------|
| Commit کردن `.env` با توکن واقعی | credential leakage |
| گذاشتن توکن واقعی در README، issue، لاگ نمونه، screenshot در repo | credential |
| غیرفعال کردن کامل auth برای «راحتی تست» روی branch اصلی | exposure عمومی Funnel |
| hard-code مسیر شخصی (`/mnt/.../Ali/...`) در کد محصول | غیرقابل‌حمل؛ شکست برای همه کاربران |
| باز کردن path policy بدون به‌روزرسانی SRS و هشدار UI | ریسک سیستم کاربر |

---

## 2. خطوط قرمز پروتکل MCP

| ممنوع | به‌جای آن |
|--------|-----------|
| `print()` / لاگ روی stdout در مسیر سرور | stderr یا `file_logging` |
| برگرداندن متن خام وقتی `outputSchema` ثبت شده | structured مطابق schema یا حذف schema |
| برگرداندن خطا به‌صورت success | `error_result` / flag خطا |
| `asyncio.run()` داخل event loop برای parallel tools | `async def` + `gather` |
| فرض اینکه همه کلاینت‌ها stateless یکسان‌اند | تست Streamable HTTP و session |

---

## 3. خطوط قرمز بسته‌بندی و subprocess

| ممنوع | به‌جای آن |
|--------|-----------|
| `subprocess.*` بدون scrub env | `env=clean_subprocess_env()` |
| اعتماد به `LD_LIBRARY_PATH` ارثی از PyInstaller | پاک‌سازی در `dana/subprocess_env.py` |
| شکستن prefetch/retry بیلد Windows NSIS برای «ساده کردن CI» | حفظ cache/retry |
| حذف sidecar ضروری از installer برای کم‌حجم‌سازی بی‌ضابطه | بهینه‌سازی با لیست allow از قابلیت Must |

---

## 4. خطوط قرمز UX / lifecycle

| ممنوع | به‌جای آن |
|--------|-----------|
| auto-start بعد از Stop دستی کاربر | فقط Start صریح |
| چند instance همزمان از tray + شورتکات | single-instance lock |
| Quit از tray ولی زنده ماندن پروسه MCP | shutdown کامل |
| حلقه دیالوگ دانلود 100% تکراری | تشخیص installed و رفتن به step بعد |
| پیام فقط stack trace انگلیسی برای کاربر نهایی | پیام اقدام‌پذیر + جزئیات در collapsible |

---

## 5. خطوط قرمز محصول و scope

| ممنوع | دلیل |
|--------|------|
| افزودن انبوه repo خارجی بدون معیار پذیرش | پیچیدگی و رگرسیون |
| فیچر فان (مثل Whip) به‌عنوان blocker انتشار | انحراف از پایداری |
| major version برای فقط تغییر UI | SemVer را بی‌معنی می‌کند |
| «فعلاً لاگ را خاموش کنیم تا خطا نیاید» | مخفی کردن باگ |

---

## 6. رگرسیون‌های تاریخی (دوباره ایجاد نکن)

این‌ها قبلاً در پروژه دیده شده‌اند:

1. **OpenSSL / HTTPS از AppImage** ← نشت `LD_LIBRARY_PATH`  
2. **`Session not found` / schema validation** ← outputSchema و session HTTP  
3. **`charmap` روی Windows** ← encode کاراکترهای UI در console  
4. **PUBLIC قطع با LOCAL سبز** ← نبود watchdog جدا  
5. **placeholder اشتباهاً در فایل اصلی** ← همیشه محتوای واقعی را verify کن  
6. **مسیر SuperMCP شخصی** ← فقط env/`DANA_SUPERMCP_HOME` و مسیر قابل‌حمل  

---

## 7. حداقل بررسی بعد از تغییر حساس

| نوع تغییر | بررسی |
|-----------|--------|
| subprocess / installer / agent | grep برای `subprocess.` بدون `env=` |
| MCP tool result | Inspector یا کلاینت واقعی؛ بدون validation error |
| setup / funnel | first-run و second-run (نباید re-download اجباری) |
| UI lifecycle | stop، quit tray، single window |
| docs | SRS/Roadmap/این guardrail اگر رفتار عوض شد |

---

## 8. Changelog

| نسخه | تاریخ | شرح |
|------|------|------|
| 1.0.0 | 2026-11-08 | ثبت خطوط قرمز و رگرسیون‌های تاریخی |
