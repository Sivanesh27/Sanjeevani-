import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { KeyRound, ScanFace, Stethoscope, Mail } from "lucide-react";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Button, Input, Logo, Tabs } from "../components/ui";
import FaceCapture, { cameraSupported } from "../components/FaceCapture";

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="grid min-h-[100dvh] lg:grid-cols-[1fr_1.05fr]">
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-600 to-[#0b4f4a] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -bottom-24 -right-16 h-96 w-96 rounded-full bg-white/10 blur-2xl" /><Logo className="[&_span]:text-white [&_span_span]:text-emerald-200" />
        <div className="relative max-w-md"><h2 className="h-display text-4xl font-extrabold leading-tight">Medicine safety that knows <em className="not-italic text-emerald-200">you</em>.</h2><p className="mt-4 text-lg text-emerald-50/85">Personalised interaction checks, diet guidance and a care team that can see the full picture.</p></div>
        <p className="relative text-sm text-emerald-50/70">Decision support only - always confirm with your doctor or pharmacist.</p></div>
      <div className="safe-t safe-b flex flex-col px-5 py-8 sm:px-10"><Link to="/" className="mb-8 lg:hidden"><Logo /></Link>
        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center"><h1 className="h-display text-3xl font-extrabold">{title}</h1><p className="mt-1.5 text-muted">{subtitle}</p><div className="mt-7">{children}</div>
          <div className="mt-8 text-center text-sm text-muted">{footer}</div></div></div></div>);
}

export default function Login({ admin = false }) {
  const { user, login, otp, faceLogin } = useAuth();
  const nav = useNavigate(); const loc = useLocation();
  const [tab, setTab] = useState("password"); const [email, setEmail] = useState(""); const [pw, setPw] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const [faceFor, setFaceFor] = useState(null); const [otpTok, setOtpTok] = useState(null); const [code, setCode] = useState("");
  const [notice, setNotice] = useState(loc.state?.notice || "");
  const canFace = !admin && cameraSupported();
  if (user) return <Navigate to={user.role === "admin" ? "/admin" : "/app"} replace />;
  const go = (u) => nav(u.role === "admin" ? "/admin" : (loc.state?.from || "/app"), { replace: true });

  const submit = async (e, face) => {
    e?.preventDefault(); setErr(""); setBusy(true);
    try {
      const d = await login(email.trim(), pw, face);
      if (d.otp_required) setOtpTok(d.otp_token); else go(d.user);
    } catch (ex) {
      if (ex.code === "face_required") setFaceFor("2fa");
      else if (ex.code === "email_not_verified") setErr("Please verify your email first - check your inbox for the link.");
      else setErr(ex.message);
    } finally { setBusy(false); }
  };
  const onFace = async ({ descriptor }) => {
    const mode = faceFor; setFaceFor(null); setBusy(true); setErr("");
    try {
      const { nonce } = await api.get("/auth/face/challenge");
      if (mode === "2fa") { await submit(null, { descriptor, nonce }); }
      else { const d = await faceLogin(email.trim(), descriptor, nonce); go(d.user); }
    } catch (ex) { setErr(ex.message === "Face not recognised" ? "We could not match your face. Try again in good light, or use your password." : ex.message); } finally { setBusy(false); }
  };

  if (faceFor) return (<AuthShell title="Face check" subtitle="Look at the camera and follow the prompt."><FaceCapture mode="verify" onDone={onFace} onCancel={() => setFaceFor(null)} /></AuthShell>);
  if (otpTok) return (
    <AuthShell title="Check your email" subtitle="We sent a 6-digit sign-in code to your doctor email.">
      <form className="space-y-4" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setErr(""); try { const d = await otp(otpTok, code); go(d.user); } catch (ex) { setErr(ex.message); } finally { setBusy(false); } }}>
        <Input label="One-time code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} className="text-center text-2xl tracking-[.4em]" />
        {err && <p className="text-sm font-medium text-sev-crit" role="alert">{err}</p>}<Button className="w-full" loading={busy} disabled={code.length !== 6}>Verify & sign in</Button></form></AuthShell>);

  return (
    <AuthShell title={admin ? "Doctor sign-in" : "Welcome back"} subtitle={admin ? "Access the clinical console." : "Sign in to your Sanjeevani AI account."}
      footer={admin ? <Link to="/login" className="font-semibold text-brand-600">Patient sign-in</Link> : <>New here? <Link to="/register" className="font-semibold text-brand-600">Create an account</Link> · <Link to="/admin/login" className="font-semibold text-brand-600">Doctor login</Link></>}>
      {notice && <div className="mb-4 rounded-xl bg-brand-50 p-3 text-sm font-medium text-brand-700">{notice}</div>}
      {canFace && <Tabs className="mb-5" value={tab} onChange={(t) => { setTab(t); setErr(""); }} tabs={[["password", "Password", KeyRound], ["face", "Face", ScanFace]]} />}
      {tab === "password" ? (
        <form className="space-y-4" onSubmit={submit}>
          <Input label="Email" type="email" autoComplete="username" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input label="Password" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required />
          {err && <p className="rounded-xl bg-sev-crit/10 p-3 text-sm font-medium text-sev-crit" role="alert">{err}</p>}
          <Button className="w-full !min-h-[50px]" loading={busy} icon={admin ? Stethoscope : undefined}>Sign in</Button>
          <div className="text-center text-sm"><Link to="/forgot" className="font-semibold text-muted hover:text-ink">Forgot password?</Link></div></form>
      ) : (
        <div className="space-y-4"><Input label="Email" type="email" autoComplete="username" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          {err && <p className="rounded-xl bg-sev-crit/10 p-3 text-sm font-medium text-sev-crit" role="alert">{err}</p>}
          <Button className="w-full !min-h-[50px]" icon={ScanFace} loading={busy} disabled={!/.+@.+\..+/.test(email)} onClick={() => setFaceFor("login")}>Continue with face</Button>
          <p className="text-center text-xs text-muted">Face sign-in is available once you have registered your face.</p></div>)}
    </AuthShell>);
}

