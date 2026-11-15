import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pill as PillIcon, Stethoscope, ShieldAlert, FileText, Plus, Pencil, Trash2, Upload, Sparkles, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "../lib/api";
import { Button, Card, CardHeader, Confirm, EmptyState, Input, Modal, PageLoader, Pill, Select, Tabs, Textarea, useToast } from "./ui";
import { cx, fmtDate } from "../lib/utils";

const FREQ = ["once daily", "twice daily", "three times daily", "four times daily", "at bedtime", "as needed", "weekly"];

function DrugInput({ value, onChange }) {
  const [opts, setOpts] = useState([]); const t = useRef();
  const q = (val) => { onChange(val); clearTimeout(t.current); if (val.trim().length < 2) return setOpts([]); t.current = setTimeout(() => api.get(`/meta/drugs?q=${encodeURIComponent(val.trim())}`).then(setOpts).catch(() => {}), 200); };
  const id = useMemo(() => `dl-${Math.random().toString(36).slice(2)}`, []);
  return (<><Input label="Medicine name" value={value} onChange={(e) => q(e.target.value)} list={id} placeholder="e.g. Warfarin, Dolo 650, Glycomet" autoComplete="off" required />
    <datalist id={id}>{opts.map((o) => <option key={o} value={o} />)}</datalist></>);
}

function Crud({ base, kind, columns, form, empty, icon: Icon, addLabel }) {
  const [rows, setRows] = useState(null); const [edit, setEdit] = useState(null); const [del, setDel] = useState(null);
  const toast = useToast();
  const load = useCallback(() => api.get(`${base}/${kind}`).then(setRows).catch((e) => toast.error(e.message)), [base, kind]); // eslint-disable-line
  useEffect(() => { load(); }, [load]);
  if (!rows) return <PageLoader />;
  const save = async (data) => {
    try { edit.id ? await api.put(`${base}/${kind}/${edit.id}`, data) : await api.post(`${base}/${kind}`, data); setEdit(null); toast.success("Saved"); load(); } catch (e) { toast.error(e.message); }
  };
  return (
    <Card>
      <CardHeader icon={Icon} title={addLabel.title} subtitle={`${rows.length} saved`} action={<Button icon={Plus} onClick={() => setEdit({})} className="!min-h-[40px]">Add</Button>} />
      {rows.length === 0 ? <EmptyState icon={Icon} title={empty.title} text={empty.text} action={<Button icon={Plus} onClick={() => setEdit({})}>{addLabel.cta}</Button>} /> :
        <ul className="divide-y divide-line">{rows.map((r) => (
          <li key={r.id} className="flex items-center gap-3 px-5 py-3.5">
            <div className="min-w-0 flex-1">{columns(r)}</div>
            <button className="btn btn-ghost !min-h-[40px] !px-2.5" onClick={() => setEdit(r)} aria-label="Edit"><Pencil className="h-4 w-4" /></button>
            <button className="btn btn-ghost !min-h-[40px] !px-2.5 hover:!text-sev-crit" onClick={() => setDel(r)} aria-label="Delete"><Trash2 className="h-4 w-4" /></button>
          </li>))}</ul>}
      <FormModal open={!!edit} item={edit} onClose={() => setEdit(null)} onSave={save} title={`${edit?.id ? "Edit" : "Add"} ${addLabel.noun}`} render={form} />
      <Confirm open={!!del} danger title="Delete this record?" message="This cannot be undone." confirmLabel="Delete" onClose={() => setDel(null)}
        onConfirm={async () => { try { await api.del(`${base}/${kind}/${del.id}`); setDel(null); toast.success("Deleted"); load(); } catch (e) { toast.error(e.message); } }} />
    </Card>
  );
}

function FormModal({ open, item, onClose, onSave, title, render }) {
  const [d, setD] = useState({}); const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setD(item || {}); }, [open, item]);
  const set = (k) => (e) => setD((s) => ({ ...s, [k]: e?.target ? e.target.value : e }));
  const strip = (o) => Object.fromEntries(Object.entries(o).filter(([k]) => !["id", "created_at", "normalized_name", "in_kb", "source"].includes(k)).map(([k, v]) => [k, v === "" ? null : v]));
  return (
    <Modal open={open} onClose={onClose} title={title} footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button loading={busy} onClick={async () => { setBusy(true); await onSave(strip(d)); setBusy(false); }}>Save</Button></>}>
      <div className="space-y-4">{render(d, set, setD)}</div>
    </Modal>
  );
}

