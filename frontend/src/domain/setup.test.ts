import { describe, expect, it } from "vitest";
import type { Setup } from "../api/types";
import { setupSteps } from "./setup";

const empty: Setup = {
  units_total: 0, units_without_members: [], users_total: 0, users_without_role: 0, active_cycle: null, draft_cycles: [],
  closed_cycles: 0, current_round: null, units_scheduled: 0, units_unscheduled: [], goals_total: 0, krs_total: 0,
  krs_with_goal: 0, objectives_total: 0, units_without_objectives: [],
};
const state = (d: Setup) => Object.fromEntries(setupSteps(d).map((s) => [s.key, s.state]));
const cycle = { id: "c", name: "پاییز", status: "active", starts_on: "2026-09-23", ends_on: "2027-01-20", time_points: 5 };
const u = (name: string) => ({ id: name, name, session_id: null });

describe("setup checklist", () => {
  it("a fresh system: everything to do, cycle-bound steps wait", () => {
    expect(state(empty)).toEqual({ units: "todo", users: "todo", cycle: "todo", sessions: "wait", goals: "todo", okrs: "wait" });
  });

  it("a draft cycle is half-done until activated", () => {
    expect(state({ ...empty, draft_cycles: [{ ...cycle, status: "draft" }] }).cycle).toBe("partial");
  });

  it("missing units make a step partial and are listed", () => {
    const d: Setup = { ...empty, units_total: 3, users_total: 2, units_without_members: [u("مالی")], active_cycle: cycle,
      units_scheduled: 1, units_unscheduled: [u("فنی"), u("مالی")], objectives_total: 4, units_without_objectives: [u("مالی")] };
    const steps = setupSteps(d);
    expect(state(d)).toMatchObject({ units: "done", users: "partial", cycle: "done", sessions: "partial", okrs: "partial" });
    expect(steps.find((s) => s.key === "sessions")?.lines[0]).toContain("۱ از ۳ واحد");
    expect(steps.find((s) => s.key === "users")?.missing?.map((x) => x.name)).toEqual(["مالی"]);
  });

  it("all set up", () => {
    const d: Setup = { ...empty, units_total: 3, users_total: 5, active_cycle: cycle, units_scheduled: 3, goals_total: 4,
      krs_total: 10, krs_with_goal: 8, objectives_total: 6 };
    expect(Object.values(state(d)).every((s) => s === "done")).toBe(true);
  });
});
