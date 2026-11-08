# 09 — Software Requirements Specification (SRS)

> **عنوان محصول:** Dana MCP Server  
> **وضعیت سند:** زنده (Living Document) — باید با هر تغییر رفتاری مهم به‌روز شود  
> **نسخه سند:** 1.0.0  
> **تاریخ به‌روزرسانی:** 2026-11-08  
> **نسخه محصول مبنا:** 1.6.17  
> **مخزن:** https://github.com/seyed-ali-002/Dana-MCP-Server

---

## 0. نحوهٔ نگهداری SRS

این SRS مرجع الزامات **فعلی و هدف** Dana است.

| قاعده | توضیح |
|--------|--------|
| هم‌زمانی با کد | پس از merge فیچر/رفتار جدید، بخش الزامات و ماتریس ردیابی به‌روز شود |
| هم‌زمانی با Roadmap | آیتم‌های `done` در `08-development-roadmap.md` به وضعیت «پیاده‌سازی‌شده» در SRS منتقل شوند |
| شماره‌گذاری | الزامات با شناسه پایدار (`FR-xxx`, `NFR-xxx`, `UI-xxx`, …) |
| اولویت | `Must` / `Should` / `Could` / `Won't` (MoSCoW) |
| وضعیت | `Implemented` / `Partial` / `Planned` / `Deprecated` |

**هر PR که رفتار کاربر یا API عمومی را عوض می‌کند باید بخش مرتبط SRS را لمس کند یا صریحاً بگوید «بدون تغییر SRS».**

---

## 1. مقدمه

### 1.1 هدف

تعریف دقیق دامنه، بازیگران، الزامات کارکردی و غیرکارکردی Dana تا توسعه، تست و انتشار بر اساس یک مرجع مشترک انجام شود.

### 1.2 دامنه محصول

Dana یک **self-hosted MCP Server و agent runtime** است که:

- روی ماشین کاربر (یا سرور تحت کنترل کاربر) اجرا می‌شود؛
- به کلاینت‌های سازگار با MCP اجازه می‌دهد ابزارها را فراخوانی کنند؛
- اختیاری از طریق Tailscale Funnel endpoint عمومی امن فراهم می‌کند؛
- رابط CLI و Desktop Control Center برای نصب، کنترل، لاگ و تعمیر دارد.

Dana **سرویس ابری میزبانی‌شده توسط فروشنده نیست**؛ داده و اجرا در کنترل کاربر است.

### 1.3 تعاریف و مخفف‌ها

| اصطلاح | معنی |
|--------|------|
| MCP | Model Context Protocol |
| LOCAL endpoint | `http://127.0.0.1:<port>/<token>/mcp` (یا معادل) |
| PUBLIC endpoint | URL مبتنی بر Funnel/Tailscale با HTTPS |
| Funnel | قابلیت Tailscale برای expose عمومی |
| Control Center | اپ دسکتاپ Tauri/React |
| Skill pack | بستهٔ راهنما/ابزار افزوده |
| Worker | اسلات اجرای همزمان ابزار |

### 1.4 مراجع

- `00-project-overview.md` … `07-development-guidelines.md`
- `08-development-roadmap.md`
- `README.md` / `README_FA.md` / `README_EN.md`
- مشخصات MCP (نسخهٔ سازگار با dependency `mcp>=1.9,<2`)

---

## 2. توصیف کلی سیستم

### 2.1 چشم‌انداز

کلاینت‌های AI (چت‌بات‌ها و IDEها) از طریق MCP به قابلیت‌های واقعی ماشین کاربر دسترسی کنترل‌شده داشته باشند؛ بدون اجبار به سپردن محیط به یک SaaS بسته.

### 2.2 بازیگران (Actors)

| بازیگر | نقش |
|--------|------|
| کاربر نهایی | نصب، فعال‌سازی، اتصال کلاینت، نظارت |
| کلاینت MCP | فراخوانی ابزارها (DeepSeek، ChatGPT، Cursor، …) |
| مدیر سیستم | اختیاری؛ sudo/policy روی ماشین |
| CI/CD | بیلد و انتشار installer |
| توسعه‌دهنده | توسعه ابزار و UI |

### 2.3 محیط‌های اجرا

| محیط | الزام |
|--------|--------|
| Linux (x86_64 / در حد امکان ARM) | Must |
| Windows 10/11 | Must |
| macOS (Intel / Apple Silicon) | Must |
| اجرای از سورس Python 3.11+ | Must |
| Installer دسکتاپ (deb/AppImage/MSI/dmg بر اساس CI) | Should |
| Docker | Could |

