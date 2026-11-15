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
  });
  it("formats Persian digits", () => {
    expect(fa(62)).toBe("۶۲");
    expect(pct(null)).toBe("—");
  });
});
