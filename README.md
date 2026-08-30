# 🧠 Dana MCP Server

> **سرور MCP پایتون برای تبدیل کامپیوتر شما به یک Agent قابل استفاده از طریق ChatGPT، Grok و Claude**

🇬🇧 **English documentation:** [README_EN.md](README_EN.md)

---

Dana یک MCP Server کراس‌پلتفرم و مستقل از PHP است. برای نصب اولیه فقط از Installer استفاده کنید؛ سپس می‌توانید آن را در Local Mode روی کامپیوتر شخصی یا در Server Mode روی Linux server اجرا کنید.

## 📚 فهرست مطالب

- [امکانات](#-امکانات)
- [ساختار Installer و Runtime](#-ساختار-installer-و-runtime)
- [رابط ترمینال و Worker Logs](#-رابط-ترمینال-و-worker-logs)
- [حالت‌های استقرار](#-حالتهای-استقرار)
  - [نصب تعاملی](#نصب-تعاملی)
  - [Local Mode](#local-mode)
  - [Server Mode](#server-mode)
  - [ظاهر ترمینال](#ظاهر-ترمینال)
- [اجرای سریع](#-اجرای-سریع)
  - [دریافت پروژه](#1-دریافت-پروژه)
  - [نصب و راه‌اندازی](#2-نصب-و-راهاندازی)
  - [لینک اتصال](#3-لینک-اتصال)
- [راه‌اندازی Tailscale](#-راهاندازی-و-login-در-tailscale)
- [مدیریت سرویس در Server Mode](#️-مدیریت-سرویس-dana-در-server-mode)
- [مدیریت Token](#-مدیریت-token)
- [ابزارهای Browser و Security](#-فعالسازی-کامل-ابزارهای-browser-و-security)
- [اتصال به ChatGPT، Grok و Claude](#-اتصال-به-chatgpt-grok-و-claude)
- [محدودسازی مسیرهای دسترسی](#-محدودسازی-مسیرهای-دسترسی-dana)
- [استفاده کلی](#️-استفاده-کلی)
- [معماری](#-معماری-کلی)
- [تست](#-تست)
- [مشارکت](#-مشارکت)
- [مجوز](#-مجوز)
- [تشکر ویژه](#-تشکر-ویژه)

---

> برای دسترسی سریع‌تر، ابتدا **اجرای سریع** را بخوانید و سپس متناسب با محیط خود **Local Mode** یا **Server Mode** را دنبال کنید.

---

## 🙏 تشکر ویژه

تشکر ویژه از **محسن صمدی‌نژاد (Mohsen Samadinejad)** که ایده اجرایی اصلی این ابزار با ایشان بود و معماری و مسیر اجرایی اولیه پروژه از آن ایده شکل گرفت.

پیاده‌سازی PHP ایشان، یعنی پروژه **PHP MCP Server**، مبنای اصلی و مرجع رفتاری این بازنویسی Python بوده است. در فرایند مهاجرت، رفتارهای قابل مشاهده، قرارداد ابزارها، پروتکل MCP و سناریوهای سازگاری با نسخه PHP به‌عنوان مرجع در نظر گرفته شده‌اند.

صفحه GitHub محسن صمدی‌نژاد:

🔗 https://github.com/samadinejad

## ✨ امکانات

- 🐍 پیاده‌سازی کامل با Python و مستقل از PHP
- 🖥️ پشتیبانی از Linux، Windows و macOS
- 🚀 Installer تعاملی با ساخت خودکار `.venv` و نصب ایزوله وابستگی‌ها
- 🌐 Local Mode با Tailscale Funnel
- 🌐 Server Mode با Domain، HTTPS، Reverse Proxy موجود و systemd
- 🔐 Local Mode با لینک Tokenized و Server Mode با Endpoint استاندارد HTTPS
- 📁 مدیریت فایل و پوشه و ویرایش کد
- 💻 اجرای دستورات و مدیریت Process
- 🌿 Git، تست، Lint، Build و Package Management
- 🌍 HTTP/API و ابزارهای شبکه
- 🐳 Docker و SQLite
- 🌐 ابزارهای Web و Browser Automation
- 🐞 ابزارهای Debug و بررسی کیفیت کد
- 📄 ساخت Word و PDF با پشتیبانی RTL و فارسی
- 📝 تولید README، Changelog، گزارش و مستندات

## 🚀 حالت‌های استقرار

دانا یک هسته مشترک با دو حالت کاملاً مجزا دارد:

- **Local Mode**: اجرای دانا روی کامپیوتر شخصی و اتصال عمومی از طریق Tailscale.
- **Server Mode**: اجرای Dana روی VPS یا سرور اختصاصی، بدون وابستگی به Tailscale، با Domain و HTTPS، Backend ایزوله روی localhost، Reverse Proxy خودکار و systemd.

حالت فعال با `DANA_DEPLOYMENT_MODE=local` یا `DANA_DEPLOYMENT_MODE=server` مشخص می‌شود.

### نصب تعاملی

برای نصب و راه‌اندازی معمولی، فقط Installer را اجرا کنید:

```bash
python3 install.py
```

Installer خودش محیط `.venv` را می‌سازد و تمام وابستگی‌ها را داخل آن نصب می‌کند؛ بنابراین با PEP 668 و Python مدیریت‌شده سیستم تداخلی ندارد. رابط Installer برای انتخاب Mode، تعداد Worker، احراز هویت و تنظیمات شبکه نیز به‌صورت اختصاصی طراحی شده است.

پس از نصب، برای اجرای مستقیم Dana از محیط ایجادشده استفاده می‌شود. `scripts/run.py` و فایل‌های `run*` Runnerهای مستقیم/سازگاری هستند و مسیر نصب اصلی نیستند.

Installer ابتدا حالت استقرار را می‌پرسد و سپس مراحل موردنیاز همان حالت را انجام می‌دهد. بعد از بررسی و نصب وابستگی‌ها، صفحه ترمینال پاک می‌شود و فقط اطلاعات نهایی اتصال نمایش داده می‌شود.

### Server Mode

Server Mode برای سرورهایی طراحی شده که ممکن است از قبل یک یا چند پروژه وب فعال داشته باشند. Dana روی یک **پورت داخلی آزاد** اجرا می‌شود و فقط روی `127.0.0.1` گوش می‌دهد؛ بنابراین با پورت‌های عمومی `80` و `443` یا سرویس‌های وب موجود تداخل مستقیم ندارد.

Installer به‌صورت خودکار:

1. یک پورت آزاد برای Backend Dana انتخاب می‌کند.
2. Dana را با systemd روی `127.0.0.1:<PORT>` اجرا می‌کند.
3. Reverse Proxy موجود را تشخیص می‌دهد:
   - Nginx
   - Caddy
   - Apache
4. فایل Virtual Host مربوط به دامنه را پیدا می‌کند.
5. قبل از تغییر، Backup می‌گیرد.
6. Route مربوط به `/mcp` را به Backend Dana اضافه می‌کند.
7. تنظیمات Proxy را Validate می‌کند.
8. در صورت خطا، تنظیمات را Rollback می‌کند.
9. Proxy را فقط بعد از اعتبارسنجی موفق Reload می‌کند.

نمونه معماری:

```text
Internet
   │
   ▼
https://mcp.example.com
   │
   ▼
Existing Nginx / Caddy / Apache
   ├── /     → Existing Web Project
   └── /mcp  → 127.0.0.1:<DANA_PORT>
                    │
                    ▼
                 Dana MCP
```

نمونه تنظیمات:

```env
DANA_DEPLOYMENT_MODE=server
DANA_HOST=127.0.0.1
DANA_PORT=<auto-selected-port>
DANA_PUBLIC_HOST=mcp.example.com
```

پس از نصب، Endpoint استاندارد MCP به شکل زیر است:

```text
https://mcp.example.com/mcp
```

> در Server Mode توکن داخل URL قرار نمی‌گیرد تا URL استاندارد و HTTPS باقی بماند.

### Local Mode

Local Mode جریان فعلی Tailscale را حفظ می‌کند و URL شامل token path است. **برای نصب و راه‌اندازی معمولی فقط `python3 install.py` را اجرا کنید.** Installer محیط `.venv` را می‌سازد، وابستگی‌ها را نصب می‌کند و حالت Local را تنظیم می‌کند.

`./run.sh`، `run.bat` و `scripts/run.py` فقط Runnerهای مستقیم/سازگاری برای اجرای بعدی هستند و جایگزین Installer نیستند.

Installer و Runtime به‌صورت mode-aware هستند و تنظیمات شبکه Local و Server با یکدیگر مخلوط نمی‌شوند.

### ظاهر ترمینال

Installer و Runtime دو رابط جدا دارند. Installer برای نمایش مراحل نصب و تنظیمات طراحی شده و Runtime فقط Dashboard زنده Dana و لاگ‌های Workerها را نمایش می‌دهد. Runtime دیگر مراحل نصب، `pip install` یا خروجی خام Tailscale را نشان نمی‌دهد.

## 🧱 ساختار Installer و Runtime

مسیر اجرای پیشنهادی به این شکل است:

```text
python install.py
      │
      ├── create/update .venv
      ├── install dependencies
      ├── select deployment mode
      ├── configure workers
      ├── generate persistent token
      └── configure networking / Tailscale

run / run.sh / run.bat
      │
      ▼
Dana Runtime
      │
      ├── Dashboard
      ├── Worker status
      └── Worker job logs
```

`install.py` و `dana/installer.py` مسئول نصب و پیکربندی هستند. Runtime نباید برای نصب وابستگی یا آماده‌سازی محیط استفاده شود.

### Tailscale در Local Mode

در Local Mode، Installer پیکربندی Tailscale Funnel را انجام می‌دهد و خروجی خام فرمان‌های Tailscale را به کاربر نمایش نمی‌دهد. Runtime فقط URL نهایی MCP را از تنظیمات خوانده و نمایش می‌دهد.

### Worker Logs

هر Worker یک نام تصادفی از فهرست داخلی Dana دریافت می‌کند و شماره ثابت خود را حفظ می‌کند. بعد از پایان هر عملیات، لاگ شامل نام و شماره Worker، نام عملیات، زمان اجرا و اطلاعات Token ثبت می‌شود.

نمونه:

```text
DONE Atlas #1  read_file
     tokens 1,284 in / 4,912 out  time 184ms

DONE Orion #3  edit_file
     tokens 2,031 in / 1,447 out  time 921ms
```

پیام‌های داخلی Transport مانند `Terminating session: None` برای خروجی معمول Runtime نمایش داده نمی‌شوند.

## 🚀 اجرای سریع

**مسیر پیشنهادی برای همه کاربران: فقط Installer را اجرا کنید.**

### 1. دریافت پروژه

```bash
git clone git@github.com:seyed-ali-002/Dana-MCP-Server.git
cd Dana-MCP-Server
```

### 2. نصب و راه‌اندازی

**Linux / macOS / Windows:**

```bash
python3 install.py
```

در Windows در صورت نبودن `python3` از `python install.py` استفاده کنید.

Installer تنها مسیر پیشنهادی نصب است و ساخت `.venv`، نصب وابستگی‌ها، انتخاب Local/Server و تنظیمات مربوط به همان Mode را مدیریت می‌کند.

`./run.sh`، `run.bat` و `scripts/run.py` فقط Runnerهای مستقیم/سازگاری برای اجرای Dana پس از نصب هستند و نباید برای نصب اولیه استفاده شوند.

> ⚠️ اگر Tailscale روی سیستم نصب یا Login نشده باشد، ابتدا آن را نصب و وارد حساب خود شوید.

### 🔐 راه‌اندازی و Login در Tailscale

اگر Tailscale روی سیستم نصب نیست یا هنوز وارد حساب نشده‌اید، مراحل زیر را انجام دهید.

#### 🐧 Linux

1. Tailscale را از صفحه رسمی دانلود و نصب کنید:
   https://tailscale.com/download/linux
2. سپس سرویس را فعال کنید:

```bash
sudo systemctl enable --now tailscaled
```

3. Login را انجام دهید:

```bash
sudo tailscale up
```

4. دستور یک لینک احراز هویت نمایش می‌دهد. لینک را در مرورگر باز کنید و وارد حساب Tailscale شوید.
5. برای بررسی وضعیت:

```bash
tailscale status
```

#### 🪟 Windows

1. Tailscale را از صفحه رسمی دانلود کنید:
   https://tailscale.com/download/windows
2. برنامه را نصب و اجرا کنید.
3. روی **Log in** کلیک کنید.
4. مرورگر باز می‌شود؛ وارد حساب Tailscale شوید و دسترسی را تأیید کنید.
5. پس از ورود، مطمئن شوید Tailscale در حالت **Connected** قرار دارد.

#### 🍎 macOS

1. Tailscale را از صفحه رسمی دانلود کنید:
   https://tailscale.com/download/mac
2. برنامه را نصب و اجرا کنید.
3. Tailscale را از نوار منو باز کنید و **Log in** را انتخاب کنید.
4. در مرورگر وارد حساب Tailscale شوید و دسترسی را تأیید کنید.
5. پس از ورود، وضعیت Tailscale باید **Connected** باشد.

> 💡 **نکته:** Dana برای ایجاد لینک عمومی MCP به Tailscale Funnel نیاز دارد؛ بنابراین همان حسابی که روی سیستم Login کرده‌اید باید اجازه استفاده از Funnel را داشته باشد.

🔗 مستندات رسمی: https://tailscale.com/kb/start

## ⏹️ مدیریت سرویس Dana در Server Mode

Dana در Server Mode به‌صورت یک سرویس systemd با نام `dana` اجرا می‌شود.

### توقف سرویس

```bash
sudo systemctl stop dana
```

### شروع سرویس

```bash
sudo systemctl start dana
```

### Restart سرویس

```bash
sudo systemctl restart dana
```

### بررسی وضعیت

```bash
sudo systemctl status dana --no-pager
```

### مشاهده لاگ زنده

```bash
sudo journalctl -u dana -f
```

### جلوگیری از اجرای خودکار پس از Boot

```bash
sudo systemctl disable dana
```

### فعال‌سازی مجدد اجرای خودکار

```bash
sudo systemctl enable dana
```

> Backend Dana به‌صورت عادی فقط روی `127.0.0.1` اجرا می‌شود. بنابراین برای بستن دسترسی اینترنتی آن نیازی به بستن پورت در Firewall نیست؛ دسترسی عمومی فقط از طریق HTTPS Reverse Proxy و مسیر `/mcp` انجام می‌شود.

### 👷 تعداد Workerها

تعداد Workerها در مرحله **Installer** انتخاب می‌شود، نه هنگام اجرای معمول Runtime. مقدار پیش‌فرض **5** است و بازه مجاز **1 تا 128** است.

پس از نصب، Runtime بدون پرسیدن سؤال‌های نصب مستقیماً Dashboard را اجرا می‌کند. نام هر Worker نیز به‌صورت تصادفی از فهرست نام‌های داخلی Dana انتخاب می‌شود.

مقدار انتخاب‌شده در `.env` با نام زیر ذخیره می‌شود:

```env
DANA_WORKERS=5
```

### 3. لینک اتصال

پس از نصب و اجرای Runtime، Dashboard لینک اتصال را نمایش می‌دهد. در Local Mode URL به شکل زیر است:

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

همین URL را در بخش اتصال MCP سرویس موردنظر قرار دهید. **در Local Mode نیازی به Authorization Header جداگانه نیست.**

برای Server Mode از URL استاندارد زیر استفاده کنید:

```text
https://<your-domain>/mcp
```

## 🔑 مدیریت Token

Token به‌صورت پایدار نگهداری می‌شود و با هر اجرای Dana تغییر نمی‌کند.

برای تولید Token جدید:

```bash
python scripts/regenerate_token.py
```

سپس Dana را restart کنید. Token قبلی دیگر نباید برای اتصال جدید استفاده شود.

## 🌐 فعال‌سازی کامل ابزارهای Browser و Security

برای فعال شدن کامل قابلیت‌های پیشرفته Dana، می‌توانید وابستگی‌های اختیاری را نصب کنید:

```bash
pip install -e ".[full]"
playwright install chromium
```

یا فقط Browser را نصب کنید:

```bash
pip install -e ".[browser]"
playwright install chromium
```

این کار ابزارهای Playwright و بررسی امنیت وابستگی‌ها را فعال می‌کند.

## 🤖 اتصال به ChatGPT، Grok و Claude

### ChatGPT

در ChatGPT به بخش **Plugins / Connectors** بروید و گزینه مربوط به افزودن اتصال MCP یا Custom Connector را انتخاب کنید. URL چاپ‌شده توسط Dana را وارد کنید.

> نام و محل دقیق گزینه‌ها ممکن است با توجه به نسخه و رابط کاربری ChatGPT تغییر کند.

### Grok

در Grok وارد بخش **Custom Connectors** شوید، یک اتصال جدید MCP بسازید و URL زیر را وارد کنید:

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

### Claude

در Claude وارد بخش **Custom Connectors** شوید، اتصال MCP را اضافه کنید و همان URL Dana را وارد کنید.

### ⚠️ نکته مهم

اگر Connector قبلاً با نسخه قدیمی Dana ساخته شده، برای دریافت فهرست ابزارهای جدید ممکن است لازم باشد اتصال قبلی را حذف و دوباره ایجاد کنید تا `tools/list` مجدداً دریافت شود.

## 🔒 محدودسازی مسیرهای دسترسی Dana

Dana می‌تواند فقط به مسیرهایی که شما تعیین می‌کنید دسترسی داشته باشد. تنظیمات در `config/access_policy.json` ذخیره می‌شود.

```json
{
  "allowed_paths": ["/home/user/projects", "/mnt/workspace"],
  "deny_paths": []
}
```

اگر `allowed_paths` خالی باشد، Dana به همه مسیرها دسترسی دارد؛ با این حال `deny_paths` همچنان می‌تواند مسیرهای حساس را مسدود کند. کنترل مسیر در ابزارهای فایل، تحلیل پروژه، لاگ، دیتابیس، Build و خروجی Browser اعمال می‌شود و مسیرها پس از `resolve()` بررسی می‌شوند تا مسیرهای `..` و Symlink نتوانند به‌سادگی Policy را دور بزنند. ابزارهای `get_allowed_paths`، `set_allowed_paths_tool`، `add_allowed_path_tool`، `remove_allowed_path_tool` و `validate_path_access` نیز برای مدیریت Policy در MCP در دسترس هستند.

## 🛠️ استفاده کلی

پس از اتصال، Chatbot می‌تواند ابزارهای Dana را از طریق MCP مشاهده و استفاده کند. برای مثال می‌توانید از آن بخواهید فایل ایجاد یا ویرایش کند، کد را جستجو کند، تست اجرا کند، Git را مدیریت کند، یک API را بررسی کند، مشکل برنامه را Debug کند یا یک فایل Word/PDF فارسی بسازد.

Dana ابزارها را روی **همان سیستمی که Server روی آن اجرا شده** اجرا می‌کند؛ بنابراین دسترسی‌های سیستم‌عامل و سطح دسترسی کاربر اجراکننده اهمیت دارد.

## 🧩 معماری کلی

### Local Mode

```text
ChatGPT / Grok / Claude
          │
          │ MCP over HTTPS
          ▼
   Tailscale Funnel
          │
          ▼
      Dana Server
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
 Files  Shell  Git ...
```

### Server Mode

```text
ChatGPT / Grok / Claude
          │
          │ MCP over HTTPS
          ▼
 Existing Reverse Proxy :443
 Nginx / Caddy / Apache
          │
          ├── /     → Existing Web Projects
          │
          └── /mcp  → 127.0.0.1:<DANA_PORT>
                           │
                           ▼
                        Dana MCP
```

در Server Mode Dana از پورت داخلی اختصاصی خود استفاده می‌کند و مسیر `/mcp` به‌صورت خودکار با Reverse Proxy موجود یکپارچه می‌شود؛ بنابراین پروژه‌های وب موجود روی همان سرور حفظ می‌شوند.

## 🧪 تست

```bash
pytest -q
```

## 🤝 مشارکت

Pull Request و Issue کاملاً استقبال می‌شود. اگر باگ، ناسازگاری، ابزار موردنیاز یا ایده‌ای برای بهتر شدن Dana دارید:

1. یک Issue ایجاد کنید 🐛
2. راه‌حل یا قابلیت پیشنهادی خود را پیاده‌سازی کنید 🛠️
3. تست‌های مربوط را اضافه کنید 🧪
4. یک Pull Request ارسال کنید 🚀

لطفاً هنگام گزارش خطا، سیستم‌عامل، نسخه Python، نسخه Dana و لاگ مرتبط را نیز تا حد امکان ذکر کنید.

## 📜 مجوز

این پروژه تحت مجوز موجود در فایل [LICENSE](LICENSE) منتشر شده است.

---

⭐ اگر Dana برای شما مفید است، با Star کردن پروژه و مشارکت در توسعه آن از پروژه حمایت کنید.

## 🧠 Codebase Memory و Context Optimization
Dana پروژه را با SQLite + FTS5 به‌صورت افزایشی ایندکس می‌کند. با `index_codebase` ایندکس بسازید و با `search_codebase_memory` فقط Context مرتبط را با بودجه مشخص دریافت کنید. `get_library_docs` مستندات URLهای عمومی را Cache می‌کند و `context_compress` متن‌های تکراری را فشرده می‌کند.

## 🧠 بهینه‌سازی Context بدون محدودیت Token

Dana اطلاعات پروژه را بدون اعمال سقف مصنوعی Token بازیابی می‌کند و با Deduplication، Context ID و Cache، Delta Context، بارگذاری مرحله‌ای، تحلیل Symbol و Dependency، و فشرده‌سازی ساختاری، Context تکراری و غیرضروری را کاهش می‌دهد. اطلاعات مرتبط به دلیل رسیدن به یک Budget پیش‌فرض حذف نمی‌شوند.


## 📊 تحلیل Token و زمان

Dana می‌تواند مصرف Token و زمان هر عملیات را ثبت کند. آمار شامل هر عملیات، مجموع Session و مجموع کل پروژه است. برای مصرف دقیق مدل، Client/API باید `input_tokens` و `output_tokens` واقعی را گزارش کند؛ در غیر این صورت فقط تخمین Context قابل ارائه است.


## 🖥️ رابط گرافیکی
رابط مدرن و مینیمال Dana با **PySide6 (Qt)** پیاده‌سازی شده و از Tkinter استفاده نمی‌کند. اجرا: `python run_gui.py` یا `dana-gui`
