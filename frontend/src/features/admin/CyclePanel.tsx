import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useGet } from "../../api/typed";
import type { CycleAdmin, SessionHead } from "../../api/types";
import { fa, jDate, tpLabel } from "../../domain/format";
import { parseJalaliDate, parseJalaliDateTime, toJalaliFields } from "../../domain/jalali";
import JalaliDate from "../../ui/JalaliDate";
import { Empty, ErrorBox, Skeleton } from "../../ui/parts";
import { usePeek } from "../../ui/Peek";
import { Field, Msg, Select, useAction } from "./fields";

const KIND_LABEL: Record<string, string> = { start: "جلسهٔ شروع", review: "پایش", final: "جلسهٔ نهایی" };
const STATUS_LABEL: Record<string, string> = { draft: "پیش‌نویس", active: "فعال", closed: "بسته" };

type TP = { kind: string; label: string };

function NewCycleForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reviews, setReviews] = useState("3");
  const [labels, setLabels] = useState<TP[]>([]);
  const a = useAction();

  const n = Math.max(0, Math.min(12, parseInt(reviews, 10) || 0));
  const preset: TP[] = [{ kind: "start", label: "شروع" }, ...Array.from({ length: n }, (_, i) => ({ kind: "review", label: `R${i + 1}` })), { kind: "final", label: "نهایی" }];
  const tps = labels.length ? labels : preset;
  const f = parseJalaliDate(from), t = parseJalaliDate(to);

  const submit = async () => {
    if (!f || !t) return a.run(async () => { throw new Error("تاریخ‌ها را جلالی و مثل ۱۴۰۵/۰۷/۰۱ وارد کنید"); });
    if (await a.run(() => api("/admin/cycles", { method: "POST", body: { name, starts_on: f, ends_on: t, time_points: tps } }))) onDone();
  };
  return (
    <>
      <h3>دورهٔ جدید</h3>
      <Field label="نام دوره" value={name} onChange={setName} placeholder="مثلاً: دورهٔ بهار ۱۴۰۵" />
      <div className="two">
        <div className="f"><label htmlFor="cy-from">شروع</label><JalaliDate id="cy-from" label="تاریخ شروع" value={from} onChange={setFrom} placeholder="1405/01/01" /></div>
        <div className="f"><label htmlFor="cy-to">پایان</label><JalaliDate id="cy-to" label="تاریخ پایان" value={to} onChange={setTo} placeholder="1405/04/31" /></div>
      </div>
      <Field label="تعداد پایش‌ها" value={reviews} onChange={(v) => { setReviews(v); setLabels([]); }} dir="ltr" hint="جلسهٔ شروع و جلسهٔ نهایی خودکار اضافه می‌شوند" />
      <div className="sec" style={{ marginTop: 14 }}><h2>نقطه‌های زمانی <span className="num">{fa(tps.length)}</span></h2></div>
      {tps.map((p, i) => (
        <div key={i} className="two" style={{ marginTop: 6 }}>
          <input aria-label="برچسب" value={p.label} onChange={(e) => setLabels(tps.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} style={{ padding: "6px 10px", border: "1px solid var(--line-strong)", borderRadius: 8, background: "var(--surface)" }} />
          <span className="faint tiny" style={{ alignSelf: "center" }}>{KIND_LABEL[p.kind]}</span>
        </div>
      ))}
      <div className="note">برای هر واحد، برای هر نقطهٔ زمانی یک جلسه ساخته می‌شود؛ زمان و مکانش را بعد از ساخت دوره در همین صفحه می‌گذارید.</div>
      <Msg err={a.err} />
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}><button className="btn" disabled={a.busy || !name.trim()} onClick={submit}>ساخت دوره</button><button className="btn o" onClick={onDone}>انصراف</button></div>
    </>
  );
}

