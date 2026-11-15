// Persian numerals and Jalali dates via Intl (no external library, works offline).

const FA = "۰۱۲۳۴۵۶۷۸۹";

export const fa = (n: number | string | null | undefined, maxFraction = 1): string =>
  n == null || n === ""
    ? "—"
    : Number(n).toLocaleString("fa-IR", { useGrouping: false, maximumFractionDigits: maxFraction });

/** Persian digits in a code or label as written ("1.10" stays 1.10, unlike a number). */
export const faDigits = (s: string): string => s.replace(/\d/g, (d) => FA[+d]);

export const pct = (n: number | null | undefined): string => (n == null ? "—" : `${fa(n)}٪`);

/** Parse user input typed with Persian or Arabic digits. Empty string -> null; invalid -> undefined. */
export function parseNumber(raw: string): number | null | undefined {
  const s = raw
    .replace(/[۰-۹]/g, (d) => String(FA.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x660))
    .replace(/[٫,]/g, ".")
    .replace(/[٬\s]/g, "")
    .replace(/−/g, "-");
  if (s.trim() === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}

const dateFmt = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Tehran" });
const dayMonthFmt = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { day: "numeric", month: "long", timeZone: "Asia/Tehran" });
const timeFmt = new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "Asia/Tehran" });

export const jDate = (iso?: string | null) => (iso ? dateFmt.format(new Date(iso)) : "—");
export const jDayMonth = (iso?: string | null) => (iso ? dayMonthFmt.format(new Date(iso)) : "—");
export const jTime = (iso?: string | null) => (iso ? timeFmt.format(new Date(iso)) : "—");
export const jDateTime = (iso?: string | null) => (iso ? `${jDate(iso)}، ساعت ${jTime(iso)}` : "—");

/** Jalali "YYYY/MM/DD" parts for a Gregorian date (for forms). */
export function jalaliParts(d: Date): { y: number; m: number; d: number } {
  const parts = new Intl.DateTimeFormat("en-u-ca-persian-nu-latn", { year: "numeric", month: "numeric", day: "numeric", timeZone: "Asia/Tehran" }).formatToParts(d);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return { y: get("year"), m: get("month"), d: get("day") };
}
