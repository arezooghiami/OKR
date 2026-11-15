# مرجع فنی سامانهٔ پایش OKR

تاریخ: ۲۴ آبان ۱۴۰۵ (۲۰۲۶-۱۱-۱۵) · مخاطب: برنامه‌نویس، مدیر سیستم، بازبین فنی
مبنا: کد فعلی مخزن و [07-review-and-roadmap.md](07-review-and-roadmap.md). اگر این سند با [05-technical-design.md](05-technical-design.md) فرق داشت، این سند وضع **فعلی کد** را می‌گوید و ۰۵ طرح اولیه است.

---

## ۱. خلاصه

| مورد | وضعیت |
|---|---|
| نوع سیستم | وب‌اپ تک‌سازمانی (single-tenant)، نصب روی شبکهٔ داخلی، بدون نیاز به اینترنت در زمان اجرا |
| معماری | SPA (React) ← nginx ← REST API (FastAPI) ← PostgreSQL |
| زبان رابط | فارسی، راست‌به‌چپ، تقویم جلالی، اعداد فارسی |
| حجم کد | بک‌اند حدود ۵٬۹۰۰ خط Python، فرانت حدود ۳٬۷۰۰ خط TS/TSX (بدون فایل تولیدی `schema.d.ts`)، ۶۱۸ خط CSS در سه فایل |
| تست | بک‌اند ۶۴ تست (pytest)، فرانت ۱۸ تست (vitest)، `tsc` بدون خطا. همه پاس |
| آمادگی production | **هنوز نه.** git، بکاپ، HTTPS و چند کنترل امنیتی کم است (بخش ۱۲) |

---

## ۲. پشتهٔ فناوری

| لایه | فناوری | نکته |
|---|---|---|
| بک‌اند | Python، FastAPI، Uvicorn | `requires-python >=3.13` در `pyproject.toml`، ولی image داکر `python:3.12-slim` است (ناسازگاری، بخش ۱۲) |
| ORM و migration | SQLAlchemy 2، Alembic | سه migration در `backend/migrations/versions/` |
| اعتبارسنجی | Pydantic v2، pydantic-settings | همهٔ تنظیمات با پیشوند `OKR_` |
| دیتابیس | PostgreSQL 17 (image رسمی) | درایور psycopg 3 |
| امنیت | argon2-cffi (هش رمز)، PyJWT (توکن) | ldap3 نصب است ولی به login وصل نیست |
| اکسل | openpyxl | ورود و خروج xlsx |
| فرانت | React 18، TypeScript 5.6، Vite 5، react-router 6 | بدون کتابخانهٔ UI و بدون CDN. فونت محلی |
| قرارداد API | OpenAPI ← `openapi-typescript` | کلاینت تایپ‌شده از روی قرارداد |
| تست | pytest + httpx، vitest | Playwright هنوز نیست (فاز ۳) |
| استقرار | Docker Compose (سه سرویس: db، api، web) | میرور pip/npm قابل تنظیم برای شبکهٔ محدود |

---

## ۳. معماری

```
مرورگر (SPA)
   │  HTTPS (هنوز HTTP)       Authorization: Bearer <access>
   ▼
nginx (کانتینر web، پورت 8088 روی میزبان)
   ├─ /            → فایل‌های استاتیک build (index.html بدون cache، /assets/ با cache یک‌ساله)
   ├─ /api/        → proxy به api:8000   (حداکثر حجم آپلود 25MB، timeout 120s)
   └─ /health      → api:8000/health
   ▼
FastAPI (کانتینر api)
   routers/  ← لایهٔ HTTP، ورودی/خروجی، بررسی دسترسی
   services/ ← منطق دامنه (محاسبه، ACL، جلسه، ورود اکسل، درخت سازمان)
   models/   ← SQLAlchemy
   core/     ← config، db، security، audit، deps
   ▼
PostgreSQL (کانتینر db، volume `okr_pg`)
```

