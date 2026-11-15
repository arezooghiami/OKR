// Compile-time checks (run by `npm run typecheck`): wrong paths or params must not type-check.
import type { GetResponse, PathParams } from "./typed";
import { useGet } from "./typed";

export function _checks() {
  useGet("/api/v1/dashboard/overview");
  useGet("/api/v1/sessions/{session_id}", { session_id: "x" });
  // @ts-expect-error unknown path
  useGet("/api/v1/does-not-exist");
  // @ts-expect-error path params are required
  useGet("/api/v1/sessions/{session_id}");
  // @ts-expect-error wrong param name
  useGet("/api/v1/sessions/{session_id}", { id: "x" });
  const score: GetResponse<"/api/v1/dashboard/overview">["org_score"] = null;
  const p: PathParams<"/api/v1/sessions/{session_id}"> = { session_id: "x" };
  return [score, p];
}
