// Path-checked GETs: the path must exist in the generated OpenAPI schema and the result type follows from it.
import type { paths } from "./schema";
import { useFetch, type Fetched } from "./hooks";

export type GetPath = { [P in keyof paths]: paths[P] extends { get: object } ? P : never }[keyof paths];
type GetOp<P extends GetPath> = paths[P] extends { get: infer G } ? G : never;
export type GetResponse<P extends GetPath> = GetOp<P> extends { responses: { 200: { content: { "application/json": infer R } } } } ? R : never;
export type PathParams<P extends GetPath> = GetOp<P> extends { parameters: { path: infer X } } ? X : never;
type Query = Record<string, string | number | undefined | null>;

const PREFIX = "/api/v1"; // the client's base URL already ends with it

export function buildPath(path: string, params?: Record<string, string | number> | null, query?: Query): string {
  let p = path.startsWith(PREFIX) ? path.slice(PREFIX.length) : path;
  for (const [k, v] of Object.entries(params ?? {})) p = p.replace(`{${k}}`, encodeURIComponent(String(v)));
  const qs = Object.entries(query ?? {}).filter(([, v]) => v != null && v !== "").map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
  return qs ? `${p}?${qs}` : p;
}

/**
 * useGet("/api/v1/dashboard/overview")
 * useGet("/api/v1/sessions/{session_id}", { session_id: id })   // pass null to wait (e.g. id not known yet)
 */
export function useGet<P extends GetPath>(
  path: P,
  ...rest: [PathParams<P>] extends [never] ? [opts?: { query?: Query; skip?: boolean }] : [params: PathParams<P> | null, opts?: { query?: Query; skip?: boolean }]
): Fetched<GetResponse<P>> {
  const hasParams = path.includes("{");
  const params = (hasParams ? rest[0] : null) as Record<string, string | number> | null;
  const opts = (hasParams ? rest[1] : rest[0]) as { query?: Query; skip?: boolean } | undefined;
  const skip = opts?.skip || (hasParams && params === null);
  return useFetch<GetResponse<P>>(skip ? null : buildPath(path, params, opts?.query));
}
