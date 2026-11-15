import { Link } from "react-router-dom";
import { useGet } from "../api/typed";
import { tpLabel } from "../domain/format";

export type UnitTab = "table" | "session" | "history";

/** One unit, three views (docs/07 phase 2): its objectives table, its review session, and its file with history.
 *  The session tab opens the unit's open session: the first one not yet held, otherwise the last one. */
export default function UnitTabs({ unitId, active, cycleId, sessionLabel }: {
  unitId: string; active: UnitTab; cycleId?: string | null; sessionLabel?: string;
}) {
  const sessions = useGet("/api/v1/units/{unit_id}/sessions", { unit_id: unitId }, { query: { cycle_id: cycleId ?? null } });
  const list = sessions.data ?? [];
  const current = list.find((s) => s.status !== "held") ?? list[list.length - 1];
  const q = cycleId ? `?cycle=${cycleId}` : "";
  const tabs: { key: UnitTab; label: string; to: string | null }[] = [
    { key: "table", label: "اهداف و نتایج کلیدی", to: `/unit/${unitId}${q}` },
    { key: "session", label: active === "session" && sessionLabel ? `جلسهٔ ${sessionLabel}` : current ? `جلسهٔ ${tpLabel(current.time_point)}` : "جلسهٔ پایش",
      to: current ? `/sessions/${current.id}` : null },
    { key: "history", label: "پرونده و تاریخچه", to: `/units/${unitId}${q}` },
  ];
  return (
    <nav className="utabs" aria-label="بخش‌های واحد">
      {tabs.map((t) => t.key === active
        ? <span key={t.key} className="on" aria-current="page">{t.label}</span>
        : t.to ? <Link key={t.key} to={t.to}>{t.label}</Link> : <span key={t.key} className="off">{t.label}</span>)}
    </nav>
  );
}
