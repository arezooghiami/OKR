import { useState } from "react";
import { useGet } from "../../api/typed";
import type { OrgNode } from "../../api/types";
import { fa, jDate } from "../../domain/format";
import { Empty, ErrorBox, Icon, Skeleton, Tag } from "../../ui/parts";

function Node({ n, depth }: { n: OrgNode; depth: number }) {
  const [open, setOpen] = useState(depth < 2);
  const kids = n.children.length > 0;
  return (
    <div className="tr">
      <div className={`n ${open ? "open" : ""}`} role={kids ? "button" : undefined} tabIndex={0} aria-expanded={kids ? open : undefined}
        onClick={() => kids && setOpen(!open)} onKeyDown={(e) => kids && (e.key === "Enter" || e.key === " ") && setOpen(!open)}>
        <svg className="i ch" viewBox="0 0 24 24" style={{ opacity: kids ? 1 : 0 }} aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
        <div style={{ flex: 1, minWidth: 0 }}><div className="nm">{n.name}</div><div className="fa">{n.manager ? `مدیر: ${n.manager}` : "بدون مدیر"}{kids && `، ${fa(n.children.length)} زیرواحد`}</div></div>
        {n.type && <Tag color={n.type_color ?? "--g0"}>{n.type}</Tag>}
      </div>
      {kids && <div className={`kids ${open ? "open" : ""}`}>{n.children.map((c) => <Node key={c.id} n={c} depth={depth + 1} />)}</div>}
    </div>
  );
}

const count = (ns: OrgNode[]): number => ns.reduce((s, n) => s + 1 + count(n.children), 0);

export default function OrgPanel() {
  const { data, error, loading, reload } = useGet("/api/v1/org/tree");
  if (loading && !data) return <Skeleton />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data || !data.units.length) return <Empty title="ساختاری تعریف نشده است" />;
  return (
    <>
      <div className="card" style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: 1 }}><b>نسخهٔ ساختار {fa(data.version)}</b> <span className="lvl">فعال</span><div className="faint tiny">اجرا از {jDate(data.effective_from)}</div></div>
      </div>
      <div className="sec"><h2>واحدها <span className="num">{fa(count(data.units))}</span></h2></div>
      <div className="note"><Icon d="M12 8v5m0 3h.01" /> ویرایش ساختار (جابه‌جایی، ادغام، نسخهٔ جدید) هنوز پیاده‌سازی نشده است؛ فعلاً فقط نمایش.</div>
      {data.units.map((n) => <Node key={n.id} n={n} depth={0} />)}
    </>
  );
}