const medForm = (d, set) => (<>
  <DrugInput value={d.name || ""} onChange={(v) => set("name")(v)} />
  <div className="grid grid-cols-2 gap-3"><Input label="Dose" value={d.dose || ""} onChange={set("dose")} placeholder="500 mg" />
    <Select label="Frequency" value={d.frequency || ""} onChange={set("frequency")} placeholder="Select" options={FREQ} /></div>
  <Select label="Status" value={d.status || "active"} onChange={set("status")} options={[["active", "Currently taking"], ["stopped", "Stopped"]]} />
  <p className="text-xs text-muted">Brand names and common misspellings are recognised automatically.</p></>);

export function Medicines({ base }) {
  return <Crud base={base} kind="medications" icon={PillIcon} addLabel={{ title: "Medicines", noun: "medicine", cta: "Add a medicine" }} empty={{ title: "No medicines yet", text: "Add everything you take - including supplements and over-the-counter tablets - to check for interactions." }} form={medForm}
    columns={(r) => (<><div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{r.name}</span>
      {r.normalized_name && r.normalized_name.toLowerCase() !== r.name.toLowerCase() && <Pill>= {r.normalized_name}</Pill>}
      {r.status === "stopped" && <Pill>stopped</Pill>}
      {r.in_kb ? <Pill className="!bg-sev-low/10 !text-sev-low">checked</Pill> : <Pill className="!bg-sev-mod/10 !text-sev-mod" ><AlertCircle className="h-3 w-3" />not in database</Pill>}</div>
      <div className="mt-0.5 text-sm text-muted">{[r.dose, r.frequency].filter(Boolean).join(" · ") || "No dose recorded"}</div></>)} />;
}

export function Conditions({ base }) {
  const [opts, setOpts] = useState([]);
  useEffect(() => { api.get("/meta/conditions").then(setOpts).catch(() => {}); }, []);
  const form = (d, set, setD) => (<>
    <Select label="Common conditions" placeholder="Pick one (optional)" value={d.condition_key || ""} options={opts.map((o) => [o.key, o.label])}
      onChange={(e) => { const o = opts.find((x) => x.key === e.target.value); setD((s) => ({ ...s, condition_key: e.target.value || null, name: s.name || o?.label || "" })); }} />
    <Input label="Name" value={d.name || ""} onChange={set("name")} placeholder="e.g. Type 2 diabetes" required />
    <Select label="Status" value={d.status || "active"} onChange={set("status")} options={[["active", "Active"], ["resolved", "Resolved"]]} /></>);
  return <Crud base={base} kind="conditions" icon={Stethoscope} addLabel={{ title: "Health conditions", noun: "condition", cta: "Add a condition" }} empty={{ title: "No conditions recorded", text: "Conditions such as kidney disease or diabetes change how interactions are scored for you." }} form={form}
    columns={(r) => (<><div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{r.name}</span>{r.status === "resolved" && <Pill>resolved</Pill>}{r.condition_key && <Pill className="!bg-brand-50 !text-brand-700">used in scoring</Pill>}</div></>)} />;
}

export function Allergies({ base }) {
  const form = (d, set) => (<><Input label="Allergen" value={d.allergen || ""} onChange={set("allergen")} placeholder="e.g. Penicillin, Aspirin, Sulfa" required />
    <Input label="Reaction" value={d.reaction || ""} onChange={set("reaction")} placeholder="e.g. rash, swelling" />
    <Select label="Severity" value={d.severity || ""} onChange={set("severity")} placeholder="Select" options={["mild", "moderate", "severe"]} /></>);
  return <Crud base={base} kind="allergies" icon={ShieldAlert} addLabel={{ title: "Allergies", noun: "allergy", cta: "Add an allergy" }} empty={{ title: "No allergies recorded", text: "Add drug allergies so we can warn you about related medicines." }} form={form}
    columns={(r) => (<><div className="font-semibold">{r.allergen}</div><div className="text-sm text-muted">{[r.reaction, r.severity].filter(Boolean).join(" · ") || "No details"}</div></>)} />;
}

const TYPE = { MEDICATION: "bg-sky-500/20 text-sky-700 dark:text-sky-300", CONDITION: "bg-violet-500/20 text-violet-700 dark:text-violet-300", ALLERGY: "bg-rose-500/20 text-rose-700 dark:text-rose-300", LAB: "bg-amber-500/25 text-amber-800 dark:text-amber-300", FOOD: "bg-lime-500/20 text-lime-800 dark:text-lime-300" };

