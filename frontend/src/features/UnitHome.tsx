import { useRef } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useGet } from "../api/typed";
import type { SessionHead, Workspace } from "../api/types";
import { fa, jDate, jDayMonth, jTime } from "../domain/format";
import ExportButton from "../ui/ExportButton";
import { Crumb, Empty, ErrorBox, NoCycle, Skeleton } from "../ui/parts";
import UnitTable from "./UnitTable";

const DAY = 86_400_000;

/** "۳ روز دیگر" / "امروز" / "فردا" for an upcoming session; null for past ones. */
function relDays(iso: string | null | undefined, now = Date.now()): string | null {
  if (!iso) return null;
  const startOf = (t: number) => { const d = new Date(t); d.setHours(0, 0, 0, 0); return d.getTime(); };
  const days = Math.round((startOf(new Date(iso).getTime()) - startOf(now)) / DAY);
  if (days < 0) return null;
  return days === 0 ? "امروز" : days === 1 ? "فردا" : `${fa(days)} روز دیگر`;
}

/** /unit → the first unit the user works in; /unit/:unitId → that unit; ?cycle=<id> → a past cycle (read-only). */
export default function UnitHome() {
  const { unitId } = useParams();
  const [params] = useSearchParams();
  const cycleId = params.get("cycle");
  const units = useGet("/api/v1/me/units", { query: { cycle_id: cycleId } });
  if (units.loading && !units.data) return <Skeleton rows={6} />;
  if (units.status === 404) return <NoCycle />;
  if (units.error) return <ErrorBox message={units.error} onRetry={units.reload} />;
  const list = units.data ?? [];
  if (list.length === 0) return <Empty title="واحدی به شما سپرده نشده است" hint="مدیر سیستم باید در «مدیریت ← کاربران» به شما نقش و واحد بدهد." />;
  if (!unitId) return <Navigate to={`/unit/${list[0].id}${cycleId ? `?cycle=${cycleId}` : ""}`} replace />;
  return <UnitWorkspace key={`${unitId}-${cycleId}`} unitId={unitId} cycleId={cycleId} units={list} />;
}

function UnitWorkspace({ unitId, cycleId, units }: { unitId: string; cycleId: string | null; units: { id: string; name: string }[] }) {
  const { data, error, loading, reload } = useGet("/api/v1/units/{unit_id}/workspace", { unit_id: unitId }, { query: { cycle_id: cycleId } });
  const cycles = useGet("/api/v1/cycles");
  const nav = useNavigate();
  const newObjective = useRef<HTMLInputElement>(null);
  if (loading && !data) return <Skeleton rows={6} />;
  if (error || !data) return <ErrorBox message={error ?? "یافت نشد"} onRetry={reload} />;

  const krCount = data.objectives.reduce((n, o) => n + o.key_results.length, 0);
  const start = data.sessions.find((s) => s.id === data.start_session_id);

  return (
    <>
      <Crumb items={[data.unit_name, "واحد من"]} />
      <div className="mh">
        <div>
          <h1>{data.unit_name}</h1>
          <CycleLine data={data} />
        </div>
        <div className="pickers">
          {(cycles.data?.length ?? 0) > 1 && (
            <div className="f">
              <label htmlFor="cycle-pick">دوره</label>
              <select id="cycle-pick" value={data.cycle.id}
                onChange={(e) => { const c = cycles.data?.find((x) => x.id === e.target.value); nav(`/unit/${unitId}${c && c.status !== "active" ? `?cycle=${c.id}` : ""}`); }}>
                {cycles.data?.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.status === "active" ? "جاری" : "بسته (فقط‌خواندنی)"}</option>)}
              </select>
            </div>
          )}
          {units.length > 1 && (
            <div className="f">
              <label htmlFor="unit-pick">واحد</label>
              <select id="unit-pick" value={unitId} onChange={(e) => nav(`/unit/${e.target.value}${cycleId ? `?cycle=${cycleId}` : ""}`)}>
                {units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            </div>
          )}
          <Link className="btn o" to={`/units/${unitId}${data.read_only ? `?cycle=${data.cycle.id}` : ""}`}>پروندهٔ واحد</Link>
          <ExportButton path={`/units/${unitId}/export.xlsx?cycle_id=${data.cycle.id}`} label="خروجی Excel" />
        </div>
      </div>

      {data.read_only && (
        <div className="pastbar" role="status">
          <b>دورهٔ «{data.cycle.name}» بسته شده است.</b>
          <span>اهداف، نتایج کلیدی، مقادیر و جلسه‌ها همان‌طور که در پایان دوره بودند نمایش داده می‌شوند و قابل تغییر نیستند.</span>
          {cycles.data?.some((c) => c.status === "active") && <Link className="lnk" to={`/unit/${unitId}`}>رفتن به دورهٔ جاری</Link>}
        </div>
      )}

      <div className="sec" style={{ marginTop: 26 }}><h2>جلسه‌های این دوره <span className="num">{fa(data.sessions.length)}</span></h2></div>
      <Timeline sessions={data.sessions} next={data.current_session_id} />

      {!data.read_only && !data.start_held && start && <Readiness data={data} start={start} />}

      <div className="sec">
        <h2>اهداف و نتایج کلیدی <span className="num">{fa(data.objectives.length)} هدف · {fa(krCount)} KR</span></h2>
        {data.can_define && <button className="btn" onClick={() => { newObjective.current?.scrollIntoView({ block: "center" }); newObjective.current?.focus(); }}>+ هدف جدید</button>}
      </div>
      {data.read_only ? null : data.can_edit
        ? <div className="note">مثل فایل اکسل: روی هر خانه کلیک کنید، تغییر دهید و Enter بزنید. هر تغییر با نام شما و زمانش در تاریخچه می‌ماند؛ «حذف» هم فقط از فهرست برمی‌دارد.</div>
        : <div className="note">این فهرست برای شما فقط‌خواندنی است.</div>}
      <UnitTable data={data} reload={reload} newObjectiveRef={newObjective} />
    </>
  );
}

