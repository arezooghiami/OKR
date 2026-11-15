import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useGet } from "../api/typed";
import type { KRRow, SessionHead, SessionPage as SessionT } from "../api/types";
import { percent, statusFor, STATUS_CLASS, STATUS_LABEL } from "../domain/calc";
import { fa, jDateTime, parseNumber, pct } from "../domain/format";
import { Crumb, ErrorBox, Pie, Skeleton, Tag } from "../ui/parts";
import { usePeek } from "../ui/Peek";
import ExportButton from "../ui/ExportButton";
import KRForm from "./KRForm";
import ObjectiveForm from "./ObjectiveForm";

type Saving = "idle" | "saving" | "saved" | "error";

export default function SessionPage() {
  const { id } = useParams();
  const { me } = useAuth();
  const { data, error, loading, reload } = useGet("/api/v1/sessions/{session_id}", id ? { session_id: id } : null);
  const sessions = useGet("/api/v1/sessions/{session_id}/siblings", id ? { session_id: id } : null);
  const [view, setView] = useState<"cur" | "all">("cur");
  const [saving, setSaving] = useState<Saving>("idle");
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [confirmHold, setConfirmHold] = useState(false);
  const [holdErr, setHoldErr] = useState<string | null>(null);
  const peek = usePeek();
  const [selected, setSelected] = useState(-1);
  const rowsRef = useRef<HTMLDivElement>(null);

  const flat = useMemo(() => data?.objectives.flatMap((o) => o.key_results) ?? [], [data]);

  const openForm = useCallback((kr: KRRow | null) => {
    if (!data) return;
    const ctx = { unitId: data.unit_id, canEdit: data.can_edit_definitions, sessionId: data.id, objectives: data.objectives };
    peek.open(<KRForm key={kr?.id ?? "new"} ctx={ctx} kr={kr} onDone={() => { peek.close(); reload(); }} />);
  }, [data, peek, reload]);

  // J/K move, Enter edits the value, Space opens the definition (desktop shortcuts; every action also has a click path)
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = (e.target as HTMLElement).tagName;
      if (t === "INPUT" || t === "TEXTAREA" || t === "SELECT" || e.ctrlKey || e.metaKey) return;
      if (e.key === "j" || e.key === "ArrowDown") { setSelected((s) => Math.min(flat.length - 1, s + 1)); e.preventDefault(); }
      else if (e.key === "k" || e.key === "ArrowUp") { setSelected((s) => Math.max(0, s - 1)); e.preventDefault(); }
      else if (e.key === "Enter" && selected >= 0) { rowsRef.current?.querySelectorAll<HTMLInputElement>("input.inp")[selected]?.focus(); e.preventDefault(); }
      else if (e.key === " " && selected >= 0) { openForm(flat[selected]); e.preventDefault(); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [flat, selected, openForm]);

  if (loading && !data) return <Skeleton rows={6} />;
  if (error || !data) return <ErrorBox message={error ?? "یافت نشد"} onRetry={reload} />;

  const hold = async () => {
    setHoldErr(null);
    try { await api(`/sessions/${data.id}/hold`, { method: "POST", body: {} }); setConfirmHold(false); reload(); sessions.reload(); }
    catch (e) { setHoldErr((e as Error).message); setConfirmHold(false); }
  };

  const readOnlyWhy = !data.can_edit_values ? (data.entry_blocker ?? "شما اجازهٔ ثبت مقدار در این جلسه را ندارید") : null;

  return (
    <>
      <Crumb items={[data.unit_name, `جلسهٔ ${data.time_point}`]} />
      <div className="mh">
        <div>
          <h1>{data.time_point} · {data.unit_name}</h1>
          <div className="mut" style={{ marginTop: 2 }}>
            {data.status === "unscheduled" ? <span className="risk">زمان جلسه تعیین نشده</span> : <>{jDateTime(data.held_at ?? data.scheduled_at)}{data.place && `، ${data.place}`}{data.status === "held" && " · برگزار شد"}</>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <ExportButton path={`/units/${data.unit_id}/export.xlsx`} />
          {data.status === "scheduled" && me?.is_system_admin && (confirmHold
            ? <><button className="btn" onClick={hold}>تأیید: جلسه برگزار شد</button><button className="btn o" onClick={() => setConfirmHold(false)}>انصراف</button></>
            : <button className="btn o" onClick={() => setConfirmHold(true)}>برگزار شد ✓</button>)}
          {data.can_edit_definitions && <button className="btn o" onClick={() => peek.open(<ObjectiveForm key="obj" unitId={data.unit_id} unitName={data.unit_name} sessionId={data.id} onDone={() => { peek.close(); reload(); }} />)}>+ هدف جدید</button>}
          {data.can_edit_definitions && data.objectives.length > 0 && <button className="btn" onClick={() => openForm(null)}>+ KR جدید</button>}
        </div>
      </div>
      {holdErr && <div className="warnbar" role="alert">{holdErr}</div>}

      <div className="steps" aria-label="مراحل چرخه">
        {(sessions.data ?? []).map((s) => (
          <span key={s.id} className={s.id === data.id ? "cur" : s.status === "held" ? "dn" : ""}>
            {s.id === data.id ? <>{s.time_point} · {s.status === "held" ? "برگزار شد" : "جاری"}</> : <Link to={`/sessions/${s.id}`}>{s.time_point}{s.status === "held" ? " ✓" : ""}</Link>}
          </span>
        ))}
      </div>

      <div className="toolbar">
        <div className="seg"><button className={view === "cur" ? "on" : ""} onClick={() => setView("cur")}>پایش جاری</button><button className={view === "all" ? "on" : ""} onClick={() => setView("all")}>همهٔ پایش‌ها</button></div>
        <span className="faint tiny">{fa(flat.length)} نتیجه کلیدی در {fa(data.objectives.length)} هدف{data.score != null && ` · امتیاز جلسه ${pct(data.score)}${data.status === "held" ? "" : " (تا این لحظه؛ پس از «برگزار شد» ثابت می‌شود)"}`}</span>
      </div>
      {readOnlyWhy && view === "cur" && <div className="note" role="status">{readOnlyWhy}</div>}

      {view === "all" ? <AllRounds sessions={sessions.data ?? []} /> : (
        <div ref={rowsRef} className={data.objectives.length ? "sheet" : undefined}>
          {data.objectives.length === 0 && <div className="empty"><b>هنوز هدفی تعریف نشده است</b></div>}
          {data.objectives.map((o) => (
            <section className="ob" key={o.id}>
              <div className="og"><span className="no">هدف {fa(o.number)}</span><b>{o.title}</b>
                <span className={`tiny ${o.owner_name ? "mut" : "risk"}`}>{o.owner_name ? `متصدی: ${o.owner_name}` : "بدون متصدی"}</span>
                {data.can_edit_definitions && <button className="lnk tiny" onClick={() => peek.open(<ObjectiveForm key={o.id} unitId={data.unit_id} unitName={data.unit_name} sessionId={data.id} objective={o} onDone={() => { peek.close(); reload(); }} />)}>ویرایش</button>}
                <span className="sc"><Pie p={o.score} size={17} /><span className={`num ${STATUS_CLASS[statusFor(o.score)]}`}>{pct(o.score)}</span></span></div>
              <div className="kh"><span>#</span><span>نتیجه کلیدی</span><span>مبنا ← هدف</span><span>میزان پیشرفت</span><span>درصد</span><span>توضیحات {data.time_point}</span></div>
              {o.key_results.map((k) => {
                const idx = flat.indexOf(k);
                return <Row key={k.id} k={k} sessionId={data.id} editable={data.can_edit_values && !k.frozen} selected={idx === selected}
                  onSelect={() => setSelected(idx)} onOpen={() => openForm(k)} onSaving={(s, m) => { setSaving(s); setSaveErr(m ?? null); if (s === "saved" || (s === "error" && m)) reload(); }} />;
              })}
            </section>
          ))}
        </div>
      )}

      {view === "cur" && data.can_edit_values && saving !== "idle" && (
        <div className="foot" role="status">
          <span className={saving === "error" ? "bad" : "saved"}>{saving === "saving" ? "در حال ذخیره…" : saving === "error" ? saveErr : saving === "saved" ? "ذخیره شد ✓" : ""}</span>
        </div>
      )}
    </>
  );
}

function Row({ k, sessionId, editable, selected, onSelect, onOpen, onSaving }: {
  k: KRRow; sessionId: string; editable: boolean; selected: boolean; onSelect: () => void; onOpen: () => void;
  onSaving: (s: Saving, msg?: string) => void;
}) {
  const [val, setVal] = useState(k.value == null ? "" : fa(k.value, 4));
  const [note, setNote] = useState(k.note ?? "");
  const [bad, setBad] = useState(false);
  const version = useRef(k.entry_version);
  const timer = useRef<number>();
  const latest = useRef({ val, note });
  latest.current = { val, note };

  const def = { kind: k.kind, baseline: k.baseline, target: k.target };
  const parsed = parseNumber(val);
  const livePercent = k.frozen ? k.percent : parsed === undefined ? k.percent : percent(def, parsed);
  const status = k.frozen ? k.status : statusFor(livePercent);

  const save = () => {
    const v = parseNumber(latest.current.val);
    if (v === undefined) return;
    onSaving("saving");
    api<{ entry_version: number }>(`/sessions/${sessionId}/entries/${k.id}`, {
      method: "PUT", body: { value: v, note: latest.current.note || null, expected_version: version.current },
    }).then((r) => { version.current = r.entry_version; onSaving("saved"); })
      .catch((e: Error) => onSaving("error", e.message));
  };
  const schedule = () => { window.clearTimeout(timer.current); timer.current = window.setTimeout(save, 600); };
  useEffect(() => () => window.clearTimeout(timer.current), []);

  return (
    <div className={`kr2 ${selected ? "sel" : ""}`} tabIndex={0} onClick={(e) => { onSelect(); if ((e.target as HTMLElement).tagName !== "INPUT") onOpen(); }}>
      <span className="num faint">{k.code.split(".").map((p) => fa(p)).join(".")}</span>
      <div><div className="t">{k.title}</div>
        <div className="m">{k.goal && <Tag color={k.goal.color}>{k.goal.title}</Tag>}{k.owner_name && <span className="faint tiny">مسئول: {k.owner_name}</span>}{k.definition_version > 1 && <span className="faint tiny">نسخهٔ تعریف {fa(k.definition_version)}</span>}</div></div>
      <span className="bt num mut" style={{ whiteSpace: "nowrap" }}>{fa(k.baseline)} ← <b style={{ color: "var(--text)" }}>{fa(k.target)}</b></span>
      <input className={`inp num ${editable ? "" : "ro"} ${bad ? "err" : ""}`} aria-label={`میزان پیشرفت ${k.title}`} inputMode="decimal" placeholder="—" value={val} readOnly={!editable}
        onFocus={(e) => { e.target.select(); onSelect(); }}
        onChange={(e) => { setVal(e.target.value); setBad(parseNumber(e.target.value) === undefined); schedule(); }} />
      <span className="pcell"><Pie p={livePercent} status={status} /><span className={`num ${STATUS_CLASS[status]}`} title={STATUS_LABEL[status]}>{pct(livePercent)}</span></span>
      <span className="ntw"><input className={`nt ${editable ? "" : "ro"}`} aria-label="توضیحات" placeholder="توضیح…" value={note} readOnly={!editable}
        onChange={(e) => { setNote(e.target.value); schedule(); }} /></span>
    </div>
  );
}

function AllRounds({ sessions }: { sessions: SessionHead[] }) {
  const [pages, setPages] = useState<SessionT[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    Promise.all(sessions.filter((s) => s.kind !== "start").map((s) => api<SessionT>(`/sessions/${s.id}`))).then(setPages).catch((e: Error) => setErr(e.message));
  }, [sessions]);
  if (err) return <ErrorBox message={err} />;
  if (!pages) return <Skeleton />;
  const rows = pages[0]?.objectives.flatMap((o) => o.key_results.map((k) => ({ o, k }))) ?? [];
  const cell = (p: SessionT, id: string) => p.objectives.flatMap((o) => o.key_results).find((x) => x.id === id);
  return (
    <div className="tw">
      <table className="dt">
        <thead><tr><th>نتیجه کلیدی</th><th className="c">مبنا</th><th className="c">هدف</th>{pages.map((p) => <th key={p.id} className="c">{p.time_point}</th>)}</tr></thead>
        <tbody>{rows.map(({ k }) => (
          <tr key={k.id}><td className="l"><span className="num faint">{k.code.split(".").map((x) => fa(x)).join(".")}</span> {k.title}</td><td className="num mut c">{fa(k.baseline)}</td><td className="num c"><b>{fa(k.target)}</b></td>
            {pages.map((p) => { const c = cell(p, k.id); return c?.value == null ? <td key={p.id} className="c empty-c" /> : <td key={p.id} className="c"><div className="num" style={{ fontWeight: 600 }}>{fa(c.value)}</div><div className={`pp num ${STATUS_CLASS[c.status]}`}>{pct(c.percent)}</div></td>; })}
          </tr>))}</tbody>
      </table>
    </div>
  );
}
