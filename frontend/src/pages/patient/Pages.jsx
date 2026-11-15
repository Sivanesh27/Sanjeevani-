import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Activity, ArrowRight, CheckCircle2, Circle, Download, FileText, HeartPulse, KeyRound, LogOut, Pill as PillIcon, ScanFace, ShieldAlert, Trash2, Sparkles } from "lucide-react";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Button, Card, CardHeader, Confirm, Input, LevelBadge, Modal, PageLoader, Stat, Switch, useToast } from "../../components/ui";
import ProfileForm from "../../components/ProfileForm";
import Medical from "../../components/Medical";
import Analysis from "../../components/Analysis";
import FaceCapture, { cameraSupported } from "../../components/FaceCapture";
import { downloadJSON, fmtDate, lvl } from "../../lib/utils";
import { useNavigate } from "react-router-dom";

const B = "/patient";

export function Dashboard() {
  const { user } = useAuth(); const [s, setS] = useState(null); const loc = useLocation(); const toast = useToast();
  useEffect(() => { api.get(`${B}/summary`).then(setS).catch((e) => toast.error(e.message)); }, []); // eslint-disable-line
  if (!s) return <PageLoader />;
  const c = s.counts, p = s.profile, la = s.latest_analysis;
  const steps = [["Complete your profile", p.completeness >= 70, "/app/profile", `${p.completeness}% complete`], ["Add your medicines", c.medications > 0, "/app/medical", `${c.medications} added`], ["Run your first analysis", c.analyses > 0, "/app/analysis", la ? "Done" : "Takes a few seconds"]];
  const first = (user?.display_name || "").split(" ")[0] || "there";
  return (
    <div className="space-y-6">
      <div className="fade-up"><h1 className="h-display text-3xl font-extrabold">Hello, {first}</h1><p className="text-muted">{loc.state?.welcome ? "Welcome! Let's set up your record in three quick steps." : "Here is your medicine-safety overview."}</p></div>
      {la ? (
        <Card className="fade-up overflow-hidden"><div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6"><div className="flex items-center gap-4">
          <div className={`grid h-16 w-16 place-items-center rounded-2xl border text-2xl font-extrabold ${lvl(la.level).soft} ${lvl(la.level).text}`}>{la.score}</div>
          <div><div className="text-sm text-muted">Latest analysis · {fmtDate(la.created_at)}</div><div className="mt-0.5 flex items-center gap-2"><span className="h-display text-xl font-bold">Overall risk</span><LevelBadge level={la.level} /></div></div></div>
          <div className="flex gap-2"><Link to="/app/analysis" className="btn btn-primary">View details<ArrowRight className="h-4 w-4" /></Link></div></div></Card>
      ) : (
        <Card className="fade-up border-brand-500/30 bg-gradient-to-br from-brand-50 to-surface p-6"><div className="flex items-start gap-4"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-brand-600 text-onbrand"><Sparkles className="h-6 w-6" /></span>
          <div><h2 className="h-display text-xl font-bold">Get your personalised safety check</h2><p className="mt-1 text-muted">Add your medicines and we will check every combination against your health profile.</p>
            <Link to="/app/medical" className="btn btn-primary mt-4">Add medicines<ArrowRight className="h-4 w-4" /></Link></div></div></Card>)}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><Stat label="Medicines" value={c.medications} icon={PillIcon} /><Stat label="Conditions" value={c.conditions} icon={HeartPulse} /><Stat label="Allergies" value={c.allergies} icon={ShieldAlert} /><Stat label="Reports" value={c.documents} icon={FileText} /></div>
      <Card><CardHeader title="Getting set up" subtitle="Three steps to a complete picture" />
        <ul className="divide-y divide-line">{steps.map(([t, done, to, sub]) => (<li key={t}><Link to={to} className="flex min-h-[64px] items-center gap-3 px-5 py-3 hover:bg-raised">
          {done ? <CheckCircle2 className="h-6 w-6 text-sev-low" /> : <Circle className="h-6 w-6 text-line" />}<div className="flex-1"><div className="font-semibold">{t}</div><div className="text-sm text-muted">{sub}</div></div><ArrowRight className="h-4 w-4 text-muted" /></Link></li>))}</ul></Card>
    </div>);
}

export const ProfilePage = () => (<div className="space-y-5"><div><h1 className="h-display text-3xl font-extrabold">My profile</h1><p className="text-muted">Everything here is editable and used to personalise your results.</p></div><ProfileForm base={B} /></div>);
export const MedicalPage = () => (<div className="space-y-5"><div><h1 className="h-display text-3xl font-extrabold">My health record</h1><p className="text-muted">Medicines, conditions, allergies and reports.</p></div><Medical base={B} /></div>);
export const AnalysisPage = () => <Analysis base={B} />;

