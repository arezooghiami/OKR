import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useGet } from "../api/typed";
import { useEntrySave } from "../api/useEntrySave";
import type { KRRow, SessionHead, SessionPage as SessionT } from "../api/types";
import { percent, statusFor, STATUS_CLASS, STATUS_LABEL } from "../domain/calc";
import { fa, jDateTime, parseNumber, pct, tpLabel } from "../domain/format";
import { Crumb, ErrorBox, Pie, Skeleton, Tag } from "../ui/parts";
import { usePeek } from "../ui/Peek";
import ExportButton from "../ui/ExportButton";
import UnitTabs from "../ui/UnitTabs";
import KRForm from "./KRForm";
import ObjectiveForm from "./ObjectiveForm";

type Saving = "idle" | "saving" | "saved" | "error";

export default function SessionPage() {
  const { id } = useParams();
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

  // J/K move, Enter edits the value, Space opens the definition (desktop shortcuts; every action also has a click path).
  // e.code is the physical key, so J/K work with the Persian keyboard layout too (e.key would be «ت»/«ن»).
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = (e.target as HTMLElement).tagName;
      if (["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"].includes(t) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.code === "KeyJ" || e.key === "ArrowDown") { setSelected((s) => Math.min(flat.length - 1, s + 1)); e.preventDefault(); }
      else if (e.code === "KeyK" || e.key === "ArrowUp") { setSelected((s) => Math.max(0, s - 1)); e.preventDefault(); }
      else if (e.key === "Enter" && selected >= 0) { rowsRef.current?.querySelectorAll<HTMLInputElement>("input.inp")[selected]?.focus(); e.preventDefault(); }
      else if (e.code === "Space" && selected >= 0) { openForm(flat[selected]); e.preventDefault(); }
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
      <Crumb items={["واحدها", data.unit_name, `جلسهٔ ${tpLabel(data.time_point)}`]} />
      <div className="mh">
        <div>
          <h1>{data.unit_name}</h1>
          <div className="mut" style={{ marginTop: 2 }}>
            {data.status === "unscheduled" ? <>زمان جلسه هنوز تعیین نشده؛ ثبت مقدار باز است.</> : <>{jDateTime(data.held_at ?? data.scheduled_at)}{data.place && `، ${data.place}`}{data.status === "held" && "، برگزار شد"}</>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <ExportButton path={`/units/${data.unit_id}/export.xlsx`} label="خروجی Excel" />
          {data.can_hold && (confirmHold
            ? <><button className="btn" onClick={hold}>تأیید: جلسه برگزار شد</button><button className="btn o" onClick={() => setConfirmHold(false)}>انصراف</button></>
            : <button className="btn o" onClick={() => setConfirmHold(true)}>برگزار شد ✓</button>)}
          {data.can_edit_definitions && <button className="btn o" onClick={() => peek.open(<ObjectiveForm key="obj" unitId={data.unit_id} unitName={data.unit_name} sessionId={data.id} onDone={() => { peek.close(); reload(); }} />)}>+ هدف جدید</button>}
          {data.can_edit_definitions && data.objectives.length > 0 && <button className="btn" onClick={() => openForm(null)}>+ نتیجهٔ کلیدی</button>}
        </div>
      </div>
      <UnitTabs unitId={data.unit_id} active="session" sessionLabel={tpLabel(data.time_point)} />
      {holdErr && <div className="warnbar" role="alert">{holdErr}</div>}

      <div className="steps" aria-label="جلسه‌های دوره">
        {(sessions.data ?? []).map((s) => (
          <span key={s.id} className={s.id === data.id ? "cur" : s.status === "held" ? "dn" : ""}>
            {s.id === data.id ? <>{tpLabel(s.time_point)}، {s.status === "held" ? "برگزار شد" : "جاری"}</> : <Link to={`/sessions/${s.id}`}>{tpLabel(s.time_point)}{s.status === "held" ? " ✓" : ""}</Link>}
          </span>
        ))}
      </div>

      <div className="toolbar">
        <div className="seg"><button className={view === "cur" ? "on" : ""} onClick={() => setView("cur")}>پایش جاری</button><button className={view === "all" ? "on" : ""} onClick={() => setView("all")}>همهٔ پایش‌ها</button></div>
        <span className="faint tiny">{fa(flat.length)} نتیجهٔ کلیدی در {fa(data.objectives.length)} هدف{data.score != null && ` · امتیاز جلسه ${pct(data.score)}${data.status === "held" ? "" : " (تا این لحظه؛ پس از «برگزار شد» ثابت می‌شود)"}`}</span>
      </div>
      {readOnlyWhy && view === "cur" && <div className="note" role="status">{readOnlyWhy}</div>}

      {view === "all" ? <AllRounds sessions={sessions.data ?? []} /> : (
        <div ref={rowsRef} className={data.objectives.length ? "sheet" : undefined}>
          {data.objectives.length === 0 && <div className="empty"><b>هنوز هدفی تعریف نشده است</b></div>}
          {data.objectives.map((o) => (
            <section className="ob" key={o.id}>
              <div className="og"><span className="no">هدف {fa(o.number)}</span><b>{o.title}</b>
                <span className={`tiny ${o.owner_name ? "mut" : "risk"}`}>{o.owner_name ? `مسئول هدف: ${o.owner_name}` : "بدون مسئول هدف"}</span>
                {data.can_edit_definitions && <button className="lnk tiny" onClick={() => peek.open(<ObjectiveForm key={o.id} unitId={data.unit_id} unitName={data.unit_name} sessionId={data.id} objective={o} onDone={() => { peek.close(); reload(); }} />)}>ویرایش</button>}
                <span className="sc"><Pie p={o.score} size={17} /><span className={`num ${STATUS_CLASS[statusFor(o.score)]}`}>{pct(o.score)}</span></span></div>
              <div className="kh"><span>#</span><span>نتیجهٔ کلیدی</span><span>مبنا ← هدف</span><span>میزان پیشرفت</span><span>درصد</span><span>توضیحات {tpLabel(data.time_point)}</span></div>
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
  const initial = { val: k.value == null ? "" : fa(k.value, 4), note: k.note ?? "" };
  const [val, setVal] = useState(initial.val);
  const [note, setNote] = useState(initial.note);
  const [bad, setBad] = useState(false);
  const saver = useEntrySave({ sessionId, krId: k.id, entryVersion: k.entry_version, initial, onState: onSaving });

  const parsed = parseNumber(val);
  // this row has no range bounds, so a "keep within range" KR shows the server's percent until saved
  const live = !k.frozen && parsed !== undefined && k.kind !== "maintain";
  const livePercent = live ? percent({ kind: k.kind, baseline: k.baseline, target: k.target }, parsed) : k.percent;
  const status = live ? statusFor(livePercent) : k.status;

  return (
    <div className={`kr2 ${selected ? "sel" : ""}`} tabIndex={0} onClick={(e) => { onSelect(); if ((e.target as HTMLElement).tagName !== "INPUT") onOpen(); }}>
      <span className="num faint">{k.code.split(".").map((p) => fa(p)).join(".")}</span>
      <div><div className="t">{k.title}</div>
        <div className="m">{k.goal && <Tag color={k.goal.color}>{k.goal.title}</Tag>}{k.owner_name && <span className="faint tiny">مسئول: {k.owner_name}</span>}{k.definition_version > 1 && <span className="faint tiny">نسخهٔ تعریف {fa(k.definition_version)}</span>}</div></div>
      <span className="bt num mut" style={{ whiteSpace: "nowrap" }}>{fa(k.baseline)} ← <b style={{ color: "var(--text)" }}>{fa(k.target)}</b></span>
      <input className={`inp num ${editable ? "" : "ro"} ${bad ? "err" : ""}`} aria-label={`میزان پیشرفت ${k.title}`} inputMode="decimal" placeholder="—" value={val} readOnly={!editable}
        onFocus={(e) => { e.target.select(); onSelect(); }}
        onChange={(e) => { setVal(e.target.value); setBad(parseNumber(e.target.value) === undefined); saver.track(e.target.value, note); }}
        onBlur={saver.flush} onKeyDown={(e) => { if (e.key === "Enter") saver.flush(); }} />
      <span className="pcell"><Pie p={livePercent} status={status} /><span className={`num ${STATUS_CLASS[status]}`} title={STATUS_LABEL[status]}>{pct(livePercent)}</span></span>
      <span className="ntw"><input className={`nt ${editable ? "" : "ro"}`} aria-label="توضیحات" placeholder="توضیح…" value={note} readOnly={!editable}
        onChange={(e) => { setNote(e.target.value); saver.track(val, e.target.value); }} onBlur={saver.flush}
        onKeyDown={(e) => { if (e.key === "Enter") saver.flush(); }} /></span>
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
        <thead><tr><th>نتیجهٔ کلیدی</th><th className="c">مبنا</th><th className="c">هدف</th>{pages.map((p) => <th key={p.id} className="c">{tpLabel(p.time_point)}</th>)}</tr></thead>
        <tbody>{rows.map(({ k }) => (
          <tr key={k.id}><td className="l"><span className="num faint">{k.code.split(".").map((x) => fa(x)).join(".")}</span> {k.title}</td><td className="num mut c">{fa(k.baseline)}</td><td className="num c"><b>{fa(k.target)}</b></td>
            {pages.map((p) => { const c = cell(p, k.id); return c?.value == null ? <td key={p.id} className="c empty-c" /> : <td key={p.id} className="c"><div className="num" style={{ fontWeight: 600 }}>{fa(c.value)}</div><div className={`pp num ${STATUS_CLASS[c.status]}`}>{pct(c.percent)}</div></td>; })}
          </tr>))}</tbody>
      </table>
    </div>
  );
}
