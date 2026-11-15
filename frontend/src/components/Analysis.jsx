import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, Apple, ChevronDown, ClipboardList, FlaskConical, HelpCircle, Info, Printer, ShieldAlert, Sparkles, Ban, Gauge, Clock, Leaf, ThumbsUp, StickyNote } from "lucide-react";
import { api } from "../lib/api";
import { Button, Card, CardHeader, EmptyState, LevelBadge, PageLoader, Pill, useToast } from "./ui";
import { cx, fmtDateTime, lvl } from "../lib/utils";

export function Gauge180({ score, level }) {
  const r = 70, c = Math.PI * r, off = c * (1 - Math.min(100, score) / 100);
  const color = { Critical: "rgb(var(--crit))", High: "rgb(var(--high))", Moderate: "rgb(var(--mod))", Low: "rgb(var(--low))", None: "rgb(var(--low))" }[level] || "rgb(var(--low))";
  return (
    <div className="relative mx-auto w-[220px]">
      <svg viewBox="0 0 180 100" className="w-full" role="img" aria-label={`Risk score ${score} out of 100, ${level}`}>
        <path d="M 20 90 A 70 70 0 0 1 160 90" fill="none" stroke="rgb(var(--line))" strokeWidth="14" strokeLinecap="round" />
        <path d="M 20 90 A 70 70 0 0 1 160 90" fill="none" stroke={color} strokeWidth="14" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off} style={{ transition: "stroke-dashoffset .9s ease" }} />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center"><div className="h-display text-5xl font-extrabold leading-none">{score}</div><div className="mt-1 text-xs font-semibold uppercase tracking-wider text-muted">risk score</div></div>
    </div>);
}

function Bar({ score }) { const l = lvl(score >= 75 ? "Critical" : score >= 55 ? "High" : score >= 30 ? "Moderate" : "Low"); return <div className="h-1.5 w-full overflow-hidden rounded-full bg-raised"><div className={cx("h-full rounded-full", l.bar)} style={{ width: `${Math.max(4, score)}%` }} /></div>; }

function Interaction({ r, open: o }) {
  return (
    <details open={o} className={cx("group rounded-2xl border", lvl(r.level).soft)}>
      <summary className="flex cursor-pointer list-none items-start gap-3 p-4">
        <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="h-display text-[16px] font-bold">{r.drug_a} + {r.drug_b}</span><LevelBadge level={r.level} />
          {r.source === "model_estimate" && <Pill>unverified estimate</Pill>}</div>
          <p className="mt-1.5 text-[14.5px] leading-relaxed text-ink/85">{r.summary}</p><div className="mt-3 flex items-center gap-3"><Bar score={r.score} /><span className="w-12 shrink-0 text-right text-xs font-bold text-muted">{r.score}/100</span></div></div>
        <ChevronDown className="mt-1 h-5 w-5 shrink-0 text-muted transition group-open:rotate-180" />
      </summary>
      <div className="space-y-4 border-t border-line/70 bg-surface/60 px-4 py-4 text-sm">
        {r.factors.length > 0 && <div><div className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-muted"><Gauge className="h-3.5 w-3.5" />Why this is rated {r.level.toLowerCase()} for you</div>
          <ul className="space-y-1.5">{r.factors.map((f, i) => (<li key={i} className="flex gap-2"><span className="mt-0.5 h-fit shrink-0 rounded bg-brand-50 px-1.5 text-xs font-bold text-brand-700">+{f.points}</span><span><b>{f.label}.</b> <span className="text-muted">{f.detail}</span></span></li>))}</ul></div>}
        <Detail title="What happens" text={r.effect} /><Detail title="How it works" text={r.mechanism} /><Detail title="What to do" text={r.management} />
        {r.diet_advice && !/^no (specific|diet)/i.test(r.diet_advice) && <Detail title="Diet & lifestyle" text={r.diet_advice} />}
      </div>
    </details>);
}
const Detail = ({ title, text }) => text ? <div><div className="text-xs font-bold uppercase tracking-wide text-muted">{title}</div><p className="mt-0.5 leading-relaxed">{text}</p></div> : null;

