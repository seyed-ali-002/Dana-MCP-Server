# 13 — Smoke Test Matrix

> **وضعیت:** زنده  
> **نسخه:** 1.0.0  
> **تاریخ:** 2026-11-08  
> **هدف:** چک‌لیست کوتاه قبل از release و بعد از تغییرات پرریسک  
> **مرتبط:** `09-srs.md` · `10-ai-implementation-guide.md`

---

## 1. سطح‌ها

| سطح | چه وقت |
|------|--------|
| L0 | هر PR کد Python حساس (compile + در صورت امکان pytest) |
| L1 | قبل از تگ patch |
| L2 | قبل از تگ minor (1.7, 1.8, …) |
| L3 | قبل از major (2.0) یا تغییر Funnel/auth |

---

## 2. ماتریس

| ID | سناریو | سطح | OS هدف | Pass criteria |
|----|--------|------|---------|----------------|
| SM-01 | `py_compile` روی `dana/` ماژول‌های تغییر‌یافته | L0 | dev | بدون SyntaxError |
| SM-02 | `pytest -q` (اگر dev deps هست) | L0–L1 | dev | سبز یا skip مستند |
| SM-03 | `dana doctor` بدون کرش | L1 | Win/macOS/Linux | خروجی خوانا |
| SM-04 | Start → LOCAL قابل وصل | L1 | حداقل یک OS | MCP یا health OK |
| SM-05 | Stop دستی → auto-start نمی‌شود | L1 | همان | پروسه down می‌ماند |
| SM-06 | Start مجدد بعد از Stop | L1 | همان | دوباره LOCAL OK |
| SM-07 | Second open از شورتکات → instance دوم نه | L2 | GUI OS | یک پنجره/پروسه |
| SM-08 | Quit از tray → پروسه تمام | L2 | GUI OS | بدون listener روی پورت |
| SM-09 | Funnel/PUBLIC جدا گزارش می‌شود | L2 | با Tailscale | LOCAL≠فرض غلط PUBLIC |
| SM-10 | First-run Tailscale already installed → بدون re-download اجباری | L2 | GUI | step بعدی بدون حلقه 100% |
| SM-11 | ابزار subprocess از بسته‌بندی‌شده (git/curl) | L2 | AppImage/exe | بدون OPENSSL/https url type error |
| SM-12 | کلاینت Streamable HTTP (ترجیحاً DeepSeek) یک tool call | L3 | + شبکه | بدون Session not found ماندگار |
| SM-13 | schema tool: success و error path | L2 | dev | validation client نمی‌شکند |
| SM-14 | Logs collapsible جزئیات خطا را نشان می‌دهد | L2 | GUI | جزئیات قابل باز شدن |
| SM-15 | README نمونه بدون توکن واقعی | L1 | — | review diff |

---

## 3. دستورهای کمکی

```bash
# L0
python -m compileall -q dana
pytest -q

# جستجوی subprocess مشکوک (باید env= داشته باشد یا popen_kwargs)
rg -n "subprocess\.(run|Popen)\(" dana -g '*.py'

# پورت
ss -ltn | rg 8765 || netstat -an | rg 8765
```

---

## 4. ثبت نتیجه (قالب)

```text
Date:
Version/Commit:
OS:
Level: L0/L1/L2/L3
SM-04: PASS/FAIL — notes
SM-05: ...
```

نتایج رسمی می‌توانند در issue یا `.dana/smoke-last.md` (محلی، gitignore) بمانند؛ توکن ننویس.

---

## 5. Changelog

| نسخه | تاریخ | شرح |
|------|------|------|
| 1.0.0 | 2026-11-08 | ماتریس اسموک اولیه |
