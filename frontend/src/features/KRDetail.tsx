import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useGet } from "../api/typed";
import type { KRDetail, Version } from "../api/types";
import { STATUS_CLASS, STATUS_LABEL } from "../domain/calc";
import { fa, jDate, pct } from "../domain/format";
import { Crumb, ErrorBox, Skeleton } from "../ui/parts";

const CTX: Record<string, string> = { initial: "ایجاد اولیه", in_session: "اصلاح در جلسه", between: "بین جلسات", after_session: "پس از جلسه" };

function Chart({ series }: { series: KRDetail["series"] }) {
  const W = 480, H = 140, n = Math.max(series.length, 2);
  const x = (i: number) => 20 + (i * (W - 40)) / (n - 1), y = (v: number) => H - 24 - (v * (H - 44)) / 100;
  const pts = series.map((s, i) => ({ s, i })).filter(({ s }) => s.percent != null);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="نمودار پیشرفت در پایش‌ها" style={{ overflow: "visible" }}>
      {[0, 50, 100].map((v) => <line key={v} x1="0" x2={W} y1={y(v)} y2={y(v)} stroke="var(--line)" />)}
      <path d={"M" + pts.map(({ s, i }) => `${x(i)},${y(s.percent!)}`).join(" L")} fill="none" stroke="var(--ac)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      {pts.map(({ s, i }, k) => <g key={i}><circle cx={x(i)} cy={y(s.percent!)} r={k === pts.length - 1 ? 5 : 3.5} fill={k === pts.length - 1 ? "var(--ac)" : "var(--panel)"} stroke="var(--ac)" strokeWidth="2" />
        <text x={x(i)} y={y(s.percent!) - 11} fontSize="12" fontWeight="700" textAnchor="middle" fill="var(--tx)">{fa(Math.round(s.percent!))}</text></g>)}
      {series.map((s, i) => <text key={i} x={x(i)} y={H - 4} fontSize="11" textAnchor="middle" fill="var(--faint)">{s.label}</text>)}
    </svg>
  );
}

function Diff({ a, b }: { a: Version; b: Version }) {
  const rows: [string, string, string][] = [];
  if (a.target !== b.target) rows.push(["هدف", fa(a.target), fa(b.target)]);
  if (a.baseline !== b.baseline) rows.push(["مبنا", fa(a.baseline), fa(b.baseline)]);
  if (a.title !== b.title) rows.push(["عنوان", a.title, b.title]);
  if (a.weight !== b.weight) rows.push(["وزن", fa(a.weight), fa(b.weight)]);
  return <>{rows.map(([l, x, y]) => <div className="diff" key={l}><div className="a"><small>قبل · {l}</small><b className="num">{x}</b></div><div className="b"><small>بعد · {l}</small><b className="num">{y}</b></div></div>)}</>;
}

export default function KRDetailPage() {
  const { id } = useParams();
  const { data: d, error, loading, reload } = useGet("/api/v1/key-results/{kr_id}", id ? { kr_id: id } : null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (loading && !d) return <Skeleton rows={6} />;
  if (error || !d) return <ErrorBox message={error ?? "یافت نشد"} onRetry={reload} />;

  const post = async () => {
    setBusy(true); setErr(null);
    try { await api(`/key-results/${d.id}/comments`, { method: "POST", body: { body: text } }); setText(""); reload(); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  const f = d.formula;
  return (
    <>
      <Crumb items={["نتیجه کلیدی", d.code.split(".").map((p) => fa(p)).join(".")]} />
      <div className="mh"><div><div className="faint tiny">نتیجهٔ کلیدی {d.code.split(".").map((p) => fa(p)).join(".")}{d.definition.goal && ` · ${d.definition.goal}`}</div><h1 style={{ marginTop: 4 }}>{d.definition.title}</h1></div></div>
      <div className="two2" style={{ marginTop: 22 }}>
        <div>
          <div className="card"><h3>پیشرفت در پایش‌ها</h3>{d.series.length ? <Chart series={d.series} /> : <div className="faint">هنوز مقداری ثبت نشده است.</div>}</div>
          <div className="card"><h3>تاریخچهٔ نسخه‌ها</h3>
            <div className="tl">{d.versions.map((v, i) => (
              <div key={v.number} className={`ver ${i > 0 ? "old" : ""}`}><span className="dot" />
                <div><b>نسخهٔ {fa(v.number)}</b> {i === 0 && <span className="lvl">فعلی</span>}
                  <div className="faint tiny">{jDate(v.at)} · {v.actor} · {CTX[v.context] ?? v.context}</div>
                  {d.versions[i + 1] ? <Diff a={d.versions[i + 1]} b={v} /> : <div className="mut tiny" style={{ marginTop: 4 }}>مبنا {fa(v.baseline)} · هدف {fa(v.target)}</div>}
                  {v.reason && <div className="note" style={{ margin: "8px 0 0" }}><b style={{ color: "var(--tx)" }}>دلیل:</b> {v.reason}</div>}
                </div></div>))}</div></div>
          <div className="card"><h3>گفتگو</h3>
            {d.comments.length === 0 && <div className="faint tiny">هنوز کامنتی نیست.</div>}
            {d.comments.map((c) => <div className="cm" key={c.id}><div className="av">{c.author?.[0]}</div><div><b>{c.author}</b> <span className="faint tiny">{jDate(c.at)}</span><div>{c.body}</div></div></div>)}
            <div className="f"><label htmlFor="cm">کامنت جدید</label><textarea id="cm" value={text} onChange={(e) => setText(e.target.value)} /></div>
            {err && <div className="note" role="alert" style={{ color: "var(--bad)" }}>{err}</div>}
            <button className="btn" style={{ marginTop: 10 }} disabled={busy || !text.trim()} onClick={post}>ارسال</button></div>
        </div>
        <div>
          {f && <div className="card"><h3>این درصد چطور محاسبه شد؟</h3><div className="frm">{f.expression}<br />= ({fa(f.value)} − {fa(f.baseline)}) / ({fa(f.target)} − {fa(f.baseline)})<br />= <b style={{ color: "var(--tx)" }}>{pct(f.percent)}</b></div></div>}
          <div className="card"><h3>مشخصات</h3>
            <div className="rv"><span className="faint">مبنا ← هدف</span><b className="num">{fa(d.definition.baseline)} ← {fa(d.definition.target)}</b></div>
            <div className="rv"><span className="faint">مسئول</span><b>{d.definition.owner ?? "—"}</b></div>
            <div className="rv"><span className="faint">وضعیت</span><b className={STATUS_CLASS[d.status]}>{STATUS_LABEL[d.status]}</b></div>
            {d.definition.expectation && <div className="note" style={{ margin: "10px 0 0" }}><b style={{ color: "var(--tx)" }}>شرح انتظار</b><br />{d.definition.expectation}</div>}
          </div>
        </div>
      </div>
    </>
  );
}
