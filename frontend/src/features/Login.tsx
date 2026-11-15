import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { me, signIn } = useAuth();
  const nav = useNavigate();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (me) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try { await signIn(u.trim(), p); nav("/", { replace: true }); }
    catch (x) { setErr((x as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="login">
      <form className="card" onSubmit={submit}>
        <div className="logo" style={{ marginBottom: 18 }}><i>O</i>OKR</div>
        <h1 style={{ fontSize: 20, fontWeight: 600 }}>ورود به سامانه</h1>
        <div className="f"><label htmlFor="u">نام کاربری</label><input id="u" value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" autoFocus dir="ltr" /></div>
        <div className="f"><label htmlFor="p">رمز عبور</label><input id="p" type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" dir="ltr" /></div>
        {err && <div className="note" role="alert" style={{ color: "var(--bad)" }}>{err}</div>}
        <button className="btn" style={{ width: "100%", justifyContent: "center", marginTop: 16 }} disabled={busy || !u || !p}>{busy ? "در حال ورود…" : "ورود"}</button>
      </form>
    </div>
  );
}