function Highlighted({ text, entities }) {
  const parts = []; let i = 0;
  [...entities].sort((a, b) => a.start - b.start).forEach((e) => {
    if (e.start < i) return; parts.push(text.slice(i, e.start));
    parts.push(<mark key={e.id || e.start} title={`${e.type}${e.normalized ? " → " + e.normalized : ""}${e.negated ? " (negated)" : ""}${e.family ? " (family history)" : ""}`}
      className={cx("rounded px-0.5", TYPE[e.type], (e.negated || e.family) && "line-through opacity-60")}>{text.slice(e.start, e.end)}</mark>); i = e.end;
  });
  parts.push(text.slice(i));
  return <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-raised p-4 font-sans text-sm leading-7">{parts}</pre>;
}

function Reports({ base, onApplied }) {
  const [text, setText] = useState(""); const [busy, setBusy] = useState(false); const [doc, setDoc] = useState(null); const [sel, setSel] = useState(null); const [docs, setDocs] = useState([]);
  const toast = useToast(); const file = useRef();
  const loadDocs = useCallback(() => api.get(`${base}/documents`).then(setDocs).catch(() => {}), [base]);
  useEffect(() => { loadDocs(); }, [loadDocs]);
  const open = (d) => { setDoc(d); setSel({ m: d.suggestions.medications.map(() => true), c: d.suggestions.conditions.map(() => true), a: d.suggestions.allergies.map(() => true), labs: Object.fromEntries(Object.keys(d.labs).map((k) => [k, true])) }); };
  const go = async (fn) => { setBusy(true); try { open(await fn()); loadDocs(); } catch (e) { toast.error(e.message); } finally { setBusy(false); } };
  const apply = async () => {
    const s = doc.suggestions; setBusy(true);
    try {
      const profile = Object.fromEntries(Object.entries(doc.labs).filter(([k]) => sel.labs[k]));
      const r = await api.post(`${base}/documents/${doc.id}/apply`, {
        medications: s.medications.filter((_, i) => sel.m[i]).map((m) => ({ name: m.name, dose: m.dose || null, frequency: m.frequency || null, route: m.route || null, status: m.status })),
        conditions: s.conditions.filter((_, i) => sel.c[i]).map((c) => ({ name: c.name, condition_key: c.condition_key })),
        allergies: s.allergies.filter((_, i) => sel.a[i]).map((a) => ({ allergen: a.allergen, reaction: a.reaction || null })),
        profile: Object.keys(profile).length ? profile : null });
      const a = r.added; toast.success(`Added ${a.medications} medicines, ${a.conditions} conditions, ${a.allergies} allergies`); setDoc(null); setText(""); loadDocs(); onApplied?.();
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  if (doc) {
    const s = doc.suggestions; const tog = (k, i) => setSel((x) => ({ ...x, [k]: x[k].map((v, j) => (j === i ? !v : v)) }));
    const Row = ({ on, onClick, children }) => (<label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3 hover:bg-raised"><input type="checkbox" checked={on} onChange={onClick} className="mt-1 h-5 w-5 accent-[rgb(var(--b600))]" /><div className="min-w-0 flex-1 text-sm">{children}</div></label>);
    return (
      <div className="space-y-5">
        <Card><CardHeader icon={Sparkles} title="Review what we found" subtitle="Untick anything that is wrong. Nothing is saved until you confirm." />
          <div className="space-y-4 p-5"><Highlighted text={doc.text} entities={doc.entities} />
            <div className="flex flex-wrap gap-2 text-xs">{Object.entries(TYPE).map(([k, c]) => <span key={k} className={cx("rounded px-2 py-0.5 font-semibold", c)}>{k.toLowerCase()}</span>)}</div></div></Card>
        {s.medications.length > 0 && <Card><CardHeader icon={PillIcon} title="Medicines" /><div className="space-y-2 p-5">{s.medications.map((m, i) => (
          <Row key={i} on={sel.m[i]} onClick={() => tog("m", i)}><div className="flex flex-wrap items-center gap-2"><b>{m.name}</b>{m.status === "stopped" && <Pill>stopped</Pill>}{!m.in_kb && <Pill className="!bg-sev-mod/10 !text-sev-mod">not in database</Pill>}</div>
            <div className="text-muted">{[m.dose, m.frequency, m.route].filter(Boolean).join(" · ") || "no dose found"}</div></Row>))}</div></Card>}
        {s.conditions.length > 0 && <Card><CardHeader icon={Stethoscope} title="Conditions" /><div className="space-y-2 p-5">{s.conditions.map((c, i) => <Row key={i} on={sel.c[i]} onClick={() => tog("c", i)}><b>{c.name}</b></Row>)}</div></Card>}
        {s.allergies.length > 0 && <Card><CardHeader icon={ShieldAlert} title="Allergies" /><div className="space-y-2 p-5">{s.allergies.map((a, i) => <Row key={i} on={sel.a[i]} onClick={() => tog("a", i)}><b>{a.allergen}</b>{a.reaction && <span className="text-muted"> · {a.reaction}</span>}</Row>)}</div></Card>}
        {Object.keys(doc.labs).length > 0 && <Card><CardHeader icon={FileText} title="Test results & vitals" subtitle="These update your profile values" /><div className="grid gap-2 p-5 sm:grid-cols-2">{Object.entries(doc.labs).map(([k, v]) => (
          <Row key={k} on={sel.labs[k]} onClick={() => setSel((x) => ({ ...x, labs: { ...x.labs, [k]: !x.labs[k] } }))}><b>{k.replace(/_/g, " ")}</b>: {v}</Row>))}</div></Card>}
        {!s.medications.length && !s.conditions.length && !s.allergies.length && !Object.keys(doc.labs).length && <Card><EmptyState icon={AlertCircle} title="Nothing recognised" text="Try pasting the medicine list as plain text, one per line (e.g. Metformin 500 mg twice daily)." /></Card>}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button variant="secondary" onClick={() => setDoc(null)}>Discard</Button><Button icon={CheckCircle2} loading={busy} onClick={apply}>Save selected to my record</Button></div>
      </div>);
  }
  return (
    <div className="space-y-5">
      <Card><CardHeader icon={Upload} title="Upload your report" subtitle="Prescription, discharge summary or lab report - we read it and fill in your record for you to confirm." />
        <div className="space-y-4 p-5">
          <input ref={file} type="file" accept=".pdf,.txt,.csv,.json,.md" className="hidden" onChange={(e) => e.target.files[0] && go(() => api.upload(`${base}/documents/upload`, e.target.files[0]))} />
          <button onClick={() => file.current.click()} disabled={busy} className="flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-line p-8 text-center transition hover:border-brand-500 hover:bg-brand-50">
            <Upload className="h-7 w-7 text-brand-600" /><span className="font-semibold">Choose a PDF, TXT or CSV file</span><span className="text-xs text-muted">Text-based PDFs only (scanned photos need to be typed in) · max 3 MB</span></button>
          <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-muted"><span className="h-px flex-1 bg-line" />or paste text<span className="h-px flex-1 bg-line" /></div>
          <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={"Tab Metformin 500 mg BD\nTab Ecosprin 75 mg OD\nHistory: Type 2 diabetes, CKD. Allergic to sulfa.\nCreatinine 1.8, K 5.3"} className="min-h-[140px]" />
          <Button icon={Sparkles} loading={busy} disabled={text.trim().length < 3} onClick={() => go(() => api.post(`${base}/documents/text`, { text }))} className="w-full sm:w-auto">Analyse text</Button></div></Card>
      {docs.length > 0 && <Card><CardHeader icon={FileText} title="Past reports" /><ul className="divide-y divide-line">{docs.map((d) => (
        <li key={d.id} className="flex items-center gap-3 px-5 py-3"><div className="min-w-0 flex-1"><div className="truncate font-medium">{d.filename}</div><div className="text-xs text-muted">{fmtDate(d.created_at)} · {d.n_entities} items found · {d.status}</div></div>
          <Button variant="ghost" className="!min-h-[36px]" onClick={() => api.get(`${base}/documents/${d.id}`).then(open)}>Review</Button>
          <button className="btn btn-ghost !min-h-[36px] !px-2 hover:!text-sev-crit" aria-label="Delete" onClick={async () => { await api.del(`${base}/documents/${d.id}`); loadDocs(); }}><Trash2 className="h-4 w-4" /></button></li>))}</ul></Card>}
    </div>);
}

export default function Medical({ base, initial = "meds" }) {
  const [tab, setTab] = useState(initial);
  return (
    <div className="space-y-5">
      <Tabs value={tab} onChange={setTab} tabs={[["meds", "Medicines", PillIcon], ["conds", "Conditions", Stethoscope], ["allergies", "Allergies", ShieldAlert], ["reports", "Reports", FileText]]} />
      {tab === "meds" && <Medicines base={base} />}{tab === "conds" && <Conditions base={base} />}{tab === "allergies" && <Allergies base={base} />}
      {tab === "reports" && <Reports base={base} onApplied={() => setTab("meds")} />}
    </div>);
}