export function Forgot() {
  const [email, setEmail] = useState(""); const [done, setDone] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  return (
    <AuthShell title="Reset password" subtitle="We will email you a secure link." footer={<Link to="/login" className="font-semibold text-brand-600">Back to sign in</Link>}>
      {done ? <div className="flex gap-3 rounded-2xl bg-brand-50 p-4 text-brand-700"><Mail className="h-5 w-5 shrink-0" /><p className="text-sm font-medium">If an account exists for that email, a reset link is on its way. It expires in 30 minutes.</p></div> :
        <form className="space-y-4" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setErr(""); try { await api.post("/auth/forgot", { email }); setDone(true); } catch (ex) { setErr(ex.message); } finally { setBusy(false); } }}>
          <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />{err && <p className="text-sm text-sev-crit">{err}</p>}<Button className="w-full" loading={busy}>Send reset link</Button></form>}
    </AuthShell>);
}

export function Reset() {
  const token = new URLSearchParams(useLocation().search).get("token") || ""; const nav = useNavigate();
  const [pw, setPw] = useState(""); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  return (
    <AuthShell title="Choose a new password" subtitle="At least 10 characters with letters and numbers.">
      <form className="space-y-4" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setErr(""); try { await api.post("/auth/reset", { token, password: pw }); nav("/login", { state: { notice: "Password updated. Please sign in." } }); } catch (ex) { setErr(ex.message); } finally { setBusy(false); } }}>
        <Input label="New password" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} required />{err && <p className="text-sm font-medium text-sev-crit">{err}</p>}<Button className="w-full" loading={busy}>Update password</Button></form></AuthShell>);
}

export function VerifyEmail() {
  const token = new URLSearchParams(useLocation().search).get("token") || ""; const [s, setS] = useState("working");
  const ran = useRef(false);
  useEffect(() => { if (ran.current) return; ran.current = true; api.post("/auth/verify-email", { token }).then(() => setS("ok")).catch(() => setS("bad")); }, [token]);
  return (<AuthShell title={s === "ok" ? "Email verified" : s === "bad" ? "Link problem" : "Verifying…"} subtitle={s === "ok" ? "Your email address is confirmed." : s === "bad" ? "This verification link is invalid or has expired." : "One moment."}
    footer={<Link to="/login" className="font-semibold text-brand-600">Go to sign in</Link>}><span /></AuthShell>);
}
