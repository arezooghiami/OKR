Build a complete, production-quality web app UI called "OKR": an Objectives & Key Results management platform for large Persian-speaking organizations. Use Next.js (App Router), TypeScript, Tailwind CSS and shadcn/ui, with mock data only (no backend). Create all pages listed below, linked through a shared app shell, so I can click through the whole product.

## Hard requirements
- Fully RTL (`dir="rtl"`, `lang="fa"`). All UI text in Persian. Use Persian digits (۰-۹) everywhere, with tabular figures. Use logical CSS properties (ms/me/ps/pe, start/end), never left/right.
- Font: Vazirmatn (self-hosted via next/font/local or a local @font-face). No external CDNs, fonts, analytics or remote images at runtime; the app is deployed on an internal network with no internet. Icons: lucide-react (bundled).
- Dates are shown in the Jalali (Shamsi) calendar (e.g. «۲۵ آبان ۱۴۰۵»). Use a small Jalali formatting helper with mock data.
- Light theme by default, with an optional dark theme (toggle in the profile menu). Define all colors as CSS variables / design tokens so an admin can re-brand later by changing one accent color.
- Accessibility: WCAG AA contrast, visible focus rings, full keyboard navigation, status never conveyed by color alone (always a text label too).
- Responsive: desktop-first, but readable and usable on tablet and phone (top tabs collapse into a menu; the peek panel becomes full-width).

