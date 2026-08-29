# 🧠 Dana MCP Server

> **سرور MCP پایتون برای تبدیل کامپیوتر شما به یک Agent قابل استفاده از طریق ChatGPT، Grok و Claude**

🇬🇧 **English documentation:** [README_EN.md](README_EN.md)

Dana یک MCP Server کراس‌پلتفرم و مستقل از PHP است که روی سیستم شما اجرا می‌شود و از طریق Tailscale Funnel یک endpoint امن HTTPS در اختیار Chatbotها و Agentهای سازگار با MCP قرار می‌دهد.

## 🙏 تشکر ویژه


تشکر ویژه از **محسن صمدی‌نژاد (Mohsen Samadinejad)** که ایده اجرایی اصلی این ابزار با ایشان بود و معماری و مسیر اجرایی اولیه پروژه از آن ایده شکل گرفت.

پیاده‌سازی PHP ایشان، یعنی پروژه **PHP MCP Server**، مبنای اصلی و مرجع رفتاری این بازنویسی Python بوده است. در فرایند مهاجرت، رفتارهای قابل مشاهده، قرارداد ابزارها، پروتکل MCP و سناریوهای سازگاری با نسخه PHP به‌عنوان مرجع در نظر گرفته شده‌اند.

صفحه GitHub محسن صمدی‌نژاد:

🔗 https://github.com/samadinejad

## ✨ امکانات

- 🐍 پیاده‌سازی کامل با Python و مستقل از PHP
- 🖥️ پشتیبانی از Linux، Windows و macOS
- 🌐 اتصال عمومی HTTPS با Tailscale Funnel
- 🔐 لینک اتصال دارای Token ثابت و اختصاصی
- 📁 مدیریت فایل و پوشه و ویرایش کد
- 💻 اجرای دستورات و مدیریت Process
- 🌿 Git، تست، Lint، Build و Package Management
- 🌍 HTTP/API و ابزارهای شبکه
- 🐳 Docker و SQLite
- 🌐 ابزارهای Web و Browser Automation
- 🐞 ابزارهای Debug و بررسی کیفیت کد
- 📄 ساخت Word و PDF با پشتیبانی RTL و فارسی
- 📝 تولید README، Changelog، گزارش و مستندات

## 🚀 اجرای سریع

### 1. دریافت پروژه

```bash
git clone git@github.com:seyed-ali-002/Dana-MCP-Server.git
cd Dana-MCP-Server
```

### 2. اجرا

**Linux / macOS:**

```bash
./run.sh
```

**Windows:**

```bat
run.bat
```

همه مراحل توسط Launcher انجام می‌شود: ساخت محیط Python، نصب وابستگی‌ها، ایجاد Token پایدار، اجرای Dana، اتصال Dana به Tailscale Funnel، پیدا کردن hostname و نمایش لینک اتصال MCP.

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

### 3. لینک اتصال

پس از اجرا، Launcher لینک زیر را نمایش می‌دهد:

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

همین URL را در بخش اتصال MCP سرویس موردنظر قرار دهید. **نیازی به Authorization Header جداگانه نیست.**

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
  "allowed_paths": [
    "/home/user/projects",
    "/mnt/workspace"
  ],
  "deny_paths": []
}
```

اگر `allowed_paths` خالی باشد، Dana به همه مسیرها دسترسی دارد؛ با این حال `deny_paths` همچنان می‌تواند مسیرهای حساس را مسدود کند. کنترل مسیر در ابزارهای فایل، تحلیل پروژه، لاگ، دیتابیس، Build و خروجی Browser اعمال می‌شود و مسیرها پس از `resolve()` بررسی می‌شوند تا مسیرهای `..` و Symlink نتوانند به‌سادگی Policy را دور بزنند. ابزارهای `get_allowed_paths`، `set_allowed_paths_tool`، `add_allowed_path_tool`، `remove_allowed_path_tool` و `validate_path_access` نیز برای مدیریت Policy در MCP در دسترس هستند.

## 🛠️ استفاده کلی

پس از اتصال، Chatbot می‌تواند ابزارهای Dana را از طریق MCP مشاهده و استفاده کند. برای مثال می‌توانید از آن بخواهید فایل ایجاد یا ویرایش کند، کد را جستجو کند، تست اجرا کند، Git را مدیریت کند، یک API را بررسی کند، مشکل برنامه را Debug کند یا یک فایل Word/PDF فارسی بسازد.

Dana ابزارها را روی **همان سیستمی که Server روی آن اجرا شده** اجرا می‌کند؛ بنابراین دسترسی‌های سیستم‌عامل و سطح دسترسی کاربر اجراکننده اهمیت دارد.

## 🧩 معماری کلی

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

Dana مستقل از سرویس PHP است و برای جلوگیری از تداخل با سرویس‌های موجود، Funnel و پورت اختصاصی خودش را استفاده می‌کند.

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
