import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useGet } from "../../api/typed";
import type { RoleT } from "../../api/types";
import { fa } from "../../domain/format";
import { ErrorBox, Skeleton } from "../../ui/parts";
import { Field, Msg, Select, useAction } from "./fields";
import UnitOverrides from "./UnitOverrides";

const RES: Record<string, string> = { objective: "هدف", key_result: "نتیجهٔ کلیدی", review_value: "مقدار پایش", session: "جلسه", report: "گزارش", users: "کاربران" };
/** «تأیید» on «جلسه» is «برگزار شد»: freezing a round. */
const ACT: Record<string, string> = { view: "مشاهده", create: "ایجاد", edit: "ویرایش", delete: "حذف", approve: "تأیید" };
const SCOPE: Record<string, string> = { unit: "واحد خود", unit_tree: "واحد و زیرمجموعه", all: "همه" };
type Cell = "allow" | "deny" | undefined;
const next = (c: Cell): Cell => (c === "allow" ? "deny" : c === "deny" ? undefined : "allow"); // allow -> deny -> undefined

export default function RolesPanel() {
  const { data, error, loading, reload } = useGet("/api/v1/admin/roles");
  const [sel, setSel] = useState(0);
  const [draft, setDraft] = useState<RoleT | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [copyFrom, setCopyFrom] = useState("");
  const add = useAction();
  const role = data?.roles[sel];
  useEffect(() => { setDraft(role ? structuredClone(role) : null); setMsg(null); }, [role]);

  if (loading && !data) return <Skeleton />;
  if (error || !data || !draft) return <ErrorBox message={error ?? "نقشی نیست"} onRetry={reload} />;

  const dirty = JSON.stringify(draft.permissions) !== JSON.stringify(role!.permissions) || JSON.stringify(draft.scopes) !== JSON.stringify(role!.scopes);
  const toggle = (res: string, act: string) => {
    const d = structuredClone(draft);
    const n = next(d.permissions[res]?.[act]);
    d.permissions[res] ??= {};
    if (n) d.permissions[res][act] = n; else delete d.permissions[res][act];
    setDraft(d);
  };
  const save = async () => {
    try {
      await api(`/admin/roles/${draft.id}`, { method: "PUT", body: { permissions: draft.permissions, scopes: draft.scopes, expected_version: draft.version } });
      setMsg("ذخیره شد ✓"); reload();
    } catch (e) { setMsg((e as Error).message); }
  };

  return (
    <div className="two3">
      <div>{adding && (
        <div className="card"><Field label="نام نقش" value={newName} onChange={setNewName} /><Select label="کپی مجوزها از" value={copyFrom} onChange={setCopyFrom} empty="نقش خالی" options={data.roles.map((r) => [r.id, r.name])} />
          <Msg err={add.err} />
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}><button className="btn" disabled={!newName.trim() || add.busy} onClick={async () => { if (await add.run(() => api("/admin/roles", { method: "POST", body: { name: newName, copy_from_id: copyFrom || null } }))) { setAdding(false); setNewName(""); setCopyFrom(""); reload(); } }}>ساخت</button><button className="btn o" onClick={() => setAdding(false)}>انصراف</button></div></div>)}
      {data.roles.map((r, i) => (
        <div key={r.id} className={`rr ${i === sel ? "sel" : ""}`} role="button" tabIndex={0} onClick={() => setSel(i)} onKeyDown={(e) => e.key === "Enter" && setSel(i)}>
          <b>{r.name}</b><div className="faint tiny">{r.description}</div><div className="faint tiny num" style={{ marginTop: 2 }}>{fa(r.users)} کاربر</div>
        </div>))}
      {!adding && <button className="btn o" style={{ width: "100%", justifyContent: "center", marginTop: 8 }} onClick={() => setAdding(true)}>+ نقش جدید</button>}</div>
      <div>
        <div className="card"><h3>ماتریس مجوز · {draft.name} <span className="faint tiny" style={{ fontWeight: 400 }}>روی هر خانه کلیک کنید: مجاز ← ممنوع ← تعریف‌نشده</span></h3>
          <div className="pm head"><span>منبع</span><span>دامنه</span>{data.actions.map((a) => <span key={a} style={{ textAlign: "center" }}>{ACT[a]}</span>)}</div>
          {data.resources.map((res) => (
            <div className="pm" key={res}><b>{RES[res]}</b>
              <select aria-label={`دامنه ${RES[res]}`} value={draft.scopes[res]} onChange={(e) => setDraft({ ...draft, scopes: { ...draft.scopes, [res]: e.target.value } })}>
                {Object.entries(SCOPE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
              {data.actions.map((a) => { const c = draft.permissions[res]?.[a]; return (
                <button key={a} className={`pc ${c === "allow" ? "ok" : c === "deny" ? "none" : "faint"}`} aria-label={`${ACT[a]} ${RES[res]}: ${c === "allow" ? "مجاز" : c === "deny" ? "ممنوع" : "تعریف‌نشده"}`} onClick={() => toggle(res, a)}>
                  {c === "allow" ? "مجاز" : c === "deny" ? "ممنوع" : "—"}</button>); })}
            </div>))}
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 14 }}>
            <button className="btn" disabled={!dirty} onClick={save}>ذخیرهٔ تغییرات</button>
            {dirty && <button className="btn o" onClick={() => setDraft(structuredClone(role!))}>بازگردانی</button>}
            {msg && <span className={msg.includes("✓") ? "ok" : "bad"} role="status">{msg}</span>}
          </div>
        </div>
        <div className="note">قانون «ممنوع» همیشه بر «مجاز» غلبه می‌کند و «تعریف‌نشده» یعنی ممنوع. «تأیید» روی «جلسه» یعنی زدن «برگزار شد»؛ در نصب پیش‌فرض با مدیر سامانه است. تغییرات پس از ذخیره در گزارش ممیزی ثبت می‌شود.</div>
        {role && <UnitOverrides key={role.id} role={role} resources={data.resources} actions={data.actions} res={RES} act={ACT} />}
      </div>
    </div>
  );
}
