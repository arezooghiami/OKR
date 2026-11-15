import { describe, expect, it } from "vitest";
import { jalaliToGregorian, parseJalaliDate, parseJalaliDateTime, toJalaliDate, toJalaliFields } from "./jalali";

describe("jalali", () => {
  it("converts known dates", () => {
    expect(jalaliToGregorian(1405, 8, 24)).toEqual([2026, 11, 15]);
    expect(jalaliToGregorian(1405, 1, 1)).toEqual([2026, 3, 21]);
    expect(jalaliToGregorian(1403, 12, 30)).toEqual([2025, 3, 20]); // leap year end
  });
  it("round-trips through the form fields", () => {
    const iso = parseJalaliDateTime("۱۴۰۵/۰۸/۲۴", "۱۱:۰۰")!;
    expect(iso).toBe("2026-11-15T11:00:00+03:30");
    expect(toJalaliFields(iso)).toEqual({ date: "1405/08/24", time: "11:00" });
  });
  it("rejects invalid input", () => {
    expect(parseJalaliDateTime("1405/07/31", "10:00")).toBeNull(); // Mehr has 30 days
    expect(parseJalaliDateTime("x", "10:00")).toBeNull();
    expect(parseJalaliDateTime("1405/01/01", "25:00")).toBeNull();
  });
  it("date-only helpers round-trip", () => {
    expect(parseJalaliDate("۱۴۰۵/۰۷/۰۱")).toBe("2026-09-23");
    expect(toJalaliDate("2026-09-23")).toBe("1405/07/01");
    expect(parseJalaliDate("1405/13/01")).toBeNull();
  });
});

import { firstWeekday, monthDays } from "../ui/JalaliDate";

describe("calendar grid", () => {
  it("knows month lengths, including leap Esfand", () => {
    expect(monthDays(1405, 1)).toBe(31);
    expect(monthDays(1405, 7)).toBe(30);
    expect(monthDays(1403, 12)).toBe(30); // 1403 is a leap year
    expect(monthDays(1404, 12)).toBe(29);
  });
  it("starts each month on the right weekday (0 = Saturday)", () => {
    expect(firstWeekday(1405, 8)).toBe(6); // 1 Aban 1405 = Friday 23 Oct 2026
    expect(firstWeekday(1405, 1)).toBe(0); // 1 Farvardin 1405 = Saturday 21 Mar 2026
  });
});
