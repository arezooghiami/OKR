import { useState } from "react";
import { api } from "../../api/client";
import { useGet } from "../../api/typed";
import { fa } from "../../domain/format";
import { Empty, ErrorBox, Skeleton, Tag } from "../../ui/parts";
import { Field, Msg, useAction } from "./fields";

/** Business goals (اهداف کلان): the labels KRs are tagged with. */
export default function GoalsPanel() {
  const { data, error, loading, reload } = useGet("/api/v1/admin/goals");
  const [title, setTitle] = useState("");
  const a = useAction();
  if (loading && !data) return <Skeleton />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const list = data ?? [];
  return (
    <>
      <div className="sec"><h2>اهداف کسب‌وکاری <span className="num">{fa(list.length)}</span></h2></div>
      <div className="note">هر نتیجهٔ کلیدی را می‌توان به یکی از این اهداف برچسب زد. اختیاری است.</div>
      {list.length === 0 && <Empty title="هنوز هدف کسب‌وکاری‌ای تعریف نشده است" />}
      {list.map((g) => (
        <div className="row" key={g.id} style={{ gridTemplateColumns: "1fr 90px", opacity: g.active ? 1 : 0.5, cursor: "default" }}>
          <Tag color={g.color}>{g.title}</Tag>
          <button className="lnk" onClick={() => a.run(() => api(`/admin/goals/${g.id}`, { method: "PATCH", body: { active: !g.active } })).then((ok) => ok && reload())}>{g.active ? "غیرفعال" : "فعال‌سازی"}</button>
        </div>
      ))}
      <div className="card" style={{ marginTop: 16 }}>
        <h3>هدف جدید</h3>
        <Field label="عنوان" value={title} onChange={setTitle} placeholder="مثلاً: تحقق سودآوری پایدار" />
        <Msg err={a.err} />
        <button className="btn" style={{ marginTop: 10 }} disabled={!title.trim() || a.busy} onClick={() => a.run(() => api("/admin/goals", { method: "POST", body: { title } })).then((ok) => { if (ok) { setTitle(""); reload(); } })}>افزودن</button>
      </div>
    </>
  );
}
