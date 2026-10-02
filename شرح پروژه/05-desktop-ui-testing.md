# Desktop UI, Setup API and Testing

## 1. Desktop stack

UI فعلی در `ui/` قرار دارد.

Stack:

- React 19
- TypeScript
- Vite
- Tauri 2
- @tauri-apps/api
- Tauri opener plugin

Build:

```bash
cd ui
npm run build
```

Build فعلی از TypeScript compilation و سپس Vite build تشکیل می‌شود.

## 2. Desktop responsibilities

Control Center برای عملیات زیر طراحی شده است:

### Setup

- detect current machine state
- install Tailscale
- authenticate Tailscale
- activate Dana
- approve/enable Funnel

### Dashboard

نمایش وضعیت:

- Dana
- Tailscale
- Funnel
- runtime
- usage

### Connections

- local tokenized URL
- public tokenized URL
- copy
- connection test
- MCP handshake result

### Runtime

- start
- stop
- restart/status
- local listener state

### Security

- current token
- custom token
- apply token
- revoke/replace
- path access controls

### Logs

نمایش setup/runtime diagnostics.

## 3. Setup HTTP API

`dana/setup_service.py` یک local HTTP service ارائه می‌کند.

نمونه endpointها:

```text
GET  /api/setup/status
GET  /api/setup/auth-flow
GET  /api/setup/usage
GET  /api/setup/logs
GET  /api/setup/download
GET  /api/setup/config
GET  /api/setup/connection-test

POST /api/setup/install-tailscale
POST /api/setup/login-tailscale
POST /api/setup/enable-funnel
POST /api/setup/security/revoke-token
POST /api/setup/security/token
POST /api/setup/config
```

## 4. Connection test

Connection test باید با endpoint واقعی MCP انجام شود.

حداقل checks:

1. URL قابل دسترسی است.
2. status مناسب است.
3. content type مناسب است.
4. MCP initialize request ارسال می‌شود.
5. پاسخ JSON-RPC/MCP معتبر است.
6. error body به صورت قابل تشخیص گزارش می‌شود.

GET ساده به `/mcp` تست کافی نیست.

## 5. Backend tests

Suite در `tests/` قرار دارد.

دسته‌های مهم:

- setup
- connector
- token
- tokenized OAuth
- path policy
- tool registry
- runtime/concurrency
- deployment
- doctor
- documents
- memory
- performance
- launcher
- desktop control

اجرای کامل:

```bash
pytest -q
```

## 6. Build validation

Backend syntax:

```bash
python3 -m py_compile dana/http.py
```

UI:

```bash
cd ui
npm run build
```

## 7. Test strategy

هر تغییر را حداقل در سه سطح بررسی کنید:

### Unit

منطق مستقل.

### Integration

تعامل بین setup/server/auth/tool registry.

### Runtime

listener، MCP handshake، Tailscale/Funnel و connection URL.

## 8. مهم‌ترین regressionها

### 421 Misdirected Request

علت محتمل: TrustedHost یا DNS rebinding policy hostname واقعی Tailscale را قبول نمی‌کند.

راه‌حل:

- تشخیص hostname واقعی
- اضافه کردن به allowed hosts/origins
- استفاده صحیح از public host

### 404 روی public MCP

علت محتمل: Funnel روی port/path دیگری قرار گرفته است.

بررسی:

`tailscale funnel status`

هدف:

`443 → 8765`

### Authentication failure

بررسی:

- persistent token
- tokenized path
- Authorization header
- environment precedence
- token rotation

### Connection failed در client

به ترتیب:

1. local endpoint
2. real MCP initialize
3. public endpoint
4. hostname
5. Funnel route
6. proxy/auth

## 9. Current baseline test result

آخرین baseline ثبت‌شده در پروژه:

- backend tests: **126 passed, 1 warning**
- UI build: موفق
- warning شناخته‌شده: deprecation مربوط به استفاده از httpx با Starlette TestClient و پیشنهاد استفاده از httpx2 در آینده

این عدد باید با اجرای مجدد suite در releaseهای بعدی به‌روزرسانی شود.

## 10. Diagnostic artifacts

فایل‌هایی مانند:

- `report.html`
- logs
- runtime databases
- build artifacts

باید با توجه به `.gitignore` و سیاست repository مدیریت شوند.

Credential نباید در artifactهای عمومی باقی بماند.

## 11. UI regression policy

هر تغییر در UI باید:

1. TypeScript build شود.
2. interactionهای اصلی بررسی شوند.
3. setup flow بررسی شود.
4. connection URL generation بررسی شود.
5. auth modal/polling بررسی شود.
6. در صورت تغییر API، backend tests نیز اجرا شوند.
