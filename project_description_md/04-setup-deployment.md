# Setup and Deployment

## 1. روش‌های نصب

### Desktop

برای کاربر معمولی روش پیشنهادی، Desktop Control Center است.

Desktop مسئول orchestration موارد زیر است:

- Tailscale installation
- Tailscale login
- Dana activation
- Funnel approval
- connection URLs
- security/token controls
- runtime control
- logs

### CLI

برای server یا کاربر terminal-oriented:

```bash
git clone https://github.com/seyed-ali-002/Dana-MCP-Server.git
cd Dana-MCP-Server
python3 -m pip install -e .
dana run
```

دستورهای مهم:

```bash
dana start
dana stop
dana restart
dana status
dana logs
dana update
dana uninstall
dana doctor
```

### Native installer

```bash
python3 install.py
```

در Windows:

```powershell
py -3 install.py
```

### Docker

Repository دارای Dockerfile و docker-compose است. Docker deployment برای محیط‌هایی که runtime containerized لازم دارند مناسب است.

## 2. Local Mode

معماری:

```text
AI Client
    ↓
Tailscale Funnel HTTPS
    ↓
127.0.0.1:8765
    ↓
Dana
```

Public URL:

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

## 3. Server Mode

معماری:

```text
Internet
   ↓
Nginx / Caddy / Apache
   ↓
127.0.0.1:<DANA_PORT>
   ↓
Dana
```

Server Mode برای VPS/dedicated server طراحی شده است.

## 4. Reverse proxy

Dana می‌تواند proxy موجود را detect کند.

ترتیب مفهومی:

1. domain دریافت شود.
2. Nginx/Caddy/Apache تشخیص داده شود.
3. config موجود backup شود.
4. Dana route اضافه شود.
5. config validate شود.
6. service reload شود.
7. endpoint تست شود.

اگر Nginx نصب نباشد و server deployment به reverse proxy نیاز داشته باشد، Caddy می‌تواند به عنوان گزینه fallback استفاده شود.

## 5. Nginx

در tokenized deployment route مفهومی:

`/<TOKEN>/mcp → http://127.0.0.1:<PORT>/mcp`

header authentication می‌تواند توسط proxy به upstream منتقل شود.

## 6. Caddy

Caddy برای deploymentهایی که مدیریت HTTPS ساده‌تری می‌خواهند مناسب است.

در حالت tokenized route باید فقط path مورد نظر Dana به upstream متصل شود.

## 7. Apache

Apache نیز با ProxyPass/ProxyPassReverse قابل استفاده است.

## 8. Setup state machine

```text
Initial
  │
  ├── Tailscale missing ──> Install
  │
  ▼
Tailscale installed
  │
  ├── backend not running ──> Login/Start
  │
  ▼
Tailscale authenticated
  │
  ├── Funnel inactive ──> Funnel approval/configuration
  │
  ▼
Funnel active
  │
  ▼
Dana start
  │
  ▼
Local MCP test
  │
  ▼
Public MCP test
  │
  ▼
Ready
```

## 9. Pending browser flow

Setup API ممکن است پاسخ pending بدهد:

- `pending=true`
- `auth_url=<browser URL>`

Desktop باید URL را باز کند و سپس status را polling کند.

پس از تکمیل auth، Setup باید به مرحله بعد برود.

## 10. Tailscale installer fallback

Installer نباید فقط به یک URL وابسته باشد.

Fallback chain:

```text
Official installer
      ↓
Official package index
      ↓
Configured mirror
      ↓
Static mirror
      ↓
GitHub release artifact
```

متغیر optional:

`DANA_TAILSCALE_MIRROR`

## 11. Funnel ownership

Dana باید فقط routeی را که متعلق به runtime خودش است مدیریت کند.

به طور خاص:

- route مربوط به application دیگر نباید به عنوان Dana شناخته شود.
- stop کردن Dana نباید routeهای unrelated را خراب کند.
- startup watchdog باید فقط route canonical مورد انتظار را restore کند.

## 12. Shutdown

در Desktop lifecycle، shutdown باید:

1. Dana process را stop کند.
2. Funnel route متعلق به Dana را stop کند.
3. routeهای unrelated را دستکاری نکند.
4. PID/runtime state را پاک کند.

## 13. Doctor

برای diagnostic:

```bash
dana doctor
```

برای URL کامل:

```bash
dana doctor --show-url
```

برای JSON:

```bash
dana doctor --json
```

Doctor باید مواردی مانند:

- version/commit
- Python
- environment
- files
- dependencies
- health
- OAuth
- Tailscale
- Funnel
- deployment mode
- connector URL

را بررسی کند.

## 14. Production checklist

- [ ] token persistent و secret است
- [ ] OS permissions محدود و آگاهانه است
- [ ] allowed/denied paths تنظیم شده
- [ ] local MCP handshake موفق است
- [ ] public route canonical است
- [ ] 443 به Dana متصل است
- [ ] trusted host شامل hostname واقعی است
- [ ] reverse proxy config معتبر است
- [ ] logs بدون credential حساس هستند
- [ ] backup config قبل از تغییر موجود است
- [ ] tests اجرا شده‌اند
- [ ] version/tag مطابق release policy است
