import { useEffect, useRef, useState } from "react";
import { fa, jalaliParts } from "../domain/format";
import { jalaliToGregorian } from "../domain/jalali";

const MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
const WEEK = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
const p2 = (n: number) => String(n).padStart(2, "0");
const toLatin = (s: string) => s.replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)));

/** Days in a Jalali month (Esfand is 30 in leap years). */
export function monthDays(y: number, m: number): number {
  if (m <= 6) return 31;
  if (m <= 11) return 30;
  const [gy, gm, gd] = jalaliToGregorian(y, 12, 30);
  return jalaliParts(new Date(Date.UTC(gy, gm - 1, gd, 12))).d === 30 ? 30 : 29;
}

/** 0 = Saturday … 6 = Friday, for the first day of a Jalali month. */
export function firstWeekday(y: number, m: number): number {
  const [gy, gm, gd] = jalaliToGregorian(y, m, 1);
  return (new Date(Date.UTC(gy, gm - 1, gd, 12)).getUTCDay() + 1) % 7;
}

function parse(v: string): { y: number; m: number; d: number } | null {
  const r = toLatin(v).trim().match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$/);
  return r && +r[2] >= 1 && +r[2] <= 12 ? { y: +r[1], m: +r[2], d: +r[3] } : null;
}

/** A Jalali date field: type it ("1405/08/24") or click to pick it from a Persian calendar. */
export default function JalaliDate({ value, onChange, label, disabled, placeholder = "1405/08/24", id }: {
  value: string; onChange: (v: string) => void; label?: string; disabled?: boolean; placeholder?: string; id?: string;
}) {
  const today = jalaliParts(new Date());
  const [open, setOpen] = useState(false);
  const sel = parse(value);
  const [view, setView] = useState(() => sel ?? today);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const show = () => { if (disabled) return; setView(parse(value) ?? today); setOpen(true); };
  const move = (delta: number) => setView((v) => {
    const i = v.y * 12 + (v.m - 1) + delta;
    return { y: Math.floor(i / 12), m: (i % 12) + 1, d: 1 };
  });
  const pick = (d: number) => { onChange(`${view.y}/${p2(view.m)}/${p2(d)}`); setOpen(false); };

  const n = monthDays(view.y, view.m), lead = firstWeekday(view.y, view.m);
  const cells = [...Array(lead).fill(null), ...Array.from({ length: n }, (_, i) => i + 1)];
  return (
    <div className="jd" ref={box} onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      <input id={id} aria-label={label} dir="ltr" placeholder={placeholder} value={value} disabled={disabled} autoComplete="off"
        onChange={(e) => onChange(e.target.value)} onFocus={show} onClick={show} aria-haspopup="dialog" aria-expanded={open} />
      {open && (
        <div className="jd-pop" role="dialog" aria-label="انتخاب تاریخ">
          <div className="jd-h">
            <button type="button" className="jd-nav" aria-label="ماه قبل" onClick={() => move(-1)}>‹</button>
            <b>{MONTHS[view.m - 1]} {fa(view.y)}</b>
            <button type="button" className="jd-nav" aria-label="ماه بعد" onClick={() => move(1)}>›</button>
          </div>
          <div className="jd-g">
            {WEEK.map((w) => <span key={w} className="jd-w">{w}</span>)}
            {cells.map((d, i) => d === null ? <span key={`e${i}`} /> : (
              <button type="button" key={d} onClick={() => pick(d)}
                className={`jd-d${sel && sel.y === view.y && sel.m === view.m && sel.d === d ? " on" : ""}${today.y === view.y && today.m === view.m && today.d === d ? " today" : ""}${i % 7 === 6 ? " fri" : ""}`}>
                {fa(d)}
              </button>
            ))}
          </div>
          <div className="jd-f">
            <button type="button" className="lnk" onClick={() => { onChange(`${today.y}/${p2(today.m)}/${p2(today.d)}`); setOpen(false); }}>امروز</button>
            {value && <button type="button" className="lnk faint" onClick={() => { onChange(""); setOpen(false); }}>پاک کردن</button>}
          </div>
        </div>
      )}
    </div>
  );
}
