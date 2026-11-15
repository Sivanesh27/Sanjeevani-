import { Link } from "react-router-dom";
import { ArrowRight, ScanFace, ShieldCheck, FileText, Apple, Activity, Lock, Stethoscope, HeartPulse, CheckCircle2 } from "lucide-react";
import { Logo } from "../components/ui";

const features = [
  [Activity, "Personalised interaction check", "Risk is scored for your age, kidney and liver function, conditions, allergies, labs and lifestyle - not a one-size-fits-all list."],
  [FileText, "Understands your reports", "Upload a prescription or lab report. Medical NER finds medicines (including Indian brand names), conditions, allergies and test values."],
  [Apple, "Diet & lifestyle guidance", "Foods to avoid, limit or keep consistent, and when to take each medicine - tailored to what you actually take."],
  [ScanFace, "Face sign-in on your phone", "Register with a live face capture and sign in with a quick liveness check. Password sign-in always works too."],
  [Lock, "Private by design", "Your records are isolated to your account, encrypted at rest, and every doctor access is written to an audit log."],
  [Stethoscope, "Built with doctors in the loop", "Your care team can review your record and analyses, update data and tune the knowledge base."],
];

export default function Landing() {
  return (
    <div className="min-h-[100dvh] bg-bg">
      <header className="safe-t mx-auto flex max-w-6xl items-center justify-between px-5 py-5"><Logo />
        <nav className="flex items-center gap-2"><Link to="/admin/login" className="btn btn-ghost hidden text-sm sm:inline-flex">Doctor login</Link><Link to="/login" className="btn btn-secondary">Sign in</Link><Link to="/register" className="btn btn-primary hidden sm:inline-flex">Create account</Link></nav></header>
      <section className="relative mx-auto max-w-6xl px-5 pb-16 pt-8 sm:pt-16">
        <div className="pointer-events-none absolute -top-20 right-0 h-72 w-72 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="relative grid items-center gap-12 lg:grid-cols-[1.1fr_.9fr]">
          <div className="fade-up"><span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs font-semibold text-brand-700"><HeartPulse className="h-3.5 w-3.5" />Medicine safety, made personal</span>
            <h1 className="h-display mt-5 text-[2.5rem] font-extrabold leading-[1.05] sm:text-6xl">Know how your medicines work <span className="text-brand-600">together</span> - in your body.</h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">Sanjeevani AI checks drug-to-drug interactions against your own health profile, explains them in plain language, and gives you a diet and monitoring plan you can take to your doctor.</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row"><Link to="/register" className="btn btn-primary !min-h-[52px] px-6 text-base">Get started free<ArrowRight className="h-5 w-5" /></Link><Link to="/login" className="btn btn-secondary !min-h-[52px] px-6 text-base">I already have an account</Link></div>
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">{["Works on phone & desktop", "Encrypted records", "Face or password sign-in"].map((t) => <li key={t} className="flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4 text-brand-600" />{t}</li>)}</ul></div>
          <div className="fade-up relative" style={{ animationDelay: ".1s" }}>
            <div className="card overflow-hidden p-0 shadow-pop"><div className="border-b border-line bg-brand-50 px-5 py-3 text-sm font-semibold text-brand-700">Warfarin + Ibuprofen · for Mr. Rao, 72</div>
              <div className="space-y-4 p-5"><div className="flex items-end justify-between"><div><div className="h-display text-5xl font-extrabold text-sev-crit">91</div><div className="text-xs font-semibold uppercase tracking-wider text-muted">personal risk score</div></div><span className="rounded-full border border-sev-crit/30 bg-sev-crit/10 px-3 py-1 text-sm font-bold text-sev-crit">Critical</span></div>
                <div className="h-2 overflow-hidden rounded-full bg-raised"><div className="h-full w-[91%] rounded-full bg-sev-crit" /></div>
                <ul className="space-y-2 text-sm">{[["+8", "Age 72"], ["+15", "Kidney function (eGFR 37)"], ["+12", "Past stomach ulcer"], ["+18", "INR already 3.4"]].map(([p, t]) => <li key={t} className="flex gap-2"><span className="rounded bg-brand-50 px-1.5 text-xs font-bold text-brand-700">{p}</span>{t}</li>)}</ul>
                <p className="rounded-xl bg-raised p-3 text-xs text-muted">Illustrative example. Base rating for a typical patient: Major (62).</p></div></div></div></div></section>
      <section className="border-y border-line bg-surface"><div className="mx-auto grid max-w-6xl gap-px bg-line sm:grid-cols-2 lg:grid-cols-3">{features.map(([Icon, t, d]) => (
        <div key={t} className="bg-surface p-7"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-brand-50 text-brand-600"><Icon className="h-5 w-5" /></span><h3 className="h-display mt-4 text-lg font-bold">{t}</h3><p className="mt-1.5 text-[15px] leading-relaxed text-muted">{d}</p></div>))}</div></section>
      <section className="mx-auto max-w-6xl px-5 py-16"><h2 className="h-display text-center text-3xl font-extrabold">How it works</h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-3">{[["1", "Create your profile", "Register with your email and a live face capture, and tell us about yourself."], ["2", "Add your medicines", "Type them in or upload a report - review what we found before anything is saved."], ["3", "Get your plan", "See interactions ranked for you, with diet guidance and questions for your doctor."]].map(([n, t, d]) => (
          <div key={n} className="card p-6"><span className="h-display grid h-10 w-10 place-items-center rounded-xl bg-brand-600 text-lg font-extrabold text-onbrand">{n}</span><h3 className="h-display mt-4 text-lg font-bold">{t}</h3><p className="mt-1 text-[15px] text-muted">{d}</p></div>))}</div></section>
      <footer className="border-t border-line bg-surface"><div className="mx-auto max-w-6xl space-y-3 px-5 py-8 text-sm text-muted"><div className="flex items-center gap-2 font-semibold text-ink"><ShieldCheck className="h-4 w-4 text-brand-600" />Important</div>
        <p>Sanjeevani AI is a decision-support aid, not medical advice, diagnosis or treatment. Never start, stop or change a medicine without speaking to your doctor or pharmacist. “No interaction found” means none is recorded in our database - it does not prove a combination is safe.</p><p>© Sanjeevani AI</p></div></footer>
    </div>);
}
