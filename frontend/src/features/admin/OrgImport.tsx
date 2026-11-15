import { useRef, useState } from "react";
import { upload } from "../../api/client";
import type { OrgImport as Report, OrgImportRow } from "../../api/types";
import { fa } from "../../domain/format";
import ExportButton from "../../ui/ExportButton";
import { Msg, useAction } from "./fields";

const STATUS: Record<string, [string, string]> = {
  new: ["ok", "جدید"], update: ["ac", "تغییر"], same: ["none", "بدون تغییر"], error: ["bad", "خطا"],
};

function Rows({ title, rows, users }: { title: string; rows: OrgImportRow[]; users?: boolean }) {
  const [all, setAll] = useState(false);
  if (!rows.length) return null;
  const same = rows.filter((r) => r.status === "same").length;
  const shown = all ? rows : rows.filter((r) => r.status !== "same");
  return (
    <div className="imp-sec">
      <div className="imp-sec-h">
        <h4>{title} <span className="num faint">{fa(rows.length)} ردیف</span></h4>
        {same > 0 && <button className="lnk tiny" onClick={() => setAll(!all)}>{all ? "فقط ردیف‌های تغییرکرده" : `نمایش ${fa(same)} ردیف بدون تغییر`}</button>}
      </div>
      {shown.length === 0 ? <div className="faint tiny">هیچ ردیفی تغییری ندارد.</div> : (
        <div className="imp-wrap">
          <table className="imp-t">
            <thead><tr><th>ردیف</th><th>{users ? "کاربر" : "واحد"}</th>{users && <th>نقش و واحد</th>}<th>وضعیت</th><th>جزئیات</th></tr></thead>
            <tbody>
              {shown.map((r, i) => {
                const [cls, label] = STATUS[r.status] ?? ["none", r.status];
                return (
                  <tr key={`${r.row}-${i}`} className={r.status === "error" ? "err" : undefined}>
                    <td className="num faint">{fa(r.row)}</td>
                    <td>{users ? <><b>{r.full_name || r.name}</b><div className="faint tiny" dir="ltr">{r.name}</div></> : <b>{r.name || "—"}</b>}</td>
                    {users && <td>{r.role ? `${r.role} · ${r.unit ?? "کل سازمان"}` : <span className="faint">—</span>}</td>}
                    <td><span className={`badge ${cls}`}>{label}</span></td>
                    <td>{r.detail && <div>{r.detail}</div>}{r.message && <div className={r.status === "error" ? "bad" : "faint"}>{r.message}</div>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function saveCsv(rows: Report["credentials"]) {
  const esc = (s: string) => `"${s.replace(/"/g, '""')}"`;
  const csv = "﻿" + ["نام کاربری,نام,رمز اولیه", ...rows.map((c) => [c.username, c.full_name, c.password].map(esc).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  Object.assign(document.createElement("a"), { href: url, download: "okr-new-users.csv" }).click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Units and users from Excel: download the current organisation, edit, check the preview (nothing saved), commit. */
export default function OrgImport({ usersFirst, onClose, onDone }: { usersFirst?: boolean; onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [done, setDone] = useState<Report | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const a = useAction();

  const send = (what: "preview" | "commit", f: File) => {
    const form = new FormData();
    form.append("file", f);
    return upload<Report>(`/admin/import/org/${what}`, form);
  };
  const pick = (f: File | undefined) => {
    if (!f) return;
    setFile(f); setReport(null); setDone(null);
    a.run(async () => setReport(await send("preview", f)));
  };
  const commit = () => file && a.run(async () => { const r = await send("commit", file); setDone(r); setReport(null); onDone(); });

  const t = (report ?? done)?.totals;
  const changes = t ? t.units_new + t.units_updated + t.users_new + t.users_updated : 0;
  const sections = (r: Report) => {
    const u = <Rows key="u" title="واحدها" rows={r.units} />, s = <Rows key="s" title="کاربران" rows={r.users} users />;
    return usersFirst ? [s, u] : [u, s];
  };

  return (
    <div className="card imp-card">
      <div className="imp-sec-h"><h3>ورود واحدها و کاربران از اکسل</h3><button className="lnk" onClick={onClose}>بستن</button></div>

      {done ? (
        <>
          <p className="ok" style={{ fontWeight: 700 }}>ثبت شد ✓</p>
          <p>{fa(done.totals.units_new)} واحد جدید، {fa(done.totals.units_updated)} واحد تغییرکرده · {fa(done.totals.users_new)} کاربر جدید، {fa(done.totals.users_updated)} کاربر تغییرکرده
            {done.totals.errors > 0 && <span className="bad"> · {fa(done.totals.errors)} ردیف خطا وارد نشد</span>}</p>
          {done.credentials.length > 0 && (
            <div className="imp-sec">
              <div className="warnbar" role="status"><b>رمز اولیهٔ {fa(done.credentials.length)} کاربر جدید فقط همین یک بار نشان داده می‌شود.</b> فایل را بگیرید و به هر نفر رمز خودش را بدهید.</div>
              <div className="imp-wrap"><table className="imp-t">
                <thead><tr><th>نام</th><th>نام کاربری</th><th>رمز اولیه</th></tr></thead>
                <tbody>{done.credentials.map((c) => <tr key={c.username}><td>{c.full_name}</td><td dir="ltr">{c.username}</td><td dir="ltr"><code>{c.password}</code></td></tr>)}</tbody>
              </table></div>
              <button className="btn" style={{ marginTop: 10 }} onClick={() => saveCsv(done.credentials)}>دانلود رمزها (CSV)</button>
            </div>
          )}
          {sections(done)}
          <button className="btn o" style={{ marginTop: 12 }} onClick={() => { setDone(null); setFile(null); }}>ورود فایل دیگر</button>
        </>
      ) : (
        <>
          <ol className="imp-steps">
            <li>
              <b>فایل فعلی را بگیرید.</b> همهٔ واحدها و کاربران فعلی در آن هست؛ ردیف اضافه یا ویرایش کنید. با ورود فایل چیزی حذف نمی‌شود.
              <div style={{ marginTop: 8 }}><ExportButton path="/admin/import/org/template.xlsx" label="دریافت فایل اکسل واحدها و کاربران" /></div>
            </li>
            <li>
              <b>فایل ویرایش‌شده را انتخاب کنید.</b> اول پیش‌نمایش ساخته می‌شود و تا «ثبت» را نزنید چیزی ذخیره نمی‌شود.
              <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
                <input ref={input} type="file" accept=".xlsx" hidden onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
                <button className="btn o" disabled={a.busy} onClick={() => input.current?.click()}>{file ? "انتخاب فایل دیگر" : "انتخاب فایل xlsx"}</button>
                {file && <span className="faint tiny" dir="auto">{file.name}</span>}
                {a.busy && <span className="faint tiny" aria-live="polite">در حال بررسی…</span>}
              </div>
            </li>
          </ol>
          <Msg err={a.err} />
          {report && (
            <>
              {report.blocking.map((b) => <div key={b} className="warnbar" role="alert">{b}</div>)}
              {!report.blocking.length && t && (
                <p className="imp-sum">
                  <b>پیش‌نمایش:</b> {fa(t.units_new)} واحد جدید، {fa(t.units_updated)} واحد تغییر · {fa(t.users_new)} کاربر جدید، {fa(t.users_updated)} کاربر تغییر
                  {t.errors > 0 && <span className="bad"> · {fa(t.errors)} ردیف خطا (وارد نمی‌شوند؛ در فایل درست کنید و دوباره انتخاب کنید)</span>}
                  {report.types_created.length > 0 && <span className="faint"> · نوع واحد جدید: {report.types_created.join("، ")}</span>}
                </p>
              )}
              {sections(report)}
              {!report.blocking.length && (
                <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
                  <button className="btn" disabled={a.busy || changes === 0} onClick={commit}>{changes ? `ثبت ${fa(changes)} تغییر` : "تغییری برای ثبت نیست"}</button>
                  {t && t.users_new > 0 && <span className="faint tiny">برای کاربران جدید بدون «رمز اولیه»، رمز ساخته و بعد از ثبت نشان داده می‌شود.</span>}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
