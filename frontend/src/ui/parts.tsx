import type { ReactNode } from "react";
import { STATUS_CLASS, statusFor, type Status } from "../domain/calc";

/** Status is never colour-only: filled pie + percent + text label (design principle 4). */
export function Pie({ p, status, size = 15 }: { p: number | null; status?: Status; size?: number }) {
  const cls = STATUS_CLASS[status ?? statusFor(p)];
  return (
    <svg className={`i ${cls}`} style={{ width: size, height: size }} viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--line2)" strokeWidth="1.4" />
      {p ? <circle cx="8" cy="8" r="3.25" fill="none" stroke="currentColor" strokeWidth="6.5" strokeDasharray={`${(p / 100) * 20.42} 20.42`} transform="rotate(-90 8 8)" /> : null}
    </svg>
  );
}

export const Tag = ({ color, children }: { color: string; children: ReactNode }) => (
  <span className="tag" style={{ ["--c" as string]: `var(${color})` }}>{children}</span>
);

export const Bar = ({ p, status }: { p: number | null; status?: Status }) => (
  <div className="mbw"><div className={`mb ${STATUS_CLASS[status ?? statusFor(p)]}`} style={{ ["--w" as string]: `${p ?? 0}%` }}><i /></div></div>
);

export const Skeleton = ({ rows = 4 }: { rows?: number }) => (
  <div aria-busy="true" aria-label="در حال بارگذاری">
    {Array.from({ length: rows }, (_, i) => <div key={i} className="sk" style={{ width: `${92 - i * 9}%` }} />)}
  </div>
);

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="note" role="alert" style={{ color: "var(--bad)" }}>
      <b>خطا:</b> {message}
      {onRetry && <> · <button className="lnk" onClick={onRetry}>تلاش دوباره</button></>}
    </div>
  );
}

export const Empty = ({ title, hint }: { title: string; hint?: string }) => (
  <div className="empty"><b>{title}</b>{hint && <div className="faint tiny">{hint}</div>}</div>
);

/** Shown while the system has no active cycle (a fresh install, or between cycles). */
export function NoCycle() {
  return (
    <div className="empty">
      <b>چرخهٔ فعالی وجود ندارد</b>
      <div className="faint tiny">مدیر سیستم باید در «مدیریت ← چرخه و جلسه‌ها» یک چرخه بسازد و فعال کند؛ پیش از آن واحدها و کاربران را تعریف کنید.</div>
      <a className="btn o" href="/admin/units" style={{ marginTop: 12 }}>رفتن به مدیریت</a>
    </div>
  );
}

export const Crumb = ({ items }: { items: string[] }) => (
  <div className="crumb">{items.map((t, i) => (i === items.length - 1 ? <b key={i}>{t}</b> : <span key={i}>{t} ‹</span>))}</div>
);

export const Icon = ({ d }: { d: string }) => <svg className="i" viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg>;
