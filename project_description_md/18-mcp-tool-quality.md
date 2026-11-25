# 18 — کیفیت ابزار MCP (Dana-adapted mcp-builder)

> **وضعیت:** زنده  
> **نسخه سند:** 1.0.0  
> **تاریخ:** 2026-11-25  
> **منابع الهام:** [anthropics/skills mcp-builder](https://github.com/anthropics/skills/tree/main/skills/mcp-builder) — شخصی‌سازی‌شده برای Dana

---

## 1. هدف

بالا بردن قابلیت‌کشف و قابلیت‌اجرای ابزارهای Dana توسط مدل‌ها **بدون** بازنویسی معماری (UI، Funnel، SuperMCP).

## 2. قواعد Dana (اجباری برای ابزار جدید / بازنویسی)

| قاعده | پیاده‌سازی |
|--------|------------|
| توضیحات دقیق و منطبق با رفتار | docstring روی `@mcp.tool` |
| Annotations | `READ_ONLY` / `DESTRUCTIVE` / `MUTATING` / `OPEN_WORLD` از `dana/tools/mcp_quality.py` |
| خطای actionable | `actionable_error(...)` با next_steps و related_tools |
| لیست‌های بزرگ | `limit`/`offset` + در صورت نیاز `paginate()` |
| مسیر فایل | همیشه `require_path` |
| subprocess | همیشه `env=clean_subprocess_env()` |
| شکست واقعی | `raise` نه success با متن خطا (FR-016) |
| stdout MCP | بدون `print` روی مسیر سرور |

## 3. ماژول‌های مرتبط

| فایل | نقش |
|------|------|
| `dana/tools/mcp_quality.py` | annotations، pagination، actionable_error |
| `dana/mcp_result_format.py` | ensure_structured / error_result برای کلاینت‌های سخت‌گیر |
| `dana/tools/tool_catalog.py` | enrich شامل annotations در discovery |
| `dana/tools/agent_planning.py` | نمونهٔ ابزار با کیفیت |
| `dana/tools/filesystem.py` | list_directory با limit/offset |

## 4. ارزیابی (اختیاری)

برای رگرسیون کیفیت عامل، ۱۰ سؤال read-only مستقل بسازید که چند ابزار Dana را زنجیره کنند (الگوی evaluation در mcp-builder).

## 5. Changelog

| نسخه | تاریخ | شرح |
|------|------|------|
| 1.0.0 | 2026-11-25 | شخصی‌سازی mcp-builder برای Dana + بازیابی mcp_result_format |