## Visual direction
Precise, tool-like and quiet (think Linear / Vercel): minimal, formal and professional, but not dry. Calm off-white page background (#f7f8fb), white surfaces, hairline 1px borders, generous whitespace, very soft or no shadows, 9–14px radii. Not crowded: one clear focus per screen, secondary details revealed on hover or in a side panel.
Color (use exactly this palette; define as CSS variables):
- Neutrals: bg #f7f8fb, panel #fff, hover #f1f3f9, line #e6e9f1 / #d3d8e6, text #161a2e, muted #5d6580.
- Accent: blue #3b5bf0 → violet #8b5cf6 (used for primary buttons, current step, logo mark, focus ring, selection).
- Six goal/tag hues for strategic goals (blue #3b6cf0, violet #8b5cf6, pink #e5489b, amber #f08a24, green #13a36b, teal #0aa5b8), shown only as small dots and soft tinted tag backgrounds (13% tint, never solid blocks), plus a 2px multi-hue line under the top bar.
- Semantic status colors, muted: on-track #12875a, at-risk #c26a06, behind #d03a45, not-registered/neutral #646d88.
- The organization score card has a soft tinted gradient background (blue/violet/pink at ~10%). No other gradients, no gradient text, no glow, no glassmorphism, no emoji, no decorative blobs. Do NOT use colored or gradient avatar squares for units; show a unit as plain text (name + type/KR count).
- Dark theme with equivalent tokens; keep AA contrast in both.
Objective groups (meeting page and my-KRs): each objective is a tinted container (7% of its goal hue over the page bg, 1px border at 28% hue) with a filled number badge, bold 15–16px title, a tinted column-header strip, and its KRs as white bordered cards inside; value inputs are large (15px, 1.5px border, 90px wide), notes inputs have a visible border. Meeting header sits on a soft blue/violet tinted card, the time-point stepper in its own white bordered card.
Rows: every list row (units, KRs, strategic goals) is its own bordered card (white, 1px line, 11–12px radius, ~6–8px gap between rows); hover darkens the border and tints the background; the selected row gets an accent border. Large numbers medium-weight with tabular figures, small muted labels, clear hierarchy.
Status is shown with a small pie-glyph icon (filled proportionally) + percent + text label, never color alone.
Motion: subtle and purposeful only: soft fade/slide-up on page load, bars filling on first view, gentle hover states, a pulsing dot for the "current" step. Respect `prefers-reduced-motion`. Use skeleton loaders, never spinners.

## App shell and navigation (no sidebar)
- **Top bar, not a sidebar.** Left to right in RTL order: logo "OKR" (small gradient square), the global **cycle selector** (e.g. «بهار ۱۴۰۵ · پایش ۲ ▾» with a green live dot), top tabs: نمای کلی، جلسهٔ پایش، اهداف، گزارش‌ها (more under a «⋯» menu: همترازی، تعهدات، سازمان، تنظیمات), then a search button that opens the **Ctrl+K command palette** (go-to pages, units, objectives, KRs, actions), theme toggle, and user avatar menu (profile, theme, sign out).
- Below the bar: breadcrumb. Content max-width ~1080px, centered.
- **Peek side panel**: clicking a unit or KR row slides a 420px panel (from the end side) with details and actions instead of navigating away.
- **Keyboard**: J/K move between rows, Enter edits the value, Space opens details, Esc closes panels; show a small hint bar at the bottom of the meeting page with auto-save state («ذخیره شد ✓»).
- Every page must also have designed empty, loading (skeleton), error (with retry), no-permission, and read-only (closed cycle) states, and a demo-mode banner at the top.

## Domain model (use these terms)
- Cycle (چرخه): e.g. 4-month period. Time points in a cycle: جلسه شروع → پایش ۱ → پایش ۲ → پایش ۳ → جلسه نهایی. Each unit has its own meeting date/time/place per time point; a unit with no meeting scheduled shows a «بدون زمان جلسه» warning.
- Unit (واحد): node in an org tree (معاونت، مدیریت، تیم), unlimited depth.
- Objective (هدف) has Key Results (KR). KR types: numeric increasing, numeric decreasing, milestone (0–100), yes/no, maintain-within-range. Each KR has baseline (مبنا), target (هدف), measured value per review, owner, collaborators, strategic-goal tag.
- Progress % for increasing KR = clamp((v − baseline)/(target − baseline)) ; for decreasing = clamp((baseline − v)/(baseline − target)). Empty value = «ثبت نشده» (not zero).
- Statuses (always label + color): شروع‌نشده، روی مسیر، در خطر، عقب، مسدود، انجام‌شده. Plus confidence: کم / متوسط / زیاد.
- Every change to a KR definition creates a new version with who/when/why/in-which-meeting. Every percentage is clickable to show formula and source data.

## Real data fields (from the organization's Excel template; mirror these exactly)
- Objective (هدف): numbered title, e.g. «ایجاد پشتیبانی IT قابل‌پیگیری، شفاف و قابل‌پیش‌بینی», with an aggregated score and status glyph.
- Key result (نتیجه کلیدی) columns: شناسه (e.g. ۱.۱), عنوان, مبنا → هدف, then one block per time point **R1…R6 and نهایی**, each with: مقدار (value), درصد پیشرفت (computed), توضیحات (note). Plus: هدف کسب‌وکاری (strategic goal tag, one of six), تیم‌های همکار (collaborating teams), شرح انتظار (expectation description), owner, and definition version (e.g. «نسخهٔ ۲ · اصلاح در جلسهٔ شروع»).
- Changing a KR's target after the start meeting requires a mandatory reason field and creates a new version.
- Meeting page ("جلسهٔ پایش ۲ · فناوری اطلاعات"): header with Jalali date, time, place; time-point pills (شروع ✓ · R1 ✓ · R2 current · R3 … نهایی); toggle «پایش جاری / همهٔ پایش‌ها» (the latter shows all R columns side by side); objectives as bordered header cards with score, KRs as bordered rows with an inline value input; buttons «+ KR جدید» and «Excel».
- Dashboard: org score hero (large %, delta vs previous review, trend line vs expected line, counts of on-track / at-risk / not-registered), then a segmented switch **فهرست | ماتریس | هدف کسب‌وکاری** for units (grouped «نیازمند توجه» first, then «در مسیر»), the units × time-points heat matrix (hatched «بدون جلسه» cells), and strategic-goal progress rows.

## Pages to build (all with realistic Persian mock data: a leather-manufacturing company with ~8 units, ~15 objectives, ~45 KRs)
1. **/login** — clean centered login (username/password, "ورود با Active Directory" option). No self-signup.
2. **/dashboard (organization dashboard)** — cycle stepper with the current time point highlighted; KPI row (org score with a thin progress ring, on-track count, at-risk count, unregistered count); **heat-matrix table: units × time points** with score per cell, hatched cells for "not held yet"/"no meeting"; unit performance table with inline bars and change vs previous review; "needs attention" list (unit without meeting time, KRs without owner, big drop) with action links; upcoming meetings list; a "Why this number?" explainer card (Health Score breakdown in plain Persian). Clicking a unit row opens a side panel with that unit's KRs and explanation.
3. **/my-krs (home for members)** — my KRs grouped by objective, unregistered ones first, inline value entry with live percent/status. Entering a value must take max 3 clicks.
4. **/units/[id] (unit dashboard)** — unit score, objectives with expandable KRs, meeting schedule, "changes since last meeting" filter, comments.
5. **/meetings/[unitId]/[point] (meeting page + review tab)** — the core screen. Header with meeting date/place and a "برگزار شد" (mark as held) action. Excel-like inline-editable table: #, KR title, baseline→target, value this review, live progress bar + %, status chip, note, attachments count. Auto-save draft indicator, bulk "ثبت و ارسال", comments thread per KR, version badge ("نسخه ۲ · اصلاح در جلسه شروع"), banner when the tab is locked or not yet open. Tabs for each review (پایش ۱ … نهایی); future tabs are disabled.
6. **/objectives** and **/objectives/[id]** — filterable list (unit, status, strategic goal); detail with KRs, owners, alignment links, timeline.
7. **/krs/[id]** — KR detail: formula, current vs target chart over time points, **version history timeline** with before/after diff view, attachments, comments, collaborators.
8. **/alignment** — collapsible tree of objectives aligned to higher-level objectives, with rolled-up progress; secondary graph view toggle.
9. **/commitments** — cross-team requests in three tabs: «از من خواسته‌اند / من خواسته‌ام / عقب‌افتاده»; accept / reject-with-reason / done actions.
10. **/reports** — choose cycle / time point / template, live preview, export PDF or Excel buttons.
11. **/cycles** and **/cycles/[id]** — list and setup: name, Jalali date range, define time points, per-unit meeting scheduling table (date, time, place/link), copy-from-previous-cycle, activate; unit state machine (draft → active → closed).
12. **/imports** — stepper: pick template → upload → row-level validation report (errors/warnings with row numbers) → dry-run preview → confirm → import log.
13. **/admin/org** — org tree editor (drag to reorder/move, unit types with color/icon, snapshot versions with effective date).
14. **/admin/users** — users table, multiple memberships/roles per user, AD sync status.
15. **/admin/roles** — role list + **permission matrix** (action × resource × scope × allow/deny) as a clean grid with toggles.
16. **/admin/access-simulator** — pick user + action + resource → result «مجاز/ممنوع» with the effective rule and the reason.
17. **/admin/audit** — searchable, filterable audit log table with before/after values and an integrity-check badge.
18. **/admin/settings** — branding (logo upload, **accent color picker with live contrast check**), terminology renaming, strategic goals list, units of measure, status thresholds, approval workflow toggle.
19. **/me** — profile and preferences (Persian/Latin digits, light/dark, sessions).
20. **/403, /404, /500** — friendly error pages with a clear way out.

## Quality bar
- Treat this as a design-system-first build: create reusable components (StatCard, ProgressRing, ProgressBar, StatusChip, CycleStepper, HeatCell, InlineValueInput, VersionTimeline, DiffView, PermissionMatrix, EmptyState, Skeleton) and use them consistently across pages.
- Data tables: sticky header, comfortable-compact density, row hover, keyboard-focusable rows, sortable columns.
- Realistic copy in natural, professional Persian (no lorem ipsum). Write helpful empty-state text with a suggested next action.
- Interactions must really work with local state: inline editing recalculates progress/status live, tabs and filters work, side panels open, theme toggle works, the command palette opens with Ctrl+K.
- Keep the code clean, typed, and componentized; mock data in separate files.

Admin panel (under a top tab «مدیریت», with a segmented sub-nav): درخت سازمان (collapsible bordered tree rows with type tags, manager, user/KR counts, drag handle, structure version «نسخهٔ ۳ · اجرا از …»), نقش‌ها و مجوزها (role cards on one side; permission matrix resource × action with three-state cells مجاز/ممنوع/تعریف‌نشده and a scope select per resource; deny beats allow), چرخه و جلسه‌ها (cycle header + time-point stepper, warning banner for units without meeting time, per-unit date/time/place table with warning-tinted rows), کاربران (AD sync card, user rows with role tag, membership count, sync status), شبیه‌ساز دسترسی (pick user/action/resource/unit → big «مجاز/ممنوع» with the effective rule and reason, driven by the same matrix state).

A working static reference prototype of this exact look is in `docs/design/precise-v7.html; see docs/design/design-system.md for tokens and components`; match its structure, spacing and colors.

Start with the design tokens, the app shell and the shared components, then build the pages in the order: dashboard → meeting/review page → my KRs → KR detail → the rest.