**اصول طراحی که در کد رعایت شده:**
1. **API-first:** هیچ HTML سمت سرور نیست و همه‌چیز از `/api/v1` می‌گذرد. کلاینت موبایل آینده همین API را مصرف می‌کند.
2. **منطق خالص جدا از دیتابیس:** `services/calc.py` و `services/acl.py` هیچ دسترسی به دیتابیس ندارند و مستقل تست می‌شوند.
3. **هویت جدا از نسخه:** `objective` و `key_result` فقط هویت‌اند. تعریف (عنوان، مبنا، هدف، وزن و …) در `objective_version` و `kr_version` است و هر ویرایش یک نسخهٔ تازه با دلیل می‌سازد.
4. **احراز هویت بدون کوکی:** توکن Bearer (ADR-21)، تا وب و موبایل یک جریان ورود داشته باشند.

---

## ۴. چیدمان مخزن

```
OKR_project/
├─ backend/
│  ├─ app/
│  │  ├─ main.py            ساخت برنامه، CORS، ثبت ۱۲ router زیر /api/v1، مسیر /health
│  │  ├─ bootstrap.py       راه‌اندازی دیتابیس خالی: نقش‌ها، انواع واحد، یک ادمین (‎--reset برای پاک‌سازی کامل)
│  │  ├─ defaults.py        ماتریس دسترسی چهار نقش استاندارد و انواع واحد
│  │  ├─ export_openapi.py  تولید frontend/openapi.json
│  │  ├─ core/              config · db · security · audit · deps
│  │  ├─ models/            access · audit · cycle · okr · org · support · user
│  │  ├─ schemas/out.py     مدل‌های پاسخ = مرجع قرارداد API
│  │  ├─ services/          calc · acl · access · cycles · okr · reviews · orgtree · excel_import · org_import · export
│  │  ├─ routers/           auth · admin · admin_data · dashboard · dossier · exports · goals_view · imports · okr · sessions · setup · workspace
│  │  └─ auth_providers/    base · ldap (فعلاً استفاده نمی‌شود)
│  ├─ migrations/           Alembic
│  ├─ tests/                pytest (+ demo_seed.py فقط برای تست)
│  ├─ Dockerfile · docker-compose.yml · .env.example · pyproject.toml
├─ frontend/
│  ├─ src/
│  │  ├─ domain/            منطق خالص: calc، format، jalali، setup (+ تست)
│  │  ├─ api/               client، hooks، typed (useGet)، schema.d.ts (تولیدی)، types (alias)
│  │  ├─ auth/              AuthContext
│  │  ├─ ui/                Layout، parts، Peek، JalaliDate، ExportButton
│  │  ├─ features/          صفحه‌ها (بخش ۹) و admin/
│  │  └─ styles/            app.css، extra.css، v2.css (قرار است یکی شوند)
│  ├─ openapi.json · nginx.conf · Dockerfile · vite.config.ts
└─ docs/
```

**پاک‌سازی فاز ۰ (انجام شد، ۲۴ آبان ۱۴۰۵):** فایل‌های قالب IDE در ریشه (`main.py`، `pyproject.toml`، `poetry.lock`، `test_main.http`)، `features/Alignment.tsx`، `routers/alignment.py` و `services/alignment.py` و سه تست همترازی حذف شدند. HTMLهای آزمایشی به `docs/design/archive/` رفتند. مدل و جدول `alignment` فعلاً در دیتابیس مانده‌اند تا حذفشان با migration جدا انجام شود.

---

## ۵. مدل داده

قواعد عمومی: کلید UUID، زمان به UTC، حذف = آرشیو (`archived_at`)، فیلد `version` برای قفل خوش‌بینانه.

