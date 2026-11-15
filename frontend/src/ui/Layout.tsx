import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useGet } from "../api/typed";
import type { Overview } from "../api/types";
import { isOrgWide, useAuth } from "../auth/AuthContext";
import { APP_VERSION, Icon, Mark, Signature } from "./parts";
import { PeekProvider } from "./Peek";

function useTheme() {
  const [dark, setDark] = useState(() => {
    try { return (localStorage.getItem("okr.theme") ?? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark"; } catch { return false; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
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
      // e.code is the physical key, so Ctrl+K also works with the Persian keyboard layout
      if ((e.ctrlKey || e.metaKey) && e.code === "KeyK") { e.preventDefault(); setPalette(true); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const groups = navFor(isOrgWide(me), !!me?.is_system_admin, me?.home === "unit");
  const { pathname } = useLocation();

  return (
    <PeekProvider>
      <div className="shell">
        <aside className="side" aria-label="منوی اصلی">
          <NavLink className="brand" to="/">
            <Mark />
            <span><b>OKR</b><small>{cycle.data?.name ?? (cycle.status === 404 ? "بدون دورهٔ فعال" : "…")}</small></span>
          </NavLink>
          <nav>
            {groups.map((g) => (
              <div className="ng" key={g.title}>
                <div className="ngt">{g.title}</div>
                {g.items.map((it) => (
                  <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => `ni ${(it.match ? it.match(pathname) : isActive) ? "on" : ""} ${it.wide ? "wide" : ""}`}>
                    <Icon d={it.icon} /><span className="long">{it.label}</span><span className="short" aria-hidden="true">{it.short}</span>
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          <Signature />
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

type NavItem = { to: string; label: string; short: string; icon: string; end?: boolean; wide?: boolean; match?: (path: string) => boolean };
const I = {
  dash: "M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-3H4zM14 7h6V4h-6z",
  unit: "M4 21V6l8-3v18M12 21V9l8 3v9M3 21h18M8 9v.01M8 13v.01M8 17v.01M16 15v.01",
  mine: "M20 12a8 8 0 1 1-8-8M16 12a4 4 0 1 1-4-4M12 12l8-8M17 4h3v3",
  tree: "M12 3v5M5 13v-2h14v2M5 13v3M19 13v3M12 8v8M3 16h4v4H3zM17 16h4v4h-4zM10 16h4v4h-4z",
  admin: "M4 7h9M17 7h3M4 12h3M11 12h9M4 17h11M19 17h1M15 5v4M9 10v4M17 15v4",
};

/** Menu by role (docs/07 phase 2). Managers: dashboard · units · strategic goals · my KRs · admin (super admin only).
 *  Unit users: my KRs · my unit. A unit's session and its file are tabs of the unit page, not menu items. */
function navFor(orgWide: boolean, admin: boolean, unitFirst: boolean): { title: string; items: NavItem[] }[] {
  // `short` is the one-word label of the phone bottom bar
  const mine: NavItem = { to: "/my", label: "KRهای من", short: "کار من", icon: I.mine };
  const unitPage = (p: string) => p.startsWith("/unit") || p.startsWith("/sessions/") || p.startsWith("/session");
  if (!orgWide) {
    const unit: NavItem = { to: "/unit", label: "واحد من", short: "واحد", icon: I.unit, match: unitPage };
    return [{ title: "کار من", items: unitFirst ? [unit, mine] : [mine, unit] }];
  }
  const groups = [
    { title: "سازمان", items: [
      { to: "/", label: "داشبورد", short: "داشبورد", icon: I.dash, end: true },
      { to: "/units", label: "واحدها", short: "واحدها", icon: I.unit, match: unitPage },
      { to: "/goals", label: "اهداف کلان", short: "اهداف", icon: I.tree }] },
    { title: "کار من", items: [mine] },
  ];
  if (admin) groups.push({ title: "سامانه", items: [{ to: "/admin", label: "مدیریت", short: "مدیریت", icon: I.admin, wide: true, match: (p) => p.startsWith("/admin") }] });
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
          <div className="who"><b>{name}</b>{admin && <span className="faint tiny">سوپر ادمین</span>}</div>
          <button role="menuitem" className="it danger" onClick={() => { setOpen(false); onSignOut(); }}>خروج از حساب</button>
          <div className="about"><span>OKR نسخهٔ {APP_VERSION}</span><span>A.G</span></div>
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
    const base = [["داشبورد", "/"], ["واحدها", "/units"], ["KRهای من", "/my"], ["اهداف کلان", "/goals"], ...(admin ? [["مدیریت", "/admin"], ["ورود از اکسل", "/admin/import"]] : [])].map(([t, to]) => ({ group: "برو به", t, run: go(to) }));
    const units = (overview?.units ?? []).map((u) => ({ group: "واحدها", t: u.unit_name, run: go(`/unit/${u.unit_id}`) }));
    const meetings = (overview?.units ?? []).filter((u) => u.current_session_id)
      .map((u) => ({ group: "جلسهٔ پایش", t: `جلسهٔ ${u.unit_name}`, run: go(`/sessions/${u.current_session_id}`) }));
    return [...base, ...units, ...meetings].filter((x) => x.t.includes(q));
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
