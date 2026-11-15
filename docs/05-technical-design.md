# OKR — طراحی فنی نسخه اول (برش عمودی هسته)

> مبنا: [02-PRD.md](02-PRD.md) و [04-core-scenario.md](04-core-scenario.md) · طرح UI: [design/design-system.md](design/design-system.md) (طرح‌های HTML قدیمی در [design/archive/](design/archive/) بایگانی‌اند) · تصمیم‌های این سند از گفتگوی ۱۴۰۵/۰۸/۱۲ آمده است.

## ۱. تصمیم‌های قطعی

| موضوع | تصمیم | تفاوت با PRD |
|---|---|---|
| دامنه مرحله ۱ | برش عمودی هسته: ورود، سازمان، چرخه و جلسه‌ها، O/KR با نسخه‌بندی، صفحه جلسه و پایش، KRهای من، جزئیات KR، نمای کلی، دسترسی (نقش‌ها + شبیه‌ساز) | — |
| دیتابیس | PostgreSQL از روز اول (Docker برای توسعه) | — |
| احراز هویت کلاینت | توکن Bearer: access کوتاه‌عمر + refresh چرخشی | PRD کوکی HttpOnly گفته بود؛ برای مسیر موبایل عوض شد (ADR-21) |
| ورود | حساب محلی + AD/LDAP همزمان، پشت واسط Provider | — |
| بک‌اند | FastAPI، SQLAlchemy 2، Alembic، Pydantic v2، Poetry | — |
| فرانت | React + TypeScript + Vite، بدون CDN، فونت محلی | — |

## ۲. قواعد «آماده برای موبایل» (هزینه‌شان الان تقریباً صفر است)

1. **API-first.** هر کاری که UI می‌کند از `/api/v1` می‌گذرد؛ هیچ HTML سمت سرور، هیچ وابستگی به کوکی یا نشست سرور.
2. **قرارداد OpenAPI** تنها مرجع؛ کلاینت تایپ‌شده از آن تولید می‌شود. کلاینت موبایل همین را می‌گیرد.
3. **آدرس API قابل پیکربندی در زمان اجرا** (`window.__OKR_CONFIG__.apiBase`)؛ نه فرض same-origin. CORS از تنظیمات سرور.
4. **لایه‌بندی فرانت:** `domain/` (منطق خالص: محاسبه درصد، وضعیت، تاریخ جلالی، فرمت عدد — بدون DOM)، `api/` (کلاینت)، `ui/` (اجزای بصری)، `features/` (صفحات). `domain` و `api` در React Native / Capacitor بدون تغییر قابل استفاده‌اند.
5. **انتزاع ذخیره‌سازی:** توکن‌ها و ترجیحات از رابط `Storage` می‌گذرند (وب: `localStorage`؛ موبایل: Keychain/Keystore با افزونه).
6. **UI لمسی‌دوست:** هدف لمسی حداقل ۴۴px، هیچ عملکردی فقط با hover، میانبر صفحه‌کلید (Ctrl+K، J/K) فقط **افزوده** است، نه تنها راه. چیدمان واکنش‌گرا از ۳۶۰px (تبدیل پنل کناری به صفحه تمام‌عرض / bottom sheet).
7. **فایل‌ها با هدر Authorization** (نه URL عمومی یا کوکی)؛ دانلود از طریق endpoint با بررسی ACL.
8. **همزمانی خوش‌بینانه:** هر منبع قابل ویرایش فیلد `version` (ETag/`If-Match`) دارد؛ ثبت دوباره/آفلاین بعداً ممکن می‌شود.
9. **صفحه‌بندی مبتنی بر cursor** و پاسخ‌های سبک (فهرست جدا از جزئیات) برای شبکه ضعیف.
10. **اعلان‌ها** از ابتدا موجودیت `Notification` در دیتابیس دارند؛ بعداً push (FCM/APNs) پشت یک واسط وصل می‌شود.

## ۳. چیدمان مخزن

