import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useGet } from "../api/typed";
import type { Workspace, WorkspaceKR, WorkspaceObjective } from "../api/types";
import { STATUS_CLASS, STATUS_LABEL } from "../domain/calc";
import { fa, parseNumber, pct } from "../domain/format";

const code = (c: string) => c.split(".").map((p) => fa(p)).join(".");
const TRASH = "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3";
const Trash = () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d={TRASH} /></svg>;
const numText = (n: number | null | undefined) => (n == null ? "" : fa(n, 4));
type Opt = { id: string; label: string };

/** The unit's objectives and KRs of a cycle as one sheet, like the Excel file:
 *  every row visible, cells edited in place (each save is a new version), delete = archive with a reason. */
export default function UnitTable({ data, reload, newObjectiveRef }: {
  data: Workspace; reload: () => void; newObjectiveRef: React.RefObject<HTMLInputElement>;
}) {
  const canEdit = data.can_edit, canDefine = data.can_define, canDelete = data.can_delete;
  const members = useGet("/api/v1/units/{unit_id}/members", canEdit ? { unit_id: data.unit_id } : null);
  const goals = useGet("/api/v1/goals");
  const people: Opt[] = (members.data ?? []).map((m) => ({ id: m.id, label: m.full_name }));
  const goalOpts: Opt[] = (goals.data ?? []).map((g) => ({ id: g.id, label: g.title }));
  const [adding, setAdding] = useState<string | null>(null);

  return (
    <div className="xlw">
      <table className="xl">
        <colgroup><col style={{ width: 56 }} /><col /><col style={{ width: 86 }} /><col style={{ width: 86 }} /><col style={{ width: 92 }} />
          <col style={{ width: 120 }} /><col style={{ width: 136 }} /><col style={{ width: 184 }} />{(canEdit || canDelete) && <col style={{ width: 48 }} />}</colgroup>
        <thead><tr>
          <th>کد</th><th>نتیجهٔ کلیدی</th><th className="c">خط مبنا</th><th className="c">هدف</th><th className="c">آخرین مقدار</th>
          <th>پیشرفت</th><th>مسئول</th><th>هدف کلان</th>{(canEdit || canDelete) && <th><span className="sr-only">عملیات</span></th>}
        </tr></thead>
        <tbody>
          {data.objectives.length === 0 && <tr><td colSpan={9} className="mut" style={{ padding: 18, textAlign: "center" }}>هنوز هدفی برای این دوره تعریف نشده است.</td></tr>}
          {data.objectives.map((o) => (
            <ObjectiveRows key={`${o.id}-${o.definition_version}`} o={o} people={people} goals={goalOpts} canEdit={canEdit} canDefine={canDefine}
              canDelete={canDelete} adding={adding === o.id} onAdd={() => setAdding(o.id)} onAdded={() => { setAdding(null); reload(); }}
              onCancelAdd={() => setAdding(null)} reload={reload} />
          ))}
          {canDefine && <NewObjectiveRow unitId={data.unit_id} inputRef={newObjectiveRef} onDone={reload} />}
        </tbody>
      </table>
    </div>
  );
}

/** Text or number cell that saves on blur/Enter and reverts on Escape. */
function Cell({ value, num, multiline, disabled, label, onSave }: {
  value: string; num?: boolean; multiline?: boolean; disabled?: boolean; label: string; onSave: (v: string) => void;
}) {
  const [v, setV] = useState(value);
  const bad = num && parseNumber(v) === undefined;
  if (disabled) return <span className={num ? "ro-n num" : "ro-t"}>{value || "—"}</span>;
  const commit = () => { if (v !== value && !bad) onSave(v); };
  const keys = (e: KeyboardEvent) => {
    if (e.key === "Escape") { setV(value); (e.target as HTMLElement).blur(); }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); (e.target as HTMLElement).blur(); }
  };
  return multiline
    ? <textarea className="cell" aria-label={label} rows={Math.max(1, Math.ceil(v.length / 34))} value={v} onChange={(e) => setV(e.target.value)} onBlur={commit} onKeyDown={keys} />
    : <input className={`cell ${num ? "num" : ""} ${bad ? "err" : ""}`} aria-label={label} inputMode={num ? "decimal" : undefined} value={v}
        onChange={(e) => setV(e.target.value)} onBlur={commit} onKeyDown={keys} />;
}

