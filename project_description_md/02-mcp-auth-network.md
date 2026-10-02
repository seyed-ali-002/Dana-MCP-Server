# MCP, Authentication and Network

## 1. MCP endpoint

پورت محلی پیش‌فرض:

`127.0.0.1:8765`

مسیر canonical:

`/mcp`

Local tokenized URL:

```text
http://127.0.0.1:8765/<TOKEN>/mcp
```

Public Tailscale URL:

```text
https://<tailscale-host>/<TOKEN>/mcp
```

## 2. چرا URL tokenized وجود دارد؟

برخی MCP clients در حالت custom connector یک URL را به عنوان credential/endpoint می‌پذیرند و کنترل محدودی روی header دارند.

بنابراین Dana اجازه می‌دهد credential در path قرار گیرد:

`/<TOKEN>/mcp`

در backend این token باید به authentication استاندارد Dana تبدیل شود.

## 3. Bearer authentication

Dana علاوه بر URL tokenized از:

```http
Authorization: Bearer <TOKEN>
```

پشتیبانی می‌کند.

این حالت برای clientهایی مناسب است که می‌توانند header سفارشی ارسال کنند.

## 4. Persistent token

منبع persistent:

`~/.config/dana/.env`

کلید:

`DANA_AUTH_TOKEN`

قاعده:

- startup → token موجود حفظ شود
- restart → token تغییر نکند
- explicit rotate → token جدید تولید شود
- revoke → token قبلی invalid شود
- tokenized URLs قدیمی پس از rotation معتبر نباشند

## 5. OAuth compatibility

Dana برای MCP clientهایی که OAuth discovery/PKCE انتظار دارند، routeهای compatibility ارائه می‌کند و access token به credential اصلی Dana متصل است.

OAuth lifetime در configuration طولانی تنظیم شده تا connector مجبور به reconnect غیرضروری نشود.

این compatibility به معنی استفاده از یک identity provider مستقل برای هر user نیست؛ token اصلی Dana منبع credential است.

## 6. MCP handshake

Connection test واقعی باید MCP JSON-RPC initialize را بررسی کند.

توالی مفهومی:

```text
Client
  │
  ├── initialize
  │
  ▼
Dana MCP transport
  │
  ├── validate host/origin
  ├── validate authentication
  ├── create/restore MCP session
  │
  ▼
initialize response
```

HTTP 200 به تنهایی کافی نیست.

## 7. Trusted Host / DNS rebinding

در public Tailscale deployments، hostname واقعی باید در trusted host/origin policy شناخته شود.

Dana hostname را می‌تواند از:

`tailscale status --json`

تشخیص دهد.

همچنین `DANA_PUBLIC_HOST` می‌تواند public hostname را صریحاً مشخص کند.

این موضوع برای جلوگیری از خطاهایی مانند:

`421 Misdirected Request`

اهمیت دارد.

## 8. Tailscale Funnel

Local Mode از Tailscale Funnel برای public HTTPS استفاده می‌کند:

```text
Internet
   │
   ▼
Tailscale Funnel :443
   │
   ▼
127.0.0.1:8765
   │
   ▼
Dana /mcp
```

route canonical مورد انتظار:

`HTTPS 443 → Dana 8765`

اگر port 443 به سرویس دیگری متصل باشد، URL Dana نباید سالم فرض شود.

## 9. Funnel status

Dana نباید صرفاً با دیدن یک listener عمومی نتیجه بگیرد Funnel سالم است.

باید بررسی شود که route مربوط به port 443 واقعاً به port Dana اشاره می‌کند.

مثلاً:

- 443 → 2775 = route مربوط به Dana نیست
- 8443 → 8765 = به تنهایی public canonical route Dana نیست
- 443 → 8765 = route مورد انتظار Dana

## 10. Tailscale installation fallback

setup installer از چند مسیر fallback استفاده می‌کند:

1. official installer
2. official static package index
3. configured mirror
4. static mirror
5. GitHub release artifact

Architecture mapping برای archive نیز انجام می‌شود، از جمله:

- x86_64 / amd64
- aarch64 / arm64
- armv7l / arm
- 386
- mips variants
- riscv64
- geode

Static installation در صورت نیاز `tailscale` و `tailscaled` را نصب و در سیستم‌های دارای systemd سرویس را فعال می‌کند.

## 11. Privileged commands

برخی عملیات نیازمند privilege سیستم‌عامل هستند:

- نصب package
- تغییر service
- Funnel configuration
- reverse proxy configuration

Dana نباید password sudo را در configuration، environment، logs یا code ذخیره کند.

مسیرهای مجاز برای privilege:

- root execution
- interactive sudo
- graphical pkexec در محیط مناسب
- fallback به sudo

## 12. Browser authentication

Tailscale login ممکن است browser approval بخواهد.

Setup state machine:

```text
not installed
   ↓
install
   ↓
installed / not authenticated
   ↓
browser login
   ↓
authenticated
   ↓
Funnel approval
   ↓
Funnel active
   ↓
Dana ready
```

GUI باید pending state را polling کند و بعد از تکمیل authentication به صورت خودکار ادامه دهد.

## 13. Connection troubleshooting

ترتیب بررسی:

1. process Dana
2. local port 8765
3. local tokenized MCP URL
4. MCP initialize handshake
5. Tailscale backend
6. hostname
7. Funnel 443 route
8. public tokenized URL
9. public MCP initialize handshake

این ترتیب از اشتباه گرفتن مشکل شبکه با مشکل MCP جلوگیری می‌کند.
