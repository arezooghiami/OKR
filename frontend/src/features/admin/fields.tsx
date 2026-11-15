import { useState, type ReactNode } from "react";

/** Labelled input in the design's form style. */
export function Field({ label, value, onChange, placeholder, type = "text", dir, hint, disabled }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string; dir?: "ltr" | "rtl"; hint?: string; disabled?: boolean;
}) {
  return (
    <div className="f"><label>{label}
      <input type={type} value={value} dir={dir} placeholder={placeholder} disabled={disabled} onChange={(e) => onChange(e.target.value)} autoComplete="off" /></label>
      {hint && <span className="faint tiny">{hint}</span>}</div>
  );
}

export function Select({ label, value, onChange, options, empty }: {
  label: string; value: string; onChange: (v: string) => void; options: [string, string][]; empty?: string;
}) {
  return (
    <div className="f"><label>{label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>{empty !== undefined && <option value="">{empty}</option>}
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label></div>
  );
}

/** Runs an async action, tracking busy state and the server's error message. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>, success?: string) => {
    setBusy(true); setErr(null); setOk(null);
    try { await fn(); if (success) setOk(success); return true; }
    catch (e) { setErr((e as Error).message); return false; }
    finally { setBusy(false); }
  };
  return { busy, err, ok, run };
}

export const Msg = ({ err, ok }: { err: string | null; ok?: string | null }) =>
  err ? <div className="note" role="alert" style={{ color: "var(--bad)" }}>{err}</div> : ok ? <div className="note ok" role="status">{ok}</div> : null;

export const Section = ({ title, children }: { title: ReactNode; children: ReactNode }) => (
  <div className="card"><h3>{title}</h3>{children}</div>
);
