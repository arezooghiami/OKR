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

const TABS = [["setup", "راه‌اندازی"], ["units", "واحدها"], ["cycle", "چرخه و جلسه‌ها"], ["users", "کاربران"], ["roles", "نقش‌ها و مجوزها"], ["goals", "اهداف کلان"], ["import", "ورود از اکسل"], ["sim", "شبیه‌ساز دسترسی"]] as const;

export default function Admin() {
  const { tab = "setup" } = useParams();
  const { me } = useAuth();
  if (!me?.is_system_admin) return <Empty title="شما به این بخش دسترسی ندارید" hint="فقط مدیر سیستم می‌تواند تنظیمات را ببیند." />;
  const Panel = { setup: SetupPanel, units: UnitsPanel, roles: RolesPanel, cycle: CyclePanel, users: UsersPanel, goals: GoalsPanel, import: ImportPanel, sim: SimulatorPanel }[tab] ?? SetupPanel;
  return (
    <>
      <Crumb items={["مدیریت", TABS.find((t) => t[0] === tab)?.[1] ?? ""]} />
      <div className="mh"><h1>مدیریت سامانه</h1></div>
      <div className="seg" style={{ margin: "16px 0", display: "inline-flex", flexWrap: "wrap" }}>
        {TABS.map(([k, l]) => <NavLink key={k} to={`/admin/${k}`} className={tab === k ? "on" : ""} style={{ fontSize: 14 }}>{l}</NavLink>)}
      </div>
      <Panel />
    </>
  );
}
