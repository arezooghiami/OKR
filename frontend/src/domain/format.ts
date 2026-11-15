// Persian numerals and Jalali dates via Intl (no external library, works offline).

const FA = "۰۱۲۳۴۵۶۷۸۹";

/** Persian digits. Numbers from 10,000 up get the Persian thousands separator (۱۲٬۵۰۰٬۰۰۰) so large
 *  amounts can be read at a glance; smaller ones (years like ۱۴۰۵, counts, codes) stay ungrouped. */
export const fa = (n: number | string | null | undefined, maxFraction = 1): string => {
  if (n == null || n === "") return "—";
  const x = Number(n);
  return x.toLocaleString("fa-IR", { useGrouping: Math.abs(x) >= 10_000, maximumFractionDigits: maxFraction });
};

/** Persian digits in a code or label as written ("1.10" stays 1.10, unlike a number). */
export const faDigits = (s: string): string => s.replace(/\d/g, (d) => FA[+d]);

/** Display name of a review point (glossary, docs/07 phase 2): «R1» → «پایش ۱». Stored labels stay as
 *  they are, because Excel files and exports use them; only what people read changes. */
export const tpLabel = (label: string | null | undefined): string => {
  if (!label) return "";
  const m = /^\s*R\s*(\d+)\s*$/i.exec(label);
  return m ? `پایش ${faDigits(m[1])}` : faDigits(label);
};

export const pct = (n: number | null | undefined): string => (n == null ? "—" : `${fa(n)}٪`);

/** Parse user input typed with Persian, Arabic or Latin digits. Empty string -> null; invalid -> undefined.
 *  Decimal point: «٫» or «.». Commas («,» «،» «٬») are thousands separators only, as in Excel:
 *  «1,200» is 1200. A comma that isn't a valid thousands grouping («1,5») is rejected rather than
 *  guessed, so a typo can never silently turn into a number 1000 times off. */
export function parseNumber(raw: string): number | null | undefined {
  const s = raw
    .replace(/[۰-۹]/g, (d) => String(FA.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x660))
    .replace(/٫/g, ".")
    .replace(/[−–]/g, "-")
    .replace(/\s/g, "");
  if (s === "") return null;
  let plain = s;
  if (/[,،٬]/.test(s)) {
    if (!/^[-+]?\d{1,3}([,،٬]\d{3})+(\.\d+)?$/.test(s)) return undefined;
    plain = s.replace(/[,،٬]/g, "");
  }
  if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(plain)) return undefined;
  const n = Number(plain);
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
