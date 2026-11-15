import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useGet } from "../api/typed";
import type { GoalRef } from "../api/types";
import { fa, parseNumber } from "../domain/format";

const numStr = (n: number | null | undefined) => (n == null ? "" : fa(n, 4));

/** The fields of a KR the form edits (a session row or a workspace row both fit). */
export interface KRDraft {
  id: string; code: string; title: string; description: string | null; baseline: number | null; target: number | null;
  owner_id: string | null; goal: GoalRef | null; definition_version: number;
}

/** Where the form is opened from: the unit, its objectives, and (optionally) the session the edit belongs to. */
export interface KRContext { unitId: string; canEdit: boolean; objectives: { id: string; title: string }[]; sessionId?: string | null }

/** Create or edit a KR definition. Editing creates a new version; changing the target requires a reason. */
export default function KRForm({ ctx, kr, objectiveId, onDone }: { ctx: KRContext; kr: KRDraft | null; objectiveId?: string; onDone: () => void }) {
  const session = { id: ctx.sessionId ?? null, objectives: ctx.objectives, can_edit_definitions: ctx.canEdit };
  const goals = useGet("/api/v1/goals");
  const members = useGet("/api/v1/units/{unit_id}/members", ctx.canEdit ? { unit_id: ctx.unitId } : null);
  const [owner, setOwner] = useState(kr?.owner_id ?? "");
  const isNew = kr === null;
  const [title, setTitle] = useState(kr?.title ?? "");
  const [desc, setDesc] = useState(kr?.description ?? "");
  const [base, setBase] = useState(numStr(kr?.baseline));
  const [target, setTarget] = useState(numStr(kr?.target));
  const [goal, setGoal] = useState(kr?.goal?.id ?? "");
  const [objective, setObjective] = useState(objectiveId ?? session.objectives[0]?.id ?? "");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const targetChanged = !isNew && parseNumber(target) !== kr.target;
  const readOnly = !session.can_edit_definitions;

  const submit = async () => {
    setErr(null);
    const b = parseNumber(base), t = parseNumber(target);
    if (!title.trim()) return setErr("عنوان را وارد کنید");
    if (b === undefined || t === undefined) return setErr("مبنا و هدف باید عدد باشند");
    if (b !== null && b === t) return setErr("مبنا و هدف نباید برابر باشند");
    if (targetChanged && !reason.trim()) return setErr("دلیل تغییر هدف الزامی است");
    setBusy(true);
    try {
      if (isNew) {
        await api(`/objectives/${objective}/key-results`, { method: "POST", body: { title, description: desc || null, baseline: b, target: t, strategic_goal_id: goal || null, owner_id: owner || null, session_id: session.id } });
      } else {
        await api(`/key-results/${kr.id}`, { method: "PATCH", body: { title, description: desc || null, baseline: b, target: t, strategic_goal_id: goal || null, owner_id: owner || null, reason: reason || null, session_id: session.id } });
      }
      onDone();
    } catch (e) { setErr((e as Error).message); setBusy(false); }
  };

  return (
    <>
      <div className="faint tiny">{isNew ? "نتیجهٔ کلیدی جدید" : `نتیجهٔ کلیدی ${kr.code.split(".").map((p) => fa(p)).join(".")}`}</div>
      <h3>{isNew ? "نتیجهٔ کلیدی جدید" : kr.title}</h3>
      {!isNew && <div style={{ marginTop: 4 }}><span className="lvl">نسخهٔ تعریف {fa(kr.definition_version)}</span> <Link className="lnk tiny" to={`/krs/${kr.id}`}>تاریخچه و جزئیات</Link></div>}
      {readOnly && <div className="note">شما اجازهٔ ویرایش تعریف را ندارید.</div>}
      {isNew && <div className="f"><label htmlFor="ob">هدف</label><select id="ob" value={objective} onChange={(e) => setObjective(e.target.value)}>{session.objectives.map((o) => <option key={o.id} value={o.id}>{o.title}</option>)}</select></div>}
      <div className="f"><label htmlFor="t">عنوان</label><input id="t" value={title} disabled={readOnly} onChange={(e) => setTitle(e.target.value)} placeholder="مثلاً: کاهش میانگین زمان رفع تیکت‌ها" /></div>
      <div className="f"><label htmlFor="d">توضیحات</label><textarea id="d" value={desc} disabled={readOnly} onChange={(e) => setDesc(e.target.value)} /></div>
      <div className="two">
        <div className="f"><label htmlFor="b">خط مبنا</label><input id="b" className="num" inputMode="decimal" value={base} disabled={readOnly} onChange={(e) => setBase(e.target.value)} /></div>
        <div className="f"><label htmlFor="g">هدف</label><input id="g" className="num" inputMode="decimal" value={target} disabled={readOnly} onChange={(e) => setTarget(e.target.value)} /></div>
      </div>
      {targetChanged && <div className="f"><label htmlFor="r">دلیل تغییر هدف (الزامی)</label><input id="r" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="چرا هدف تغییر کرد؟" /></div>}
      <div className="f"><label htmlFor="gs">هدف کسب‌وکاری</label>
        <select id="gs" value={goal} disabled={readOnly} onChange={(e) => setGoal(e.target.value)}><option value="">—</option>{(goals.data ?? []).map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}</select></div>
      <div className="f"><label htmlFor="ow">مسئول</label>
        <select id="ow" value={owner} disabled={readOnly} onChange={(e) => setOwner(e.target.value)}><option value="">— بدون مسئول —</option>{(members.data ?? []).map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}</select>
        {members.data && members.data.length === 0 && <span className="faint tiny">این واحد هنوز عضوی ندارد؛ در مدیریت ← کاربران، کاربر را به واحد اضافه کنید.</span>}</div>
      {err && <div className="note err-box" role="alert">{err}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
        <button className="btn" onClick={submit} disabled={busy || readOnly}>{busy ? "…" : "ذخیره"}</button>
        <button className="btn o" onClick={onDone}>انصراف</button>
      </div>
    </>
  );
}
