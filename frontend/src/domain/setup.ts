// The system administrator's setup checklist, derived from GET /admin/setup. Framework-free.
import type { Setup, SetupUnit } from "../api/types";
import { fa, jDate } from "./format";

export type StepState = "done" | "partial" | "todo" | "wait" | "optional";
export const BADGE: Record<StepState, [string, string]> = {
  done: ["ok", "انجام شد"], partial: ["risk", "ناقص"], todo: ["bad", "انجام نشده"], wait: ["none", "منتظر مرحلهٔ قبل"], optional: ["none", "اختیاری"],
};

export type Step = {
  key: string; title: string; why: string; state: StepState; lines: string[];
  missingTitle?: string; missing?: SetupUnit[]; unitLink?: boolean;
  actions: { to: string; label: string }[];
};

/** The order a new system follows: units & users → cycle & sessions → strategic goals → unit OKRs. */
export function setupSteps(d: Setup): Step[] {
  const cyc = d.active_cycle;
  const draft = d.draft_cycles[0];
  const noMembers = d.units_without_members.length;
  const unsched = d.units_unscheduled.length;
  const inRound = d.units_scheduled + unsched;
  const noObj = d.units_without_objectives.length;
  return [
    {
      key: "units", title: "واحدهای سازمان", why: "درخت سازمان؛ هر واحد جدول اهداف و جلسه‌های خودش را دارد. همه را می‌شود یک‌جا از اکسل وارد کرد.",
      state: d.units_total >= 2 ? "done" : "todo",
      lines: [d.units_total ? `${fa(d.units_total)} واحد در ساختار سازمان` : "هنوز واحدی تعریف نشده است. اولین واحد ریشهٔ سازمان است."],
      actions: [{ to: "/admin/units", label: "واحدها" }],
    },
    {
      key: "users", title: "کاربران و دسترسی‌ها", why: "هر کاربر با نقش و واحدش وارد می‌شود: مدیر واحد، مسئول KR، ناظر. با همان فایل اکسل واحدها هم وارد می‌شوند.",
      state: d.users_total === 0 ? "todo" : noMembers || d.users_without_role ? "partial" : "done",
      lines: [
        d.users_total ? `${fa(d.users_total)} کاربر` : "هنوز کاربری ساخته نشده است.",
        ...(d.users_without_role ? [`${fa(d.users_without_role)} کاربر هنوز نقش و واحد ندارد و چیزی نمی‌بیند.`] : []),
        ...(d.units_total && noMembers ? [`${fa(noMembers)} از ${fa(d.units_total)} واحد هنوز هیچ کاربری ندارد.`] : []),
      ],
      missingTitle: "واحدهای بدون کاربر", missing: d.units_without_members,
      actions: [{ to: "/admin/users", label: "کاربران" }, { to: "/admin/access", label: "دسترسی‌ها" }],
    },
    {
      key: "cycle", title: "دوره و نقطه‌های پایش", why: "دورهٔ جاری با جلسهٔ شروع، پایش‌ها (R1، R2، …) و جلسهٔ نهایی.",
      state: cyc ? "done" : draft ? "partial" : "todo",
      lines: cyc
        ? [`دورهٔ «${cyc.name}» فعال است: ${jDate(cyc.starts_on)} تا ${jDate(cyc.ends_on)} · ${fa(cyc.time_points)} جلسه برای هر واحد`,
           ...(d.closed_cycles ? [`${fa(d.closed_cycles)} دورهٔ قبلی (فقط‌خواندنی)`] : [])]
        : draft ? [`دورهٔ «${draft.name}» ساخته شده ولی هنوز فعال نشده است. تا فعال نشود واحدها آن را نمی‌بینند.`]
        : ["هنوز دوره‌ای ساخته نشده است."],
      actions: [{ to: "/admin/cycle", label: cyc ? "دوره‌ها" : draft ? "فعال‌سازی دوره" : "ساخت دوره" }],
    },
    {
      key: "sessions", title: "زمان جلسه‌ها", why: "زمان جلسه به اعضای واحد می‌گوید تا کی مقدارها را ثبت کنند. ثبت مقدار بدون آن هم باز است.",
      state: !cyc ? "wait" : unsched === 0 ? "done" : d.units_scheduled ? "partial" : "todo",
      lines: !cyc ? ["بعد از فعال‌شدن دوره."]
        : inRound === 0 ? ["همهٔ جلسه‌های این دوره برگزار شده‌اند."]
        : [`جلسهٔ جاری${d.current_round ? ` (${d.current_round})` : ""}: ${fa(d.units_scheduled)} از ${fa(inRound)} واحد زمان جلسه دارند.`],
      missingTitle: "واحدهای بدون زمان جلسه", missing: cyc ? d.units_unscheduled : [],
      actions: [{ to: "/admin/cycle", label: "زمان‌بندی جلسه‌ها" }],
    },
    {
      key: "goals", title: "اهداف کلان", why: "واحدها هر KR را به یکی از اهداف کلان وصل می‌کنند؛ گزارش مدیریت بر همین پایه است.",
      state: d.goals_total ? "done" : "todo",
      lines: [
        d.goals_total ? `${fa(d.goals_total)} هدف کلان فعال` : "هنوز هدف کلانی تعریف نشده است.",
        ...(cyc && d.krs_total ? [`${fa(d.krs_with_goal)} از ${fa(d.krs_total)} KR به هدف کلان وصل‌اند.`] : []),
      ],
      actions: [{ to: "/admin/goals", label: "اهداف کلان" }],
    },
    {
      key: "okrs", title: "اهداف و KRهای واحدها", why: "از فایل اکسل پایش وارد کنید، یا هر واحد در جدول خودش تعریف کند.",
      state: !cyc ? "wait" : noObj === 0 && d.units_total ? "done" : d.objectives_total ? "partial" : "optional",
      lines: !cyc ? ["بعد از فعال‌شدن دوره."] : [
        `${fa(d.objectives_total)} هدف و ${fa(d.krs_total)} KR در دورهٔ جاری`,
        ...(noObj ? [`${fa(noObj)} از ${fa(d.units_total)} واحد هنوز هدفی ندارند.`] : []),
      ],
      missingTitle: "واحدهای بدون هدف", missing: cyc ? d.units_without_objectives : [], unitLink: true,
      actions: [{ to: "/admin/import", label: "ورود از اکسل" }],
    },
  ];
}
