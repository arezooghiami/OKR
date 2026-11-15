import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGet } from "../api/typed";
import type { Overview as OverviewT, OverviewUnit } from "../api/types";
import { STATUS_CLASS, STATUS_LABEL, statusFor } from "../domain/calc";
import { fa, jDayMonth, jTime, pct, tpLabel } from "../domain/format";
import ExportButton from "../ui/ExportButton";
import { Bar, Crumb, Empty, ErrorBox, NoCycle, Pie, Skeleton } from "../ui/parts";
import { usePeek } from "../ui/Peek";
import { useAuth } from "../auth/AuthContext";
import HoldPanel from "./HoldPanel";

const sessionOf = (u: OverviewUnit) => u.current_session_id;
/** Label of the held round the unit's score comes from. */
const roundOf = (u: OverviewUnit) => tpLabel([...u.cells].reverse().find((c) => c.status === "held" && c.score != null)?.time_point);
/** The open round's live score, when its session is scheduled and has values. */
const liveOf = (u: OverviewUnit) => u.cells.find((c) => c.status === "scheduled" && c.score != null);
/** Weakest first inside a status group; units without a score go last. */
const byScore = (a: OverviewUnit, b: OverviewUnit) => (a.latest_score ?? 101) - (b.latest_score ?? 101);
/** Real average score of a status group (for its small pie); null when no unit in it has a score. */
const avgScore = (us: OverviewUnit[]) => {
  const xs = us.map((u) => u.latest_score).filter((x): x is number => x != null);
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
};

export default function Overview() {
  const { data, error, status, loading, reload } = useGet("/api/v1/dashboard/overview");
  const [view, setView] = useState<"list" | "mx">("list");
  const peek = usePeek();
  const nav = useNavigate();
  const [sel, setSel] = useState<string | null>(null);
  const { me } = useAuth();

  if (loading && !data) return <Skeleton rows={6} />;
  if (status === 404) return <NoCycle />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data || data.units.length === 0) return <Empty title="واحدی برای نمایش نیست" hint="دسترسی شما به هیچ واحدی تعریف نشده است." />;

  const recorded = data.units.reduce((n, u) => n + u.recorded, 0);
  const totalKrs = data.units.reduce((n, u) => n + u.total_krs, 0);
  const unscheduled = data.units.filter((u) => u.warnings.includes("زمان جلسه تعیین نشده")).length;
  const groups = (["behind", "at_risk", "not_recorded", "on_track"] as const)
    .map((st) => ({ st, units: data.units.filter((u) => u.status === st).sort(byScore) })).filter((g) => g.units.length > 0);
  const open = (u: OverviewUnit) => { setSel(u.unit_id); peek.open(<UnitPeek unit={u} onGo={() => { peek.close(); nav(`/sessions/${sessionOf(u)}`); }} />); };

  const Row = ({ u }: { u: OverviewUnit }) => (
    <div className={`row ov-row ${sel === u.unit_id && peek.isOpen ? "sel" : ""}`} tabIndex={0} role="button" onClick={() => open(u)} onKeyDown={(e) => e.key === "Enter" && open(u)}>
      <div><div className="nm">{u.unit_name}</div><div className="faint tiny">{u.manager ?? ""}</div></div>
      <div className={`why ${u.warnings.length ? "w" : ""}`}>{u.warnings[0] ?? (u.next_session ? `جلسه ${jDayMonth(u.next_session.at)}، ساعت ${jTime(u.next_session.at)}` : "")}</div>
      <div className={`rec ${u.total_krs && u.recorded / u.total_krs < 0.5 ? "lo" : ""}`} title="نتایج کلیدی‌ای که در پایش جاری مقدار گرفته‌اند">
        {u.total_krs ? <><b className="num">{fa(u.recorded)} از {fa(u.total_krs)}</b> ثبت در {tpLabel(u.current_round)}</> : "—"}</div>
      <Bar p={u.latest_score} status={u.status} />
      <div className="v num" title={u.latest_score == null ? "هنوز پایشی برگزار نشده" : `امتیاز ${roundOf(u)} (آخرین جلسهٔ برگزارشده)`}>{pct(u.latest_score)}
        {u.latest_score != null && <div className="faint tiny">{roundOf(u)}{u.delta != null && <span className={u.delta < 0 ? "bad" : "ok"}> {u.delta < 0 ? "−" : "+"}{fa(Math.abs(u.delta))}</span>}</div>}</div>
    </div>
  );

  return (
    <>
      <Crumb items={["سازمان", "نمای کلی"]} />
      <div className="mh"><div><h1>داشبورد سازمان</h1><div className="sub">{data.cycle.name}</div></div>
        <div className="pickers">
          {me?.can_hold && <button className="btn" onClick={() => peek.open(<HoldPanel units={data.units} onDone={reload} />)}>ثبت برگزاری جلسه‌ها</button>}
          <ExportButton path="/export/org.xlsx" label="گزارش Excel کل سازمان" />
        </div></div>
      <div className="kpis">
        <div className="kpi">
          <span className="l">امتیاز سازمان</span>
          <span className="v num">{data.org_score == null ? "—" : fa(Math.round(data.org_score))}{data.org_score != null && <small>٪</small>}</span>
          <span className="h">میانگین آخرین پایشِ برگزارشدهٔ واحدها</span>
        </div>
        <div className="kpi">
          <span className="l">ثبت پیشرفت در پایش جاری</span>
          <span className="v num">{fa(recorded)}<small>از {fa(totalKrs)} نتیجهٔ کلیدی</small></span>
          <Bar p={totalKrs ? (recorded / totalKrs) * 100 : null} status={statusFor(totalKrs ? (recorded / totalKrs) * 100 : null)} />
          <span className="h">{totalKrs ? `${pct(Math.round((recorded / totalKrs) * 100))} از نتایج کلیدی پایش جاری ثبت شده` : "پایش بازی وجود ندارد"}</span>
        </div>
        <div className="kpi">
          <span className="l">واحدهای نیازمند توجه</span>
          <span className="v num">{fa(data.counts.behind + data.counts.at_risk)}<small>از {fa(data.units.length)}</small></span>
          <span className="h"><span className="bad">{fa(data.counts.behind)} {STATUS_LABEL.behind}</span>، <span className="risk">{fa(data.counts.at_risk)} {STATUS_LABEL.at_risk}</span></span>
        </div>
        <div className="kpi">
          <span className="l">جلسهٔ بدون زمان</span>
          <span className="v num">{fa(unscheduled)}<small>واحد</small></span>
          <span className="h">{unscheduled ? "ثبت مقدار باز است، ولی اعضا نمی‌دانند تا کی وقت دارند" : "همهٔ واحدها زمان جلسه دارند"}</span>
        </div>
      </div>
      <div className="sec"><h2>واحدها <span className="num">{fa(data.units.length)}</span></h2>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}><div className="seg" role="tablist"><button className={view === "list" ? "on" : ""} onClick={() => setView("list")}>فهرست</button><button className={view === "mx" ? "on" : ""} onClick={() => setView("mx")}>ماتریس</button></div></div></div>
      {view === "list" ? (
        <div className="list">
          {groups.map((g) => (
            <div key={g.st}>
              <div className="grp"><Pie p={avgScore(g.units)} status={g.st} /> {STATUS_LABEL[g.st]} <span className="faint num">{fa(g.units.length)}</span></div>
              {g.units.map((u) => <Row key={u.unit_id} u={u} />)}
            </div>
          ))}
        </div>
      ) : <Matrix data={data} onOpen={open} />}
    </>
  );
}

