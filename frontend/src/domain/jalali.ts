import { jalaliParts } from "./format";

const isLeap = (y: number) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;

/** Jalali (jy, jm, jd) -> Gregorian [gy, gm, gd]. */
export function jalaliToGregorian(jy: number, jm: number, jd: number): [number, number, number] {
  jy += 1595;
  let days = -355668 + 365 * jy + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4) + jd + (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186);
  let gy = 400 * Math.floor(days / 146097);
  days %= 146097;
  if (days > 36524) {
    gy += 100 * Math.floor(--days / 36524);
    days %= 36524;
    if (days >= 365) days++;
  }
  gy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    gy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  let gd = days + 1;
  const sal = [0, 31, isLeap(gy) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  let gm = 0;
  while (gm < 13 && gd > sal[gm]) gd -= sal[gm++];
  return [gy, gm, gd];
}

const norm = (s: string) => s.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)));

/** "1405/08/24" + "11:00" (Persian or Latin digits) -> ISO string in Tehran time (+03:30), or null if invalid. */
export function parseJalaliDateTime(date: string, time: string): string | null {
  const dm = norm(date).trim().match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$/);
  const tm = norm(time).trim().match(/^(\d{1,2}):(\d{2})$/);
  if (!dm || !tm) return null;
  const [jy, jm, jd] = [+dm[1], +dm[2], +dm[3]];
  const [hh, mm] = [+tm[1], +tm[2]];
  if (jm < 1 || jm > 12 || jd < 1 || jd > (jm <= 6 ? 31 : 30) || hh > 23 || mm > 59) return null;
  const [gy, gm, gd] = jalaliToGregorian(jy, jm, jd);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${gy}-${p(gm)}-${p(gd)}T${p(hh)}:${p(mm)}:00+03:30`;
}

/** ISO instant -> "۱۴۰۵/۰۸/۲۴" and "۱۱:۰۰" for form fields. */
export function toJalaliFields(iso: string | null): { date: string; time: string } {
  if (!iso) return { date: "", time: "" };
  const d = new Date(iso);
  const { y, m, d: day } = jalaliParts(d);
  const p = (n: number) => String(n).padStart(2, "0");
  const time = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "Asia/Tehran" }).format(d);
  return { date: `${y}/${p(m)}/${p(day)}`, time };
}

/** "1405/07/01" (Persian or Latin digits) -> "2026-09-23", or null when invalid. */
export function parseJalaliDate(date: string): string | null {
  const dm = norm(date).trim().match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$/);
  if (!dm) return null;
  const [jy, jm, jd] = [+dm[1], +dm[2], +dm[3]];
  if (jm < 1 || jm > 12 || jd < 1 || jd > (jm <= 6 ? 31 : 30)) return null;
  const [gy, gm, gd] = jalaliToGregorian(jy, jm, jd);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${gy}-${p(gm)}-${p(gd)}`;
}

/** "2026-09-23" -> "1405/07/01" for form fields. */
export function toJalaliDate(isoDate: string): string {
  const { y, m, d } = jalaliParts(new Date(`${isoDate}T12:00:00+03:30`));
  const p = (n: number) => String(n).padStart(2, "0");
  return `${y}/${p(m)}/${p(d)}`;
}