| گروه | جدول‌ها | توضیح |
|---|---|---|
| کاربر و ورود | `user_account`، `auth_identity`، `refresh_token`، `setting` | `auth_identity.provider` فعلاً فقط `local`. refresh token به‌صورت هش ذخیره می‌شود |
| سازمان | `unit_type`، `unit`، `org_version`، `unit_placement`، `membership` | درخت سازمان نسخه‌دار است: جایگاه هر واحد در `unit_placement` برای یک `org_version`. عضویت = (کاربر، واحد، نقش) |
| دسترسی | `role`، `role_permission`، `role_scope` | اثر (allow/deny) برای هر (منبع، عمل) و دامنه برای هر منبع |
| دوره و جلسه | `strategic_goal`، `cycle`، `time_point`، `unit_session` | `time_point` = پایش ۱..n. `unit_session` = جلسهٔ یک واحد در یک پایش، با زمان، مکان، وضعیت و `held_at` |
| OKR | `objective`، `objective_version`، `key_result`، `kr_version`، `kr_collaborator` | نسخهٔ آخر = تعریف جاری |
| پایش | `review_entry` | مقدار، یادداشت، و برای جلسهٔ برگزارشده `is_frozen`، `frozen_kr_version_id`، `frozen_percent` |
| همراه | `comment`، `attachment`، `notification` | کامنت فعال است. پیوست و اعلان فقط جدول دارند و endpoint ندارند |
| ممیزی | `audit_event` | زنجیرهٔ هش (بخش ۸) |
| بایگانی | `alignment` | همترازی هدف به هدف، کنار گذاشته شد. API و صفحه‌اش حذف شده‌اند. فقط جدول مانده است |

---

## ۶. موتور محاسبه (`services/calc.py`)

**انواع KR و فرمول درصد پیشرفت (۰ تا ۱۰۰، با برش به بازه):**

| نوع | فرمول |
|---|---|
| `numeric` | `(مقدار − مبنا) ÷ (هدف − مبنا) × 100`. جهت صعودی یا نزولی از خود مبنا و هدف می‌آید. مبنا = هدف خطای تعریف است |
| `milestone` | خود مقدار (۰ تا ۱۰۰) |
| `boolean` | بله = ۱۰۰، خیر = ۰ |
| `maintain` | داخل بازهٔ [min, max] = ۱۰۰. بیرون از بازه به نسبت فاصله تا عرض بازه کم می‌شود |

- مقدار ثبت‌نشده `None` برمی‌گرداند، نه صفر.
- **وضعیت:** `≥ 70` در مسیر، `≥ 40` در خطر، کمتر از آن عقب، و `None` ثبت‌نشده. آستانه‌ها ثابت‌اند و نسبت به زمان نیستند (تصمیم مالک، بخش ۱۳).
- **امتیاز هدف و واحد:** میانگین وزنی (`weighted_mean`). امتیاز هدف از KRها و امتیاز واحد از هدف‌های دارای KR.
- **قاعدهٔ وسط دوره:** KRی که بعد از زمان جلسه ساخته شده یا قبل از آن آرشیو شده، در آن جلسه حساب نمی‌شود (`_counts_in_session`).

**ایرادهای شناخته‌شده (فاز ۳):**
- `weighted_mean` مقدار ثبت‌نشده را **صفر** حساب می‌کند. باید «پوشش ثبت» از «پیشرفت» جدا شود.
- وزن صفر یا منفی رد نمی‌شود.
- آستانه‌های وضعیت در فرانت هم تکرار شده‌اند. API باید خودش `status` را برگرداند.

---

## ۷. موتور دسترسی (`services/acl.py`)

- **منابع:** هدف، نتیجهٔ کلیدی، مقدار پایش، جلسه، گزارش، کاربران.
- **عمل‌ها:** مشاهده، ایجاد، ویرایش، حذف، تأیید.
- **دامنه برای هر منبع:** واحد خود · واحد و زیرمجموعه · همه.
- **قواعد:**
  - deny بر allow غالب است و تعریف‌نشده یعنی ممنوع.
  - allow هر نقش فقط وقتی حساب است که واحد هدف داخل دامنهٔ آن نقش باشد.
  - allowهای چند نقش با هم جمع می‌شوند.
