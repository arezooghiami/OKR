import { useState } from "react";
import { api } from "../api/client";
import type { OverviewUnit } from "../api/types";
import { fa, jDayMonth, jTime, tpLabel } from "../domain/format";

type Result = { session_id: string; ok: boolean; error: string | null };

/** «برگزار شد» for several units at once (docs/07 phase 2). Lists each unit's open session; the system manager
 *  ticks the ones that took place. Each session is checked and saved on its own, so one refusal stops nothing. */
export default function HoldPanel({ units, onDone }: { units: OverviewUnit[]; onDone: () => void }) {
  const open = units
    .map((u) => ({ u, cell: u.cells.find((c) => c.time_point === u.current_round) }))
    .filter(({ u, cell }) => u.current_session_id && cell && cell.status !== "held");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<Map<string, Result> | null>(null);
  const [confirm, setConfirm] = useState(false);
  const flip = (id: string) => setPicked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const ids = open.map(({ u }) => u.current_session_id!);
  const all = ids.length > 0 && ids.every((id) => picked.has(id));

  const run = async () => {
    setBusy(true);
    try {
      const r = await api<Result[]>("/sessions/hold", { method: "POST", body: { session_ids: [...picked] } });
      setResults(new Map(r.map((x) => [x.session_id, x])));
      setPicked(new Set(r.filter((x) => !x.ok).map((x) => x.session_id)));
      onDone();
    } finally { setBusy(false); setConfirm(false); }
  };
  const okCount = results ? [...results.values()].filter((r) => r.ok).length : 0;

  return (
    <>
      <h3>ثبت برگزاری جلسه‌ها</h3>
      <p className="mut tiny" style={{ marginTop: 4 }}>
        جلسه‌هایی را که برگزار شده‌اند تیک بزنید. با «برگزار شد» درصد هر نتیجهٔ کلیدی در آن پایش ثابت می‌شود و پایش بعدی واحد برای ثبت باز می‌شود.
      </p>
      {results && <div className={`note ${okCount === results.size ? "" : "err-box"}`} role="status">
        {fa(okCount)} جلسه برگزارشده ثبت شد{okCount < results.size && `؛ ${fa(results.size - okCount)} جلسه ثبت نشد (دلیل کنار همان واحد آمده)`}.
      </div>}
      {open.length === 0
        ? <div className="empty"><b>جلسهٔ بازی نمانده است</b><div className="mut">جلسهٔ جاری همهٔ واحدها برگزار شده است.</div></div>
        : <>
          <label className="hold-row hold-all">
            <input type="checkbox" className="pickbox" checked={all} onChange={(e) => setPicked(e.target.checked ? new Set(ids) : new Set())} />
            <b>همهٔ واحدها</b><span className="faint num">{fa(open.length)} جلسه</span>
          </label>
          {open.map(({ u, cell }) => {
            const id = u.current_session_id!;
            const res = results?.get(id);
            return (
              <label key={id} className="hold-row">
                <input type="checkbox" className="pickbox" checked={picked.has(id)} onChange={() => flip(id)} />
                <span className="hold-u"><b>{u.unit_name}</b>
                  <span className="faint tiny">{tpLabel(u.current_round)}، {cell?.status === "unscheduled" || !u.next_session ? "بدون زمان" : `${jDayMonth(u.next_session.at)}، ساعت ${jTime(u.next_session.at)}`}</span>
                  {res && !res.ok && <span className="bad tiny" role="alert">{res.error}</span>}
                </span>
                <span className="num tiny mut">{u.total_krs ? `${fa(u.recorded)} از ${fa(u.total_krs)} ثبت` : "—"}</span>
              </label>
            );
          })}
          <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
            {confirm
              ? <><button className="btn" disabled={busy} onClick={run}>{busy ? "در حال ثبت…" : `تأیید: ${fa(picked.size)} جلسه برگزار شد`}</button>
                  <button className="btn o" onClick={() => setConfirm(false)}>انصراف</button></>
              : <button className="btn" disabled={picked.size === 0} onClick={() => setConfirm(true)}>برگزار شد برای {fa(picked.size)} جلسه</button>}
          </div>
        </>}
    </>
  );
}