```
OKR_project/
├─ backend/
│  ├─ pyproject.toml        alembic.ini        docker-compose.yml (PostgreSQL)
│  ├─ migrations/
│  ├─ app/
│  │  ├─ main.py            ساخت برنامه، CORS، مسیرها
│  │  ├─ core/              config، db، security (Argon2/JWT)، audit (هش زنجیره‌ای)، errors
│  │  ├─ models/            SQLAlchemy
│  │  ├─ schemas/           Pydantic (ورودی/خروجی API)
│  │  ├─ services/          calc، acl، versioning، sessions، dashboard
│  │  ├─ auth_providers/    local، ldap
│  │  ├─ routers/           auth، org، cycles، okr، reviews، dashboard، admin
│  │  └─ seed.py            دمو (سازمان فرضی هم‌شکل طرح v7)
│  └─ tests/
├─ frontend/                Vite + React + TS (بعد از بک‌اند اولیه)
└─ docs/
```

فایل‌های نمونه ریشه (`main.py`, `test_main.http`, `pyproject.toml`) مربوط به قالب اولیه‌اند و با `backend/` جایگزین می‌شوند.

## ۴. مدل داده (برش اول)

هویت پایدار جدا از نسخه است تا «تا آن جلسه» و تاریخچه ساده بماند.

| گروه | جدول‌ها |
|---|---|
| کاربر و ورود | `user`, `auth_identity(provider, external_id)`, `refresh_token`, `setting` |
| سازمان | `unit_type`, `unit` (هویت)، `org_version`, `unit_placement(org_version, unit, parent, sort)`, `membership(user, unit, role)` |
| دسترسی | `role`, `role_permission(role, resource, action, effect)`, `role_scope(role, resource, scope)` |
| چرخه | `strategic_goal`, `cycle`, `time_point(cycle, kind, ordinal)`, `unit_session(unit, time_point, scheduled_at, place, status, held_at)` |
| OKR | `objective`, `key_result` (هویت)، `objective_version`, `kr_version` (فیلدهای تعریفی + شماره، فاعل، زمینه، دلیل)، `kr_collaborator` |
| پایش | `review_entry(kr, unit_session, value, note, status, confidence, kr_version_id, frozen_percent)` |
| همراهان | `attachment`, `comment`, `notification` |
| حسابرسی | `audit_event(seq, prev_hash, hash, actor, action, resource, before, after, ip, at)` |

قواعد کلیدی:
- شناسه UUID، زمان UTC، حذف نرم، `version` برای قفل خوش‌بینانه.
- `key_result` فیلد تعریفی ندارد؛ آخرین `kr_version` همان تعریف جاری است.
- درصد جلسه **زنده** = با آخرین نسخه تعریف؛ با «برگزار شد» `kr_version_id` و `frozen_percent` ثبت و منجمد می‌شود (PRD §3).
- ساختار سازمان با `org_version` نسخه‌دار است؛ گزارش هر چرخه با نسخه ساختار همان چرخه ساخته می‌شود.

## ۵. موتور دسترسی (ACL)

مطابق ماتریس طرح v7: برای هر **نقش** و هر **منبع** (هدف، نتیجه کلیدی، مقدار پایش، جلسه، گزارش، کاربران) پنج عمل (مشاهده، ایجاد، ویرایش، حذف، تأیید) با سه حالت **مجاز / ممنوع / تعریف‌نشده** و یک **دامنه** (واحد خود · واحد و زیرمجموعه · همه).

- ممنوع بر مجاز غالب است؛ تعریف‌نشده = ممنوع.
- اجتماع مجوز نقش‌های کاربر؛ دامنه در لایه کوئری اعمال می‌شود: `scope_filter(user, action, resource)` شرط SQL برمی‌گرداند (زیرمجموعه‌ها با CTE بازگشتی روی `unit_placement` نسخه فعال).
- `explain(user, action, resource, unit)` همان پاسخ **شبیه‌ساز** را می‌دهد: نتیجه + قانون مؤثر + دلیل. یک پیاده‌سازی، دو استفاده (اجرا و توضیح).
- هر تغییر قانون در `audit_event`.

## ۶. احراز هویت

