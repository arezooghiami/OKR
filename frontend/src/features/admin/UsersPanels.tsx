import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import { useGet } from "../../api/typed";
import type { AdminUser, OrgNode, SimResult } from "../../api/types";
import { fa } from "../../domain/format";
import { ErrorBox, Skeleton, Tag } from "../../ui/parts";
import { usePeek } from "../../ui/Peek";
import OrgImport from "./OrgImport";
import { Field, Msg, Select, useAction } from "./fields";

function randomPassword(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";
  const bytes = crypto.getRandomValues(new Uint32Array(12));
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

function UserForm({ user, onDone }: { user: AdminUser | null; onDone: () => void }) {
  const roles = useGet("/api/v1/admin/roles");
  const units = useGet("/api/v1/admin/units");
  const [username, setUsername] = useState(user?.username ?? "");
  const [name, setName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [password, setPassword] = useState("");
  const [admin, setAdmin] = useState(user?.is_system_admin ?? false);
  const [active, setActive] = useState(user?.active ?? true);
  const [role, setRole] = useState("");
  const [unit, setUnit] = useState("");
  const [current, setCurrent] = useState<AdminUser | null>(user);
  const a = useAction();
  const m = useAction();

  const save = async () => {
    const ok = await a.run(async () => {
      if (!user) {
        const created = await api<AdminUser>("/admin/users", { method: "POST", body: { username, full_name: name, email: email || null, password, is_system_admin: admin } });
        setCurrent(created);
      } else {
        await api(`/admin/users/${user.id}`, { method: "PATCH", body: { full_name: name, email: email || null, is_active: active, is_system_admin: admin, password: password || undefined } });
      }
    }, user ? "ذخیره شد" : "کاربر ساخته شد؛ حالا نقش بدهید");
    if (ok && user) onDone();
  };
  const grant = async () => {
    if (!current) return;
    await m.run(async () => setCurrent(await api<AdminUser>(`/admin/users/${current.id}/memberships`, { method: "POST", body: { role_id: role, unit_id: unit || null } })));
  };
  const revoke = async (id: string) => m.run(async () => setCurrent(await api<AdminUser>(`/admin/memberships/${id}`, { method: "DELETE" })));

  return (
    <>
      <h3>{user ? user.full_name : "کاربر جدید"}</h3>
      <Field label="نام کاربری (انگلیسی)" value={username} onChange={setUsername} dir="ltr" disabled={!!user} />
      <Field label="نام کامل" value={name} onChange={setName} />
      <Field label="ایمیل (اختیاری)" value={email} onChange={setEmail} dir="ltr" />
      <div className="f"><label>{user ? "رمز جدید (خالی = بدون تغییر)" : "رمز عبور (دست‌کم ۸ نویسه)"}
        <div style={{ display: "flex", gap: 6 }}>
          <input value={password} onChange={(e) => setPassword(e.target.value)} dir="ltr" autoComplete="new-password" style={{ flex: 1 }} />
          <button type="button" className="btn o" onClick={() => setPassword(randomPassword())}>ساخت رمز</button></div></label>
        {password && <span className="faint tiny">این رمز را همین الان یادداشت کنید؛ بعد از ذخیره قابل مشاهده نیست.</span>}</div>
      <label style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center" }}><input type="checkbox" checked={admin} onChange={(e) => setAdmin(e.target.checked)} /> سوپر ادمین (دسترسی کامل)</label>
      {user && <label style={{ display: "flex", gap: 8, marginTop: 6, alignItems: "center" }}><input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> فعال</label>}
      <Msg err={a.err} ok={a.ok} />
      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <button className="btn" disabled={a.busy || !name.trim() || (!user && (!username || password.length < 8))} onClick={save}>{user ? "ذخیره" : "ساخت کاربر"}</button>
        <button className="btn o" onClick={onDone}>بستن</button>
      </div>

      {current && (
        <>
          <div className="sec" style={{ marginTop: 22 }}><h2>نقش‌ها و واحدها</h2></div>
          {current.memberships.length === 0 && <div className="faint tiny">هنوز نقشی ندارد؛ بدون نقش به هیچ چیز دسترسی ندارد.</div>}
          {current.memberships.map((x) => (
            <div key={x.id} className="kr"><Tag color="--ac">{x.role}</Tag><span style={{ flex: 1 }}>{x.unit ?? "کل سازمان"}</span>
              <button className="lnk" onClick={() => revoke(x.id)} aria-label={`حذف نقش ${x.role}`}>حذف</button></div>
          ))}
          <div className="two" style={{ marginTop: 10 }}>
            <Select label="نقش" value={role} onChange={setRole} empty="انتخاب…" options={(roles.data?.roles ?? []).map((r) => [r.id, r.name])} />
            <Select label="واحد" value={unit} onChange={setUnit} empty="کل سازمان" options={(units.data ?? []).filter((u) => !u.archived).map((u) => [u.id, u.name])} />
          </div>
          <Msg err={m.err} />
          <button className="btn o" style={{ marginTop: 10 }} disabled={!role || m.busy} onClick={grant}>+ افزودن نقش</button>
        </>
      )}
    </>
  );
}

export function UsersPanel() {
  const [q, setQ] = useState("");
  const [dq, setDq] = useState("");
  useEffect(() => { const t = setTimeout(() => setDq(q), 250); return () => clearTimeout(t); }, [q]);
  const { data, error, loading, reload } = useGet("/api/v1/admin/users", { query: { q: dq } });
  const peek = usePeek();
  const open = (u: AdminUser | null) => peek.open(<UserForm key={u?.id ?? "new"} user={u} onDone={() => { peek.close(); reload(); }} />);
  const [imp, setImp] = useState(false);
  return (
    <>
      <div className="sec"><h2>کاربران <span className="num">{fa(data?.length ?? 0)}</span></h2>
        <div style={{ display: "flex", gap: 8 }}><input className="srch" placeholder="جستجوی نام…" aria-label="جستجو" value={q} onChange={(e) => setQ(e.target.value)} /><button className="btn o" aria-expanded={imp} onClick={() => setImp(!imp)}>ورود از اکسل</button><button className="btn" onClick={() => open(null)}>+ کاربر جدید</button></div></div>
      {imp && <OrgImport usersFirst onClose={() => setImp(false)} onDone={reload} />}
      {loading && !data && <Skeleton />}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {data?.map((u) => (
        <div className="mrow urow" key={u.id} role="button" tabIndex={0} style={{ cursor: "pointer", opacity: u.active ? 1 : 0.55 }} onClick={() => open(u)} onKeyDown={(e) => e.key === "Enter" && open(u)}>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}><div className="av" style={{ width: 30, height: 30 }}>{u.full_name[0]}</div>
            <div><b>{u.full_name}</b><div className="faint tiny" dir="ltr" style={{ textAlign: "start" }}>{u.username}</div></div></div>
          <span style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>{u.memberships.map((m) => <Tag key={m.id} color="--ac">{m.role}{m.unit ? ` · ${m.unit}` : ""}</Tag>)}{u.memberships.length === 0 && <span className="risk tiny">بدون نقش</span>}</span>
          <span className="faint tiny">{u.is_system_admin ? "سوپر ادمین" : u.source === "ldap" ? "AD" : "محلی"}</span>
          <span className={`tiny ${u.active ? "ok" : "bad"}`} style={{ fontWeight: 600 }}>{u.active ? "● فعال" : "▲ غیرفعال"}</span>
        </div>))}
      {data?.length === 0 && !loading && <div className="empty"><b>کاربری پیدا نشد</b></div>}
    </>
  );
}

const ACT: [string, string][] = [["view", "مشاهده"], ["create", "ایجاد"], ["edit", "ویرایش"], ["delete", "حذف"], ["approve", "تأیید"]];
const RES: [string, string][] = [["objective", "هدف"], ["key_result", "نتیجه کلیدی"], ["review_value", "مقدار پایش"], ["session", "جلسه"], ["report", "گزارش"], ["users", "کاربران"]];
const flat = (ns: OrgNode[]): OrgNode[] => ns.flatMap((n) => [n, ...flat(n.children)]);

export function SimulatorPanel() {
  const users = useGet("/api/v1/admin/users");
  const org = useGet("/api/v1/org/tree");
  const units = useMemo(() => flat(org.data?.units ?? []), [org.data]);
  const [f, setF] = useState({ user_id: "", action: "edit", resource: "review_value", unit_id: "" });
  const [res, setRes] = useState<SimResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const user = f.user_id || users.data?.[0]?.id || "";
  const unit = f.unit_id || units[0]?.id || "";

  useEffect(() => {
    if (!user) return;
    setErr(null);
    api<SimResult>("/admin/access/simulate", { method: "POST", body: { user_id: user, action: f.action, resource: f.resource, unit_id: unit || null } })
      .then(setRes).catch((e: Error) => setErr(e.message));
  }, [user, unit, f.action, f.resource]);

  return (
    <div className="two3">
      <div className="card"><h3>پرسش</h3>
        <Select label="کاربر" value={user} onChange={(v) => setF({ ...f, user_id: v })} options={(users.data ?? []).map((u) => [u.id, `${u.full_name} · ${u.memberships.map((m) => m.role).join("، ") || "بدون نقش"}`])} />
        <Select label="عمل" value={f.action} onChange={(v) => setF({ ...f, action: v })} options={ACT} />
        <Select label="منبع" value={f.resource} onChange={(v) => setF({ ...f, resource: v })} options={RES} />
        <Select label="واحد هدف" value={unit} onChange={(v) => setF({ ...f, unit_id: v })} options={units.map((u) => [u.id, u.name])} />
      </div>
      <div>
        {err && <ErrorBox message={err} />}
        {res && <div className="card" style={{ borderColor: res.allowed ? "var(--ok)" : "var(--bad)" }} role="status">
          <div className={res.allowed ? "ok" : "bad"} style={{ fontSize: "var(--fs-2xl)", fontWeight: 700 }}>{res.allowed ? "مجاز" : "ممنوع"}</div>
          <div className="mut" style={{ marginTop: 6, lineHeight: 2 }}>{res.reason}</div>
          <div className="frm" style={{ marginTop: 12 }}>rule={res.rule}</div></div>}
      </div>
    </div>
  );
}
