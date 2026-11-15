import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useGet } from "../api/typed";
import type { GoalBlock } from "../api/types";
import { STATUS_CLASS, statusFor } from "../domain/calc";
import { fa, faDigits, pct } from "../domain/format";
import { Bar, Crumb, Empty, ErrorBox, Skeleton } from "../ui/parts";

/** One strategic goal: its progress and, opened, every unit → objective → KR that is linked to it. */
function Goal({ g, open, onToggle, unlinked }: { g: GoalBlock; open: boolean; onToggle: () => void; unlinked?: boolean }) {
  const units = g.units.length;
  return (
    <section className={`gl${unlinked ? " gl-un" : ""}${open ? " open" : ""}`}>
      <button className="gl-h" aria-expanded={open} onClick={onToggle} disabled={!g.krs}>
        <span className="gl-dot" style={g.color ? { background: `var(${g.color})` } : undefined} aria-hidden="true" />
        <span className="gl-t">
          <b>{g.title}</b>
          <span className="faint tiny">
            {g.krs
              ? `${fa(g.krs)} نتیجهٔ کلیدی در ${fa(g.objectives)} هدف از ${fa(units)} واحد، ${fa(g.recorded)} مورد مقدار ثبت‌شده دارد`
              : unlinked ? "همهٔ نتایج کلیدی به یک هدف کلان وصل‌اند." : "هنوز هیچ نتیجهٔ کلیدی‌ای به این هدف وصل نشده است."}
          </span>
        </span>
        {!unlinked && <span className="gl-p">{g.progress != null ? <><b className={STATUS_CLASS[statusFor(g.progress)]}>{pct(g.progress)}</b><Bar p={g.progress} /></> : <span className="faint tiny">بدون مقدار</span>}</span>}
        {g.krs > 0 && <svg className="gl-chev i" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>}
      </button>
      {open && (
        <div className="gl-b">
          {unlinked && <p className="faint tiny">برای وصل کردن، در جدول همان واحد ستون «هدف کلان» را انتخاب کنید.</p>}
          {g.units.map((u) => (
            <div key={u.unit_id} className="gl-u">
              <div className="gl-uh">
                <Link to={`/unit/${u.unit_id}`}><b>{u.unit_name}</b></Link>
                {!unlinked && u.progress != null && <b className={`num ${STATUS_CLASS[statusFor(u.progress)]}`}>{pct(u.progress)}</b>}
              </div>
              {u.objectives.map((o) => (
                <div key={o.id} className="gl-o">
                  <div className="gl-ot">هدف {fa(o.number)}: {o.title}</div>
                  {o.krs.map((k) => (
                    <Link key={k.id} to={`/krs/${k.id}`} className="gl-k">
                      <span className="num faint">{faDigits(k.code)}</span>
                      <span className="gl-kt">{k.title}{k.owner && <small className="faint"> · {k.owner}</small>}</span>
                      <span className={`num ${k.progress == null ? "faint" : STATUS_CLASS[k.status as keyof typeof STATUS_CLASS]}`}>{pct(k.progress)}{k.round && <small className="faint"> {k.round}</small>}</span>
                    </Link>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/** /goals — the organisation's strategic goals and what pushes each of them (replaces the objective-tree "alignment"). */
export default function Goals() {
  const [params, setParams] = useSearchParams();
  const cycleId = params.get("cycle");
  const { data, error, loading, reload } = useGet("/api/v1/goals/overview", { query: { cycle_id: cycleId } });
  const cycles = useGet("/api/v1/cycles");
  const [open, setOpen] = useState<Set<string>>(new Set());
  if (loading && !data) return <Skeleton rows={6} />;
  if (error || !data) return <ErrorBox message={error ?? "خطا"} onRetry={reload} />;
  const toggle = (id: string) => setOpen((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const all = [...data.goals.map((g) => g.id ?? ""), "none"];
  const allOpen = all.every((id) => open.has(id));
  const linked = data.goals.reduce((n, g) => n + g.krs, 0), total = linked + data.unlinked.krs;
  return (
    <>
      <Crumb items={["سازمان", "اهداف کلان"]} />
      <div className="mh">
        <div>
          <h1>اهداف کلان</h1>
          <p className="faint">هر نتیجهٔ کلیدی در جدول واحد به یکی از اهداف کلان وصل می‌شود. اینجا می‌بینید هر هدف کلان را کدام واحدها و اهداف پیش می‌برند، چقدر جلو رفته‌اند و چه چیزی به هیچ هدف کلانی وصل نیست.</p>
        </div>
        <div className="pickers">
          {(cycles.data?.length ?? 0) > 1 && data.cycle && (
            <div className="f"><label htmlFor="g-cycle">دوره</label>
              <select id="g-cycle" value={data.cycle.id} onChange={(e) => setParams(e.target.value === cycles.data?.[0]?.id ? {} : { cycle: e.target.value })}>
                {cycles.data?.map((c) => <option key={c.id} value={c.id}>{c.name}{c.status === "active" ? " · جاری" : " · بسته"}</option>)}
              </select></div>
          )}
          <button className="btn o" onClick={() => setOpen(allOpen ? new Set() : new Set(all))}>{allOpen ? "بستن همه" : "باز کردن همه"}</button>
        </div>
      </div>
      {total > 0 && (
        <p className="gl-sum">{fa(linked)} از {fa(total)} نتیجهٔ کلیدی این دوره به یک هدف کلان وصل‌اند
          {data.unlinked.krs > 0 && <span className="risk">، {fa(data.unlinked.krs)} مورد وصل نیست</span>}.</p>
      )}
      {data.goals.length === 0 && <Empty title="هنوز هدف کلانی تعریف نشده است" hint="مدیر سیستم از «راه‌اندازی ← اهداف کلان» آن‌ها را تعریف می‌کند." />}
      <div className="gls">
        {data.goals.map((g) => <Goal key={g.id} g={g} open={open.has(g.id ?? "")} onToggle={() => toggle(g.id ?? "")} />)}
        {data.goals.length > 0 && <Goal g={data.unlinked} unlinked open={open.has("none")} onToggle={() => toggle("none")} />}
      </div>
    </>
  );
}
