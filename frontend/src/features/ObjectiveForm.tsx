import { useState } from "react";
import { api } from "../api/client";
import { useGet } from "../api/typed";
import { fa } from "../domain/format";

export interface ObjectiveDraft { id: string; number: number; title: string; description: string | null; owner_id: string | null; definition_version?: number }

/**
 * Create or edit an objective of a unit, with its متصدی (owner). Creating opens version 1; every later edit
 * creates a new version. `sessionId` tags the edit with the session it was made in.
 */
export default function ObjectiveForm({ unitId, unitName, objective, sessionId, onDone }: {
  unitId: string; unitName: string; objective?: ObjectiveDraft | null; sessionId?: string | null; onDone: () => void;
}) {
  const members = useGet("/api/v1/units/{unit_id}/members", { unit_id: unitId });
  const isNew = !objective;
  const [title, setTitle] = useState(objective?.title ?? "");
  const [description, setDescription] = useState(objective?.description ?? "");
  const [owner, setOwner] = useState(objective?.owner_id ?? "");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!title.trim()) return setErr("عنوان هدف را وارد کنید");
    setBusy(true); setErr(null);
    const body = { title: title.trim(), description: description.trim() || null, owner_id: owner || null };
    try {
      if (isNew) await api(`/units/${unitId}/objectives`, { method: "POST", body });
      else await api(`/objectives/${objective.id}`, { method: "PATCH", body: { ...body, session_id: sessionId ?? null } });
      onDone();
    } catch (e) { setErr((e as Error).message); setBusy(false); }
  };

  return (
    <>
      <div className="faint tiny">{unitName}</div>
      <h3>{isNew ? "هدف جدید" : `ویرایش هدف ${fa(objective.number)}`}</h3>
      {!isNew && objective.definition_version && <div style={{ marginTop: 4 }}><span className="lvl">نسخهٔ تعریف {fa(objective.definition_version)}</span></div>}
      <div className="f"><label htmlFor="ot">عنوان هدف</label><input id="ot" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus placeholder="مثلاً: تجربهٔ مشتری را متحول کنیم" /></div>
      <div className="f"><label htmlFor="od">توضیحات</label><textarea id="od" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="چرا این هدف مهم است؟" /></div>
      <div className="f"><label htmlFor="oo">متصدی هدف</label>
        <select id="oo" value={owner} onChange={(e) => setOwner(e.target.value)}>
          <option value="">— بدون متصدی —</option>
          {(members.data ?? []).map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
        </select>
        <span className="faint tiny">کسی که پیگیر کل این هدف است و در جلسه دربارهٔ آن پاسخ می‌دهد.</span>
        {members.data && members.data.length === 0 && <span className="faint tiny">این واحد هنوز عضوی ندارد؛ مدیر سیستم باید کاربران را به واحد اضافه کند.</span>}
      </div>
      {!isNew && <div className="note">ذخیره، نسخهٔ تازه‌ای از تعریف می‌سازد و نسخهٔ قبلی در تاریخچه می‌ماند.</div>}
      {err && <div className="note err-box" role="alert">{err}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button className="btn" disabled={busy || !title.trim()} onClick={submit}>{busy ? "…" : isNew ? "افزودن هدف" : "ذخیره"}</button>
        <button className="btn o" onClick={onDone}>انصراف</button>
      </div>
    </>
  );
}