### 2.4 قیود طراحی

1. stdout برای JSON-RPC/MCP باید تمیز بماند؛ لاگ فقط stderr یا فایل.
2. خروجی ابزارهایی که `outputSchema` ندارند نباید به structured اجباری شکسته شوند؛ در صورت اعلام schema، payload مطابق قرارداد باشد.
3. متغیرهای محیطی PyInstaller (`LD_LIBRARY_PATH`, `PYTHONHOME`, …) نباید به پروسهٔ فرزند سیستم نشت کنند.
4. URL شامل توکن = credential؛ در لاگ عمومی و README نمونه نباید توکن واقعی باشد.

---

## 3. الزامات کارکردی (Functional Requirements)

### 3.1 نصب و راه‌اندازی

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| FR-001 | سیستم باید نصب از سورس (`pip install -e .` / `dana install`) را پشتیبانی کند | Must | Implemented |
| FR-002 | سیستم باید installer دسکتاپ چندپلتفرمی از CI تولید کند | Must | Implemented |
| FR-003 | در first-run باید بتوان Tailscale را در صورت نیاز دانلود/نصب کرد | Must | Partial |
| FR-004 | اگر Tailscale از قبل نصب باشد نباید بدون نیاز دوباره دانلود اجباری شود | Must | Partial |
| FR-005 | مراحل setup باید به‌صورت step (نه فقط درصد مبهم) قابل فهم باشند | Should | Partial |
| FR-006 | پس از اتمام دانلود/نصب نباید دیالوگ پیشرفت به‌اشتباه دوباره باز شود | Must | Partial |
| FR-007 | در صورت نیاز به sudo/admin، رمز یک‌بار در session گرفته و تا حد امکان reuse شود | Must | Partial |
| FR-008 | لینک تأیید/لاگین Tailscale باید در UI با دکمه کپی نمایش داده شود و مرورگر پیش‌فرض در صورت امکان باز شود | Must | Partial |

### 3.2 Runtime و MCP

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| FR-010 | سرور MCP روی host محلی و پورت قابل پیکربندی (پیش‌فرض 8765) گوش دهد | Must | Implemented |
| FR-011 | مسیر MCP پیش‌فرض `/mcp` باشد و با توکن در URL محافظت شود | Must | Implemented |
| FR-012 | حالت Streamable HTTP پشتیبانی شود | Must | Implemented |
| FR-013 | ابزارها از طریق registry ثبت و قابل فراخوانی باشند | Must | Implemented |
| FR-014 | فراخوانی موازی/دسته‌ای (`dana_parallel_call` و مشابه) بدون deadlock در event loop کار کند | Must | Implemented |
| FR-015 | در صورت وجود `outputSchema`، پاسخ structured مطابق قرارداد باشد؛ در غیر این صورت متن/دیکشنری بدون اجبار schema | Must | Partial |
| FR-016 | خطای ابزار به‌صورت failure مشخص به کلاینت برگردد نه success با متن خطا | Must | Partial |
| FR-017 | اگر پورت پیش‌فرض اشغال بود، پورت جایگزین انتخاب شود | Should | Planned |
| FR-018 | session MCP پس از قطع کوتاه قابل بازیابی باشد | Must | Planned |

### 3.3 شبکه و Endpoint عمومی

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| FR-020 | وضعیت LOCAL و PUBLIC به‌صورت جداگانه قابل استعلام باشد | Must | Partial |
| FR-021 | فعال‌سازی Funnel از CLI و UI ممکن باشد | Must | Partial |
| FR-022 | پس از قطع/وصل شبکه یا ری‌استارت کنترل‌شده، PUBLIC در صورت امکان بدون نصب مجدد برگردد | Must | Planned |
| FR-023 | حالت Local-only بدون Funnel پشتیبانی شود | Should | Planned |
| FR-024 | سازگاری با VPN کاربر نباید runtime را به‌طور کامل از کار بیندازد | Should | Partial |

### 3.4 CLI

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| FR-030 | دستورات `install`, `start`, `stop`, `restart`, `status`, `logs`, `connect`, `doctor`, `gui` | Must | Implemented |
| FR-031 | `stop` دستی نباید بدون اقدام کاربر دوباره auto-start شود | Must | Partial |
| FR-032 | `doctor` تشخیص‌های پایه (پورت، توکن، tailscale، وابستگی) بدهد | Should | Implemented |

