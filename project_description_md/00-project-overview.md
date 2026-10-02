# Project Overview

## 1. معرفی

Dana یک **self-hosted Python MCP Server و agent runtime** است که به یک MCP client اجازه می‌دهد روی ماشینی که Dana در آن اجرا می‌شود، عملیات واقعی انجام دهد.

Dana صرفاً یک endpoint برای چند تابع ساده نیست؛ پروژه مجموعه‌ای از لایه‌های زیر را در اختیار دارد:

1. MCP gateway و transport
2. authentication و OAuth compatibility
3. progressive tool discovery
4. tool registry و routing
5. filesystem و workspace control
6. system/process/network control
7. engineering و code intelligence
8. browser و API automation
9. documents/PDF/report generation
10. database intelligence
11. codebase memory و context optimization
12. concurrent worker runtime
13. planning و orchestration
14. security/access policy
15. Tailscale/Funnel deployment
16. Desktop Control Center
17. diagnostics، reporting و observability

## 2. مسئله‌ای که پروژه حل می‌کند

یک AI client معمولاً در محیط chat به متن محدود است. Dana یک مرز اجرایی ایجاد می‌کند:

`AI Client → MCP → Dana → Operating System / Files / Network / Applications`

در نتیجه client می‌تواند، در محدوده مجوزهای Dana و سیستم‌عامل:

- فایل‌ها را بخواند و تغییر دهد؛
- repository را تحلیل کند؛
- command اجرا کند؛
- تست و build انجام دهد؛
- Git را مدیریت کند؛
- browser را کنترل کند؛
- APIها را بررسی کند؛
- PDF و document بسازد؛
- context و memory پروژه را مدیریت کند؛
- کارهای مستقل را موازی اجرا کند.

## 3. اصول طراحی

### Self-hosted

عملیات روی دستگاه یا سروری انجام می‌شود که Dana روی آن اجرا شده است.

### Progressive Discovery

همه ابزارها در اولین handshake به client تحمیل نمی‌شوند. client ابتدا مجموعه کوچکی از discovery/orchestration tools را می‌بیند و قابلیت‌های دیگر را در صورت نیاز پیدا می‌کند.

### Stateful MCP Transport

Streamable HTTP/MCP session در یک transport process نگهداری می‌شود. ایجاد HTTP server مستقل برای هر worker ممنوع است چون می‌تواند session state را از بین ببرد.

### امنیت لایه‌ای

امنیت فقط در MCP authentication خلاصه نمی‌شود و شامل:

- token authentication
- OAuth compatibility
- trusted host/origin validation
- filesystem access policy
- OS permissions
- public exposure controls
- rate limiting
- secret handling

است.

### Cross-platform

کد برای Linux، macOS و Windows طراحی شده و setup flow باید تفاوت‌های platform را در نظر بگیرد.

## 4. ساختار repository

```text
Dana/
├── dana/                      # Backend Python package
│   ├── tools/                 # Tool implementations
│   └── security/              # HTTP/path security
├── tests/                     # Backend tests
├── ui/                        # React + Tauri desktop application
├── docs/                      # Project documentation assets
├── project_description_md/    # Technical architecture & policy docs
├── scripts/                   # Operational helper scripts
├── packaging/                 # Packaging/build resources
├── config/                    # Runtime/access configuration
├── build/                     # Build artifacts
├── dist/                      # Distribution artifacts
├── .github/                   # GitHub automation
├── Dockerfile
├── docker-compose.yml
├── install.py
├── pyproject.toml
├── requirements.txt
└── README*.md
```

## 5. Runtime defaults

- host: `127.0.0.1`
- port: `8765`
- MCP path: `/mcp`
- deployment mode: `local`
- workers: `5`
- Funnel support: enabled
- dangerous/local mutation tools: enabled by default, مگر قابل غیرفعال‌سازی
- maximum request body: 10 MiB
- default rate limit: 120 requests/minute
- auth burst: 20

## 6. Persistent authentication token

توکن authentication در صورت وجود در:

`~/.config/dana/.env`

خوانده می‌شود.

این token باید بین restartها ثابت بماند. startup نباید صرفاً به دلیل اجرای مجدد Dana آن را rotate کند.

توکن فقط با اقدام صریح کاربر یا script مخصوص rotation باید تغییر کند.

## 7. وضعیت فعلی و محدودیت‌های مهم

Funnel در Dana به صورت route canonical روی HTTPS/443 طراحی شده است. اگر روی همان machine سرویس دیگری port 443 را اشغال کرده باشد، یک listener دیگر نباید به اشتباه به عنوان Funnel مربوط به Dana تشخیص داده شود.

در چنین شرایطی باید route واقعی بررسی شود:

`HTTPS 443 → Dana local port 8765`

وجود یک Funnel روی port دیگری یا route متعلق به application دیگر به تنهایی به معنی سالم بودن public MCP endpoint Dana نیست.

## 8. معیار موفقیت

یک deployment سالم باید حداقل این زنجیره را برقرار کند:

`Dana process → local MCP /mcp → authentication → canonical public route → real MCP initialize handshake`

صرفاً HTTP 200 یا باز شدن صفحه وب، موفقیت MCP را ثابت نمی‌کند؛ connection test باید handshake واقعی MCP را بررسی کند.
