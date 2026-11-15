// Framework-free progress logic. Mirrors backend/app/services/calc.py so the UI can preview a
// percent while typing; the server stays the source of truth. No DOM here (reusable in mobile).

export type KRKind = "numeric" | "milestone" | "boolean" | "maintain";
export type Status = "on_track" | "at_risk" | "behind" | "not_recorded";

export interface Definition {
  kind: KRKind;
  baseline?: number | null;
  target?: number | null;
  range_min?: number | null;
  range_max?: number | null;
}

const clamp = (x: number) => Math.round(Math.max(0, Math.min(100, x)) * 100) / 100;

export function percent(d: Definition, value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null;
  switch (d.kind) {
    case "numeric": {
      const { baseline: b, target: t } = d;
      if (b == null || t == null || b === t) return null;
      return clamp(((value - b) / (t - b)) * 100);
    }
    case "milestone":
      return clamp(value);
    case "boolean":
      return value ? 100 : 0;
    case "maintain": {
      const { range_min: lo, range_max: hi } = d;
      if (lo == null || hi == null) return null;
      if (value >= lo && value <= hi) return 100;
      const dist = value < lo ? lo - value : value - hi;
      return clamp(100 - (dist / (hi - lo || Math.max(Math.abs(hi), 1))) * 100);
    }
  }
}

export function statusFor(p: number | null | undefined): Status {
  if (p == null) return "not_recorded";
  return p >= 70 ? "on_track" : p >= 40 ? "at_risk" : "behind";
}

export const STATUS_LABEL: Record<Status, string> = {
  on_track: "روی مسیر",
  at_risk: "در خطر",
  behind: "عقب",
  not_recorded: "ثبت نشده",
};

/** CSS class used by the design tokens (ok / risk / bad / none). */
export const STATUS_CLASS: Record<Status, string> = {
  on_track: "ok",
  at_risk: "risk",
  behind: "bad",
  not_recorded: "none",
};
