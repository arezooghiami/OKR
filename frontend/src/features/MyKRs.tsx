import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useGet } from "../api/typed";
import type { MyBlock } from "../api/types";
import { percent, statusFor, STATUS_CLASS, STATUS_LABEL } from "../domain/calc";
import { fa, jDayMonth, jTime, parseNumber, pct } from "../domain/format";
import { Bar, Crumb, Empty, ErrorBox, Skeleton } from "../ui/parts";

type KR = MyBlock["key_results"][number];
type Save = "idle" | "saving" | "saved" | "error";

/** The KR owner's daily page: one card per KR with everything needed to record a round, saved as you type.
 *  Replaces "find your row in the sheet, type in the right cell, hope the formula still works". */
export default function MyKRs() {
  const { data, error, loading, reload } = useGet("/api/v1/me/key-results");
  const [recorded, setRecorded] = useState<Record<string, boolean>>({});

  if (loading && !data) return <Skeleton rows={5} />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const blocks = data ?? [];
  if (blocks.length === 0) return <><Crumb items={["KRهای من"]} /><Empty title="نتیجهٔ کلیدی‌ای به شما سپرده نشده است" hint="وقتی مدیر واحد شما را مسئول یک KR کند، اینجا می‌بینید و پیشرفتش را ثبت می‌کنید." /></>;

  const all = blocks.flatMap((b) => b.key_results);
  const open = all.filter((k) => k.editable);
  const isDone = (k: KR) => recorded[k.id] ?? k.value != null;
  const done = open.filter(isDone).length;
  const round = open[0]?.round ?? all[0]?.round;
  const due = open.map((k) => k.round_at).filter(Boolean).sort()[0];

  return (
    <>
      <Crumb items={["KRهای من"]} />
      <div className="mh"><h1>ثبت پیشرفت{round && ` · پایش ${round}`}</h1></div>
      <div className="mkh">
        <div>
          {open.length > 0
            ? <><div className="big2 num">{fa(done)} از {fa(open.length)}</div><div className="mut">نتیجهٔ کلیدی برای این پایش ثبت شده{due && <> · تا جلسهٔ <b>{jDayMonth(due)}</b> ساعت {jTime(due)}</>}</div></>
            : <><div className="big2">فعلاً ثبتی لازم نیست</div><div className="mut">پایش بعدی هنوز باز نشده است؛ دلیلش زیر هر مورد آمده.</div></>}
        </div>
        {open.length > 0 && (done === open.length
          ? <span className="badge ok">همه ثبت شد</span>
          : <Bar p={(done / open.length) * 100} status={done === 0 ? "behind" : "at_risk"} />)}
      </div>
      <div className="note">عدد را وارد کنید؛ درصد خودش حساب می‌شود و همان لحظه ذخیره می‌شود. یک خط توضیح بنویسید که در جلسه لازم نباشد دوباره توضیح دهید.</div>
      {blocks.map((b) => (
        <section key={b.objective_id}>
          <div className="ogh"><b>{b.title}</b><span>{b.unit_name}</span></div>
          {b.key_results.map((k) => <KRCard key={k.id} k={k} onRecorded={(v) => setRecorded((r) => ({ ...r, [k.id]: v }))} />)}
        </section>
      ))}
    </>
  );
}

function KRCard({ k, onRecorded }: { k: KR; onRecorded: (has: boolean) => void }) {
  const [val, setVal] = useState(k.value == null ? "" : fa(k.value, 4));
  const [note, setNote] = useState(k.note ?? "");
  const [save, setSave] = useState<Save>("idle");
  const [err, setErr] = useState("");
  const version = useRef<number | null>(k.entry_version);
  const timer = useRef<number>();
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const n = parseNumber(val);
  const bad = n === undefined;
  const milestone = k.kind === "milestone";
  const p = percent({ kind: k.kind, baseline: k.baseline, target: k.target }, n ?? null);
  const st = statusFor(p);

  const schedule = (nextVal: string, nextNote: string) => {
    window.clearTimeout(timer.current);
    const v = parseNumber(nextVal);
    if (v === undefined || !k.session_id) return;
    timer.current = window.setTimeout(() => {
      setSave("saving");
      api<{ entry_version: number }>(`/sessions/${k.session_id}/entries/${k.id}`, {
        method: "PUT", body: { value: v, note: nextNote.trim() || null, expected_version: version.current },
      }).then((r) => { version.current = r.entry_version; setSave("saved"); onRecorded(v != null); })
        .catch((e: Error) => { setSave("error"); setErr(e.message); });
    }, 700);
  };

  const todo = k.editable && n == null;
  return (
    <article className={`krc ${todo ? "todo" : ""}`}>
      <div className="top">
        <span className="code num">{k.code.split(".").map((x) => fa(x)).join(".")}</span>
        <Link className="ttl" to={`/krs/${k.id}`}>{k.title}</Link>
        <span className={`badge ${STATUS_CLASS[st]}`}>{STATUS_LABEL[st]}</span>
      </div>
      <div className="stats">
        {milestone
          ? <><div className="st"><small>نوع</small><b style={{ fontSize: 16 }}>درصد انجام</b></div><div className="st"><small>هدف</small><b className="num">۱۰۰٪</b></div></>
          : <><div className="st"><small>خط مبنا</small><b className="num">{fa(k.baseline)}</b></div><div className="st"><small>هدف</small><b className="num">{fa(k.target)}</b>{k.unit_of_measure && <small style={{ display: "inline" }}> {k.unit_of_measure}</small>}</div></>}
        <div className="st"><small>{k.previous_round ? `مقدار ${k.previous_round}` : "مقدار قبلی"}</small><b className="num">{k.previous_value == null ? "—" : fa(k.previous_value, 4)}</b></div>
      </div>
      <div className="entry">
        <div>
          <label htmlFor={`v-${k.id}`}>{milestone ? "چند درصد انجام شده؟" : `مقدار ${k.round ? `پایش ${k.round}` : "فعلی"}`}</label>
          <input id={`v-${k.id}`} className={`val num ${bad ? "err" : ""}`} inputMode="decimal" placeholder={milestone ? "۰ تا ۱۰۰" : "عدد"} value={val}
            readOnly={!k.editable} aria-invalid={bad} onChange={(e) => { setVal(e.target.value); schedule(e.target.value, note); }} />
        </div>
        <div>
          <label htmlFor={`n-${k.id}`}>توضیح کوتاه: چه کار شد؟</label>
          <textarea id={`n-${k.id}`} className="note" placeholder="مثلاً: دو فروشگاه راه‌اندازی شد، دفاتر آذر" value={note} readOnly={!k.editable}
            onChange={(e) => { setNote(e.target.value); schedule(val, e.target.value); }} />
        </div>
      </div>
      <div className="res">
        <span className={`p num ${STATUS_CLASS[st]}`}>{pct(p)}</span>
        <Bar p={p} status={st} />
        <span className={`msg ${save === "error" || bad ? "bad" : save === "saved" ? "ok" : "mut"}`} role="status">
          {bad ? "عدد معتبر نیست" : save === "saving" ? "در حال ذخیره…" : save === "saved" ? "ذخیره شد ✓" : save === "error" ? err : ""}
        </span>
      </div>
      {!k.editable && k.blocker && <div className="lock">ثبت فعلاً بسته است: {k.blocker}</div>}
    </article>
  );
}
