# Versioning and Release Policy

## 1. استاندارد

Dana از **Semantic Versioning 2.0.0** با قالب زیر استفاده می‌کند:

`MAJOR.MINOR.PATCH`

مثال:

`1.2.3`

## 2. Patch

برای bug fix، regression fix، اصلاح خطای نصب، stability fix یا تغییرات backward-compatible کوچک:

`1.0.0 → 1.0.1`

نمونه:

- اصلاح Funnel detection
- رفع authentication bug
- اصلاح installer fallback
- اصلاح UI بدون تغییر contract

## 3. Minor

برای feature جدید backward-compatible:

`1.0.1 → 1.1.0`

نمونه:

- قابلیت جدید tool
- قابلیت جدید Desktop
- integration جدید
- API جدید بدون شکستن API قبلی

## 4. Major

برای breaking change یا تغییر بسیار بزرگ در public contract:

`1.1.0 → 2.0.0`

نمونه:

- تغییر incompatible در MCP contract
- حذف/تغییر breaking در tool API
- تغییر authentication که clientهای قبلی را از کار بیندازد
- تغییر معماری public deployment با migration اجباری

## 5. Release tag

هر GitHub Release باید tag متناظر داشته باشد:

`vX.Y.Z`

مثال:

`v1.2.3`

Tag و release version باید یکسان باشند.

## 6. Version sources

نسخه باید در metadataهای پروژه سازگار باشد.

منابع فعلی مهم:

- `pyproject.toml`
- `dana/__init__.py`
- `ui/package.json`
- هر metadata/package/build file دیگری که در release workflow استفاده می‌شود.

نباید یک backend version و یک desktop version بدون دلیل و بدون مستندات متفاوت باقی بمانند.

## 7. Release process

### Method: بررسی تغییرات

1. `git status`
2. `git diff`
3. tests
4. UI build در صورت تغییر UI
5. security/packaging checks در صورت نیاز

### Method: تعیین سطح نسخه

- bug fix → PATCH
- new backward-compatible feature → MINOR
- breaking/major architectural contract → MAJOR

### Method: به‌روزرسانی version

تمام version sourceهای مورد استفاده باید به نسخه جدید برسند.

### Method: commit

پیام commit باید تغییر را واضح توصیف کند.

### Method: tag

`vX.Y.Z`

### Method: push

commit و tag به remote ارسال شوند.

### Method: GitHub Release

Release با همان نسخه ایجاد شود و release notes شامل:

- highlights
- bug fixes
- breaking changes در صورت وجود
- migration notes در صورت وجود
- test status

باشد.

## 8. Pre-release

اگر نسخه هنوز stable نیست می‌توان از SemVer prerelease استفاده کرد:

`1.2.0-rc.1`

اما releaseهای پایدار باید از قالب کامل `X.Y.Z` استفاده کنند.

## 9. تاریخچه فعلی

Repository در زمان تهیه این مستندات دارای tagهای build قبلی از خانواده:

- `v0.1.0-build.13`
- `v0.1.0-build.8`

است.

این build tags با policy جدید releaseهای stable که از `vX.Y.Z` استفاده می‌کنند متفاوت‌اند. از این پس releaseهای رسمی باید بر اساس SemVer کامل منتشر شوند.

## 10. Current project version

در زمان تهیه مستندات، metadata پروژه:

`0.1.1`

است.

قبل از اولین stable release باید مشخص شود که release رسمی از چه baselineای شروع می‌شود؛ پس از آن افزایش نسخه باید strictly طبق SemVer انجام شود.

## 11. Changelog

هر release بهتر است تغییرات را بر اساس:

- Added
- Changed
- Fixed
- Security
- Breaking

گروه‌بندی کند.

## 12. Release safety

قبل از tag:

- [ ] tests سبز
- [ ] UI build سبز در صورت نیاز
- [ ] no unintended files
- [ ] no secrets
- [ ] version sources synchronized
- [ ] README/documentation updated
- [ ] migration notes برای breaking changes
- [ ] git status clean
- [ ] tag هنوز وجود ندارد

بعد از release:

- [ ] tag روی remote موجود است
- [ ] GitHub Release ساخته شده
- [ ] assetها درست هستند
- [ ] release URL کار می‌کند


## 9. Automated desktop releases

GitHub Actions workflow `.github/workflows/gui-build.yml` runs on every push to `main` and on `workflow_dispatch`.

On success it:

1. computes the next SemVer tag (`vMAJOR.MINOR.PATCH`) for the current minor line
2. builds Linux / Windows / macOS desktop packages
3. publishes a GitHub Release with those assets
4. aligns version metadata files with the published tag when needed

Failed builds do not publish a release.
