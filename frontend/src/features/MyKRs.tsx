import { useState } from "react";
import { Link } from "react-router-dom";
import { useGet } from "../api/typed";
import { useEntrySave } from "../api/useEntrySave";
import type { MyBlock } from "../api/types";
import { percent, statusFor, STATUS_CLASS, STATUS_LABEL } from "../domain/calc";
import { fa, jDayMonth, jTime, parseNumber, pct, tpLabel } from "../domain/format";
import { Bar, Crumb, Empty, ErrorBox, Skeleton } from "../ui/parts";

type KR = MyBlock["key_results"][number];
type Save = "idle" | "saving" | "saved" | "error";

/** «پنج روز مانده» / «امروز» / «فردا» / «گذشته» until the meeting. */
function daysLeft(iso: string, now = Date.now()): string {
  const day = (t: number) => { const d = new Date(t); d.setHours(0, 0, 0, 0); return d.getTime(); };
  const n = Math.round((day(new Date(iso).getTime()) - day(now)) / 86_400_000);
  return n < 0 ? "زمان جلسه گذشته است" : n === 0 ? "جلسه امروز است" : n === 1 ? "جلسه فرداست" : `${fa(n)} روز مانده`;
}

/** The KR owner's daily page: one card per KR with everything needed to record a round, saved as you type.
 *  Replaces "find your row in the sheet, type in the right cell, hope the formula still works". */
export default function MyKRs() {
  const { data, error, loading, reload } = useGet("/api/v1/me/key-results");
  const [recorded, setRecorded] = useState<Record<string, boolean>>({});

  if (loading && !data) return <Skeleton rows={5} />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const blocks = data ?? [];
  if (blocks.length === 0) return <><Crumb items={["KRهای من"]} /><div className="mh"><h1>نتیجه‌های کلیدی من</h1></div><Empty icon="inbox" title="نتیجهٔ کلیدی‌ای به شما سپرده نشده است" hint="وقتی مدیر واحد شما را مسئول یک نتیجهٔ کلیدی کند، اینجا می‌بینید و پیشرفتش را ثبت می‌کنید." /></>;

  const all = blocks.flatMap((b) => b.key_results);
  const open = all.filter((k) => k.editable);
  const isDone = (k: KR) => recorded[k.id] ?? k.value != null;
  const done = open.filter(isDone).length;
  const round = open[0]?.round ?? all[0]?.round;
  const due = open.map((k) => k.round_at).filter(Boolean).sort()[0];
  const left = open.length - done;

  return (
    <>
      <Crumb items={["KRهای من"]} />
      {/* task-first headline (docs/07 phase 2): what is waiting and how long is left */}
      <div className="mh"><div>
        <h1>{open.length === 0 ? "فعلاً ثبتی لازم نیست" : left === 0 ? "همهٔ نتیجه‌های کلیدی شما ثبت شد" : `${fa(left)} نتیجهٔ کلیدی منتظر ثبت شماست`}</h1>
        {open.length > 0 && round && <p>{`تا جلسهٔ ${tpLabel(round)}`}{due ? `، ${daysLeft(due)} (${jDayMonth(due)}، ساعت ${jTime(due)})` : "؛ زمان جلسه هنوز تعیین نشده است"}</p>}
      </div></div>
      <div className="mkh">
        <div>
          {open.length > 0
            ? <><div className="big2 num">{fa(done)} از {fa(open.length)}</div><div className="mut">برای {tpLabel(round)} ثبت شده</div></>
            : <div className="mut">پایش بعدی هنوز باز نشده است؛ دلیلش زیر هر مورد آمده.</div>}
        </div>
        {open.length > 0 && (done === open.length
          ? <span className="badge ok">همه ثبت شد</span>
          : <Bar p={(done / open.length) * 100} status={done === 0 ? "behind" : "at_risk"} />)}
      </div>
      <div className="note">عدد را وارد کنید؛ درصد خودش حساب می‌شود. با Enter یا رفتن به خانهٔ بعد ذخیره می‌شود. برای هزارگان ویرگول بزنید (۱,۲۰۰) و برای اعشار ممیز (۱٫۵). یک خط توضیح بنویسید که در جلسه لازم نباشد دوباره توضیح دهید.</div>
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
  const initial = { val: k.value == null ? "" : fa(k.value, 4), note: k.note ?? "" };
  const [val, setVal] = useState(initial.val);
  const [note, setNote] = useState(initial.note);
  const [save, setSave] = useState<Save>("idle");
  const [err, setErr] = useState("");
  const saver = useEntrySave({
    sessionId: k.session_id, krId: k.id, entryVersion: k.entry_version, initial,
    onState: (s, detail) => { setSave(s); setErr(detail ?? ""); },
    onSaved: (v) => onRecorded(v != null),
  });

  const n = parseNumber(val);
  const bad = n === undefined;
  const milestone = k.kind === "milestone";
  const maintain = k.kind === "maintain";
  const p = percent({ kind: k.kind, baseline: k.baseline, target: k.target, range_min: k.range_min, range_max: k.range_max }, n ?? null);
  const st = statusFor(p);

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
          ? <><div className="st"><small>نوع</small><b style={{ fontSize: "var(--fs-md)" }}>درصد انجام</b></div><div className="st"><small>هدف</small><b className="num">۱۰۰٪</b></div></>
          : maintain
          ? <><div className="st"><small>نوع</small><b style={{ fontSize: "var(--fs-md)" }}>حفظ در بازه</b></div><div className="st"><small>بازهٔ مجاز</small><b className="num">{fa(k.range_min, 4)} تا {fa(k.range_max, 4)}</b>{k.unit_of_measure && <small style={{ display: "inline" }}> {k.unit_of_measure}</small>}</div></>
          : <><div className="st"><small>خط مبنا</small><b className="num">{fa(k.baseline)}</b></div><div className="st"><small>هدف</small><b className="num">{fa(k.target)}</b>{k.unit_of_measure && <small style={{ display: "inline" }}> {k.unit_of_measure}</small>}</div></>}
        <div className="st"><small>{k.previous_round ? `مقدار ${tpLabel(k.previous_round)}` : "مقدار قبلی"}</small><b className="num">{k.previous_value == null ? "—" : fa(k.previous_value, 4)}</b></div>
      </div>
      <div className="entry">
        <div>
          <label htmlFor={`v-${k.id}`}>{milestone ? "چند درصد انجام شده؟" : `مقدار ${k.round ? tpLabel(k.round) : "فعلی"}`}</label>
          <input id={`v-${k.id}`} className={`val num ${bad ? "err" : ""}`} inputMode="decimal" placeholder={milestone ? "۰ تا ۱۰۰" : "عدد"} value={val}
            readOnly={!k.editable} aria-invalid={bad} aria-describedby={`h-${k.id}`}
            onChange={(e) => { setVal(e.target.value); saver.track(e.target.value, note); }}
            onBlur={saver.flush} onKeyDown={(e) => { if (e.key === "Enter") saver.flush(); }} />
          {n != null && Math.abs(n) >= 1000 && <small id={`h-${k.id}`} className="faint num">{fa(n, 4)}{k.unit_of_measure ? ` ${k.unit_of_measure}` : ""}</small>}
        </div>
        <div>
          <label htmlFor={`n-${k.id}`}>توضیح کوتاه: چه کار شد؟</label>
          <textarea id={`n-${k.id}`} className="memo" placeholder="مثلاً: دو فروشگاه راه‌اندازی شد، دفاتر آذر" value={note} readOnly={!k.editable}
            onChange={(e) => { setNote(e.target.value); saver.track(val, e.target.value); }} onBlur={saver.flush} />
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