/** A choice cell: shows the chosen name as plain (wrapping) text; a click opens the list. */
function Pick({ value, options, empty, label, disabled, onSave }: {
  value: string | null; options: Opt[]; empty: string; label: string; disabled?: boolean; onSave: (v: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const sel = useRef<HTMLSelectElement>(null);
  useEffect(() => { if (open) { sel.current?.focus(); try { sel.current?.showPicker?.(); } catch { /* not supported: focused select is enough */ } } }, [open]);
  const text = options.find((o) => o.id === value)?.label;
  if (disabled) return <span className={`ro-t${text ? "" : " faint"}`}>{text ?? empty}</span>;
  if (!open) return <button type="button" className={`pick${text ? "" : " empty"}`} aria-label={`${label}: ${text ?? empty}`} onClick={() => setOpen(true)}>{text ?? empty}</button>;
  return (
    <select ref={sel} className="cell" aria-label={label} value={value ?? ""} onBlur={() => setOpen(false)}
      onKeyDown={(e) => e.key === "Escape" && setOpen(false)} onChange={(e) => { setOpen(false); onSave(e.target.value || null); }}>
      <option value="">{empty}</option>
      {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
    </select>
  );
}

/** Inline row under a KR/objective asking for a reason (target change or delete). */
function ReasonRow({ text, action, danger, onSubmit, onCancel }: { text: string; action: string; danger?: boolean; onSubmit: (r: string) => void; onCancel: () => void }) {
  const [r, setR] = useState("");
  return (
    <tr className="ask"><td colSpan={9}>
      <div className="askb">
        <span>{text}</span>
        <input autoFocus aria-label="دلیل" placeholder="دلیل (در تاریخچه ثبت می‌شود)" value={r} onChange={(e) => setR(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && r.trim()) onSubmit(r.trim()); if (e.key === "Escape") onCancel(); }} />
        <button className={`btn mini ${danger ? "danger" : ""}`} disabled={!r.trim()} onClick={() => onSubmit(r.trim())}>{action}</button>
        <button className="btn o mini" onClick={onCancel}>انصراف</button>
      </div>
    </td></tr>
  );
}

function ObjectiveRows({ o, people, goals, canEdit, canDefine, canDelete, adding, onAdd, onAdded, onCancelAdd, reload }: {
  o: WorkspaceObjective; people: Opt[]; goals: Opt[]; canEdit: boolean; canDefine: boolean; canDelete: boolean;
  adding: boolean; onAdd: () => void; onAdded: () => void; onCancelAdd: () => void; reload: () => void;
}) {
  const [err, setErr] = useState<string | null>(null);
  const [del, setDel] = useState(false);
  const patch = (body: object) => api(`/objectives/${o.id}`, { method: "PATCH", body }).then(reload).catch((e: Error) => setErr(e.message));
  return (
    <>
      <tr className="xo"><td colSpan={9}>
        <div className="xoh">
          <span className="no">هدف {fa(o.number)}</span>
          <div className="xot"><Cell value={o.title} label={`عنوان هدف ${o.number}`} disabled={!canDefine} onSave={(title) => title.trim() && patch({ title })} /></div>
          <div className="xoo"><span>مسئول هدف</span><Pick value={o.owner_id} options={people} empty="تعیین نشده" label="مسئول هدف" disabled={!canDefine} onSave={(owner_id) => patch({ owner_id })} /></div>
          {canDefine && <button className="xadd" onClick={onAdd}>+ نتیجهٔ کلیدی</button>}
          {canDelete && <button className="icon-b" aria-label={`حذف هدف ${o.number}`} title="حذف هدف (در تاریخچه می‌ماند)" onClick={() => setDel(true)}><Trash /></button>}
        </div>
        {err && <div className="bad tiny" role="alert">{err}</div>}
      </td></tr>
      {del && <ReasonRow text={`هدف «${o.title}» و ${fa(o.key_results.length)} نتیجهٔ کلیدی‌اش از فهرست حذف می‌شوند ولی در تاریخچه می‌مانند.`} action="حذف هدف" danger
        onCancel={() => setDel(false)}
        onSubmit={(reason) => api(`/objectives/${o.id}/archive`, { method: "POST", body: { reason } }).then(reload).catch((e: Error) => { setErr(e.message); setDel(false); })} />}
      {o.key_results.map((k) => <KRRow key={`${k.id}-${k.version}`} k={k} people={people} goals={goals} canEdit={canEdit} canDelete={canDelete} reload={reload} />)}
      {o.key_results.length === 0 && !adding && <tr className="empty"><td colSpan={9}>این هدف هنوز نتیجهٔ کلیدی ندارد.{canDefine && <> <button className="xadd" onClick={onAdd}>+ افزودن</button></>}</td></tr>}
      {adding && <NewKRRow objectiveId={o.id} people={people} goals={goals} onDone={onAdded} onCancel={onCancelAdd} />}
    </>
  );
}

function KRRow({ k, people, goals, canEdit, canDelete, reload }: {
  k: WorkspaceKR; people: Opt[]; goals: Opt[]; canEdit: boolean; canDelete: boolean; reload: () => void;
}) {
  const [err, setErr] = useState<string | null>(null);
  const [pendingTarget, setPendingTarget] = useState<number | null>(null);
  const [del, setDel] = useState(false);
  const [nonce, setNonce] = useState(0);  // bumps to put cells back to the saved value
  const milestone = k.kind === "milestone";
  const save = (body: object) =>
    api(`/key-results/${k.id}`, { method: "PATCH", body: { ...body, expected_version: k.version } }).then(reload)
      .catch((e: Error) => { setErr(e.message); setNonce((n) => n + 1); });
  const st = k.progress_status;
  return (
    <>
      <tr className={`krow${err ? " has-err" : ""}`} key={nonce}>
        <td><Link className="xcode num" to={`/krs/${k.id}`} title="تاریخچه و جزئیات">{code(k.code)}</Link></td>
        <td><Cell value={k.title} multiline label={`عنوان KR ${k.code}`} disabled={!canEdit} onSave={(title) => title.trim() && save({ title })} /></td>
        <td className="c">{milestone ? <span className="ro-n faint">—</span>
          : <Cell value={numText(k.baseline)} num label={`خط مبنای ${k.code}`} disabled={!canEdit} onSave={(v) => save({ baseline: parseNumber(v) })} />}</td>
        <td className="c">{milestone ? <span className="ro-n">۱۰۰٪</span>
          : <Cell value={numText(k.target)} num label={`هدف ${k.code}`} disabled={!canEdit} onSave={(v) => { const t = parseNumber(v); if (t !== undefined) setPendingTarget(t); }} />}</td>
        <td className="c"><span className="ro-n num">{k.progress_value == null ? "—" : fa(k.progress_value, 4)}</span></td>
        <td><span className="xp" title={k.progress_round ? `${STATUS_LABEL[st]} · پایش ${k.progress_round}${k.progress_live ? "، تا این لحظه" : ""}` : "ثبت‌نشده"}>
          <b className={`num ${k.progress == null ? "faint" : STATUS_CLASS[st]}`}>{pct(k.progress)}</b><small>{k.progress_round ?? ""}</small>
          <span className={`mb ${STATUS_CLASS[st]}`}><i style={{ "--w": `${Math.max(0, Math.min(100, k.progress ?? 0))}%` } as React.CSSProperties} /></span></span></td>
        <td><Pick value={k.owner_id} options={people.length ? people : k.owner_id ? [{ id: k.owner_id, label: k.owner_name ?? "" }] : []} empty="بدون مسئول" label={`مسئول ${k.code}`} disabled={!canEdit} onSave={(owner_id) => save({ owner_id })} /></td>
        <td><Pick value={k.goal?.id ?? null} options={goals} empty="—" label={`هدف کلان ${k.code}`} disabled={!canEdit} onSave={(strategic_goal_id) => save({ strategic_goal_id })} /></td>
        {(canEdit || canDelete) && <td className="xact">{canDelete && <button className="icon-b" aria-label={`حذف ${k.code}`} title="حذف (در تاریخچه می‌ماند)" onClick={() => setDel(true)}><Trash /></button>}</td>}
      </tr>
      {err && <tr className="ask"><td colSpan={9}><div className="askb bad" role="alert">{err} <button className="lnk" onClick={() => { setErr(null); reload(); }}>بستن</button></div></td></tr>}
      {pendingTarget !== null && <ReasonRow text={`هدف از ${fa(k.target)} به ${fa(pendingTarget)} تغییر می‌کند.`} action="ثبت تغییر"
        onCancel={() => { setPendingTarget(null); setNonce((n) => n + 1); }} onSubmit={(reason) => { save({ target: pendingTarget, reason }); setPendingTarget(null); }} />}
      {del && <ReasonRow text={`«${k.title}» از فهرست حذف می‌شود ولی در تاریخچه و گزارش‌ها می‌ماند.`} action="حذف" danger onCancel={() => setDel(false)}
        onSubmit={(reason) => api(`/key-results/${k.id}/archive`, { method: "POST", body: { reason } }).then(reload).catch((e: Error) => { setErr(e.message); setDel(false); })} />}
    </>
  );
}

function NewKRRow({ objectiveId, people, goals, onDone, onCancel }: { objectiveId: string; people: Opt[]; goals: Opt[]; onDone: () => void; onCancel: () => void }) {
  const [f, setF] = useState({ title: "", baseline: "", target: "", owner: "", goal: "" });
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = () => {
    const b = parseNumber(f.baseline), t = parseNumber(f.target);
    if (!f.title.trim()) return setErr("عنوان را بنویسید");
    if (b === undefined || t === undefined) return setErr("مبنا و هدف باید عدد باشند");
    const milestone = t == null;  // no numeric target: tracked as percent done
    if (!milestone && (b ?? 0) === t) return setErr("مبنا و هدف نباید برابر باشند");
    api(`/objectives/${objectiveId}/key-results`, { method: "POST", body: {
      title: f.title.trim(), kind: milestone ? "milestone" : "numeric", baseline: milestone ? null : b ?? 0, target: milestone ? null : t,
      owner_id: f.owner || null, strategic_goal_id: f.goal || null } }).then(onDone).catch((e: Error) => setErr(e.message));
  };
  const enter = (e: KeyboardEvent) => { if (e.key === "Enter") submit(); if (e.key === "Escape") onCancel(); };
  return (
    <>
      <tr className="newr">
        <td className="faint">جدید</td>
        <td><input autoFocus className="cell" aria-label="عنوان KR جدید" placeholder="عنوان نتیجهٔ کلیدی" value={f.title} onChange={set("title")} onKeyDown={enter} /></td>
        <td><input className="cell num" aria-label="خط مبنا" placeholder="۰" inputMode="decimal" value={f.baseline} onChange={set("baseline")} onKeyDown={enter} /></td>
        <td><input className="cell num" aria-label="هدف" placeholder="عدد" inputMode="decimal" value={f.target} onChange={set("target")} onKeyDown={enter} /></td>
        <td colSpan={2} className="faint tiny">بدون عدد هدف = درصدی (۰ تا ۱۰۰)</td>
        <td><select className="cell" aria-label="مسئول" value={f.owner} onChange={set("owner")}><option value="">بدون مسئول</option>{people.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select></td>
        <td><select className="cell" aria-label="هدف کلان" value={f.goal} onChange={set("goal")}><option value="">—</option>{goals.map((g) => <option key={g.id} value={g.id}>{g.label}</option>)}</select></td>
        <td><button className="btn mini" onClick={submit}>ثبت</button></td>
      </tr>
      <tr className="ask"><td colSpan={9}><div className="askb">
        {err ? <span className="bad" role="alert">{err}</span> : <span className="faint">Enter برای ثبت، Esc برای انصراف</span>}
        <button className="btn o mini" onClick={onCancel}>انصراف</button></div></td></tr>
    </>
  );
}

function NewObjectiveRow({ unitId, inputRef, onDone }: { unitId: string; inputRef: React.RefObject<HTMLInputElement>; onDone: () => void }) {
  const [t, setT] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const busy = useRef(false);
  const submit = () => {
    if (!t.trim() || busy.current) return;
    busy.current = true;
    api(`/units/${unitId}/objectives`, { method: "POST", body: { title: t.trim() } })
      .then(() => { setT(""); setErr(null); onDone(); }).catch((e: Error) => setErr(e.message)).finally(() => { busy.current = false; });
  };
  return (
    <tr className="xo newo"><td colSpan={9}>
      <div className="xoh">
        <span className="no">+ هدف</span>
        <input ref={inputRef} className="cell" aria-label="عنوان هدف جدید" placeholder="عنوان هدف جدید را بنویسید و Enter بزنید" value={t}
          onChange={(e) => setT(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
        <button className="btn mini" disabled={!t.trim()} onClick={submit}>افزودن هدف</button>
      </div>
      {err && <div className="bad tiny" role="alert">{err}</div>}
    </td></tr>
  );
}
