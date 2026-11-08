# 11 — AI Guardrails (ضدالگوها و خطوط قرمز)

> **وضعیت:** زنده  
> **نسخه سند:** 1.0.0  
> **تاریخ:** 2026-11-08  
> **استفاده:** قبل از هر PR/patch توسط انسان یا AI خوانده شود

---

## 1. خطوط قرمز امنیتی

| ممنوع | دلیل |
|--------|------|
| Commit کردن `.env` با توکن واقعی | credential leakage |
| گذاشتن توکن نمونهٔ واقعی در README/issue/screenshot | همان |
| باز کردن path policy به «همه مسیرها» بدون مستندسازی و UI واضح | ریسک تخریب سیستم کاربر |
| اجرای دستور مخرب به‌عنوان پیش‌فرض ابزار | ایمنی کاربر |
| نوشتن secret در لاگ UI یا report عمومی | نشت |

---

## 2. خطوط قرمز پروتکل MCP

| ضدالگو | علامت شکست | کار درست |
|---------|-------------|----------|
| `print()` / log روی **stdout** در مسیر سرور | قطع session / JSON خراب | فقط stderr یا `file_logging` |
| ثبت `outputSchema` و برگرداندن متن خام | `outputSchema defined but no structured output` | یا schema را بردار یا structured مطابق قرارداد بده |
| برگرداندن خطا به‌صورت success | کلاینت validate می‌کند و قطع می‌شود | `error_result` / flag خطا |
| `asyncio.run` داخل event loop MCP | parallel/batch می‌شکند | `async def` + `await` / `asyncio.gather` |
| فرض session ابدی بدون recovery | `Session not found` | بازیابی یا پیام اقدام واضح |

---

## 3. خطوط قرمز PyInstaller / AppImage / subprocess

| ضدالگو | علامت | کار درست |
|---------|--------|----------|
| `subprocess` بدون `env=clean_subprocess_env()` | `OPENSSL_* not found`, `unknown url type: https` | همیشه env تمیز |
| پاس دادن `os.environ` خام به فرزند | همان | scrub در `subprocess_env.py` |
| hard-code مسیر `/mnt/...` یا home یک کاربر | شکست روی ماشین دیگر | env var + path قابل حمل |

**قانون:** هر `subprocess.run` / `Popen` جدید بدون `env=` در review رد شود.

---

## 4. خطوط قرمز lifecycle و UI

| ضدالگو | کار درست |
|---------|----------|
| بعد از Stop دستی، auto-start دوباره | فقط Start صریح کاربر |
| چند instance همزمان از GUI/tray | single-instance؛ focus به پنجره موجود |
| Quit از tray ولی پروسه زنده | shutdown کامل |
| دیالوگ دانلود بعد از 100% نصب موفق دوباره | تشخیص installed و رفتن به step بعد |
| گرفتن sudo در هر قدم بعد از یک‌بار موفقیت | کش session |
| تغییر Config که runtime را بدون هشدار می‌کشد | apply کنترل‌شده + restart آگاهانه |

---

## 5. خطوط قرمز محصول و scope

| ضدالگو | کار درست |
|---------|----------|
| اضافه کردن وابستگی سنگین برای فیچر حاشیه‌ای | اختیاری / lazy / optional extra |
| فیچر فان (مثل Whip) را به مسیر بحرانی MCP گره زدن | overlay جدا، قابل خاموش |
| افزایش major برای باگ‌فیکس | SemVer درست (`06-versioning-release.md`) |
| «فعلاً لاگ را حذف کنیم تا سبز شود» | ریشه را درست کن |
| تغییر رفتار عمومی بدون SRS | `09-srs.md` را هم‌زمان به‌روز کن |

---

## 6. چک ۳۰ ثانیه‌ای قبل از commit

1. آیا subprocess جدید `clean_subprocess_env` دارد؟
2. آیا stdout در مسیر MCP آلوده می‌شود؟
3. آیا schema/result با قرارداد ابزار می‌خواند؟
4. آیا Stop/Start و single-instance خراب نشده؟
5. آیا توکن/مسیر شخصی در diff هست؟
6. آیا docs زنده در صورت نیاز لمس شده؟

---

## 7. Changelog

| نسخه | تاریخ | شرح |
|------|------|------|
| 1.0.0 | 2026-11-08 | جمع‌بندی ضدالگوهای تکراری تاریخچهٔ پروژه |
