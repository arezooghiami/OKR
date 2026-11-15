import { describe, expect, it } from "vitest";
import { buildPath } from "./typed";

describe("buildPath", () => {
  it("drops the base prefix and fills params", () => {
    expect(buildPath("/api/v1/sessions/{session_id}", { session_id: "a b" })).toBe("/sessions/a%20b");
  });
  it("adds only non-empty query values", () => {
    expect(buildPath("/api/v1/admin/users", null, { q: "علی", x: "", y: undefined })).toBe(`/admin/users?q=${encodeURIComponent("علی")}`);
    expect(buildPath("/api/v1/goals")).toBe("/goals");
  });
});