function AlertCard({ a, kind }) {
  return (<div className={cx("rounded-2xl border p-4", lvl(a.level).soft)}><div className="flex flex-wrap items-center gap-2"><ShieldAlert className={cx("h-4 w-4", lvl(a.level).text)} /><b>{a.drug}</b><LevelBadge level={a.level} />
    <span className="text-xs font-semibold text-muted">{kind === "allergy" ? `allergy: ${a.allergen}` : a.condition}</span></div>
    <p className="mt-1.5 text-sm">{a.message}</p><p className="mt-1 text-sm font-medium text-ink/80">{a.advice}</p></div>);
}

const DIET = { avoid: ["Avoid", Ban, "text-sev-crit"], limit: ["Limit", AlertTriangle, "text-sev-high"], keep_consistent: ["Keep consistent", Leaf, "text-brand-600"], timing: ["Timing matters", Clock, "text-sev-mod"], recommended: ["Good choices", ThumbsUp, "text-sev-low"], notes: ["Also note", StickyNote, "text-muted"] };

export function AnalysisResult({ a }) {
  const l = lvl(a.overall.level); const p = a.patient; const c = a.overall.counts;
  return (
    <div className="space-y-5">
      <Card className="overflow-hidden"><div className="grid gap-6 p-5 sm:grid-cols-[240px_1fr] sm:p-7">
        <div><Gauge180 score={a.overall.score} level={a.overall.level} /><div className="mt-3 text-center"><LevelBadge level={a.overall.level} className="!text-sm !px-3 !py-1" /></div></div>
        <div className="flex flex-col justify-center gap-4"><div><h2 className="h-display text-xl font-extrabold leading-snug sm:text-2xl">{a.overall.headline}</h2>
          <p className="mt-1 text-sm text-muted">Personalised on {fmtDateTime(a.created_at)} · {a.overall.n_assessed} of {a.overall.n_medicines} medicines assessed</p></div>
          <div className="flex flex-wrap gap-2">{["Critical", "High", "Moderate", "Low"].filter((k) => c[k]).map((k) => <span key={k} className={cx("rounded-full border px-3 py-1 text-sm font-semibold", lvl(k).soft, lvl(k).text)}>{c[k]} {k.toLowerCase()}</span>)}
            {!Object.values(c).some(Boolean) && <span className="text-sm text-muted">No confirmed interactions between your medicines.</span>}</div>
          <div className="flex flex-wrap gap-1.5 text-xs">{p.age != null && <Pill>age {p.age}</Pill>}{p.egfr != null && <Pill>eGFR {p.egfr}{p.egfr_estimated ? " (est.)" : ""}</Pill>}{p.bmi && <Pill>BMI {p.bmi}</Pill>}
            {p.derived_conditions.map((d) => <Pill key={d.key} className="!bg-brand-50 !text-brand-700">{d.label} ({d.why})</Pill>)}</div></div></div></Card>

      {(a.allergy_alerts.length > 0 || a.precautions.length > 0) && <section className="space-y-3"><h3 className="h-display flex items-center gap-2 text-lg font-bold"><ShieldAlert className="h-5 w-5 text-sev-high" />Alerts for your health profile</h3>
        {a.allergy_alerts.map((x, i) => <AlertCard key={"a" + i} a={x} kind="allergy" />)}{a.precautions.map((x, i) => <AlertCard key={"p" + i} a={x} />)}</section>}

      <section className="space-y-3"><h3 className="h-display flex items-center gap-2 text-lg font-bold"><Activity className="h-5 w-5 text-brand-600" />Medicine interactions</h3>
        {a.interactions.length === 0 ? <Card><EmptyState icon={Sparkles} title="No interactions recorded" text="None of your assessed medicines have a documented interaction in our database. This does not guarantee safety - always confirm with your pharmacist." /></Card>
          : a.interactions.map((r, i) => <Interaction key={i} r={r} open={i === 0 && r.score >= 55} />)}</section>

      {a.possible_interactions.length > 0 && <section className="space-y-3"><h3 className="h-display flex items-center gap-2 text-lg font-bold"><Info className="h-5 w-5 text-muted" />Possible interactions (unverified)</h3>
        <p className="text-sm text-muted">Estimated by a machine-learning model from drug properties because no curated record exists. Accuracy on unseen drug pairs is limited - treat these as prompts to ask your pharmacist, not as findings.</p>
        {a.possible_interactions.map((r, i) => <Interaction key={i} r={r} />)}</section>}

      {a.unassessed.length > 0 && <Card className="border-sev-mod/40 bg-sev-mod/5 p-4"><div className="flex gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-sev-mod" /><div><b>Not checked:</b> {a.unassessed.join(", ")}.<p className="text-sm text-muted">These medicines are not in our database yet, so they were not screened. Ask your pharmacist to check them.</p></div></div></Card>}

      {a.monitoring.length > 0 && <Card><CardHeader icon={FlaskConical} title="Suggested monitoring" subtitle="Tests that help keep this combination safe" /><ul className="grid sm:grid-cols-2">{a.monitoring.map((m, i) => (
        <li key={i} className="border-t border-line px-5 py-3.5"><div className="font-semibold">{m.test}</div><div className="text-sm text-muted">{m.reason} <span className="text-ink/70">({m.drugs.join(", ")})</span></div></li>))}</ul></Card>}

      {Object.keys(a.diet).length > 0 && <Card><CardHeader icon={Apple} title="Your personalised diet & lifestyle guide" subtitle="Based on your medicines, conditions and test results" />
        <div className="grid gap-5 p-5 sm:grid-cols-2">{Object.entries(a.diet).map(([k, items]) => { const [label, Icon, color] = DIET[k]; return (
          <div key={k}><div className={cx("mb-2 flex items-center gap-2 font-bold", color)}><Icon className="h-4 w-4" />{label}</div><ul className="space-y-2.5">{items.map((it, i) => (<li key={i} className="text-sm leading-relaxed"><span className="font-medium">{it.text}</span><span className="block text-muted">{it.why}</span></li>))}</ul></div>); })}</div></Card>}

      {a.questions_for_doctor.length > 0 && <Card><CardHeader icon={HelpCircle} title="Questions to ask your doctor or pharmacist" /><ul className="list-disc space-y-2 p-5 pl-9 text-sm leading-relaxed">{a.questions_for_doctor.map((q, i) => <li key={i}>{q}</li>)}</ul></Card>}
      <p className="rounded-2xl bg-raised p-4 text-xs leading-relaxed text-muted">{a.disclaimer}</p>
    </div>);
}

