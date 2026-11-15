import { describe, expect, it } from "vitest";
import { percent, statusFor } from "./calc";
import { fa, parseNumber, pct } from "./format";

describe("percent", () => {
  it("ascending and descending", () => {
    expect(percent({ kind: "numeric", baseline: 50, target: 70 }, 61)).toBe(55);
    expect(percent({ kind: "numeric", baseline: 48, target: 24 }, 36)).toBe(50);
  });
  it("clamps and distinguishes empty from zero", () => {
    expect(percent({ kind: "numeric", baseline: 0, target: 10 }, 25)).toBe(100);
    expect(percent({ kind: "numeric", baseline: 0, target: 10 }, null)).toBeNull();
    expect(percent({ kind: "numeric", baseline: 0, target: 10 }, 0)).toBe(0);
  });
  it("maintain range", () => {
    expect(percent({ kind: "maintain", range_min: 90, range_max: 100 }, 85)).toBe(50);
  });
  it("status thresholds", () => {
    expect([null, 70, 69, 40, 39].map(statusFor)).toEqual(["not_recorded", "on_track", "at_risk", "at_risk", "behind"]);
  });
});

describe("format", () => {
  it("parses Persian digits and separators", () => {
    expect(parseNumber("۶۱")).toBe(61);
    expect(parseNumber("۱۲٫۵")).toBe(12.5);
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("abc")).toBeUndefined();
    expect(parseNumber("12.5")).toBe(12.5);
    expect(parseNumber("-3")).toBe(-3);
  });
  it("treats commas as thousands separators, never as a decimal point", () => {
    expect(parseNumber("1,200")).toBe(1200);
    expect(parseNumber("۱,۲۰۰,۰۰۰")).toBe(1200000);
    expect(parseNumber("۱٬۲۰۰٬۰۰۰٫۵")).toBe(1200000.5);
    expect(parseNumber("12،500")).toBe(12500);
    expect(parseNumber("1 200")).toBe(1200);
    // ambiguous groupings are rejected instead of silently becoming 1.5 or 15
    expect(parseNumber("1,5")).toBeUndefined();
    expect(parseNumber("1,20")).toBeUndefined();
    expect(parseNumber("1.2.3")).toBeUndefined();
    expect(parseNumber("0x10")).toBeUndefined();
  });
  it("formats Persian digits, grouping only large numbers", () => {
    expect(fa(62)).toBe("۶۲");
    expect(fa(1405)).toBe("۱۴۰۵");
    expect(fa(12500000)).toBe("۱۲٬۵۰۰٬۰۰۰");
    expect(parseNumber(fa(12500000))).toBe(12500000);
    expect(pct(null)).toBe("—");
  });
});

describe("tpLabel (glossary)", async () => {
  const { tpLabel } = await import("./format");
  it("names review points «پایش n» and keeps the others", () => {
    expect(tpLabel("R1")).toBe("پایش ۱");
    expect(tpLabel(" r 12 ")).toBe("پایش ۱۲");
    expect(tpLabel("شروع")).toBe("شروع");
    expect(tpLabel("نهایی")).toBe("نهایی");
    expect(tpLabel(null)).toBe("");
  });
});
