import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { upload } from "../../api/client";
import type { ImportReport, ImportSheet } from "../../api/types";
import { fa } from "../../domain/format";
import { Msg, useAction } from "./fields";

type Choice = { action: "existing" | "create" | "skip"; unit_id?: string | null; name?: string | null };

const STATUS: Record<ImportSheet["status"], [string, string]> = {
  ready: ["آمادهٔ ورود", "ok"],
  skipped: ["وارد نمی‌شود", "none"],
  already_imported: ["قبلاً وارد شده", "none"],
  error: ["خطا", "bad"],
};

const choiceOf = (s: ImportSheet): Choice =>
  s.action === "existing" ? { action: "existing", unit_id: s.unit_id } : s.action === "create" ? { action: "create", name: s.unit_name } : { action: "skip" };

/** Legacy Excel import: pick the file, check the preview (nothing is saved), adjust target units, then commit. */
export default function ImportPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [mapping, setMapping] = useState<Record<string, Choice>>({});
  const [done, setDone] = useState<ImportReport | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const a = useAction();

  const send = (what: "preview" | "commit", f: File, m: Record<string, Choice>) => {
    const form = new FormData();
    form.append("file", f);
    if (Object.keys(m).length) form.append("mapping", JSON.stringify(m));
    return upload<ImportReport>(`/admin/import/excel/${what}`, form);
  };

  const preview = (f: File, m: Record<string, Choice>) =>
    a.run(async () => {
      const r = await send("preview", f, m);
      setReport(r);
      setMapping(Object.fromEntries(r.sheets.map((s) => [s.sheet, m[s.sheet] ?? choiceOf(s)])));
    });

  const pick = (f: File | undefined) => {
    if (!f) return;
    setFile(f); setReport(null); setDone(null); setMapping({});
    preview(f, {});
  };

  const change = (sheet: string, value: string) => {
    const s = report?.sheets.find((x) => x.sheet === sheet);
    const c: Choice = value === "skip" ? { action: "skip" } : value === "create"
      ? { action: "create", name: (s?.action === "create" && s.unit_name) || sheet.trim() } : { action: "existing", unit_id: value };
    const next = { ...mapping, [sheet]: c };
    setMapping(next);
    if (file) preview(file, next);
  };

  const commit = () => {
    if (!file || !report) return;
    const t = report.totals;
    if (!window.confirm(`${fa(t.objectives)} هدف و ${fa(t.krs)} نتیجهٔ کلیدی در چرخهٔ «${report.cycle?.name}» ثبت شود؟`)) return;
    a.run(async () => {
      const r = await send("commit", file, mapping);
      setDone(r); setReport(null);
    });
  };

  if (done) {
    const t = done.totals;
    return (
      <div className="card">
        <h3 className="ok">ورود اطلاعات انجام شد ✓</h3>
        <div>{fa(t.objectives)} هدف، {fa(t.krs)} نتیجهٔ کلیدی، {fa(t.values)} مقدار پایش و {fa(t.notes)} یادداشت در چرخهٔ «{done.cycle?.name}» ثبت شد.
          {t.units_created > 0 && <> {fa(t.units_created)} واحد جدید ساخته شد.</>}</div>
        <div className="note">همهٔ موارد با برچسب «ایمپورت از فایل اکسل پایش» در تاریخچهٔ هر KR و در گزارش ممیزی ثبت شده‌اند.
          قدم بعد: برای واحدهای جدید در «واحدها» جایگاه و مدیر را مشخص کنید، سپس در «کاربران» مسئول KRها را تعریف کنید.</div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link className="btn" to="/">دیدن نمای کلی</Link>
          <Link className="btn o" to="/admin/units">تنظیم واحدها</Link>
        </div>
      </div>
    );
  }

  const ready = report?.sheets.filter((s) => s.status === "ready") ?? [];
  return (
    <>
      <div className="card">
        <h3>۱. فایل اکسل پایش OKR</h3>
        <div className="faint" style={{ lineHeight: 1.9 }}>هر شیت یک واحد است. ابتدا پیش‌نمایش ساخته می‌شود و <b>تا وقتی «ثبت نهایی» را نزنید هیچ چیزی ذخیره نمی‌شود.</b></div>
        <input ref={input} type="file" accept=".xlsx" hidden onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
          <button className="btn o" disabled={a.busy} onClick={() => input.current?.click()}>{file ? "انتخاب فایل دیگر" : "انتخاب فایل xlsx"}</button>
          {file && <span className="mut tiny" dir="auto">{file.name}</span>}
          {a.busy && <span className="mut tiny" aria-live="polite">در حال بررسی فایل…</span>}
        </div>
        <Msg err={a.err} />
      </div>

      {report && report.blocking.length > 0 && (
        <div className="note err-box" role="alert">
          {report.blocking.map((b) => <div key={b}>{b}</div>)}
          <Link className="lnk" to="/admin/cycle">رفتن به چرخه و جلسه‌ها</Link>
        </div>
      )}

      {report && !report.blocking.length && (
        <>
          <div className="card">
            <h3>خلاصهٔ پیش‌نمایش</h3>
            <div style={{ lineHeight: 2 }}>
              با ثبت نهایی، در چرخهٔ <b>«{report.cycle?.name}»</b>: <b>{fa(report.totals.objectives)}</b> هدف، <b>{fa(report.totals.krs)}</b> نتیجهٔ کلیدی،
              {" "}<b>{fa(report.totals.values)}</b> مقدار پایش و <b>{fa(report.totals.notes)}</b> یادداشت وارد می‌شود.
              {report.totals.units_created > 0 && <> {fa(report.totals.units_created)} واحد جدید ساخته می‌شود.</>}
              {report.totals.goals_created > 0 && <> {fa(report.totals.goals_created)} هدف کسب‌وکاری به فهرست اضافه می‌شود.</>}
            </div>
            <div className="faint tiny" style={{ marginTop: 6 }}>
              پایش‌های اکسل به ترتیب به پایش‌های این چرخه نگاشته می‌شوند: {report.review_points.length ? report.review_points.join("، ") : "چرخه پایشی ندارد"}.
              {(report.totals.warnings > 0 || report.totals.errors > 0) && <> · <span className="risk">{fa(report.totals.warnings)} هشدار</span>{report.totals.errors > 0 && <>، <span className="bad">{fa(report.totals.errors)} خطا</span></>} — جزئیات کنار هر شیت.</>}
            </div>
          </div>

          <div className="sec"><h2>۲. واحد مقصد هر شیت <span className="num">{fa(report.sheets.length)}</span></h2></div>
          <div className="faint tiny" style={{ marginBottom: 4 }}>شیت‌هایی که نامشان با یک واحد یکی است خودکار وصل شده‌اند؛ بقیه به‌صورت واحد جدید ساخته می‌شوند. هر کدام را می‌توانید عوض کنید.</div>
          {report.sheets.map((s) => {
            const c = mapping[s.sheet] ?? choiceOf(s);
            const value = c.action === "existing" ? c.unit_id ?? "" : c.action;
            const [label, cls] = STATUS[s.status];
            const warn = s.issues.filter((i) => i.level !== "info").length;
            return (
              <div key={s.sheet} className="card" style={{ padding: "10px 14px", marginBottom: 8 }}>
                <div style={{ display: "grid", gridTemplateColumns: "minmax(110px,1fr) minmax(170px,1.3fr) minmax(150px,1.4fr) auto", gap: 12, alignItems: "center" }} className="imp-row">
                  <b dir="auto">{s.sheet.trim()}</b>
                  <select aria-label={`واحد مقصد شیت ${s.sheet.trim()}`} value={value} disabled={a.busy} onChange={(e) => change(s.sheet, e.target.value)}
                    style={{ padding: "6px 8px", border: "1px solid var(--line-strong)", borderRadius: 8, background: "var(--surface)", color: "var(--text)" }}>
                    <option value="create">+ واحد جدید «{c.action === "create" ? c.name : s.sheet.trim()}»</option>
                    <optgroup label="واحدهای موجود">{report.units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</optgroup>
                    <option value="skip">وارد نشود</option>
                  </select>
                  <span className="mut tiny">{fa(s.objectives)} هدف، {fa(s.krs)} KR{s.values > 0 && <>، {fa(s.values)} مقدار</>}{s.notes > 0 && <>، {fa(s.notes)} یادداشت</>}</span>
                  <span style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "end" }}>
                    <span className={`tiny ${cls}`} style={{ fontWeight: 600 }}>{label}</span>
                    {s.issues.length > 0 && <button className="lnk tiny" aria-expanded={open === s.sheet} onClick={() => setOpen(open === s.sheet ? null : s.sheet)}>
                      {warn ? <span className="risk">{fa(warn)} هشدار</span> : `${fa(s.issues.length)} نکته`}</button>}
                  </span>
                </div>
                {open === s.sheet && (
                  <ul style={{ margin: "10px 0 0", paddingInlineStart: 18, lineHeight: 1.9, fontSize: 14 }}>
                    {s.issues.map((i, k) => <li key={k} className={i.level === "error" ? "bad" : i.level === "warning" ? "risk" : "mut"}><b>{i.where}:</b> {i.message}</li>)}
                  </ul>
                )}
              </div>
            );
          })}
          {report.ignored_sheets.length > 0 && <div className="faint tiny">شیت‌های کنارگذاشته (قالب یا خلاصه): {report.ignored_sheets.join("، ")}</div>}

          {(report.goals.length > 0 || report.unmatched_goals.length > 0) && (
            <div className="card" style={{ marginTop: 14 }}>
              <h3>اهداف کسب‌وکاری</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {report.goals.map((g) => <span key={g.title} className="tag" style={{ ["--c" as string]: "var(--g0)" }}>{g.title}، {fa(g.krs)}{g.action === "create" && " · جدید"}</span>)}
              </div>
              {report.unmatched_goals.length > 0 && (
                <div className="note">این مقادیر در ستون «هدف کسب‌وکاری» بودند ولی در فهرست اهداف نیستند (احتمالاً ستون جابه‌جا پر شده). در توضیحات KR نگه داشته می‌شوند:
                  {" "}{report.unmatched_goals.map((u) => `${u.text} (${fa(u.krs)})`).join("، ")}</div>
              )}
            </div>
          )}

          <div className="card" style={{ marginTop: 14 }}>
            <h3>۳. ثبت نهایی</h3>
            <div className="faint" style={{ marginBottom: 10 }}>{ready.length ? `${fa(ready.length)} شیت وارد می‌شود. ورود دوباره همین فایل، شیت‌های واردشده را تکرار نمی‌کند.` : "هیچ شیتی برای ورود آماده نیست."}</div>
            <button className="btn" disabled={a.busy || ready.length === 0} onClick={commit}>ثبت نهایی</button>
          </div>
        </>
      )}
    </>
  );
}