- یک پیاده‌سازی، دو کاربرد: اجرای واقعی و **شبیه‌ساز دسترسی** (`POST /admin/access/simulate`) که نتیجه، قانون مؤثر و دلیل را برمی‌گرداند.

**چهار نقش پیش‌فرض** (`defaults.py`):

| نقش | خلاصهٔ اختیار | دامنه |
|---|---|---|
| ادمین سیستم | همه‌چیز، به‌جز حذف مقدار پایش و تأیید کاربران | همه |
| مدیر واحد | تعریف و ویرایش هدف و KR، ثبت مقدار، مدیریت جلسه | واحد و زیرمجموعه |
| مسئول KR | مشاهده و ثبت مقدار برای KRهای خود | واحد خود |
| ناظر | فقط مشاهده و گزارش | همه |

**ایراد شناخته‌شده:** فهرست واحدهای قابل‌مشاهده (`visible_units`) قانون deny را در نظر نمی‌گیرد (فاز ۳).

---

## ۸. احراز هویت، امنیت و ممیزی

**ورود (`routers/auth.py`، `core/security.py`):**
- رمز با **Argon2id** هش می‌شود.
- بعد از ۵ تلاش ناموفق، حساب ۱۵ دقیقه قفل می‌شود (`max_failed_logins`، `lockout_minutes`).
- توکن access با عمر ۱۵ دقیقه و refresh با عمر ۱۴ روز.
- refresh **چرخشی** است: هر بار تعویض می‌شود و اگر توکن قدیمی دوباره استفاده شود، تشخیص داده می‌شود.
- فقط `source == "local"` پذیرفته می‌شود. LDAP طبق تصمیم مالک بعد از فروش وصل می‌شود.

**ممیزی (`core/audit.py`):**
- هر تغییر داده یک `audit_event` می‌سازد که شامل بازیگر، عمل، منبع، before/after و IP است.
- `hash = SHA-256(prev_hash, at, actor, action, resource, resource_id, before, after)`، از `GENESIS = "0"*64`.
- نویسنده‌ها با `pg_advisory_xact_lock` پشت هم قرار می‌گیرند تا زنجیره شاخه پیدا نکند. در یک تراکنش، سر زنجیره cache می‌شود تا ورودهای انبوه سریع بمانند.
- `verify_chain` اولین ردیف خراب را پیدا می‌کند.

**کنترل‌های موجود:** optimistic locking روی منابع قابل ویرایش، تست همگامی OpenAPI، اجرای کانتینر API با کاربر غیر root (uid 10001)، و تم کاملاً روی متغیر CSS (هیچ hex در tsx نیست).

---

## ۹. صفحه‌های فرانت (`App.tsx`)

| مسیر | صفحه | کاربر اصلی |
|---|---|---|
| `/login` | ورود | همه |
| `/` | نقش سازمانی ← داشبورد، بقیه ← `/unit` | — |
| `/overview` | داشبورد سازمان | مدیران ارشد |
| `/unit/:unitId?` | جدول واحد (اهداف و KRها) | مدیر واحد |
| `/session`، `/sessions/:id` | جلسهٔ پایش جاری یا مشخص | مدیر واحد |
| `/my` | KRهای من: ذخیرهٔ خودکار، مقدار قبلی، دلیل قفل | مسئول KR |
| `/krs/:id` | جزئیات KR: نسخه‌ها، مقایسه، کامنت | همه |
| `/goals` | اهداف کلان (KRها بر اساس هدف راهبردی) | مدیران |
| `/units`، `/units/:unitId` | پروندهٔ واحد (تاریخچه) | مدیران |
| `/admin/:tab?` | راه‌اندازی، واحدها، کاربران، دوره، اهداف کلان، نقش‌ها، ورود از اکسل | ادمین |

