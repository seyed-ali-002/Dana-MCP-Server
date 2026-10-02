# Dana MCP Server — Project Documentation

این پوشه مرجع فنی و اجرایی پروژه **Dana MCP Server** است. هدف آن ثبت معماری، اجزای نرم‌افزار، پروتکل MCP، احراز هویت، شبکه و Tailscale، رابط دسکتاپ، ابزارها، تست‌ها، استقرار و سیاست انتشار است.

## وضعیت مبنا

- زبان اصلی backend: Python 3.11+
- پروتکل اصلی: MCP
- HTTP runtime: FastAPI / Uvicorn و MCP Streamable HTTP
- رابط دسکتاپ: React + TypeScript + Vite + Tauri 2
- پورت محلی پیش‌فرض: `8765`
- مسیر MCP: `/mcp`
- حالت‌های استقرار: Local و Server
- احراز هویت Local Mode: توکن پایدار و URL توکن‌دار
- شبکه عمومی Local Mode: Tailscale Funnel
- معماری ابزارها: registry + progressive discovery + router
- اجرای همزمان: bounded async workers و dependency-aware plans
- مستندات عمومی اصلی: `README.md`, `README_EN.md`, `README_FA.md`

## فهرست مستندات

| فایل | موضوع |
|---|---|
| `00-project-overview.md` | هدف، دامنه، اصول طراحی و وضعیت پروژه |
| `01-architecture.md` | معماری backend، MCP، runtime و data flow |
| `02-mcp-auth-network.md` | MCP، احراز هویت، OAuth، Tailscale و Funnel |
| `03-capabilities.md` | دسته‌بندی کامل قابلیت‌ها و ابزارها |
| `04-setup-deployment.md` | نصب، Setup، Local/Server، reverse proxy و عملیات |
| `05-desktop-ui-testing.md` | Desktop UI، API setup، تست و diagnostics |
| `06-versioning-release.md` | Semantic Versioning، tag و GitHub Release |
| `07-development-guidelines.md` | قواعد توسعه، تغییر، تست و نگهداری |

## اصل مهم امنیتی

URL توکن‌دار Dana یک credential محسوب می‌شود. توکن نباید در issue، screenshot، log عمومی، README یا repository منتشر شود.

## اصل مهم توسعه

هر تغییر باید با وضعیت فعلی repository هماهنگ شود، تست مناسب داشته باشد و در صورت تغییر رفتار عمومی، مستندات مربوطه نیز به‌روزرسانی شوند.
