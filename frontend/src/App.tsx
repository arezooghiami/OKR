import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import Layout from "./ui/Layout";
import { Skeleton } from "./ui/parts";
import Login from "./features/Login";

const Overview = lazy(() => import("./features/Overview"));
const UnitHome = lazy(() => import("./features/UnitHome"));
const SessionPage = lazy(() => import("./features/SessionPage"));
const CurrentSession = lazy(() => import("./features/CurrentSession"));
const MyKRs = lazy(() => import("./features/MyKRs"));
const KRDetailPage = lazy(() => import("./features/KRDetail"));
const Goals = lazy(() => import("./features/Goals"));
const Admin = lazy(() => import("./features/admin/Admin"));
const Dossier = lazy(() => import("./features/Dossier"));
const UnitList = lazy(() => import("./features/Dossier").then((m) => ({ default: m.UnitList })));

function Protected({ children }: { children: ReactNode }) {
  const { me, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <div className="page"><Skeleton /></div>;
  return me ? <>{children}</> : <Navigate to="/login" state={{ from: loc.pathname }} replace />;
}

/** First page by role (docs/07 phase 2): senior roles → dashboard, unit managers → their unit,
 *  everyone else → «KRهای من». */
function Home() {
  const { me } = useAuth();
  if (me?.home === "dashboard") return <Overview />;
  return <Navigate to={me?.home === "unit" ? "/unit" : "/my"} replace />;
}

function NotFound() {
  return <div className="empty"><b>صفحه‌ای پیدا نشد</b><a className="btn o" href="/" style={{ marginTop: 12 }}>بازگشت به صفحهٔ اول</a></div>;
}

export default function App() {
  return (
    <Suspense fallback={<div className="page"><Skeleton /></div>}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Protected><Layout /></Protected>}>
          <Route index element={<Home />} />
          <Route path="overview" element={<Overview />} />
          <Route path="unit/:unitId?" element={<UnitHome />} />
          <Route path="session" element={<CurrentSession />} />
          <Route path="sessions/:id" element={<SessionPage />} />
          <Route path="my" element={<MyKRs />} />
          <Route path="goals" element={<Goals />} />
          <Route path="alignment" element={<Navigate to="/goals" replace />} />
          <Route path="krs/:id" element={<KRDetailPage />} />
          <Route path="units" element={<UnitList />} />
          <Route path="units/:unitId" element={<Dossier />} />
          <Route path="admin/:tab?" element={<Admin />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