**الگوها:**
- صفحه‌ها lazy load می‌شوند.
- `useGet("/api/v1/…")` مسیر و نوع پاسخ را از `schema.d.ts` می‌گیرد، پس مسیر اشتباه کامپایل نمی‌شود.
- دیگر قابلیت‌ها: پالت فرمان با Ctrl+K، حالت تیره که در `localStorage` ذخیره می‌شود، و انتخابگر تاریخ جلالی.

**ایراد شناخته‌شده:** مسئول KR به `/unit` فرستاده می‌شود، نه `/my` (`App.tsx:28`). این مورد در فاز ۲ درست می‌شود.

---

## ۱۰. سطح API (`/api/v1`)

| حوزه | مسیرها |
|---|---|
| ورود | `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /me` |
| داشبورد | `GET /dashboard/overview` · `GET /org/tree` · `GET /goals` · `GET /goals/overview` |
| فضای کار | `GET /me/units` · `GET /units/{id}/workspace` · `GET /units/{id}/dossier` · `GET /units/{id}/members` |
| OKR | `POST /units/{id}/objectives` · `PATCH /objectives/{id}` · `POST /objectives/{id}/archive` · `POST /objectives/{id}/key-results` · `GET/PATCH /key-results/{id}` · `POST /key-results/{id}/archive` · `POST /key-results/{id}/comments` · `GET /me/key-results` |
| دوره و جلسه | `GET /cycles` · `GET /cycles/current` · `GET /time-points/{id}/sessions` · `GET /units/{id}/sessions` · `GET /sessions/{id}` · `GET /sessions/{id}/siblings` · `PUT /sessions/{id}` · `POST /sessions/{id}/hold` · `PUT /sessions/{id}/entries/{kr_id}` |
| ورود و خروج اکسل | `POST /excel/preview` · `POST /excel/commit` · `GET /org/template.xlsx` · `POST /org/preview` · `POST /org/commit` · `GET /units/{id}/export.xlsx` · `GET /export/org.xlsx` |
| مدیریت | `GET /setup` · `GET/POST/PATCH` روی unit-types، units، goals، cycles، time-points، users، memberships، roles · `GET /admin/roles` · `PUT /admin/roles/{id}` · `GET /admin/users` · `POST /admin/access/simulate` · `GET /admin/audit` |
| سلامت | `GET /health` (بیرون از `/api/v1`) |

**گردش قرارداد:**
```
schemas/out.py ─► python -m app.export_openapi ─► frontend/openapi.json ─► npm run gen:api ─► src/api/schema.d.ts
```
اگر `openapi.json` کهنه باشد، تست `test_committed_openapi_is_up_to_date` شکست می‌خورد. بدنه‌های POST/PUT/PATCH هنوز با نوع دستی فرستاده می‌شوند.

---

## ۱۱. ورود از اکسل (`services/excel_import.py`)

- **ورودی:** فایل پایش قدیمی، که در آن هر شیت یک واحد است، ردیف‌ها هدف و KR هستند و ستون‌های R1..Rn مقدار هر پایش‌اند. سقف حجم ۱۰MB و ۶۰ ستون است.
- **دو نیمه:**
  - `parse_workbook` خالص است و ایرادهای فایل واقعی را تحمل می‌کند: متن سرستون داخل داده، صفرهای فرمولی، رقم فارسی، متن در خانهٔ عددی، `#REF!`، و یکسان‌سازی «ي/ی» و «ك/ک».
  - `apply_import` از همان سرویس‌های عادی می‌نویسد، یعنی با نسخه و ممیزی.
- **پیش‌نمایش = همان کد ثبت + rollback.** آنچه پیش‌نمایش نشان می‌دهد دقیقاً همان است که ثبت می‌کند.
- **idempotent:** ورود دوبارهٔ همان فایل رکورد تکراری نمی‌سازد.
- برای هر شیت واحد مقصد انتخاب می‌شود: واحد موجود، واحد جدید یا «وارد نشود». هشدارها در سه سطح error، warning و info هستند.
- ورود جداگانهٔ ساختار سازمان و کاربران با قالب `org/template.xlsx` انجام می‌شود.

