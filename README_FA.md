# دانا MCP Server

چت‌بات‌های هوش مصنوعی را به Agentهایی تبدیل کنید که روی **کامپیوتر خودتان** با فایل، کد و ابزارها کار می‌کنند.

🇬🇧 [English](README.md) · 🇮🇷 این صفحه

---

## دانا چه می‌کند؟

دانا روی سیستم شما اجرا می‌شود. Clientهای سازگار (ChatGPT، Claude، Grok و …) از طریق MCP وصل می‌شوند و می‌توانند فایل بخوانند/بنویسند، دستور اجرا کنند، Git و ابزارهای دیگر را به‌کار بگیرند.

هسته پروژه رایگان و self-hosted است؛ کنترل زیرساخت با شماست.

---

## شروع سریع (دسکتاپ — پیشنهادی)

1. آخرین نسخه **Dana Desktop** را از  
   [GitHub Releases](https://github.com/seyed-ali-002/Dana-MCP-Server/releases/latest) برای سیستم‌عامل خود دانلود کنید.
2. برنامه را باز کنید و به **Setup** بروید.
3. **Install & Activate** (یا اگر Tailscale نصب است **Activate Dana**) را بزنید.

دانا این کارها را انجام می‌دهد:

1. در صورت نیاز **Tailscale** را دانلود و نصب می‌کند (اگر یک منبع خطا بدهد، mirror دیگر را امتحان می‌کند).
2. وقتی لازم باشد از سیستم **دسترسی ادمین** می‌خواهد (UAC ویندوز، پنجره رمز لینوکس/مک).  
   دانا رمز را ذخیره نمی‌کند.
3. **لینک ورود Tailscale یا تأیید Funnel** را در همان پنجره نشان می‌دهد — کپی کنید یا در مرورگر باز کنید.
4. سرور MCP محلی را روشن می‌کند و در صورت تأیید شما Funnel را فعال می‌کند.

![Setup](docs/images/dana-desktop-setup.svg)

![دانلود](docs/images/dana-download-progress.svg)

![لینک ورود](docs/images/dana-auth-link.svg)

### سه بخش برنامه

| بخش | کاربرد |
|---|---|
| **Setup** | نصب Tailscale، ورود، روشن کردن دانا، Funnel |
| **Control** | Start/Stop، کپی URL، توکن، تنظیمات پیشرفته اختیاری |
| **Logs** | سمت چپ: نصب و خطاها · سمت راست: فعالیت ابزارهای دانا |

### آدرس MCP

محلی:

```text
http://127.0.0.1:8765/<TOKEN>/mcp
```

عمومی (بعد از Funnel):

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

این آدرس را در Client خود وارد کنید. در Control می‌توانید **Test connection** بزنید.

### رمز ادمین

نصب Tailscale یا Funnel ممکن است به دسترسی مدیر نیاز داشته باشد:

- **ویندوز** — تأیید UAC
- **لینوکس** — پنجره polkit یا `sudo`
- **مک** — پنجره رمز سیستم

اگر دانلود خودکار شکست خورد، **Open Tailscale download** را بزنید، دستی نصب کنید، بعد **Continue after install**.

---

## نصب از ترمینال (اختیاری)

```bash
git clone https://github.com/seyed-ali-002/Dana-MCP-Server.git
cd Dana-MCP-Server
python3 -m pip install -e .
dana gui
```

فقط سرور:

```bash
python3 -m dana.main
```

---

## اتصال Client

1. Setup را تا فعال شدن Funnel (یا فقط URL محلی) تمام کنید.
2. از **Control → Endpoints** آدرس را کپی کنید.
3. در ChatGPT / Claude / Grok به‌عنوان MCP server اضافه کنید.

جزئیات بیشتر: [project_description_md/](project_description_md/).

---

## نکات امنیتی

- توکن احراز هویت مثل رمز عبور است.
- Funnel دانا را روی HTTPS عمومی ماشین tailnet شما منتشر می‌کند؛ فقط اگر لازم است فعال کنید.
- بستن برنامه دسکتاپ runtime دانا را متوقف می‌کند؛ مسیر Funnel عمداً دست نخورده می‌ماند.

---

## تشکر

تشکر ویژه از [محسن صمدی‌نژاد](https://github.com/samadinejad).
