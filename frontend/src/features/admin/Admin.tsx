import { NavLink, useParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { Crumb, Empty } from "../../ui/parts";
import CyclePanel from "./CyclePanel";
import UnitsPanel from "./UnitsPanel";
import GoalsPanel from "./GoalsPanel";
import ImportPanel from "./ImportPanel";
import RolesPanel from "./RolesPanel";
import SetupPanel from "./SetupPanel";
import { SimulatorPanel, UsersPanel } from "./UsersPanels";

/** The super admin's panel: every definition and data entry happens here (docs/07 §7). */
const TABS = [["setup", "راه‌اندازی"], ["units", "واحدها"], ["cycle", "دوره و جلسه‌ها"], ["users", "کاربران"], ["access", "دسترسی‌ها"], ["goals", "اهداف کلان"], ["import", "ورود از اکسل"]] as const;

/** Role matrix, per-unit exceptions and «what can this user do?» on one tab. */
function AccessPanel() {
  return (
    <>
      <RolesPanel />
      <div className="sec"><h2>شبیه‌ساز: این کاربر چه کاری می‌تواند بکند؟</h2></div>
      <SimulatorPanel />
    </>
  );
}

export default function Admin() {
  const { tab = "setup" } = useParams();
  const { me } = useAuth();
  if (!me?.is_system_admin) return <Empty icon="lock" title="شما به این بخش دسترسی ندارید" hint="فقط سوپر ادمین می‌تواند تنظیمات را ببیند." />;
  const Panel = { setup: SetupPanel, units: UnitsPanel, access: AccessPanel, roles: AccessPanel, sim: AccessPanel, cycle: CyclePanel, users: UsersPanel, goals: GoalsPanel, import: ImportPanel }[tab] ?? SetupPanel;
  const current = tab === "roles" || tab === "sim" ? "access" : tab;
  return (
    <>
      <Crumb items={["مدیریت", TABS.find((t) => t[0] === current)?.[1] ?? ""]} />
      <div className="mh"><h1>مدیریت سامانه</h1></div>
      <div className="seg" style={{ margin: "16px 0", display: "inline-flex", flexWrap: "wrap" }}>
        {TABS.map(([k, l]) => <NavLink key={k} to={`/admin/${k}`} className={current === k ? "on" : ""}>{l}</NavLink>)}
      </div>
      <Panel />
    </>
  );
}