### 3.5 Desktop Control Center

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| UI-001 | UI دسکتاپ برای کنترل start/stop/activate و مشاهده وضعیت | Must | Implemented |
| UI-002 | تم تیره/روشن با کنترل آیکونی | Should | Partial |
| UI-003 | انتخاب accent محدود (مثلاً آبی/قرمز/سبز تیره) | Could | Partial |
| UI-004 | تب‌های ساده و کم‌تعداد با UX واضح (Control، Logs، Usage، Config، Repair، Help) | Must | Partial |
| UI-005 | دو ناحیه لاگ: خطا/سیستم و ابزارها؛ با جزئیات collapsible | Must | Partial |
| UI-006 | تب Usage با آمار تجمعی توکن/زمان | Should | Partial |
| UI-007 | تب Repair برای بازگشت تنظیمات و اتصال مجدد | Should | Planned |
| UI-008 | تب Help با فهرست و بخش‌بندی مراحل اتصال/تعمیر/کلاینت‌ها | Must | Partial |
| UI-009 | System tray؛ Quit کامل پروسه را تمام کند | Must | Partial |
| UI-010 | Single-instance: باز کردن مجدد از شورتکات session دوم نسازد | Must | Planned |
| UI-011 | نوتیفیکیشن دسکتاپ و صدای اختیاری قابل خاموش‌کردن | Should | Planned |
| UI-012 | چک آپدیت هنگام باز شدن و دکمه بررسی دستی | Should | Partial |
| UI-013 | UI در resize رفتار responsive داشته باشد | Should | Planned |
| UI-014 | کنترل‌های فرم (dropdown، input، padding/margin) یکدست و غیرپیش‌فرض‌ِ خام مرورگر | Should | Partial |

### 3.6 امنیت و دسترسی

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| FR-040 | Path policy برای محدودسازی مسیرهای فایل | Must | Implemented |
| FR-041 | اگر لیست مسیر مجاز خالی بود، رفتار امن و مستند (پیش‌فرض باز یا بسته — باید در Config روشن باشد) | Must | Partial |
| FR-042 | توکن احراز هویت اجباری برای endpoint | Must | Implemented |
| FR-043 | ابزارهای مخرب بالقوه باید قابل خاموش‌سازی باشند | Should | Partial |
| FR-044 | Audit log عملیات حساس | Could | Planned |
| FR-045 | حالت Restricted برای کاربر تازه‌کار | Could | Planned |

### 3.7 ابزارها و قابلیت‌های عامل

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| FR-050 | ابزار فایل، شِل کنترل‌شده، و ابزارهای ثبت‌شده در registry | Must | Implemented |
| FR-051 | SuperMCP tools برای همه کاربران بدون مسیر hard-coded شخصی | Must | Implemented |
| FR-052 | Skill packs قابل فعال‌سازی | Should | Implemented |
| FR-053 | نصب/مدیریت skill از UI | Should | Planned |
| FR-054 | کنترل دسکتاپ (ماوس/کیبورد) cross-platform | Should | Partial |
| FR-055 | یکپارچگی اختیاری Zero Use Computer | Could | Partial |
| FR-056 | فشرده‌سازی خروجی بزرگ (context-mode) بدون شکستن کلاینت | Should | Partial |

### 3.8 گزارش‌گیری

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| FR-060 | گزارش استفاده از ابزارها و توکن (ترمینال و UI) | Should | Partial |
| FR-061 | export گزارش | Could | Planned |

---

## 4. الزامات غیرکارکردی (Non-Functional)

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| NFR-001 | زمان انتظار آماده شدن runtime قابل پیکربندی و پیش‌فرض معقول (حدود ۲۰–۶۰s بسته به عملیات) | Must | Partial |
| NFR-002 | عدم نشت env PyInstaller به فرزند | Must | Implemented |
| NFR-003 | لاگ‌ها encoding امن روی Windows (بدون کرش charmap) | Must | Partial |
| NFR-004 | SSL/certificate روی Linux/AppImage نباید endpoint را بی‌دلیل بشکند (certifi/CA) | Must | Partial |
| NFR-005 | بیلد CI برای سه OS؛ retry برای دانلود وابستگی‌های بسته‌بندی (NSIS/WiX و مشابه) | Must | Implemented |
| NFR-006 | حجم installer تا حد ممکن بهینه بدون حذف قابلیت حیاتی | Should | Partial |
| NFR-007 | مستندات کاربر ساده؛ مستندات توسعه کامل | Must | Partial |
| NFR-008 | تست خودکار pytest برای هسته | Must | Partial |
| NFR-009 | SemVer و تگ GitHub Release پس از push مناسب | Must | Implemented |

