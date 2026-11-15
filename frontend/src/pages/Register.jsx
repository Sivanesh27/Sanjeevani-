import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, ScanFace } from "lucide-react";
import { useAuth } from "../lib/auth";
import { Button, Input, Select, Switch, Logo } from "../components/ui";
import FaceCapture, { cameraSupported } from "../components/FaceCapture";
import { clean, cx, num } from "../lib/utils";

const REQUIRE_FACE = import.meta.env.VITE_REQUIRE_FACE !== "false";
const STEPS = ["Account", "About you", "Health", "Face"];

export default function Register() {
  const { user, register } = useAuth(); const nav = useNavigate();
  const [step, setStep] = useState(0); const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [errs, setErrs] = useState({});
  const [f, setF] = useState({ email: "", password: "", confirm: "", full_name: "", dob: "", sex: "", phone: "", city: "", state: "", country: "India", address: "", emergency_contact_name: "", emergency_contact_phone: "",
    height_cm: "", weight_kg: "", blood_group: "", smoker: "", alcohol: "", diet_preference: "", pregnant: false, consent: false });
  const [face, setFace] = useState(null); const [verified, setVerified] = useState(false);
  if (user) return <Navigate to="/app" replace />;
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e?.target ? e.target.value : e }));
  const faceOk = cameraSupported();

  const validate = () => {
    const e = {};
    if (step === 0) {
      if (!/^\S+@\S+\.\S+$/.test(f.email)) e.email = "Enter a valid email";
      if (f.password.length < 10 || !/[A-Za-z]/.test(f.password) || !/\d/.test(f.password)) e.password = "At least 10 characters with letters and numbers";
      if (f.password !== f.confirm) e.confirm = "Passwords do not match";
    }
    if (step === 1) {
      if (!f.full_name.trim()) e.full_name = "Required"; if (!f.dob) e.dob = "Required"; if (!f.sex) e.sex = "Required"; if (!f.phone.trim()) e.phone = "Required";
    }
    if (step === 2) { if (!f.height_cm) e.height_cm = "Required"; if (!f.weight_kg) e.weight_kg = "Required"; }
    setErrs(e); return !Object.keys(e).length;
  };
  const next = () => { if (validate()) setStep((s) => s + 1); };

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const profile = clean({ full_name: f.full_name.trim(), dob: f.dob, sex: f.sex, phone: f.phone, city: f.city, state: f.state, country: f.country, address: f.address, emergency_contact_name: f.emergency_contact_name,
        emergency_contact_phone: f.emergency_contact_phone, height_cm: num(f.height_cm), weight_kg: num(f.weight_kg), blood_group: f.blood_group, smoker: f.smoker, alcohol: f.alcohol, diet_preference: f.diet_preference, pregnant: f.sex === "female" ? f.pregnant : false });
      const d = await register({ email: f.email.trim(), password: f.password, profile, consent: f.consent, ...(face ? { face } : {}) });
      if (d.verification_required) nav("/login", { state: { notice: "Account created. Please verify your email, then sign in." } }); else nav("/app/medical", { state: { welcome: true } });
    } catch (ex) { setErr(ex.message); } finally { setBusy(false); }
  };

  return (
    <div className="min-h-[100dvh] bg-bg">
      <header className="safe-t mx-auto flex max-w-2xl items-center justify-between px-5 py-5"><Link to="/"><Logo /></Link><Link to="/login" className="text-sm font-semibold text-brand-600">Sign in</Link></header>
      <main className="mx-auto max-w-2xl px-5 pb-16">
        <ol className="mb-7 flex items-center gap-2">{STEPS.map((s, i) => (<li key={s} className="flex flex-1 items-center gap-2"><span className={cx("grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-bold", i < step ? "bg-brand-600 text-onbrand" : i === step ? "border-2 border-brand-600 text-brand-600" : "bg-raised text-muted")}>{i < step ? <Check className="h-4 w-4" /> : i + 1}</span>
          <span className={cx("hidden text-sm font-semibold sm:block", i === step ? "text-ink" : "text-muted")}>{s}</span>{i < STEPS.length - 1 && <span className="h-px flex-1 bg-line" />}</li>))}</ol>
        <div className="card fade-up p-5 sm:p-8" key={step}>
          {step === 0 && (<div className="space-y-4"><div><h1 className="h-display text-2xl font-extrabold">Create your account</h1><p className="text-muted">Your email and a strong password.</p></div>
            <Input label="Email" type="email" autoComplete="email" inputMode="email" value={f.email} onChange={set("email")} error={errs.email} />
            <Input label="Password" type="password" autoComplete="new-password" value={f.password} onChange={set("password")} error={errs.password} hint="10+ characters, letters and numbers" />
            <Input label="Confirm password" type="password" autoComplete="new-password" value={f.confirm} onChange={set("confirm")} error={errs.confirm} /></div>)}
          {step === 1 && (<div className="space-y-4"><div><h1 className="h-display text-2xl font-extrabold">About you</h1><p className="text-muted">Used to personalise your safety checks.</p></div>
            <Input label="Full name" autoComplete="name" value={f.full_name} onChange={set("full_name")} error={errs.full_name} />
            <div className="grid grid-cols-2 gap-4"><Input label="Date of birth" type="date" value={f.dob} onChange={set("dob")} error={errs.dob} max={new Date().toISOString().slice(0, 10)} />
              <Select label="Sex" value={f.sex} onChange={set("sex")} error={errs.sex} placeholder="Select" options={[["male", "Male"], ["female", "Female"], ["other", "Other"]]} /></div>
            <Input label="Mobile number" type="tel" inputMode="tel" autoComplete="tel" value={f.phone} onChange={set("phone")} error={errs.phone} />
            <Input label="Address" autoComplete="street-address" value={f.address} onChange={set("address")} />
            <div className="grid grid-cols-3 gap-3"><Input label="City" value={f.city} onChange={set("city")} /><Input label="State" value={f.state} onChange={set("state")} /><Input label="Country" value={f.country} onChange={set("country")} /></div>
            <div className="grid grid-cols-2 gap-4"><Input label="Emergency contact" value={f.emergency_contact_name} onChange={set("emergency_contact_name")} /><Input label="Their phone" type="tel" inputMode="tel" value={f.emergency_contact_phone} onChange={set("emergency_contact_phone")} /></div></div>)}
          {step === 2 && (<div className="space-y-4"><div><h1 className="h-display text-2xl font-extrabold">Health basics</h1><p className="text-muted">You can add conditions, medicines and reports after sign-up.</p></div>
            <div className="grid grid-cols-2 gap-4"><Input label="Height (cm)" type="number" inputMode="decimal" value={f.height_cm} onChange={set("height_cm")} error={errs.height_cm} /><Input label="Weight (kg)" type="number" inputMode="decimal" value={f.weight_kg} onChange={set("weight_kg")} error={errs.weight_kg} /></div>
            <Select label="Blood group" value={f.blood_group} onChange={set("blood_group")} placeholder="Select (optional)" options={["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]} />
            <div className="grid grid-cols-2 gap-4"><Select label="Smoking" value={f.smoker} onChange={set("smoker")} placeholder="Select" options={[["never", "Never"], ["former", "Former"], ["current", "Current"]]} />
              <Select label="Alcohol" value={f.alcohol} onChange={set("alcohol")} placeholder="Select" options={[["none", "None"], ["occasional", "Occasional"], ["moderate", "Moderate"], ["heavy", "Heavy"]]} /></div>
            <Select label="Diet" value={f.diet_preference} onChange={set("diet_preference")} placeholder="Select" options={[["vegetarian", "Vegetarian"], ["non_vegetarian", "Non-vegetarian"], ["eggetarian", "Eggetarian"], ["vegan", "Vegan"]]} />
            {f.sex === "female" && <Switch label="I am pregnant" checked={f.pregnant} onChange={set("pregnant")} />}</div>)}
          {step === 3 && (<div className="space-y-5"><div><h1 className="h-display text-2xl font-extrabold">Verify it is you</h1><p className="text-muted">A quick live face capture lets you sign in with your face later, and helps your care team confirm your identity.</p></div>
            {verified ? <div className="flex items-center gap-3 rounded-2xl bg-brand-50 p-4 text-brand-700"><Check className="h-6 w-6" /><div className="font-semibold">Face captured{face?.photo && <img src={face.photo} alt="" className="mt-2 h-20 w-16 rounded-lg object-cover" />}</div><button className="ml-auto text-sm font-semibold underline" onClick={() => { setVerified(false); setFace(null); }}>Retake</button></div>
              : faceOk ? <FaceCapture mode="enroll" onDone={(d) => { setFace(d); setVerified(true); }} />
              : <div className="rounded-2xl bg-sev-mod/10 p-4 text-sm"><b>Camera not available.</b> Open this site over HTTPS in a browser with camera access.{!REQUIRE_FACE && " You can continue without it and add your face later in Settings."}</div>}
            <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-line p-4 text-sm"><input type="checkbox" checked={f.consent} onChange={(e) => setF((s) => ({ ...s, consent: e.target.checked }))} className="mt-0.5 h-5 w-5 accent-[rgb(var(--b600))]" />
              <span>I agree to the processing of my health and face data to provide personalised medicine-safety guidance. I understand this tool does not replace professional medical advice, and that I can export or delete my data at any time.</span></label>
            {err && <p className="rounded-xl bg-sev-crit/10 p-3 text-sm font-medium text-sev-crit" role="alert">{err}</p>}</div>)}
          <div className="mt-7 flex items-center justify-between gap-3">
            {step > 0 ? <Button variant="ghost" icon={ArrowLeft} onClick={() => setStep(step - 1)}>Back</Button> : <span />}
            {step < 3 ? <Button onClick={next} className="min-w-[130px]">Continue<ArrowRight className="h-4 w-4" /></Button>
              : <Button icon={ScanFace} loading={busy} disabled={!f.consent || (REQUIRE_FACE && !face)} onClick={submit} className="min-w-[160px]">Create account</Button>}</div>
        </div>
      </main></div>);
}
