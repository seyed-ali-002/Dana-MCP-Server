# دانا MCP Server

چت‌بات‌های هوش مصنوعی را به Agentهایی تبدیل کنید که روی **کامپیوتر خودتان** با فایل، کد و ابزارها کار می‌کنند.

🇬🇧 **English:** [README.md](README.md) · 🇮🇷 **فارسی:** این صفحه

---

## دانا چیست؟

دانا یک MCP Server خودمیزبان (self-hosted) است. Clientهای سازگار (ChatGPT، Claude، Grok و …) به آن وصل می‌شوند و می‌توانند روی همان ماشینی که دانا اجرا می‌شود کار واقعی انجام دهند.

---

## ۱. دسکتاپ (پیشنهادی)

1. آخرین بیلد را از [GitHub Releases](https://github.com/seyed-ali-002/Dana-MCP-Server/releases/latest) دانلود کنید.
2. **Dana** را باز کنید → **Setup**.
3. **Install & Activate** (یا **Activate Dana**) را بزنید.

دانا یک فلوی چهارمرحله‌ای ثابت دارد و هیچ مرحله‌ای را دوباره انجام نمی‌دهد:

۱. **نصب Tailscale** — یک‌بار دانلود و نصب می‌شود (ممکن است دسترسی ادمین لازم باشد؛ رمز ذخیره نمی‌شود).
۲. **ورود به Tailscale** — در صورت نیاز صفحه ورود در مرورگر باز می‌شود.
۳. **فعال‌سازی Funnel** — تأییدیه افشای عمومی را بزنید و در صورت نیاز Funnel را در مرورگر تأیید کنید.
۴. **اجرای دانا** — سرور MCP محلی روشن می‌شود و Endpoint عمومی فعال می‌گردد.

دانا نصب‌شده بودن Tailscale، متصل بودن حساب و فعال بودن مسیر Funnel را تشخیص می‌دهد؛ بنابراین اجرای دوباره فلوی Setup فقط مراحل باقی‌مانده را انجام می‌دهد.

بسته‌های دسکتاپ بعد از هر push موفق به `main` به‌صورت خودکار ساخته می‌شوند.

Control Center ظاهر مرتب دسکتاپ دارد: تم **تیره/روشن** با آیکون ماه و خورشید، و سه رنگ تاکیدی **آبی / سبز / قرمز**.

### پنل‌ها

| پنل | کاربرد |
|---|---|
| **Setup** | نصب Tailscale، ورود، فعال‌سازی Funnel، اجرای دانا |
| **Control** | Start/Stop، کپی URL، توکن، تنظیمات پیشرفته |
| **Logs** | خطاها و نصب · فعالیت ابزارها |

### آدرس MCP

محلی:

```text
http://127.0.0.1:8765/<TOKEN>/mcp
```

عمومی (Funnel):

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

URL توکن‌دار را مثل رمز نگه دارید.

---

## ۲. ترمینال / CLI

### نصب پکیج

```bash
git clone https://github.com/seyed-ali-002/Dana-MCP-Server.git
cd Dana-MCP-Server
python3 -m pip install -e .
```

ویندوز:

```powershell
py -3 -m pip install -e .
```

### اجرای کامل

```bash
dana run
```

معادل‌ها: `dana up`، `dana start-all`. اگر Docker در دسترس باشد ترجیح داده می‌شود و در غیر این صورت Runtime بومی استفاده می‌شود. اجبار به Docker:

```bash
export DANA_RUNTIME_BACKEND=docker
```

### دستورات روزمره

```bash
dana start
dana stop
dana restart
dana status
dana logs
dana update
dana uninstall
dana gui
```

گام‌به‌گام Docker:

```bash
dana install
dana connect
```

### نصب Native (بدون Docker)

```bash
python3 install.py          # Linux / macOS
py -3 install.py            # Windows
```

### فقط سرور

```bash
python3 -m dana.main
```

### Tailscale و Funnel از CLI

نصب Tailscale (اگر از دسکتاپ نصب نشده):

```bash
# Linux
curl -fsSL https://tailscale.com/install.sh | sh

# macOS
brew install --cask tailscale

# Windows — از https://tailscale.com/download
```

ورود و بررسی اتصال:

```bash
sudo tailscale up
tailscale status
```

فعال‌سازی Funnel برای پورت Dana (ممکن است به دسترسی ادمین نیاز باشد):

```bash
sudo tailscale funnel --https=443 --yes --bg 8765
tailscale funnel status
sudo tailscale funnel reset
```

نمایش URL کامل توکن‌دار:

```bash
dana doctor --show-url
```

---

## ۳. حالت‌های استقرار

**Local Mode** — کامپیوتر شخصی + Tailscale Funnel  
**Server Mode** — سرور پشت Nginx / Caddy / Apache روی مسیر `/mcp`

---

## ۴. اتصال Client

1. Setup دسکتاپ یا `dana run` را تمام کنید.
2. URL را از **Control** یا `dana doctor --show-url` کپی کنید.
3. در ChatGPT / Claude / Grok به‌عنوان MCP اضافه کنید.

---

بستن پنجره دسکتاپ دانا را به **سینی سیستم (tray)** می‌فرستد؛ خروج کامل از منوی tray است. آیکون به‌روزرسانی در نوار بالا آخرین نسخه GitHub Releases را بررسی می‌کند.

## ۵. امنیت

- محدودیت مسیر فایل: `config/access_policy.json`
- چرخش توکن از Control یا `python3 scripts/regenerate_token.py`
- Funnel را فقط در صورت نیاز فعال کنید

---

## تشکر

تشکر ویژه از [محسن صمدی‌نژاد](https://github.com/samadinejad).
