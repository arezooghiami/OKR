import { Link } from "react-router-dom";
import { useGet } from "../../api/typed";
import type { SetupUnit } from "../../api/types";
import { fa } from "../../domain/format";
import { BADGE, setupSteps } from "../../domain/setup";
import { ErrorBox, Skeleton } from "../../ui/parts";

const SHOW = 12;

function Missing({ title, units, unitLink }: { title: string; units: SetupUnit[]; unitLink?: boolean }) {
  if (!units.length) return null;
  return (
    <div className="stp-miss">
      <span className="faint">{title}:</span>
      {units.slice(0, SHOW).map((u) => unitLink
        ? <Link key={u.id} className="chip" to={`/unit/${u.id}`}>{u.name}</Link>
        : <span key={u.id} className="chip">{u.name}</span>)}
      {units.length > SHOW && <span className="faint">و {fa(units.length - SHOW)} واحد دیگر</span>}
    </div>
  );
}

/** The system administrator's start page: what is set up, what is missing, and where to fix it. */
export default function SetupPanel() {
  const { data, error, loading, reload } = useGet("/api/v1/admin/setup");
  if (loading && !data) return <Skeleton rows={6} />;
  if (error || !data) return <ErrorBox message={error ?? "خطا"} onRetry={reload} />;
  const steps = setupSteps(data);
  const done = steps.filter((s) => s.state === "done").length;
  const next = steps.find((s) => s.state === "todo" || s.state === "partial");
  return (
    <>
      <div className="stp-head">
        <div>
          <b>{done === steps.length ? "راه‌اندازی کامل است" : `${fa(done)} از ${fa(steps.length)} مرحله انجام شده`}</b>
          <span className="faint">{next ? `مرحلهٔ بعد: ${next.title}` : "واحدها می‌توانند کار کنند. این صفحه هر بار وضعیت تازه را نشان می‌دهد."}</span>
        </div>
        <div className="mb ok" style={{ height: 8 }} aria-hidden="true"><i style={{ "--w": `${(done / steps.length) * 100}%` } as React.CSSProperties} /></div>
      </div>
      <ol className="stps">
        {steps.map((s, i) => {
          const [cls, label] = BADGE[s.state];
          return (
            <li key={s.key} className={`stp ${s.state}${s === next ? " next" : ""}`}>
              <span className="stp-n" aria-hidden="true">{s.state === "done" ? "✓" : fa(i + 1)}</span>
              <div className="stp-b">
                <div className="stp-t"><h3>{s.title}</h3><span className={`badge ${cls}`}>{label}</span>{s === next && <span className="lvl">مرحلهٔ بعد</span>}</div>
                <p className="faint">{s.why}</p>
                {s.lines.map((l) => <p key={l} className="stp-l">{l}</p>)}
                {s.missing && s.missingTitle && <Missing title={s.missingTitle} units={s.missing} unitLink={s.unitLink} />}
              </div>
              <div className="stp-a">
                {s.actions.map((a, j) => <Link key={a.to} className={`btn${j === 0 && s.state !== "done" && s.state !== "wait" ? "" : " o"} mini`} to={a.to}>{a.label}</Link>)}
              </div>
            </li>
          );
        })}
      </ol>
    </>
  );
}
