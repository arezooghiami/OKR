import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Mark, Signature } from "../ui/parts";

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
      <main className="login-box">
        <div className="login-brand"><Mark /><span><b>OKR</b><small>سامانهٔ اهداف و نتایج کلیدی</small></span></div>
        <form className="card" onSubmit={submit}>
          <h1>ورود به سامانه</h1>
          <p className="lead">پیشرفت نتایج کلیدی را در چند ثانیه ثبت کنید و وضعیت هر واحد را همان لحظه ببینید.</p>
          <div className="f"><label htmlFor="u">نام کاربری</label><input id="u" value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" autoFocus dir="ltr" /></div>
          <div className="f"><label htmlFor="p">رمز عبور</label><input id="p" type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" dir="ltr" /></div>
          {err && <div className="note err-box" role="alert">{err}</div>}
          <button className="btn" style={{ width: "100%", marginTop: 20 }} disabled={busy || !u || !p}>{busy ? "در حال ورود…" : "ورود"}</button>
        </form>
      </main>
      <Signature />
    </div>
  );
}