function CycleLine({ data }: { data: Workspace }) {
  const s = new Date(data.cycle.starts_on).getTime(), e = new Date(data.cycle.ends_on).getTime() + DAY;
  const elapsed = Math.min(100, Math.max(0, ((Date.now() - s) / (e - s)) * 100));
  const left = Math.max(0, Math.ceil((e - Date.now()) / DAY));
  return (
    <div className="cyc mut">
      <span><b style={{ color: "var(--tx)" }}>{data.cycle.name}</b> · {jDate(data.cycle.starts_on)} تا {jDate(data.cycle.ends_on)}</span>
      <span className="trk" role="progressbar" aria-label="پیشرفت زمانی چرخه" aria-valuenow={Math.round(elapsed)} aria-valuemin={0} aria-valuemax={100}><i style={{ ["--w" as string]: `${elapsed}%` }} /></span>
      <span className="tiny">{data.read_only ? "بسته شده" : Date.now() < s ? `${fa(Math.ceil((s - Date.now()) / DAY))} روز تا شروع` : `${fa(left)} روز مانده`}</span>
    </div>
  );
}

function Timeline({ sessions, next }: { sessions: SessionHead[]; next: string | null }) {
  if (sessions.length === 0) return <div className="note">برای این واحد در چرخهٔ جاری جلسه‌ای ساخته نشده است.</div>;
  return (
    <div className="tl" aria-label="جلسه‌های چرخه">
      {sessions.map((s) => {
        const isNext = s.id === next && s.status !== "held";
        const rel = s.status === "scheduled" ? relDays(s.scheduled_at) : null;
        return (
          <Link key={s.id} to={`/sessions/${s.id}`} className={`${s.status === "held" ? "held" : ""} ${isNext ? "next" : ""}`}>
            <span className="lb">{s.time_point}<span className={`tiny ${s.status === "held" ? "ok" : s.status === "unscheduled" ? "risk" : "faint"}`} style={{ fontWeight: 600 }}>
              {s.status === "held" ? "برگزار شد ✓" : s.status === "unscheduled" ? "بدون زمان" : isNext ? "جلسهٔ بعدی" : "زمان‌بندی‌شده"}</span></span>
            {s.status === "held" && <span className="when mut">{jDayMonth(s.held_at)}</span>}
            {s.status === "scheduled" && <span className="when">{jDayMonth(s.scheduled_at)} · ساعت {jTime(s.scheduled_at)}</span>}
            {s.status === "unscheduled" && <span className="when faint">هنوز تعیین نشده</span>}
            {s.place && s.status !== "unscheduled" && <span className="faint tiny">{s.place}</span>}
            {rel && <span className="rel">{rel}</span>}
          </Link>
        );
      })}
    </div>
  );
}

function Readiness({ data, start }: { data: Workspace; start: SessionHead }) {
  const left = data.readiness.filter((r) => !r.done).length;
  return (
    <div className="ready">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "baseline" }}>
        <h2>آمادگی برای جلسهٔ {start.time_point}</h2>
        <span className={`tiny ${left ? "risk" : "ok"}`} style={{ fontWeight: 600 }}>{left ? `${fa(left)} مورد مانده` : "آماده برای جلسه ✓"}</span>
      </div>
      <div className="mut tiny" style={{ marginTop: 4 }}>
        در این جلسه اهداف، نتایج کلیدی و متصدی‌ها بررسی و تصویب می‌شوند.
        {start.scheduled_at && <> زمان: {jDate(start.scheduled_at)}، ساعت {jTime(start.scheduled_at)}{start.place && ` · ${start.place}`}.</>}
      </div>
      <ul>
        {data.readiness.map((r) => (
          <li key={r.key} className={r.done ? "on" : ""}>
            <span className="ck" aria-hidden="true">✓</span>
            <span>{r.label}</span>
            {!r.done && r.detail && <span className="faint tiny">— {r.detail}</span>}
            <span className="sr-only">{r.done ? "انجام شد" : "انجام نشده"}</span>
          </li>
        ))}
      </ul>
      <Link className="lnk tiny" to={`/sessions/${start.id}`} style={{ display: "inline-block", marginTop: 10 }}>باز کردن صفحهٔ جلسهٔ {start.time_point}</Link>
    </div>
  );
}