---

## 5. الزامات رابط و یکپارچه‌سازی

| ID | الزام | اولویت | وضعیت |
|----|--------|--------|--------|
| INT-001 | سازگاری با کلاینت‌های MCP مبتنی بر Streamable HTTP | Must | Partial |
| INT-002 | راهنمای اتصال برای DeepSeek به‌عنوان سناریوی اصلی هدف | Must | Partial |
| INT-003 | راهنمای OAuth/redirect برای کلاینت‌هایی مثل Gemini | Should | Planned |
| INT-004 | Docker به‌عنوان مسیر اختیاری | Could | Implemented |

---

## 6. موارد خارج از دامنه (Out of Scope) — نسخه جاری

- میزبانی چندمستأجره SaaS توسط پروژه
- تضمین bypass برای محدودیت‌های قانونی/سیاست سازمان کاربر
- امضای کد تجاری پولی به‌عنوان پیش‌نیاز اجرا روی همه ماشین‌ها
- جایگزینی کامل سیستم‌عامل یا آنتی‌ویروس

---

## 7. سناریوهای اصلی (Use Cases خلاصه)

### UC-01 نصب و فعال‌سازی اولیه

1. کاربر installer یا `dana install` را اجرا می‌کند.
2. سیستم پیش‌نیازها (از جمله Tailscale در صورت نیاز) را تأمین می‌کند.
3. کاربر Funnel/لاگین را تأیید می‌کند.
4. LOCAL و در صورت موفقیت PUBLIC آماده می‌شود.
5. کاربر URL را در کلاینت MCP قرار می‌دهد.

### UC-02 استفاده روزمره از کلاینت

1. Dana در پس‌زمینه/tray در حال اجرا است.
2. کلاینت ابزار صدا می‌زند.
3. نتیجه مطابق قرارداد MCP برمی‌گردد و در Usage/Logs ثبت می‌شود.

### UC-03 قطع شبکه و بازیابی

1. شبکه قطع و وصل می‌شود.
2. watchdog وضعیت را تشخیص می‌دهد.
3. session/endpoint در حد امکان بازیابی می‌شود یا پیام اقدام واضح نمایش داده می‌شود.

### UC-04 توقف عمدی

1. کاربر Stop می‌زند.
2. runtime متوقف می‌ماند تا Start دستی.

### UC-05 تعمیر

1. کاربر تب Repair یا `dana doctor` را اجرا می‌کند.
2. اقدامات reconnect/re-funnel/reset پیشنهاد و اجرا می‌شود.

---

## 8. ماتریس ردیابی نسخه (خلاصه)

| نسخه هدف | الزامات تمرکز |
|----------|----------------|
| 1.6.x | پایه MCP، GUI، Funnel، env scrub، CI |
| 1.7.x | FR-018, FR-022, FR-006, FR-007, UI-010, R17-* |
| 1.8.x | UI-006, UI-007, UI-012, INT-002, INT-003, R18-* |
| 1.9.x | FR-053, FR-054, UI-013, R19-* |
| 2.0 | FR-023, FR-044, FR-045, Plugin API, R20-* |

جزئیات زمان‌بندی در `08-development-roadmap.md`.

---

## 9. معیارهای پذیرش کلی انتشار

قبل از تگ minor/major:

1. [ ] pytest هسته سبز است (یا شکست‌ها مستند و پذیرفته‌شده).
2. [ ] اسموک دستی: start → LOCAL OK روی حداقل یک OS.
3. [ ] اسموک: stop عمدی auto-start نمی‌شود.
4. [ ] برای انتشار Funnel: PUBLIC یا دلیل شکست واضح.
5. [ ] README و در صورت تغییر رفتار، SRS/Roadmap به‌روز شده‌اند.
6. [ ] توکن واقعی در git نیست.

---

## 10. Changelog سند SRS

| نسخه سند | تاریخ | شرح |
|----------|------|------|
| 1.0.0 | 2026-11-08 | نگارش اولیه SRS جامع بر اساس کد و مستندات موجود و roadmap v1.7–2.0 |

---

## 11. پیوندها

- Roadmap: [`08-development-roadmap.md`](08-development-roadmap.md)
- Architecture: [`01-architecture.md`](01-architecture.md)
- MCP/Auth/Network: [`02-mcp-auth-network.md`](02-mcp-auth-network.md)
- Capabilities: [`03-capabilities.md`](03-capabilities.md)
- Desktop/UI: [`05-desktop-ui-testing.md`](05-desktop-ui-testing.md)