**ایراد شناخته‌شده:** فایل اکسل ستون «مسئول» ندارد، پس KRها بی‌مسئول وارد می‌شوند و «KRهای من» خالی می‌ماند (فاز ۲).

---

## ۱۲. استقرار و پیکربندی

**اجرا:**
```bash
docker compose -f backend/docker-compose.yml up -d --build
```
```bash
docker compose -f backend/docker-compose.yml exec api python -m app.bootstrap --admin-username admin
```
کانتینر API موقع بالا آمدن `alembic upgrade head` را اجرا می‌کند و بعد Uvicorn را روی پورت 8000 بالا می‌آورد.

**متغیرهای محیطی (`backend/.env`):**

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `OKR_DATABASE_URL` | `postgresql+psycopg://okr:okr_dev_password@…` | اتصال دیتابیس |
| `OKR_SECRET_KEY` | `dev-only-secret-change-me-…` | **کلید امضای JWT. اگر عوض نشود، می‌شود توکن جعل کرد** |
| `OKR_DB_PASSWORD` | `okr_dev_password` | قبل از اولین اجرا تعیین شود |
| `OKR_CORS_ORIGINS` | `["http://localhost:5173"]` | در compose خالی است، چون same-origin است |
| `OKR_ACCESS_TOKEN_MINUTES` / `OKR_REFRESH_TOKEN_DAYS` | 15 / 14 | عمر توکن‌ها |
| `OKR_TIMEZONE` | `Asia/Tehran` | |
| `OKR_DB_PORT` / `OKR_WEB_PORT` | 5433 / 8088 | پورت‌های منتشرشده روی میزبان |
| `PIP_INDEX_URL` / `NPM_REGISTRY` | مخزن رسمی | میرور برای شبکهٔ محدود |

**شکاف‌های عملیاتی (از بازبینی، فاز ۴):**

| شدت | مورد | محل |
|---|---|---|
| Critical | پروژه git ندارد | ریشه |
| Critical | کلید و رمز پیش‌فرض بدون هشدار اجرا می‌شوند | `core/config.py:10`، `docker-compose.yml` |
| Critical | بکاپ نیست و migration بدون بکاپ قبلی اجرا می‌شود | `backend/Dockerfile` (CMD) |
| High | HTTPS نیست، در حالی که refresh token در `localStorage` است | `nginx.conf` |
| High | کاربر نمی‌تواند رمز خودش را عوض کند | `routers/auth.py` |
| High | جلسهٔ برگزارشده واقعاً منجمد نیست: آرشیو هدف یا تغییر وزن آن گذشته را عوض می‌کند | `services/reviews.py`، `routers/sessions.py` |
| High | وابستگی‌ها pin نیستند و نسخهٔ Python در سه جا متفاوت است (3.12، ‎>=3.13، 3.14) | `Dockerfile`، `pyproject.toml`، `01-product-overview.md` |
| High | پورت دیتابیس روی میزبان باز است | `docker-compose.yml` |
| Medium | N+1 در داشبورد (هزاران query در هر بار لود) | `routers/dashboard.py` |
| Medium | قفل حساب را می‌شود برای DoS سوءاستفاده کرد و rate-limit نیست | `routers/auth.py`، `nginx.conf` |
| Medium | logging ساخت‌یافته نیست و health check فقط `ok` برمی‌گرداند | `main.py` |
| Medium | هدرهای امنیتی (CSP، HSTS، nosniff، frame-ancestors) نیست | `nginx.conf` |

---

## ۱۳. برنامهٔ کار فنی (از نقشهٔ راه)

اصل: **قابلیت تازه ساخته نمی‌شود.** هر فاز با یک معیار اندازه‌پذیر بسته می‌شود. فازهای ۱ تا ۴ تا حدی موازی‌اند.

