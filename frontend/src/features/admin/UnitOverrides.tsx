import { useMemo, useState } from "react";
import { api } from "../../api/client";
import { useGet } from "../../api/typed";
import type { OrgNode, RoleT } from "../../api/types";
import { fa } from "../../domain/format";
import { ErrorBox } from "../../ui/parts";

type Eff = "allow" | "deny";
type Perms = Record<string, Record<string, Eff>>;
const flat = (ns: OrgNode[]): OrgNode[] => ns.flatMap((n) => [n, ...flat(n.children)]);
const next = (c: Eff | undefined): Eff | undefined => (c === undefined ? "allow" : c === "allow" ? "deny" : undefined);

/** Per-unit exceptions to one role (docs/07 §7): «in Sales, unit experts may edit but not delete». Only the
 *  super admin sees this. A cell left as «مثل نقش» follows the role's matrix; the scope never widens. */
export default function UnitOverrides({ role, resources, actions, res, act }: {
  role: RoleT; resources: string[]; actions: string[]; res: Record<string, string>; act: Record<string, string>;
}) {
  const list = useGet("/api/v1/admin/roles/{role_id}/overrides", { role_id: role.id });
  const org = useGet("/api/v1/org/tree");
  const units = useMemo(() => flat(org.data?.units ?? []), [org.data]);
  const [unit, setUnit] = useState("");
  const [draft, setDraft] = useState<Perms>({});
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const open = (unitId: string) => {
    setUnit(unitId);
    setMsg(null);
    setDraft(structuredClone((list.data ?? []).find((o) => o.unit_id === unitId)?.permissions ?? {}) as Perms);
  };
  const flip = (r: string, a: string) => {
    const d = structuredClone(draft);
    const n = next(d[r]?.[a]);
    d[r] ??= {};
    if (n) d[r][a] = n; else delete d[r][a];
    if (Object.keys(d[r]).length === 0) delete d[r];
    setDraft(d);
  };
  const save = async (perms: Perms, unitId = unit) => {
    setBusy(true); setMsg(null);
    try {
      await api(`/admin/roles/${role.id}/overrides/${unitId}`, { method: "PUT", body: { permissions: perms } });
      setMsg({ ok: true, text: Object.keys(perms).length ? "استثنا ذخیره شد ✓" : "استثنا حذف شد ✓" });
      list.reload();
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }); } finally { setBusy(false); }
  };
  const summary = (p: Perms) => Object.entries(p).flatMap(([r, acts]) => Object.entries(acts).map(([a, e]) => `${act[a]} ${res[r]}: ${e === "allow" ? "مجاز" : "ممنوع"}`));
  const unitName = units.find((u) => u.id === unit)?.name;

  return (
    <div className="card">
      <h3>استثنای واحدها · {role.name}</h3>
      <p className="mut tiny" style={{ marginBottom: 8 }}>
        برای یک واحد مشخص، دسترسی این نقش را عوض کنید. مثلاً در یک واحد کارشناس‌ها ویرایش کنند ولی حذف نه. خانه‌ای که «مثل نقش» بماند از ماتریس بالا پیروی می‌کند. هر تغییر در گزارش ممیزی ثبت می‌شود.
      </p>
      {list.error && <ErrorBox message={list.error} onRetry={list.reload} />}
      {(list.data ?? []).length === 0 && !unit && <p className="faint tiny">این نقش در هیچ واحدی استثنا ندارد.</p>}
      {(list.data ?? []).map((o) => (
        <div key={o.unit_id} className="ovr">
          <div><b>{o.unit}</b><div className="faint tiny">{summary(o.permissions as Perms).join("، ")}</div></div>
          <button className="btn o mini" onClick={() => open(o.unit_id)}>ویرایش</button>
          <button className="btn o mini" disabled={busy} onClick={() => save({}, o.unit_id)}>حذف استثنا</button>
        </div>
      ))}
      <div className="f" style={{ maxWidth: 360 }}>
        <label htmlFor="ovr-unit">{unit ? "واحد" : "استثنای تازه برای واحد"}</label>
        <select id="ovr-unit" value={unit} onChange={(e) => open(e.target.value)}>
          <option value="">انتخاب واحد…</option>
          {units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </select>
      </div>
      {unit && (
        <>
          <div className="pm head" style={{ marginTop: 12 }}><span>منبع</span><span />{actions.map((a) => <span key={a} style={{ textAlign: "center" }}>{act[a]}</span>)}</div>
          {resources.map((r) => (
            <div className="pm" key={r}><b>{res[r]}</b>
              <span />
              {actions.map((a) => {
                const c = draft[r]?.[a];
                const base = role.permissions[r]?.[a];
                return (
                  <button key={a} className={`pc ${c === "allow" ? "ok" : c === "deny" ? "none" : "faint"}`}
                    aria-label={`${act[a]} ${res[r]} در ${unitName}: ${c === "allow" ? "مجاز" : c === "deny" ? "ممنوع" : "مثل نقش"}`} onClick={() => flip(r, a)}>
                    {c === "allow" ? "مجاز" : c === "deny" ? "ممنوع" : base === "allow" ? "مثل نقش ✓" : "مثل نقش"}
                  </button>
                );
              })}
            </div>
          ))}
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
            <button className="btn" disabled={busy} onClick={() => save(draft)}>ذخیرهٔ استثنای «{unitName}»</button>
            <button className="btn o" onClick={() => setUnit("")}>بستن</button>
            <span className="faint tiny">{fa(summary(draft).length)} خانه با ماتریس نقش فرق دارد</span>
          </div>
        </>
      )}
      {msg && <div className={msg.ok ? "ok" : "bad"} role="status" style={{ marginTop: 8 }}>{msg.text}</div>}
    </div>
  );
}
