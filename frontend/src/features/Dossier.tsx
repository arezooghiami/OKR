import { useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useGet } from "../api/typed";
import type { Dossier as DossierT, DossierCycle, DossierKR } from "../api/types";
import { STATUS_CLASS, STATUS_LABEL, statusFor } from "../domain/calc";
import { fa, faDigits, jDate, jDateTime, pct } from "../domain/format";
import ExportButton from "../ui/ExportButton";
import { Crumb, Empty, ErrorBox, Skeleton } from "../ui/parts";

const ROUND_STATUS: Record<string, string> = { held: "برگزار شد", scheduled: "زمان‌بندی شده", unscheduled: "بدون زمان" };
const EVENT_CLASS: Record<string, string> = { create: "ok", archive: "bad", value: "ac", session: "none", update: "risk", unit: "none", align: "none" };

/** /units — find a unit and open its dossier. */
export function DossierList() {
  const units = useGet("/api/v1/me/units");
  const overview = useGet("/api/v1/dashboard/overview");
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const rows = useMemo(() => {
    const by = new Map((overview.data?.units ?? []).map((u) => [u.unit_id, u]));
    return (units.data ?? []).map((u) => ({ ...u, o: by.get(u.id) })).filter((u) => u.name.includes(q.trim()));
  }, [units.data, overview.data, q]);
  if (units.loading && !units.data) return <Skeleton />;
  if (units.error) return <ErrorBox message={units.error} onRetry={units.reload} />;
  if ((units.data ?? []).length === 1) return <Navigate to={`/units/${units.data![0].id}`} replace />;
  return (
    <>
      <Crumb items={["سازمان", "پروندهٔ واحدها"]} />
      <div className="mh"><div><h1>پروندهٔ واحدها</h1><p className="faint">همهٔ اطلاعات و تاریخچهٔ هر واحد: اعضا، کارنامهٔ دوره‌ها، مقدار هر KR در هر پایش و همهٔ تغییرات.</p></div></div>
      <input className="srch dos-q" autoFocus placeholder="جستجوی نام واحد…" aria-label="جستجوی واحد" value={q} onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && rows[0] && nav(`/units/${rows[0].id}`)} />
      {rows.length === 0 && <Empty icon="search" title="واحدی با این نام پیدا نشد" hint="بخش کوتاه‌تری از نام واحد را امتحان کنید." />}
      <div className="dos-list">
        {rows.map((u) => {
          const st = u.o ? statusFor(u.o.latest_score) : null;
          return (
            <Link key={u.id} to={`/units/${u.id}`} className="dos-li">
              <b>{u.name}</b>
              <span className="faint tiny">{u.o?.current_round && u.o.total_krs ? `${fa(u.o.recorded)} از ${fa(u.o.total_krs)} KR ثبت در ${u.o.current_round}` : ""}</span>
              {st && <span className={`badge ${STATUS_CLASS[st]}`}>{u.o?.latest_score != null ? pct(u.o.latest_score) : STATUS_LABEL[st]}</span>}
            </Link>
          );
        })}
      </div>
    </>
  );
}

function Cell({ v }: { v: DossierKR["values"][number] }) {
  if (v.value == null) return <span className="faint">—</span>;
  const st = statusFor(v.percent);
  return (
    <span className="dos-v" title={v.note ?? undefined}>
      <b className="num">{fa(v.value, 2)}</b>
      <small className={STATUS_CLASS[st]}>{pct(v.percent)}</small>
      {v.note && <i className="dos-note" aria-label={`یادداشت: ${v.note}`}>•</i>}
    </span>
  );
}