export default function Analysis({ base, canRun = true }) {
  const [runs, setRuns] = useState(null); const [cur, setCur] = useState(null); const [busy, setBusy] = useState(false); const toast = useToast();
  const open = useCallback((id) => api.get(`${base}/analysis/${id}`).then(setCur).catch((e) => toast.error(e.message)), [base]); // eslint-disable-line
  const load = useCallback(async () => { const r = await api.get(`${base}/analysis`); setRuns(r); if (r[0]) open(r[0].id); }, [base, open]);
  useEffect(() => { load().catch((e) => toast.error(e.message)); }, [load]); // eslint-disable-line
  const run = async () => { setBusy(true); try { const r = await api.post(`${base}/analysis/run`); setCur(r); setRuns(await api.get(`${base}/analysis`)); toast.success("Analysis updated"); } catch (e) { toast.error(e.message); } finally { setBusy(false); } };
  if (!runs) return <PageLoader />;
  return (
    <div className="space-y-5">
      <div className="no-print flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div><h2 className="h-display text-2xl font-extrabold">Interaction analysis</h2><p className="text-sm text-muted">Personalised to the medicines, conditions, allergies and test results on file.</p></div>
        <div className="flex gap-2">{cur && <Button variant="secondary" icon={Printer} onClick={() => window.print()}>Print / PDF</Button>}{canRun && <Button icon={Sparkles} loading={busy} onClick={run}>{runs.length ? "Re-run analysis" : "Run analysis"}</Button>}</div></div>
      {runs.length > 1 && <div className="no-print scroll-x -mx-1 flex gap-2 px-1 pb-1">{runs.map((r) => (
        <button key={r.id} onClick={() => open(r.id)} className={cx("shrink-0 rounded-xl border px-3 py-2 text-left text-xs transition", cur?.id === r.id ? "border-brand-500 bg-brand-50" : "border-line bg-surface")}><div className="font-semibold">{fmtDateTime(r.created_at)}</div><div className={lvl(r.level).text}>{r.level} · {r.score}</div></button>))}</div>}
      {cur ? <AnalysisResult a={cur} /> : <Card><EmptyState icon={ClipboardList} title="No analysis yet" text="Add your medicines, then run your first personalised analysis." action={canRun && <Button icon={Sparkles} loading={busy} onClick={run}>Run analysis</Button>} /></Card>}
    </div>);
}
