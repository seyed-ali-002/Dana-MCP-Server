# 12 — AI Context Pack (ترتیب بارگذاری زمینه)

> **هدف:** اگر مدل فقط چند فایل می‌تواند بخواند، **همین ترتیب** را رعایت کند.  
> **نسخه سند:** 1.0.0 — 2026-11-08

---

## سطح A — حداقل اجباری (همیشه)

1. `project_description_md/11-ai-guardrails.md`
2. `project_description_md/10-ai-implementation-guide.md`
3. `project_description_md/09-srs.md` (بخش مرتبط با تسک)
4. `project_description_md/08-development-roadmap.md` (نسخهٔ جاری هدف)

## سطح B — بر اساس نوع تسک

| نوع تسک | فایل‌های اضافه |
|---------|----------------|
| MCP / tools / schema | `02-mcp-auth-network.md`, `dana/mcp_result_format.py`, `dana/server.py` |
| Funnel / install / network | `04-setup-deployment.md`, `dana/setup.py`, `dana/installer.py`, `dana/tailscale.py` |
| UI دسکتاپ | `05-desktop-ui-testing.md`, `ui/src/App.tsx`, `dana/setup_service.py` |
| امنیت path/shell | `dana/security/path_policy.py`, `dana/tools/agent.py` |
| بیلد / release | `06-versioning-release.md`, `packaging/`, `.github/workflows/gui-build.yml` |
| معماری کلی | `00-project-overview.md`, `01-architecture.md` |

## سطح C — کاربرنهایی

- `README_FA.md` یا `README.md` فقط وقتی پیام یا flow کاربر عوض می‌شود.

## سطح D — ممنوع به‌عنوان منبع حقیقت

- فایل‌های موقت `.dana/.report-*`
- `node_modules`, `.venv`, artifactهای build
- commit messageهای قدیمی بدون خواندن کد فعلی

---

## جملهٔ شروع پیشنهادی برای پرامپت سیستم/کاربر به AI

```text
You are working on Dana MCP Server. Follow project_description_md/11-ai-guardrails.md
and 10-ai-implementation-guide.md. Map work to SRS IDs in 09-srs.md and roadmap 08.
Prefer minimal diffs. Never commit secrets. Scrub subprocess env. Keep MCP stdout clean.
```

---

## Changelog

| نسخه | تاریخ | شرح |
|------|------|------|
| 1.0.0 | 2026-11-08 | بستهٔ ترتیب زمینه برای مدل‌ها |
