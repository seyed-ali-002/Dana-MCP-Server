# Architecture

## 1. نمای کلی

```text
                    ┌──────────────────────┐
                    │      AI Client       │
                    │ ChatGPT / Claude /   │
                    │ Grok / MCP Clients   │
                    └──────────┬───────────┘
                               │ MCP / HTTP
                               ▼
                    ┌──────────────────────┐
                    │    Public Boundary  │
                    │ Tailscale Funnel or │
                    │ Reverse Proxy       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Dana MCP Gateway │
                    │ FastAPI / MCP /      │
                    │ Auth / HTTP Security│
                    └──────────┬───────────┘
                               │
             ┌─────────────────┼──────────────────┐
             ▼                 ▼                  ▼
      Tool Discovery      Optimization       Runtime/Workers
             │                 │                  │
             └─────────────────┼──────────────────┘
                               ▼
                       ┌───────────────┐
                       │ Tool Registry │
                       └───────┬───────┘
                               │
       ┌────────────┬──────────┼──────────┬─────────────┐
       ▼            ▼          ▼          ▼             ▼
   Filesystem    System     Engineering Browser      Docs/PDF
       │            │          │          │             │
       └────────────┴──────────┼──────────┴─────────────┘
                               ▼
                         Local Machine
```

## 2. Python package

### `dana/config.py`

مرکز configuration است. Settings با Pydantic Settings ساخته می‌شود و environment variables با prefix `DANA_` خوانده می‌شوند.

متغیرهای کلیدی:

- `DANA_HOST`
- `DANA_PORT`
- `DANA_MCP_PATH`
- `DANA_AUTH_TOKEN`
- `DANA_PUBLIC_HOST`
- `DANA_PUBLIC_PORT`
- `DANA_PUBLIC_SCHEME`
- `DANA_DEPLOYMENT_MODE`
- `DANA_WORKERS`
- `DANA_RATE_LIMIT_RPM`
- `DANA_AUTH_BURST`
- `DANA_ALLOWED_ORIGINS`
- `DANA_ALLOWED_PATHS`
- `DANA_DENIED_PATHS`
- `DANA_TAILSCALE_FUNNEL_ENABLED`
- `DANA_TAILSCALE_FUNNEL_CHECK_SECONDS`

### `dana/server.py`

MCP/HTTP application و middlewareهای امنیتی را تشکیل می‌دهد.

مسئولیت‌های مهم:

- mount/serve کردن MCP
- authentication
- trusted host/origin handling
- tokenized route
- Tailscale hostname detection
- request validation
- health/diagnostic endpoints
- ثبت tool registry

### `dana/main.py`

Entry point اجرای server است.

مسئولیت‌ها:

- آماده‌سازی logging
- PID/runtime files
- Uvicorn
- start/stop lifecycle
- Funnel manager lifecycle

### `dana/tailscale.py`

مالک route مربوط به Dana روی Tailscale Funnel است.

منطق اصلی باید به شکل زیر باشد:

`tailscale funnel --https=443 ... 8765`

هدف این است که public HTTPS origin تمام مسیرهای مورد نیاز Dana را روی یک origin canonical ارائه کند.

### `dana/setup.py`

Control plane نصب و فعال‌سازی است.

مسئولیت‌ها:

- تشخیص platform
- نصب Tailscale
- browser login
- Funnel approval
- start/stop Dana
- connection test
- status
- token management
- setup logging
- privileged command handling

### `dana/setup_service.py`

HTTP API محلی برای Desktop Control Center.

نمونه endpointها:

- `/api/setup/status`
- `/api/setup/auth-flow`
- `/api/setup/usage`
- `/api/setup/logs`
- `/api/setup/config`
- `/api/setup/connection-test`
- `/api/setup/install-tailscale`
- `/api/setup/login-tailscale`
- `/api/setup/enable-funnel`

### `dana/runtime.py`

Runtime task orchestration.

ویژگی‌ها:

- bounded workers
- task states
- dependency graph
- concurrent execution
- compact task results
- workspace context

### `dana/deployment.py`

Server Mode reverse proxy integration.

Proxyهای پشتیبانی‌شده:

- Nginx
- Caddy
- Apache

این لایه backup/configuration/reload را مدیریت می‌کند و route مربوط به Dana را با توجه به domain، port و token تولید می‌کند.

## 3. Tool architecture

ابزارها در `dana/tools/` قرار دارند و از registry مرکزی discover می‌شوند.

گروه‌های مهم:

- access policy
- advanced intelligence
- agent/planning
- codebase memory
- context engine
- design/UI
- documents
- engineering
- filesystem
- formatting
- intelligence
- local agent
- memory
- optimization
- performance
- principal engineering
- runtime orchestration
- system
- token analytics
- tool catalog
- web quality/debugging

## 4. Progressive discovery

در حالت optimized، client در شروع فقط entry pointهای محدودی دریافت می‌کند.

نمونه:

- `dana_search_tools`
- `dana_list_tools`
- `dana_help_tool`
- `dana_call_tool`
- `dana_batch_call`
- `dana_capabilities`
- `dana_worker_status`
- `dana_runtime_health`

سپس client قابلیت مورد نیاز را search و invoke می‌کند.

برای compatibility با clientهایی که full registry می‌خواهند:

`DANA_PROGRESSIVE_TOOLS=0`

## 5. Optimization

Dana برای کاهش context و latency از موارد زیر استفاده می‌کند:

- safe-read cache
- batch parallelism
- compact results
- context compression
- deduplication
- codebase indexing
- delta context
- file summaries
- token analytics
- tool cost tracking

برای خاموش کردن cache:

`DANA_TOOL_CACHE=0`

## 6. Concurrency

Worker count با `DANA_WORKERS` کنترل می‌شود.

Workerها transport session را جایگزین نمی‌کنند. transport اصلی باید session state را حفظ کند.

برای کارهای dependency-aware، plan به DAG تبدیل می‌شود:

```text
A ──┐
    ├──> C ──> D
B ──┘
```

A و B می‌توانند همزمان اجرا شوند و C بعد از هر دو شروع می‌شود.

## 7. Failure isolation

خطا در یک tool نباید کل MCP server را از کار بیندازد.

هر layer باید failure را به result قابل تحلیل تبدیل کند:

`tool exception → compact error → MCP result → client`

Runtime نیز باید taskهای مستقل را تا حد امکان از هم جدا نگه دارد.

## 8. Observability

Dana اطلاعات زیر را تولید می‌کند:

- setup logs
- runtime logs
- tool execution duration
- operation counts
- worker state
- token usage
- health state
- report.html

اطلاعات runtime و telemetry محلی نباید وارد Git شوند.