| فاز | کار فنی | معیار بسته شدن |
|---|---|---|
| ۰. ایمنی کار (۱–۲ روز) | `git init`، `.gitignore`، remote داخلی. حذف کد مرده. یکی کردن اسناد | کد در git است و یک نقشهٔ راه معتبر هست |
| ۱. ریست بصری (~۱ هفته) | ادغام سه CSS در `tokens.css`، `base.css`، `components.css` و `screens.css` با `@layer`. توکن معنایی. پالت انتخابی. ۷ اندازهٔ فونت، ۳ وزن، ۴ شعاع. کنتراست AA. تخت کردن صفحهٔ جلسه و جدول. به‌روزرسانی `design-system.md` | تأیید مالک، همهٔ متن‌ها AA، هیچ فونتی زیر ۱۳px |
| ۲. باز کردن حلقهٔ اصلی (~۱ هفته) | مسیر خانه بر اساس نقش. ستون «مسئول» در ورود اکسل و پیش‌فرض = مسئول هدف. نبود زمان جلسه ثبت را نبندد. مدیر واحد «برگزار شد» بزند. ادغام صفحهٔ جلسه و پرونده در صفحهٔ واحد. واژه‌نامهٔ یکسان | مسئول KR دو مقدار را در کمتر از ۲ دقیقه ثبت کند |
| ۳. اعداد قابل اعتماد (~۱ هفته) | snapshot کامل امتیاز KR، هدف و واحد هنگام `hold` (این کار N+1 را هم حل می‌کند). جدا کردن پوشش ثبت از پیشرفت. امتیاز سازمان از یک دور مشخص. `status` از API. اعتبارسنجی وزن. رفع `visible_units`. **Playwright e2e** برای ورود، ثبت، «برگزار شد» و ورود اکسل | اختلاف هر واحد با اکسل کمتر از ۰٫۵ واحد درصد |
| ۴. آمادگی سرور (~۱ هفته، موازی) | رد کلید پیش‌فرض یا کوتاه در startup. compose مخصوص production بدون پورت DB. HTTPS با CA داخلی و هدرهای امنیتی. `pg_dump` شبانه، بکاپ قبل از migration و تمرین restore. تغییر رمز توسط کاربر و ابطال توکن‌ها. rate-limit و پیام خطای یکسان. lock وابستگی‌ها. logging با چرخش. runbook | چک‌لیست کامل و restore موفق روی دیتابیس خالی |
| ۵. پایلوت (۳ واحد، یک دور) | ورود داده، ساخت کاربران، فهرست «ثبت‌نکرده‌ها» با دکمهٔ کپی، اندازه‌گیری نرخ ثبت و نرخ خودثبتی | نرخ خودثبتی ≥ ۶۰٪ و رضایت ≥ ۴ از ۵ |
| ۶. بعد از دروازه | ورود دوره‌های بسته، BI، پیوست، PDF، نقشهٔ حرارتی، **CI داخلی** (pytest، vitest، tsc، ruff، e2e)، بستهٔ نصب آفلاین، حالت دمو | — |
| بعد از فروش | LDAP/AD (`auth_providers/ldap.py` آماده است ولی وصل نیست)، SSO و یکپارچه‌سازی‌ها | بر اساس نیاز مشتری |

**تصمیم‌های مالک که روی کد اثر دارند:** پالت (A یا B)، چه کسی «برگزار شد» بزند، و وضعیت نسبت به زمان یا آستانهٔ ثابت ۷۰/۴۰.

---

## ۱۴. دستورهای روزمره

```bash
cd backend && ../.venv/Scripts/python.exe -m pytest -q
```
```bash
npm --prefix frontend test
```
```bash
npm --prefix frontend run typecheck
```
```bash
cd backend && ../.venv/Scripts/python.exe -m app.export_openapi
```
```bash
npm --prefix frontend run gen:api
```

تست‌های بک‌اند روی دیتابیس‌های جدای `okr_test` و `okr_test_empty` اجرا می‌شوند و به دادهٔ توسعه دست نمی‌زنند.
