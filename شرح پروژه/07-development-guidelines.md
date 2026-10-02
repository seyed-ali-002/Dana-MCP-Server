# Development Guidelines

## 1. اصل تغییر کم‌ریسک

قبل از تغییر:

1. کد فعلی را بخوان.
2. dependency و callerها را پیدا کن.
3. behavior فعلی را مشخص کن.
4. test موجود را پیدا کن.
5. کوچک‌ترین تغییر لازم را اعمال کن.

از بازنویسی غیرضروری فایل‌های بزرگ پرهیز شود.

## 2. API compatibility

هر تغییری در موارد زیر potentially breaking است:

- MCP endpoint
- tool name
- tool input schema
- authentication behavior
- tokenized URL
- OAuth discovery
- setup API
- environment variable semantics
- Desktop ↔ setup service contract

قبل از تغییر باید compatibility بررسی شود.

## 3. Authentication rules

- token در log چاپ نشود.
- token در screenshot/README/issue قرار نگیرد.
- token بدون درخواست صریح rotate نشود.
- persistent token بر startup حفظ شود.
- revoke باید credential قبلی را invalid کند.

## 4. Privilege rules

- sudo password ذخیره نشود.
- privilege فقط برای عملیات لازم استفاده شود.
- عملیات privileged باید نتیجه و خطای قابل تشخیص داشته باشد.
- routeهای متعلق به application دیگر نباید دستکاری شوند.

## 5. Tailscale rules

Funnel باید به عنوان network boundary مدیریت شود.

قبل از اعلام public readiness:

`443 → Dana port`

باید verify شود.

وجود Tailscale backend یا یک Funnel unrelated به تنهایی کافی نیست.

## 6. Tool development

Tool جدید باید:

- description واضح
- input schema معتبر
- category
- permission model
- error handling
- test
- discovery support

داشته باشد.

## 7. Tests

تغییرات backend:

`pytest -q`

تغییرات UI:

`cd ui && npm run build`

تغییرات MCP/auth:

- unit tests
- local handshake
- tokenized route
- Bearer auth
- public route در محیط واقعی در صورت دسترسی

## 8. Commit discipline

Commitها باید focused باشند.

نمونه:

- `fix: repair tailscale funnel detection`
- `feat: add browser automation tool`
- `docs: document release workflow`

یک commit نباید چند تغییر نامرتبط را بدون دلیل ترکیب کند.

## 9. Release discipline

هر release stable باید:

`MAJOR.MINOR.PATCH`

باشد.

Patch برای bug fix، minor برای feature و major برای breaking change.

## 10. Documentation discipline

وقتی behavior تغییر می‌کند، حداقل یکی از موارد زیر باید بررسی شود:

- README
- Persian README
- English README
- architecture docs
- deployment docs
- release docs
- environment/config docs

## 11. Secrets

موارد زیر secret محسوب می‌شوند:

- Dana auth token
- credentials
- API keys
- private keys
- access tokens
- connector URLs containing credentials

این موارد نباید commit شوند.

## 12. Generated files

قبل از commit بررسی شود:

```bash
git status --short
```

فایل‌های runtime مانند logs، caches، reports و local telemetry در صورت عدم نیاز به repository نباید commit شوند.

## 13. Troubleshooting principle

هر مشکل را از پایین‌ترین لایه به بالا بررسی کنید:

```text
Process
 ↓
Port
 ↓
HTTP
 ↓
Authentication
 ↓
MCP handshake
 ↓
Tailscale
 ↓
Public route
 ↓
AI client
```

این ترتیب باعث می‌شود خطای client با خطای backend اشتباه گرفته نشود.

## 14. Definition of Done

یک تغییر زمانی کامل است که:

- implementation انجام شده
- tests مناسب سبز هستند
- build لازم موفق است
- docs به‌روز است
- secrets وارد repository نشده‌اند
- git diff بررسی شده
- commit واضح است
- در صورت release، version/tag/release درست هستند
