import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useGet } from "../api/typed";
import type { Overview } from "../api/types";
import { isOrgWide, useAuth } from "../auth/AuthContext";
import { Icon } from "./parts";
import { PeekProvider } from "./Peek";

function useTheme() {
  const [dark, setDark] = useState(() => {
    try { return (localStorage.getItem("okr.theme") ?? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark"; } catch { return false; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "";
    try { localStorage.setItem("okr.theme", dark ? "dark" : "light"); } catch { /* ignore */ }
  }, [dark]);
  return [dark, () => setDark((d) => !d)] as const;
}

export default function Layout() {
  const { me, signOut } = useAuth();
  const nav = useNavigate();
  const [dark, toggleTheme] = useTheme();
  const [palette, setPalette] = useState(false);
  const cycle = useGet("/api/v1/cycles/current");
  const overview = useGet("/api/v1/dashboard/overview");

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette(true); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const groups = navFor(isOrgWide(me), !!me?.is_system_admin);
  const { pathname } = useLocation();

  return (
    <PeekProvider>
      <div className="shell">
        <aside className="side" aria-label="منوی اصلی">
          <NavLink className="brand" to="/">
            <i aria-hidden="true">O</i>
            <span><b>پایش OKR</b><small>{cycle.data?.name ?? (cycle.status === 404 ? "بدون چرخهٔ فعال" : "…")}</small></span>
          </NavLink>
          <nav>
            {groups.map((g) => (
              <div className="ng" key={g.title}>
                <div className="ngt">{g.title}</div>
                {g.items.map((it) => (
                  <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => `ni ${(it.match ? it.match(pathname) : isActive) ? "on" : ""} ${it.wide ? "wide" : ""}`}>
                    <Icon d={it.icon} /><span>{it.label}</span>
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
        </aside>
        <div className="main">
          <header className="bar">
            <button className="cmd" onClick={() => setPalette(true)}><Icon d="M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.3-4.3" /><span>جستجوی واحد یا صفحه…</span></button>
            <div className="sp" />
            <button className="ib" onClick={toggleTheme} aria-label={dark ? "تم روشن" : "تم تیره"} title={dark ? "تم روشن" : "تم تیره"}><Icon d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></button>
            <AccountMenu name={me?.full_name ?? ""} admin={!!me?.is_system_admin} onSignOut={() => signOut().then(() => nav("/login"))} />
          </header>
          <main className="page"><Outlet /></main>
        </div>
      </div>
      {palette && <Palette onClose={() => setPalette(false)} overview={overview.data} admin={!!me?.is_system_admin} />}
    </PeekProvider>
  );
}

type NavItem = { to: string; label: string; icon: string; end?: boolean; wide?: boolean; match?: (path: string) => boolean };
const I = {
  dash: "M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-3H4zM14 7h6V4h-6z",
  unit: "M4 21V6l8-3v18M12 21V9l8 3v9M3 21h18M8 9v.01M8 13v.01M8 17v.01M16 15v.01",
  meet: "M7 3v3M17 3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM8 13h3v3H8z",
  mine: "M20 12a8 8 0 1 1-8-8M16 12a4 4 0 1 1-4-4M12 12l8-8M17 4h3v3",
  tree: "M12 3v5M5 13v-2h14v2M5 13v3M19 13v3M12 8v8M3 16h4v4H3zM17 16h4v4h-4zM10 16h4v4h-4z",
  admin: "M4 7h9M17 7h3M4 12h3M11 12h9M4 17h11M19 17h1M15 5v4M9 10v4M17 15v4",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  file: "M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6",
};

/** Menu by role: KR owners start from their own KRs, unit managers from their unit, org-wide roles from the dashboard. */
function navFor(orgWide: boolean, admin: boolean): { title: string; items: NavItem[] }[] {
  const mine: NavItem = { to: "/my", label: "KRهای من", icon: I.mine };
  const groups = orgWide
    ? [{ title: "سازمان", items: [{ to: "/", label: "داشبورد سازمان", icon: I.dash, end: true }, { to: "/unit", label: "واحدها", icon: I.unit }, { to: "/units", label: "پروندهٔ واحدها", icon: I.file },
        { to: "/session", label: "جلسه‌های پایش", icon: I.meet }, { to: "/goals", label: "اهداف کلان", icon: I.tree, wide: true }] },
       { title: "کار من", items: [mine] }]
    : [{ title: "کار من", items: [mine, { to: "/unit", label: "واحد من", icon: I.unit }, { to: "/session", label: "جلسهٔ پایش", icon: I.meet }] },
       { title: "سازمان", items: [{ to: "/overview", label: "داشبورد سازمان", icon: I.dash }, { to: "/units", label: "پروندهٔ واحد", icon: I.file }, { to: "/goals", label: "اهداف کلان", icon: I.tree, wide: true }] }];
  if (admin) groups.push({ title: "مدیریت", items: [{ to: "/admin", label: "راه‌اندازی و تنظیمات", icon: I.admin, wide: true, match: (p) => p.startsWith("/admin") && !p.startsWith("/admin/import") }, { to: "/admin/import", label: "ورود از اکسل", icon: I.upload, wide: true }] });
  return groups;
}

function AccountMenu({ name, admin, onSignOut }: { name: string; admin: boolean; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    window.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); window.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <div className="acct" ref={box}>
      <button className="av" aria-label={`حساب کاربری ${name}`} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>{name[0]}</button>
      {open && (
        <div className="menu" role="menu">
          <div className="who"><b>{name}</b>{admin && <span className="faint tiny">مدیر سیستم</span>}</div>
          <button role="menuitem" className="it" onClick={() => { setOpen(false); onSignOut(); }}>خروج از حساب</button>
        </div>
      )}
    </div>
  );
}

function Palette({ onClose, overview, admin }: { onClose: () => void; overview: Overview | null; admin: boolean }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => input.current?.focus(), []);

  const items = useMemo(() => {
    const go = (to: string) => () => nav(to);
    const base = [["واحد من", "/unit"], ["نمای کلی سازمان", "/"], ["جلسهٔ پایش", "/session"], ["KRهای من", "/my"], ["اهداف کلان", "/goals"], ["پروندهٔ واحدها", "/units"], ...(admin ? [["مدیریت سامانه", "/admin"]] : [])].map(([t, to]) => ({ group: "برو به", t, run: go(to) }));
    const units = (overview?.units ?? []).map((u) => {
      const sid = u.current_session_id;
      return { group: "واحدها", t: `جلسهٔ ${u.unit_name}`, run: go(`/sessions/${sid}`) };
    });
    const files = (overview?.units ?? []).map((u) => ({ group: "پروندهٔ واحد", t: `پروندهٔ ${u.unit_name}`, run: go(`/units/${u.unit_id}`) }));
    return [...base, ...files, ...units].filter((x) => x.t.includes(q));
  }, [q, nav, overview, admin]);

  const run = (k: number) => { const it = items[k]; onClose(); it?.run(); };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") { setI((x) => Math.min(items.length - 1, x + 1)); e.preventDefault(); }
    else if (e.key === "ArrowUp") { setI((x) => Math.max(0, x - 1)); e.preventDefault(); }
    else if (e.key === "Enter") run(i);
  };
  let last = "";
  return (
    <div className="ov on" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="pal" role="dialog" aria-label="پالت فرمان" onKeyDown={onKey}>
        <input ref={input} value={q} onChange={(e) => { setQ(e.target.value); setI(0); }} placeholder="به کجا بروم؟" autoComplete="off" />
        <div style={{ maxHeight: 340, overflow: "auto", paddingBottom: 6 }}>
          {items.length === 0 && <div className="it mut">نتیجه‌ای نیست</div>}
          {items.map((it, k) => {
            const head = it.group !== last ? <div className="g">{it.group}</div> : null;
            last = it.group;
            return <div key={k}>{head}<div className={`it ${k === i ? "on" : ""}`} onClick={() => run(k)}>{it.t}</div></div>;
          })}
        </div>
        <div className="ft"><span><span className="kbd">↑</span><span className="kbd">↓</span> انتخاب</span><span><span className="kbd">Enter</span> اجرا</span><span><span className="kbd">Esc</span> بستن</span></div>
      </div>
    </div>
  );
}