function CycleCard({ c, onChange }: { c: CycleAdmin; onChange: () => void }) {
  const a = useAction();
  const [kind, setKind] = useState("review");
  const [label, setLabel] = useState("");
  const setStatus = (status: string) => a.run(() => api(`/admin/cycles/${c.id}`, { method: "PATCH", body: { status } })).then((ok) => ok && onChange());
  return (
    <div className="card">
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: 1 }}><b style={{ fontSize: 15 }}>{c.name}</b> <span className="lvl">{STATUS_LABEL[c.status] ?? c.status}</span>
          <div className="faint tiny">{jDate(c.starts_on)} تا {jDate(c.ends_on)}، {fa(c.sessions_total)} جلسه، {fa(c.sessions_held)} برگزارشده، {fa(c.sessions_unscheduled)} بدون زمان</div></div>
        {c.status === "draft" && <button className="btn" disabled={a.busy} onClick={() => setStatus("active")}>فعال‌سازی</button>}
        {c.status === "active" && <button className="btn o" disabled={a.busy} onClick={() => window.confirm("دوره بسته شود؟ دوباره باز نمی‌شود.") && setStatus("closed")}>بستن دوره</button>}
      </div>
      <div className="steps" style={{ margin: "12px 0 0" }}>
        {c.time_points.map((t) => (
          <span key={t.id} title={KIND_LABEL[t.kind]}>{tpLabel(t.label)}
            {c.status !== "closed" && <button aria-label={`حذف ${t.label}`} className="lnk" style={{ marginInlineStart: 6, textDecoration: "none" }}
              onClick={() => window.confirm(`نقطهٔ «${t.label}» و جلسه‌هایش حذف شود؟`) && a.run(() => api(`/admin/time-points/${t.id}`, { method: "DELETE" })).then((ok) => ok && onChange())}>×</button>}
          </span>
        ))}
      </div>
      {c.status !== "closed" && (
        <div style={{ display: "flex", gap: 8, alignItems: "end", marginTop: 10, flexWrap: "wrap" }}>
          <div style={{ width: 150 }}><Select label="نوع" value={kind} onChange={setKind} options={Object.entries(KIND_LABEL)} /></div>
          <div style={{ width: 150 }}><Field label="برچسب" value={label} onChange={setLabel} placeholder="مثلاً R4" /></div>
          <button className="btn o" disabled={a.busy || !label.trim()} onClick={() => a.run(() => api(`/admin/cycles/${c.id}/time-points`, { method: "POST", body: { kind, label } })).then((ok) => { if (ok) { setLabel(""); onChange(); } })}>+ نقطهٔ زمانی</button>
        </div>
      )}
      <Msg err={a.err} />
    </div>
  );
}

function SessionRow({ s, onSaved }: { s: SessionHead; onSaved: () => void }) {
  const init = toJalaliFields(s.scheduled_at);
  const [date, setDate] = useState(init.date);
  const [time, setTime] = useState(init.time);
  const [place, setPlace] = useState(s.place ?? "");
  const a = useAction();
  const held = s.status === "held";
  const iso = parseJalaliDateTime(date, time);
  const changed = date !== init.date || time !== init.time || place !== (s.place ?? "");
  const save = () => a.run(async () => {
    if (!iso) throw new Error("تاریخ (مثل ۱۴۰۵/۰۸/۲۴) و ساعت (مثل ۱۱:۰۰) را درست وارد کنید");
    await api(`/sessions/${s.id}`, { method: "PUT", body: { scheduled_at: iso, place: place || null, expected_version: s.version } });
  }).then((ok) => ok && onSaved());
  return (
    <>
      <div className={`mrow ${s.status === "unscheduled" ? "warn" : ""}`}>
        <b>{s.unit_name}</b>
        <JalaliDate label={`تاریخ ${s.unit_name}`} value={date} disabled={held} onChange={setDate} />
        <input aria-label={`ساعت ${s.unit_name}`} dir="ltr" className="num" placeholder="11:00" value={time} disabled={held} onChange={(e) => setTime(e.target.value)} />
        <input aria-label={`مکان ${s.unit_name}`} placeholder="مکان یا لینک" value={place} disabled={held} onChange={(e) => setPlace(e.target.value)} />
        <span className="tiny" style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {held ? <span className="faint">برگزار شد · {jDate(s.held_at)}</span>
            : changed ? <button className="btn" style={{ padding: "3px 12px" }} disabled={a.busy} onClick={save}>ذخیره</button>
            : <span className={s.status === "unscheduled" ? "risk" : "ok"} style={{ fontWeight: 600 }}>{s.status === "unscheduled" ? "بدون زمان جلسه" : "زمان‌بندی شد"}</span>}
        </span>
      </div>
      <Msg err={a.err} />
    </>
  );
}