function Matrix({ data, onOpen }: { data: OverviewT; onOpen: (u: OverviewUnit) => void }) {
  const cols = data.time_points.slice(1); // the start session has no score
  return (
    <div className="mx" style={{ gridTemplateColumns: `minmax(170px,1.4fr) repeat(${cols.length},minmax(72px,1fr))` }}>
      <div className="h h0" />{cols.map((c) => <div key={c} className="h">{tpLabel(c)}</div>)}
      {data.units.map((u) => (
        <div key={u.unit_id} style={{ display: "contents" }}>
          <div className="u">{u.unit_name}</div>
          {cols.map((c) => {
            const cell = u.cells.find((x) => x.time_point === c);
            if (!cell || cell.score == null) return <div key={c} className="c e">{cell?.status === "unscheduled" ? "بدون جلسه" : "هنوز نه"}</div>;
            return <div key={c} className={`c num ${STATUS_CLASS[statusFor(cell.score)]}`} title={STATUS_LABEL[statusFor(cell.score)]} onClick={() => onOpen(u)}>{fa(Math.round(cell.score))}</div>;
          })}
        </div>
      ))}
    </div>
  );
}

function UnitPeek({ unit, onGo }: { unit: OverviewUnit; onGo: () => void }) {
  const page = useGet("/api/v1/sessions/{session_id}", unit.current_session_id ? { session_id: unit.current_session_id } : null);
  const cls = STATUS_CLASS[unit.status];
  const live = liveOf(unit);
  return (
    <>
      <div className="faint tiny">{unit.manager}</div>
      <h3>{unit.unit_name}</h3>
      <div style={{ display: "flex", gap: 12, alignItems: "baseline", marginTop: 14 }}>
        <span className="num" style={{ fontSize: "var(--fs-3xl)", fontWeight: 700 }}>{pct(unit.latest_score)}</span>
        <span className={`badge ${cls}`}>{STATUS_LABEL[unit.status]}</span>
      </div>
      <div className="note"><b style={{ color: "var(--text)" }}>این عدد از کجا آمده؟</b><br />
        {unit.latest_score == null ? "هنوز جلسه‌ای برگزار نشده است." : `میانگین پیشرفت نتایج کلیدی در ${roundOf(unit)} (آخرین جلسهٔ برگزارشده) ${pct(unit.latest_score)} است${unit.delta != null ? ` و نسبت به پایش قبل ${unit.delta < 0 ? "کاهش" : "افزایش"} ${pct(Math.abs(unit.delta))} داشته` : ""}.`}
        {live && <> {tpLabel(live.time_point)} هنوز برگزار نشده؛ امتیاز آن تا این لحظه {pct(live.score)} است و بعد از «برگزار شد» جای این عدد را می‌گیرد.</>}
        {unit.warnings.length > 0 && <> {unit.warnings.join("، ")}.</>}
      </div>
      <div className="sec" style={{ marginTop: 18 }}><h2>نتایج کلیدی{page.data && <span className="faint tiny" style={{ fontWeight: 400 }}>، {tpLabel(page.data.time_point)}{page.data.status !== "held" ? "، تا این لحظه" : ""}</span>}</h2></div>
      {page.loading && <Skeleton rows={3} />}
      {page.data?.objectives.flatMap((o) => o.key_results).map((k) => (
        <div className="kr" key={k.id}><Pie p={k.percent} status={k.status} /><span style={{ flex: 1 }}>{k.title}</span><b className={`num ${STATUS_CLASS[k.status]}`}>{pct(k.percent)}</b></div>
      ))}
      <div style={{ display: "flex", gap: 8, marginTop: 20 }}><button className="btn" onClick={onGo}>باز کردن جلسهٔ پایش</button></div>
    </>
  );
}
