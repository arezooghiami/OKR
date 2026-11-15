import { useMemo, useState } from "react";
import { api } from "../../api/client";
import { useGet } from "../../api/typed";
import type { UnitAdmin } from "../../api/types";
import { fa } from "../../domain/format";
import { Empty, ErrorBox, Skeleton, Tag } from "../../ui/parts";
import { usePeek } from "../../ui/Peek";
import OrgImport from "./OrgImport";
import { Field, Msg, Section, Select, useAction } from "./fields";

type Types = { id: string; name: string; color_token: string }[];

function UnitForm({ unit, units, types, onDone }: { unit: UnitAdmin | null; units: UnitAdmin[]; types: Types; onDone: () => void }) {
  const [name, setName] = useState(unit?.name ?? "");
  const [code, setCode] = useState(unit?.code ?? "");
  const [type, setType] = useState(unit?.type_id ?? "");
  const [manager, setManager] = useState(unit?.manager_name ?? "");
  const [parent, setParent] = useState(unit?.parent_id ?? "");
  const a = useAction();
  const parents = units.filter((u) => u.id !== unit?.id && !u.archived);
  const submit = async () => {
    const body = { name, code: code || null, type_id: type || null, manager_name: manager || null };
    const done = await a.run(() => unit
      ? api(`/admin/units/${unit.id}`, { method: "PATCH", body: { ...body, move: (unit.parent_id ?? "") !== parent, parent_id: parent || null } })
      : api("/admin/units", { method: "POST", body: { ...body, parent_id: parent || null } }));
    if (done) onDone();
  };
  return (
    <>
      <h3>{unit ? unit.name : "واحد جدید"}</h3>
      <Field label="نام واحد" value={name} onChange={setName} placeholder="مثلاً: فناوری اطلاعات" />
      <div className="two"><Field label="کد (اختیاری)" value={code} onChange={setCode} dir="ltr" />
        <Select label="نوع واحد" value={type} onChange={setType} empty="—" options={types.map((t) => [t.id, t.name])} /></div>
      <Field label="نام مدیر (نمایشی)" value={manager} onChange={setManager} />
      <Select label="واحد والد" value={parent} onChange={setParent} empty="بدون والد (ریشه)" options={parents.map((u) => [u.id, u.name])} />
      <Msg err={a.err} />
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button className="btn" onClick={submit} disabled={a.busy || !name.trim()}>{unit ? "ذخیره" : "افزودن واحد"}</button>
        {unit && <button className="btn o" disabled={a.busy} onClick={async () => { if (await a.run(() => api(`/admin/units/${unit.id}`, { method: "PATCH", body: { archived: !unit.archived } }))) onDone(); }}>{unit.archived ? "بازگردانی" : "آرشیو"}</button>}
      </div>
    </>
  );
}

export default function UnitsPanel() {
  const units = useGet("/api/v1/admin/units");
  const types = useGet("/api/v1/admin/unit-types");
  const peek = usePeek();
  const [newType, setNewType] = useState("");
  const typeAct = useAction();
  const [imp, setImp] = useState(false);

  const tree = useMemo(() => {
    const by = new Map<string | null, UnitAdmin[]>();
    (units.data ?? []).forEach((u) => by.set(u.parent_id, [...(by.get(u.parent_id) ?? []), u]));
    const out: { u: UnitAdmin; depth: number }[] = [];
    const walk = (p: string | null, depth: number) => (by.get(p) ?? []).forEach((u) => { out.push({ u, depth }); walk(u.id, depth + 1); });
    walk(null, 0);
    return out;
  }, [units.data]);

  if ((units.loading && !units.data) || (types.loading && !types.data)) return <Skeleton />;
  if (units.error || types.error) return <ErrorBox message={(units.error ?? types.error)!} onRetry={() => { units.reload(); types.reload(); }} />;
  const list = units.data ?? [], tlist = types.data ?? [];
  const open = (u: UnitAdmin | null) => peek.open(<UnitForm key={u?.id ?? "new"} unit={u} units={list} types={tlist} onDone={() => { peek.close(); units.reload(); }} />);

  return (
    <>
      <div className="sec"><h2>واحدها <span className="num">{fa(list.length)}</span></h2><div style={{ display: "flex", gap: 8 }}><button className="btn o" aria-expanded={imp} onClick={() => setImp(!imp)}>ورود از اکسل</button><button className="btn" onClick={() => open(null)}>+ واحد جدید</button></div></div>
      {imp && <OrgImport onClose={() => setImp(false)} onDone={() => { units.reload(); types.reload(); }} />}
      {list.length === 0 && <Empty title="هنوز واحدی تعریف نشده است" hint="با «واحد جدید» شروع کنید یا همهٔ واحدها را یک‌جا «از اکسل» وارد کنید؛ اولین واحد معمولاً ریشهٔ سازمان است." />}
      {tree.map(({ u, depth }) => (
        <div key={u.id} className="row" role="button" tabIndex={0} style={{ marginInlineStart: depth * 22, gridTemplateColumns: "1.4fr 1fr 110px", opacity: u.archived ? 0.55 : 1 }}
          onClick={() => open(u)} onKeyDown={(e) => e.key === "Enter" && open(u)}>
          <div><div className="nm">{u.name}{u.archived && " (آرشیو)"}</div><div className="faint tiny">{u.manager_name ? `مدیر: ${u.manager_name}` : ""}{u.code ? ` · ${u.code}` : ""}</div></div>
          <span />
          {u.type ? <Tag color={tlist.find((t) => t.id === u.type_id)?.color_token ?? "--g0"}>{u.type}</Tag> : <span className="faint tiny">بدون نوع</span>}
        </div>
      ))}
      <div style={{ marginTop: 26 }}>
        <Section title="انواع واحد">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>{tlist.map((t) => <Tag key={t.id} color={t.color_token}>{t.name}</Tag>)}</div>
          <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
            <div style={{ flex: 1 }}><Field label="نوع جدید" value={newType} onChange={setNewType} placeholder="مثلاً: دپارتمان" /></div>
            <button className="btn o" disabled={!newType.trim() || typeAct.busy} onClick={async () => { if (await typeAct.run(() => api("/admin/unit-types", { method: "POST", body: { name: newType } }))) { setNewType(""); types.reload(); } }}>افزودن</button>
          </div>
          <Msg err={typeAct.err} />
        </Section>
      </div>
    </>
  );
}