function Scorecard({ cycles, selected, onPick }: { cycles: DossierCycle[]; selected?: string; onPick: (id: string) => void }) {
  return (
    <div className="tw">
      <table className="dt dos-t">
        <thead><tr><th>دوره</th><th>اهداف · KR</th><th>پایش‌ها</th><th>آخرین امتیاز</th></tr></thead>
        <tbody>
          {cycles.map((c) => (
            <tr key={c.id} className={c.id === selected ? "on" : undefined} onClick={() => onPick(c.id)} style={{ cursor: "pointer" }}>
              <td><b>{c.name}</b><div className="faint tiny">{c.status === "active" ? "جاری" : "بسته"} · {jDate(c.starts_on)} تا {jDate(c.ends_on)}</div></td>
              <td className="num">{fa(c.objectives)}، {fa(c.krs)}</td>
              <td>
                <div className="dos-rounds">
                  {c.rounds.filter((r) => r.kind !== "start").map((r) => (
                    <span key={r.label} className={`dos-r ${r.status}`} title={ROUND_STATUS[r.status]}>
                      {r.label} <b className={r.score != null ? STATUS_CLASS[statusFor(r.score)] : "faint"}>{r.score != null ? pct(r.score) : "—"}</b>
                      {r.status === "scheduled" && r.total > 0 && <small className="faint"> ({fa(r.recorded)}/{fa(r.total)})</small>}
                    </span>
                  ))}
                </div>
              </td>
              <td>{c.score != null ? <span className={`badge ${STATUS_CLASS[statusFor(c.score)]}`}>{pct(c.score)}</span> : <span className="faint">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Matrix({ d }: { d: DossierT }) {
  const [deleted, setDeleted] = useState(false);
  const archivedCount = d.objectives.reduce((n, o) => n + (o.archived ? o.krs.length : o.krs.filter((k) => k.archived).length), 0);
  const objs = d.objectives.filter((o) => deleted || !o.archived);
  if (!d.objectives.length) return <Empty title="در این دوره هدفی برای این واحد تعریف نشده است" />;
  return (
    <>
      {archivedCount > 0 && (
        <label className="dos-toggle"><input type="checkbox" checked={deleted} onChange={(e) => setDeleted(e.target.checked)} /> نمایش {fa(archivedCount)} KR حذف‌شده</label>
      )}
      <div className="tw">
        <table className="dt dos-m">
          <thead><tr><th>KR</th><th>مبنا</th><th>هدف</th>{d.review_labels.map((l) => <th key={l}>{l}</th>)}<th>آخرین</th></tr></thead>
          <tbody>
            {objs.map((o) => (
              <FragmentRows key={o.id} title={`${fa(o.number)}. ${o.title}`} archived={o.archived} reason={o.archive_reason} cols={d.review_labels.length + 4}>
                {o.krs.filter((k) => deleted || !k.archived).map((k) => (
                  <tr key={k.id} className={k.archived ? "gone" : undefined}>
                    <td className="dos-kr">
                      <Link to={`/krs/${k.id}`}><span className="num faint">{faDigits(k.code)}</span> {k.title}</Link>
                      <div className="faint tiny">
                        {[k.owner, k.goal && `هدف کلان: ${k.goal}`, k.versions > 1 && `${fa(k.versions)} نسخه`].filter(Boolean).join(" · ")}
                        {k.archived && <span className="bad"> · حذف‌شده{k.archive_reason ? `: ${k.archive_reason}` : ""}</span>}
                      </div>
                    </td>
                    <td className="num">{fa(k.baseline, 2)}</td>
                    <td className="num">{fa(k.target, 2)}{k.unit_of_measure && <small className="faint"> {k.unit_of_measure}</small>}</td>
                    {k.values.map((v) => <td key={v.label}><Cell v={v} /></td>)}
                    <td>{k.latest_percent != null ? <span className={`badge ${STATUS_CLASS[k.latest_status as keyof typeof STATUS_CLASS]}`}>{pct(k.latest_percent)}</span> : <span className="faint">—</span>}</td>
                  </tr>
                ))}
              </FragmentRows>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function FragmentRows({ title, archived, reason, cols, children }: { title: string; archived: boolean; reason: string | null; cols: number; children: React.ReactNode }) {
  return (
    <>
      <tr className={`dos-o${archived ? " gone" : ""}`}><td colSpan={cols}><b>{title}</b>{archived && <span className="bad tiny"> · هدف حذف‌شده{reason ? `: ${reason}` : ""}</span>}</td></tr>
      {children}
    </>
  );
}

function History({ d }: { d: DossierT }) {
  const [all, setAll] = useState(false);
  const list = all ? d.history : d.history.slice(0, 25);
  if (!d.history.length) return <Empty title="هنوز تغییری ثبت نشده است" />;
  return (
    <>
      <ol className="dos-h">
        {list.map((e, i) => (
          <li key={i}>
            <span className={`dos-dot ${EVENT_CLASS[e.kind] ?? "none"}`} aria-hidden="true" />
            <div><div>{e.text}</div><div className="faint tiny">{jDateTime(e.at)}{e.actor ? ` · ${e.actor}` : ""}</div></div>
          </li>
        ))}
      </ol>
      {d.history.length > 25 && <button className="lnk" onClick={() => setAll(!all)}>{all ? "نمایش کمتر" : `نمایش همه (${fa(d.history.length)})`}</button>}
      {d.history_total > d.history.length && <p className="faint tiny">{fa(d.history.length)} تغییر آخر از {fa(d.history_total)} نشان داده شده است.</p>}
    </>
  );
}

/** /units/:unitId?cycle= — everything about one unit. */
export default function Dossier() {
  const { unitId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const cycleId = params.get("cycle");
  const { data: d, error, loading, reload } = useGet("/api/v1/units/{unit_id}/dossier", { unit_id: unitId }, { query: { cycle_id: cycleId } });
  if (loading && !d) return <Skeleton rows={8} />;
  if (error || !d) return <ErrorBox message={error ?? "خطا"} onRetry={reload} />;
  const u = d.unit;
  const sel = d.cycles.find((c) => c.id === d.cycle?.id);
  const pick = (id: string) => setParams(id === d.cycles[0]?.id ? {} : { cycle: id });
  const tableLink = `/unit/${u.id}${sel && sel.status !== "active" ? `?cycle=${sel.id}` : ""}`;
  return (
    <>
      <Crumb items={["سازمان", "پروندهٔ واحدها", u.name]} />
      <div className="mh">
        <div>
          <h1>{u.name}{u.archived && <span className="faint"> (آرشیو)</span>}</h1>
          <p className="faint">{[u.path.length ? `زیرمجموعهٔ ${u.path.join(" › ")}` : "ریشهٔ سازمان", u.type, u.manager_name && `مدیر: ${u.manager_name}`, u.code].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="pickers">
          <Link className="btn o" to="/units">واحد دیگر</Link>
          {sel && <Link className="btn o" to={tableLink}>جدول واحد</Link>}
          {sel && <ExportButton path={`/units/${u.id}/export.xlsx?cycle_id=${sel.id}`} label="خروجی Excel" />}
        </div>
      </div>

      <section className="dos-sec">
        <h2>اعضا <span className="num faint">{fa(d.members.length)}</span></h2>
        {d.members.length ? <div className="stp-miss" style={{ marginTop: 0 }}>{d.members.map((m, i) => <span key={i} className="chip">{m.full_name} · {m.role}</span>)}</div>
          : <p className="risk">هیچ کاربری عضو این واحد نیست.</p>}
      </section>

      <section className="dos-sec">
        <h2>کارنامهٔ دوره‌ها</h2>
        {d.cycles.length ? <Scorecard cycles={d.cycles} selected={sel?.id} onPick={pick} /> : <Empty title="این واحد هنوز در هیچ دوره‌ای نبوده است" />}
      </section>

      {sel && (
        <>
          <section className="dos-sec">
            <h2>نتایج کلیدی · {sel.name} {sel.status !== "active" && <span className="lvl">بسته · فقط‌خواندنی</span>}</h2>
            <p className="faint tiny">مقدار هر KR در هر پایش و درصد پیشرفتش. پایش‌های برگزارشده همان درصدی را نشان می‌دهند که در جلسه ثبت شد.</p>
            <Matrix d={d} />
          </section>

          <section className="dos-sec">
            <h2>جلسه‌ها · {sel.name}</h2>
            <div className="tw">
              <table className="dt">
                <thead><tr><th>جلسه</th><th>زمان</th><th>وضعیت</th><th>ثبت مقدار</th><th>امتیاز</th></tr></thead>
                <tbody>
                  {sel.rounds.map((r) => (
                    <tr key={r.session_id}>
                      <td><Link to={`/sessions/${r.session_id}`}><b>{r.label}</b></Link></td>
                      <td>{r.status === "held" ? jDateTime(r.held_at) : r.scheduled_at ? jDateTime(r.scheduled_at) : <span className="risk">تعیین نشده</span>}{r.place && <div className="faint tiny">{r.place}</div>}</td>
                      <td><span className={`badge ${r.status === "held" ? "ok" : r.status === "scheduled" ? "ac" : "none"}`}>{ROUND_STATUS[r.status]}</span></td>
                      <td className="num">{r.total ? `${fa(r.recorded)} از ${fa(r.total)}` : "—"}</td>
                      <td>{r.score != null ? <b className={STATUS_CLASS[statusFor(r.score)]}>{pct(r.score)}</b> : <span className="faint">—</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="dos-sec">
            <h2>تاریخچهٔ تغییرات · {sel.name} <span className="num faint">{fa(d.history_total)}</span></h2>
            <History d={d} />
          </section>
        </>
      )}
    </>
  );
}