export function Settings() {
  const { user, setUser, refresh, logout } = useAuth(); const toast = useToast(); const nav = useNavigate();
  const [pw, setPw] = useState({ current_password: "", new_password: "" }); const [busy, setBusy] = useState(false);
  const [face, setFace] = useState(null); const [reface, setReface] = useState(false); const [del, setDel] = useState(false); const [delPw, setDelPw] = useState("");
  const loadFace = () => api.get(`${B}/face`).then(setFace).catch(() => {});
  useEffect(() => { loadFace(); }, []);
  const out = async () => { await logout(); nav("/login"); };
  return (
    <div className="space-y-5">
      <div><h1 className="h-display text-3xl font-extrabold">Settings</h1><p className="text-muted">{user.email}</p></div>
      <Card><CardHeader icon={ScanFace} title="Face verification" subtitle="Sign in with your face and add a second check to password sign-in" />
        <div className="space-y-5 p-5"><div className="flex items-center gap-4">{face?.photo ? <img src={face.photo} alt="Your registered face" className="h-24 w-[72px] rounded-xl object-cover" /> : <div className="grid h-24 w-[72px] place-items-center rounded-xl bg-raised text-muted"><ScanFace className="h-7 w-7" /></div>}
          <div className="text-sm"><div className="font-semibold">{face?.enrolled ? "Face registered" : "No face registered"}</div><div className="text-muted">{face?.enrolled ? `Since ${fmtDate(face.enrolled_at)}` : "Register to enable face sign-in."}</div>
            <Button variant="secondary" className="mt-3 !min-h-[40px]" disabled={!cameraSupported()} onClick={() => setReface(true)}>{face?.enrolled ? "Update my face" : "Register face"}</Button></div></div>
          <Switch label="Require face check at password sign-in" hint="Adds a second step so a stolen password alone is not enough." checked={user.face_2fa} disabled={!user.face_enrolled}
            onChange={async (v) => { try { const d = await api.patch("/auth/security", { face_2fa: v }); setUser(d.user); toast.success(v ? "Face check required at sign-in" : "Face check turned off"); } catch (e) { toast.error(e.message); } }} /></div></Card>
      <Card><CardHeader icon={KeyRound} title="Password" />
        <form className="grid gap-4 p-5 sm:grid-cols-2" onSubmit={async (e) => { e.preventDefault(); setBusy(true); try { await api.post("/auth/change-password", pw); setPw({ current_password: "", new_password: "" }); toast.success("Password changed. Other devices were signed out."); } catch (ex) { toast.error(ex.message); } finally { setBusy(false); } }}>
          <Input label="Current password" type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} required />
          <Input label="New password" type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} required hint="10+ characters, letters and numbers" />
          <div className="sm:col-span-2"><Button loading={busy}>Change password</Button></div></form></Card>
      <Card><CardHeader icon={LogOut} title="Sessions" /><div className="flex flex-col gap-2 p-5 sm:flex-row"><Button variant="secondary" onClick={out}>Sign out</Button>
        <Button variant="secondary" onClick={async () => { await api.post("/auth/logout-all"); await refresh(); nav("/login"); }}>Sign out on all devices</Button></div></Card>
      <Card><CardHeader icon={Download} title="Your data" subtitle="You own your health data" /><div className="flex flex-col gap-2 p-5 sm:flex-row">
        <Button variant="secondary" icon={Download} onClick={async () => downloadJSON("sanjeevani-my-data.json", await api.get(`${B}/export`))}>Download my data (JSON)</Button>
        <Button variant="secondary" className="!text-sev-crit" icon={Trash2} onClick={() => setDel(true)}>Delete my account</Button></div></Card>
      <Modal open={reface} onClose={() => setReface(false)} title="Update your face"><FaceCapture mode="enroll" compact onCancel={() => setReface(false)}
        onDone={async (d) => { try { await api.put(`${B}/face`, d); setReface(false); toast.success("Face updated"); await refresh(); loadFace(); } catch (e) { toast.error(e.message); setReface(false); } }} /></Modal>
      <Confirm open={del} danger title="Delete your account?" confirmLabel="Delete everything" message="This permanently erases your profile, medicines, reports, analyses and face data. It cannot be undone." onClose={() => setDel(false)}
        onConfirm={async () => { try { await api.del("/auth/me", { password: delPw }); setUser(null); nav("/"); } catch (e) { toast.error(e.message); } }}>
        <div className="mt-4"><Input label="Confirm with your password" type="password" value={delPw} onChange={(e) => setDelPw(e.target.value)} /></div></Confirm>
    </div>);
}
