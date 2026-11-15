import type { ReactNode } from "react";
import { STATUS_CLASS, statusFor, type Status } from "../domain/calc";

/** Status is never colour-only: filled pie + percent + text label (design principle 4). */
export function Pie({ p, status, size = 15 }: { p: number | null; status?: Status; size?: number }) {
  const cls = STATUS_CLASS[status ?? statusFor(p)];
  return (
    <svg className={`i ${cls}`} style={{ width: size, height: size }} viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--line-strong)" strokeWidth="1.4" />
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
    <div className="note err-box" role="alert">
      <b>خطا:</b> {message}
      {onRetry && <> · <button className="lnk" onClick={onRetry}>تلاش دوباره</button></>}
    </div>
  );
}

const EMPTY_ICON = {
  inbox: "M4 13l2.5-7h11L20 13M4 13v5h16v-5M4 13h4.5l1 2h5l1-2H20",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.3-4.3",
  list: "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
  lock: "M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 0 1 7 0v3",
} as const;

/** Empty state: what is missing and, in the hint, who can change that. */
export const Empty = ({ title, hint, icon = "list" }: { title: string; hint?: string; icon?: keyof typeof EMPTY_ICON }) => (
  <div className="empty">
    <span className="empty-i"><svg className="i" viewBox="0 0 24 24" aria-hidden="true"><path d={EMPTY_ICON[icon]} /></svg></span>
    <b>{title}</b>{hint && <div className="mut">{hint}</div>}
  </div>
);

/** Shown while the system has no active cycle (a fresh install, or between cycles). */
export function NoCycle() {
  return (
    <div className="empty">
      <span className="empty-i"><svg className="i" viewBox="0 0 24 24" aria-hidden="true"><path d={EMPTY_ICON.list} /></svg></span>
      <b>دورهٔ فعالی وجود ندارد</b>
      <div className="mut">مدیر سیستم باید در «مدیریت ← چرخه و جلسه‌ها» یک چرخه بسازد و فعال کند؛ پیش از آن واحدها و کاربران را تعریف کنید.</div>
      <a className="btn o" href="/admin/units" style={{ marginTop: 12 }}>رفتن به مدیریت</a>
    </div>
  );
}

export const Crumb = ({ items }: { items: string[] }) => (
  <div className="crumb">{items.map((t, i) => (i === items.length - 1 ? <b key={i}>{t}</b> : <span key={i}>{t} ‹</span>))}</div>
);

export const Icon = ({ d }: { d: string }) => <svg className="i" viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg>;

/** Product mark: an objective ring with its key result at the centre. Uses the accent colour. */
export const Mark = () => (
  <svg className="mark" viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="8" fill="currentColor" />
    <circle cx="16" cy="16" r="9" fill="none" stroke="var(--on-accent)" strokeWidth="2.4" />
    <circle cx="16" cy="16" r="4.2" fill="none" stroke="var(--on-accent)" strokeWidth="2.4" />
    <circle cx="16" cy="16" r="1.3" fill="var(--on-accent)" />
  </svg>
);

/** The product owner's signature. Organisation branding never removes it (docs/07 §7). */
export const Signature = () => <div className="sig" title="طراحی و توسعه">A.G</div>;

export const APP_VERSION = __APP_VERSION__;
