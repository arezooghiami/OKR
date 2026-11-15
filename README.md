# OKR

وب‌اپ مدیریت اهداف و نتایج کلیدی (فارسی، راست‌به‌چپ). مستندات در [docs/](docs/)، طراحی فنی در [docs/05-technical-design.md](docs/05-technical-design.md).

## اجرای کامل با Docker (دیتابیس + API + وب)

از ریشهٔ پروژه (Docker Desktop باید روشن باشد):

```bash
docker compose -f backend/docker-compose.yml up -d --build
```

سپس `http://localhost:8088`. API موقع بالا آمدن خودش مهاجرت‌های دیتابیس (`alembic upgrade head`) را اجرا می‌کند؛ وب (nginx) مسیر `/api` را به API می‌فرستد.

- توقف: `docker compose -f backend/docker-compose.yml down` (داده در volume می‌ماند).
- لاگ: `docker compose -f backend/docker-compose.yml logs -f api`
- بعد از تغییر کد، همان دستور `up -d --build` را دوباره بزنید.
- تنظیمات (رمز دیتابیس، `OKR_SECRET_KEY`، پورت وب، میرور pip/npm) در `backend/.env`؛ نمونه در [backend/.env.example](backend/.env.example). **روی سرور حتماً `OKR_SECRET_KEY` و `OKR_DB_PASSWORD` را عوض کنید.**

## اجرا برای توسعه (با reload)

فقط دیتابیس در Docker، API و وب روی خود سیستم:

```bash
docker compose -f backend/docker-compose.yml up -d db
```

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --port 8010 --reload
```

```bash
npm --prefix frontend run dev
```

سپس `http://localhost:5173`.

## راه‌اندازی اول (دیتابیس خالی)

با Docker:

```bash
docker compose -f backend/docker-compose.yml exec api python -m app.bootstrap --admin-username admin
```

بدون Docker:

```bash
cd backend && ../.venv/Scripts/python.exe -m alembic upgrade head
```

```bash
cd backend && ../.venv/Scripts/python.exe -m app.bootstrap --admin-username admin
```

این دستور فقط نقش‌های استاندارد، انواع واحد و یک ادمین می‌سازد (رمز تصادفی یک‌بار چاپ می‌شود؛ یا `--admin-password` بدهید). هیچ داده نمایشی ساخته نمی‌شود. برای پاک‌کردن **همه داده** و شروع دوباره، `--reset` اضافه کنید.

## ورود داده (به‌ترتیب)

با ادمین وارد شوید. صفحهٔ «مدیریت ← راه‌اندازی» نشان می‌دهد کدام مرحله انجام شده، چه چیزی جا مانده (مثلاً واحدهای بی‌کاربر یا بدون زمان جلسه) و دکمهٔ رفتن به همان بخش را دارد. ترتیب:

1. **واحدها**: درخت سازمان (اولین واحد = ریشه). برای تعداد زیاد: «ورود از اکسل» در همین تب؛ فایل اکسل واحدها و کاربران فعلی را بگیرید، ردیف اضافه کنید و وارد کنید (پیش‌نمایش چیزی ذخیره نمی‌کند).
2. **کاربران**: کاربر بسازید و در پنل همان کاربر **نقش + واحد** بدهید. مدیر واحد، مسئول KR و ناظر را برای تست نقش‌ها بسازید.
3. **چرخه و جلسه‌ها**: چرخه (تاریخ جلالی) با تعداد پایش‌ها بسازید ← «فعال‌سازی» ← برای هر واحد زمان جلسه را بگذارید.
4. (اختیاری) **اهداف کلان** برای برچسب KR.

**مهاجرت از فایل اکسل پایش:** بعد از ساخت و فعال‌سازی چرخه، «مدیریت ← ورود از اکسل». فایل xlsx (هر شیت = یک واحد) را انتخاب کنید؛ پیش‌نمایش هیچ چیزی ذخیره نمی‌کند و برای هر شیت واحد مقصد (واحد موجود، واحد جدید، یا «وارد نشود») و همهٔ هشدارها را نشان می‌دهد. «ثبت نهایی» اهداف، KRها، مقادیر و یادداشت‌های R1..Rn را با تاریخچه و ممیزی وارد می‌کند؛ ورود دوبارهٔ همان فایل تکرار ایجاد نمی‌کند.

سپس با کاربر «مدیر واحد»: صفحهٔ «جلسه پایش» ← «+ هدف جدید» ← «+ KR جدید» (مسئول KR را انتخاب کنید) ← «برگزار شد» برای جلسهٔ شروع. با کاربر «مسئول KR» در «KRهای من» مقدار ثبت کنید.

## تست‌ها

```bash
cd backend && ../.venv/Scripts/python.exe -m pytest -q
```

```bash
npm --prefix frontend test
```

تست‌های بک‌اند روی پایگاه‌های جدا (`okr_test`، `okr_test_empty`) اجرا می‌شوند و به داده توسعه دست نمی‌زنند. داده نمایشی فقط داخل `backend/tests/demo_seed.py` است (فقط برای تست).

## قرارداد API

پس از تغییر مدل‌های پاسخ: `python -m app.export_openapi` سپس `npm --prefix frontend run gen:api` (جزئیات در بخش ۱۰ سند فنی).