function Schedule({ cycle }: { cycle: CycleAdmin }) {
  const [tp, setTp] = useState<string | null>(null);
  useEffect(() => { setTp(cycle.time_points.find((t) => t.kind !== "start")?.id ?? cycle.time_points[0]?.id ?? null); }, [cycle.id, cycle.time_points.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const rows = useGet("/api/v1/time-points/{time_point_id}/sessions", tp ? { time_point_id: tp } : null);
  const missing = (rows.data ?? []).filter((s) => s.status === "unscheduled").length;
  return (
    <>
      <div className="sec" style={{ marginTop: 22 }}><h2>زمان‌بندی جلسه‌ها · {cycle.name}</h2></div>
      <div className="seg" style={{ margin: "0 0 12px" }} role="tablist">
        {cycle.time_points.map((t) => (
          <button key={t.id} role="tab" aria-selected={t.id === tp} className={t.id === tp ? "on" : ""} onClick={() => setTp(t.id)}>{t.label}</button>))}
      </div>
      {missing > 0 && <div className="warnbar" role="status"><b>{fa(missing)} واحد بدون زمان جلسه.</b> ثبت مقدار برایشان باز است، ولی اعضا نمی‌دانند تا کی وقت دارند.</div>}
      {(rows.data ?? []).length === 0 && !rows.loading && <Empty title="جلسه‌ای نیست" hint="ابتدا واحد تعریف کنید؛ جلسه‌ها خودکار ساخته می‌شوند." />}
      {(rows.data ?? []).length > 0 && <div className="mrow head"><span>واحد</span><span>تاریخ (جلالی)</span><span>ساعت</span><span>مکان یا لینک</span><span>وضعیت</span></div>}
      {rows.loading && !rows.data ? <Skeleton rows={3} /> : (rows.data ?? []).map((s) => <SessionRow key={`${s.id}:${s.version}`} s={s} onSaved={rows.reload} />)}
    </>
  );
}

export default function CyclePanel() {
  const cycles = useGet("/api/v1/admin/cycles");
  const peek = usePeek();
  const [sel, setSel] = useState<string | null>(null);
  if (cycles.loading && !cycles.data) return <Skeleton />;
  if (cycles.error) return <ErrorBox message={cycles.error} onRetry={cycles.reload} />;
  const list = cycles.data ?? [];
  const current = list.find((c) => c.id === sel) ?? list.find((c) => c.status === "active") ?? list[0];
  const create = () => peek.open(<NewCycleForm onDone={() => { peek.close(); cycles.reload(); }} />);
  return (
    <>
      <div className="sec"><h2>دوره‌ها <span className="num">{fa(list.length)}</span></h2><button className="btn" onClick={create}>+ دورهٔ جدید</button></div>
      {list.length === 0 && <Empty title="هنوز دوره‌ای تعریف نشده است" hint="اول واحدها را تعریف کنید، بعد دوره بسازید و فعالش کنید." />}
      {list.map((c) => (
        <div key={c.id} onClick={() => setSel(c.id)} className={current?.id === c.id && list.length > 1 ? "picked" : undefined}>
          <CycleCard c={c} onChange={cycles.reload} />
        </div>
      ))}
      {current && current.status !== "closed" && <Schedule cycle={current} />}
    </>
  );
}