`AuthProvider` با دو پیاده‌سازی: `LocalProvider` (Argon2id، قفل پس از تلاش ناموفق) و `LdapProvider` (`ldap3`، LDAPS، نگاشت گروه AD به نقش، ابزار تست اتصال). ورود → `access` (۱۵ دقیقه) + `refresh` (چرخشی، ذخیره هش در دیتابیس، ابطال با خروج). AD آزمایشی در دسترس نیست؛ LDAP با سرور ساختگی تست می‌شود و تا اتصال به AD واقعی «تأییدنشده در محیط واقعی» برچسب می‌خورد.

## ۷. API (نمونه مسیرها، `/api/v1`)

| حوزه | مسیرها |
|---|---|
| auth | `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /me` |
| org | `GET /org/tree` · `POST/PATCH /units` · `POST /org/versions` |
| cycles | `GET/POST /cycles` · `GET /cycles/{id}` · `PUT /sessions/{id}` (زمان‌بندی) · `POST /sessions/{id}/hold` |
| okr | `GET /units/{id}/objectives` · `POST /objectives` · `POST /key-results` · `PATCH /key-results/{id}` (نسخه جدید + دلیل) · `GET /key-results/{id}` (+ `/versions`, `/compare`) |
| reviews | `GET /sessions/{id}` (صفحه جلسه) · `PUT /sessions/{id}/entries/{kr}` · `GET /me/key-results` |
| dashboard | `GET /dashboard/overview?cycle=` · `GET /dashboard/units/{id}` |
| files/comments | `POST /key-results/{id}/attachments` · `GET /attachments/{id}` · `POST /key-results/{id}/comments` |
| admin | `GET/PUT /admin/roles` · `GET /admin/users` · `POST /admin/access/simulate` · `GET /admin/audit` |

## ۸. ترتیب ساخت

1. بک‌اند: پروژه، Docker/PostgreSQL، مدل‌ها و migration، محاسبه، ACL، ورود، audit — با تست.
2. بک‌اند: O/KR + نسخه‌بندی، چرخه/جلسه، پایش و انجماد، داشبورد، seed دمو.
3. فرانت: توکن‌های طرح، اجزای پایه، ورود، سپس صفحات به ترتیب: جلسه ← KRهای من ← نمای کلی ← جزئیات KR ← مدیریت.
4. بازبینی سرتاسری با داده دمو و تطبیق با رفتار طرح v7.

## ۹. ADR جدید

**ADR-21:** احراز هویت کلاینت با توکن Bearer (access+refresh چرخشی) به‌جای کوکی HttpOnly، برای اینکه وب و موبایل یک API و یک جریان ورود داشته باشند. جبران: access کوتاه‌عمر، refresh چرخشی با تشخیص استفاده مجدد، ذخیره توکن در وب فقط در حافظه + refresh در `localStorage` (یا بعداً BFF اختیاری برای وب).

## ۱۰. قرارداد API و کلاینت تایپ‌شده

مرجع قرارداد، مدل‌های پاسخ در `backend/app/schemas/out.py` است (فیلدها بدون مقدار پیش‌فرض: لازم، و در صورت نیاز nullable). هر مسیر خروجی‌اش را با `response_model` اعلام می‌کند.

```
مدل‌های پاسخ ─► python -m app.export_openapi ─► frontend/openapi.json ─► npm run gen:api ─► src/api/schema.d.ts
```

- `src/api/types.ts` فقط نام‌های کوتاه (alias) روی `schema.d.ts` است؛ شکل داده را دستی ننویسید.
- `useGet("/api/v1/…", params)` مسیر را با طرح OpenAPI و نوع خروجی را از آن می‌گیرد؛ مسیر یا پارامتر اشتباه کامپایل نمی‌شود (`src/api/typed.check.ts`).
- پس از هر تغییر در مدل‌های پاسخ یا مسیرها: دو دستور بالا را به‌ترتیب اجرا کنید. تست بک‌اند `test_committed_openapi_is_up_to_date` اگر `openapi.json` کهنه باشد شکست می‌خورد.
- کلاینت موبایل (React Native / Swift / Kotlin) همین `openapi.json` را می‌گیرد؛ ابزارهای تولید کلاینت برای هر زبان آماده‌اند.
- ورودی‌ها (بدنه‌های POST/PUT/PATCH) هنوز با `api()` و نوع دستی ارسال می‌شوند؛ اتصال آن‌ها به طرح گام بعدی است.
