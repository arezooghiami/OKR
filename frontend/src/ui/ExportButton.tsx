import { useState } from "react";
import { download } from "../api/client";

/** Downloads an .xlsx from an authenticated API path and reports failures inline. */
export default function ExportButton({ path, label = "Excel" }: { path: string; label?: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = async () => {
    setBusy(true); setErr(null);
    try { await download(path); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
      <button className="btn o" onClick={run} disabled={busy}>{busy ? "در حال ساخت…" : label}</button>
      {err && <span className="bad tiny" role="alert">{err}</span>}
    </span>
  );
}
