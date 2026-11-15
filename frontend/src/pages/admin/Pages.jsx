import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Activity, ArrowLeftRight, Ban, ChevronLeft, ChevronRight, Database, FileText, Heart, KeyRound, Pencil, Plus, RefreshCw, ScanFace, Search, ShieldCheck, Trash2, Users, UserRound, ScrollText, Brain, LogOut, Pill, Stethoscope, Eye } from "lucide-react";
import { api } from "../../lib/api";
import { Button, Card, CardHeader, Confirm, EmptyState, Input, LevelBadge, Modal, PageLoader, Pill as Chip, Select, Stat, Switch, Tabs, Textarea, useToast } from "../../components/ui";
import ProfileForm from "../../components/ProfileForm";
import Medical from "../../components/Medical";
import Analysis from "../../components/Analysis";
import FaceCapture, { cameraSupported } from "../../components/FaceCapture";
import { cx, fmtDate, fmtDateTime, initials, lvl } from "../../lib/utils";

const Pager = ({ page, total, size, onPage }) => { const pages = Math.max(1, Math.ceil(total / size)); return (
  <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-muted"><span>{total} total</span><div className="flex items-center gap-1">
    <Button variant="ghost" className="!min-h-[36px] !px-2" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous"><ChevronLeft className="h-4 w-4" /></Button><span className="px-2 font-semibold text-ink">{page} / {pages}</span>
    <Button variant="ghost" className="!min-h-[36px] !px-2" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next"><ChevronRight className="h-4 w-4" /></Button></div></div>); };

export function Overview() {
  const [s, setS] = useState(null); const [m, setM] = useState(null); const toast = useToast();
  useEffect(() => { api.get("/admin/stats").then(setS).catch((e) => toast.error(e.message)); api.get("/admin/model").then(setM).catch(() => {}); }, []); // eslint-disable-line
  if (!s) return <PageLoader />;
  const dist = s.risk_distribution; const max = Math.max(1, ...Object.values(dist)); const mm = m?.metrics?.models?.XGBoost;
  return (
    <div className="space-y-6">
      <div><h1 className="h-display text-3xl font-extrabold">Clinical overview</h1><p className="text-muted">All patients at a glance.</p></div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><Stat label="Patients" value={s.patients} sub={`${s.new_this_week} new this week`} icon={Users} /><Stat label="Analyses run" value={s.analyses} icon={Activity} /><Stat label="Medicines on file" value={s.medications} icon={Pill} /><Stat label="Face enrolled" value={s.face_enrolled} icon={ScanFace} /></div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card><CardHeader icon={Heart} title="Patients by latest risk level" /><div className="space-y-3 p-5">{["Critical", "High", "Moderate", "Low", "None"].map((k) => (
          <Link key={k} to={`/admin/patients?risk=${k}`} className="flex items-center gap-3"><span className="w-20 text-sm font-semibold">{lvl(k).label}</span><div className="h-7 flex-1 overflow-hidden rounded-lg bg-raised"><div className={cx("h-full rounded-lg", lvl(k).bar)} style={{ width: `${(dist[k] / max) * 100}%`, minWidth: dist[k] ? 8 : 0 }} /></div><span className="w-8 text-right font-bold">{dist[k]}</span></Link>))}
          <Link to="/admin/patients?risk=Never" className="flex items-center gap-3 text-sm text-muted"><span className="w-20">Not analysed</span><span className="font-bold">{s.never_analysed}</span></Link></div></Card>
        <Card><CardHeader icon={Brain} title="Knowledge base & model" /><div className="space-y-3 p-5 text-sm"><div className="flex justify-between"><span className="text-muted">Drugs & foods</span><b>{s.kb_drugs}</b></div><div className="flex justify-between"><span className="text-muted">Curated interaction rules</span><b>{s.kb_interactions}</b></div>
          {mm && <><div className="flex justify-between"><span className="text-muted">Model accuracy (random split)</span><b>{(mm.accuracy * 100).toFixed(1)}%</b></div><div className="flex justify-between"><span className="text-muted">Accuracy on unseen drug classes</span><b>{(mm.group_cv_accuracy * 100).toFixed(1)}%</b></div>
            <p className="rounded-xl bg-raised p-3 text-xs text-muted">Curated rules are the source of truth. ML is only a fallback for pairs with no rule, and is shown to patients as “unverified”.</p></>}
          <div className="flex gap-2 pt-1"><Link to="/admin/data?table=kb_interactions" className="btn btn-secondary !min-h-[40px] text-sm">Edit rules</Link><Button variant="secondary" className="!min-h-[40px] text-sm" icon={RefreshCw} onClick={async () => { const r = await api.post("/admin/kb/reload"); }}>Reload KB</Button></div></div></Card></div>
    </div>);
}

export function Patients() {
  const nav = useNavigate(); const toast = useToast(); const init = new URLSearchParams(window.location.search);
  const [q, setQ] = useState(""); const [risk, setRisk] = useState(init.get("risk") || ""); const [page, setPage] = useState(1); const [d, setD] = useState(null);
  const load = useCallback(() => api.get(`/admin/patients?q=${encodeURIComponent(q)}&risk=${risk}&page=${page}&page_size=15`).then(setD).catch((e) => toast.error(e.message)), [q, risk, page]); // eslint-disable-line
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  return (
    <div className="space-y-5">
      <div><h1 className="h-display text-3xl font-extrabold">Patients</h1><p className="text-muted">Search, open and edit any patient record. Every access is audited.</p></div>
      <div className="flex flex-col gap-3 sm:flex-row"><div className="relative flex-1"><Search className="pointer-events-none absolute left-3.5 top-3.5 h-[18px] w-[18px] text-muted" /><input className="input pl-10" placeholder="Search name or email" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div>
        <select className="input sm:w-48" value={risk} onChange={(e) => { setRisk(e.target.value); setPage(1); }}><option value="">All risk levels</option>{["Critical", "High", "Moderate", "Low", "None", "Never"].map((r) => <option key={r} value={r}>{r === "Never" ? "Not analysed" : r}</option>)}</select></div>
      <Card className="overflow-hidden">{!d ? <PageLoader /> : d.items.length === 0 ? <EmptyState icon={Users} title="No patients found" /> : (<>
        <ul className="divide-y divide-line">{d.items.map((p) => (
          <li key={p.id}><button onClick={() => nav(`/admin/patients/${p.id}`)} className="flex w-full items-center gap-4 px-4 py-3.5 text-left hover:bg-raised">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-brand-50 font-bold text-brand-700">{initials(p.name || p.email)}</span>
            <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="truncate font-semibold">{p.name || "(no name)"}</span>{!p.is_active && <Chip>disabled</Chip>}</div>
              <div className="truncate text-sm text-muted">{p.email}</div><div className="text-xs text-muted">{[p.age != null && `${p.age}y`, p.sex, p.city, `${p.medications} meds`].filter(Boolean).join(" · ")}</div></div>
            <div className="shrink-0 text-right">{p.risk_level ? <><LevelBadge level={p.risk_level} /><div className="mt-1 text-xs text-muted">{p.risk_score}/100</div></> : <span className="text-xs text-muted">not analysed</span>}</div></button></li>))}</ul>
        <Pager page={page} total={d.total} size={15} onPage={setPage} /></>)}</Card></div>);
}

export function PatientDetail() {
  const { id } = useParams(); const nav = useNavigate(); const toast = useToast(); const base = `/admin/patients/${id}`;
  const [s, setS] = useState(null); const [tab, setTab] = useState("overview"); const [face, setFace] = useState(null); const [aud, setAud] = useState(null);
  const [dlg, setDlg] = useState(null); const [pw, setPw] = useState(""); const [reface, setReface] = useState(false);
  const load = useCallback(() => api.get(`${base}/summary`).then(setS).catch((e) => { toast.error(e.message); nav("/admin/patients"); }), [base]); // eslint-disable-line
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (tab === "face") api.get(`${base}/face`).then(setFace); if (tab === "audit") api.get(`/admin/audit?target=${id}&page_size=50`).then(setAud); }, [tab]); // eslint-disable-line
  if (!s) return <PageLoader />;
  const u = s.user, p = s.profile, la = s.latest_analysis;
  const act = async (fn, ok) => { try { await fn(); toast.success(ok); setDlg(null); load(); } catch (e) { toast.error(e.message); } };
  return (
    <div className="space-y-5">
      <button onClick={() => nav("/admin/patients")} className="inline-flex items-center gap-1 text-sm font-semibold text-muted hover:text-ink"><ChevronLeft className="h-4 w-4" />All patients</button>
      <Card className="p-5"><div className="flex flex-col gap-4 sm:flex-row sm:items-center"><span className="grid h-16 w-16 place-items-center rounded-full bg-brand-600 text-xl font-bold text-onbrand">{initials(u.display_name || u.email)}</span>
        <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h1 className="h-display text-2xl font-extrabold">{u.display_name || "(no name)"}</h1>{la && <LevelBadge level={la.level} />}{!u.is_active && <Chip>disabled</Chip>}</div>
          <div className="text-sm text-muted">{u.email} · {[p.age != null && `${p.age}y`, p.sex, p.blood_group, p.city].filter(Boolean).join(" · ")}</div><div className="text-xs text-muted">Joined {fmtDate(u.created_at)} · last sign-in {fmtDateTime(u.last_login_at)}</div></div>
        <div className="flex flex-wrap gap-2"><Button variant="secondary" className="!min-h-[40px]" icon={u.is_active ? Ban : ShieldCheck} onClick={() => act(() => api.patch(`${base}/account`, { is_active: !u.is_active }), u.is_active ? "Account disabled" : "Account enabled")}>{u.is_active ? "Disable" : "Enable"}</Button>
          <Button variant="secondary" className="!min-h-[40px]" icon={KeyRound} onClick={() => setDlg("pw")}>Set password</Button><Button variant="secondary" className="!min-h-[40px] !text-sev-crit" icon={Trash2} onClick={() => setDlg("del")}>Delete</Button></div></div></Card>
      <Tabs value={tab} onChange={setTab} tabs={[["overview", "Overview", Eye], ["profile", "Profile", UserRound], ["medical", "Medical", Stethoscope], ["analysis", "Analysis", Activity], ["face", "Face", ScanFace], ["audit", "Audit", ScrollText]]} />
      {tab === "overview" && <div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><Stat label="Medicines" value={s.counts.medications} icon={Pill} /><Stat label="Conditions" value={s.counts.conditions} icon={Heart} /><Stat label="Allergies" value={s.counts.allergies} icon={ShieldCheck} /><Stat label="Analyses" value={s.counts.analyses} icon={Activity} sub={la ? `Latest: ${la.level} (${la.score})` : "None yet"} /></div>}
      {tab === "profile" && <ProfileForm base={base} onSaved={load} />}
      {tab === "medical" && <Medical base={base} />}
      {tab === "analysis" && <Analysis base={base} />}
      {tab === "face" && (!face ? <PageLoader /> : <Card><CardHeader icon={ScanFace} title="Face on file" subtitle={face.enrolled ? `Registered ${fmtDate(face.enrolled_at)}` : "No face registered"} /><div className="flex flex-col items-start gap-4 p-5 sm:flex-row">
        {face.photo ? <img src={face.photo} alt="Patient face captured at registration" className="h-56 w-44 rounded-2xl object-cover" /> : <div className="grid h-56 w-44 place-items-center rounded-2xl bg-raised text-muted"><ScanFace className="h-10 w-10" /></div>}
        <div className="space-y-3 text-sm"><p className="text-muted">Captured live during registration. Use it to confirm identity at the clinic.</p><div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={!cameraSupported()} onClick={() => setReface(true)}>Capture new face</Button>{face.enrolled && <Button variant="secondary" className="!text-sev-crit" onClick={() => act(() => api.del(`${base}/face`).then(() => api.get(`${base}/face`).then(setFace)), "Face removed")}>Remove face</Button>}</div></div></div></Card>)}
      {tab === "audit" && (!aud ? <PageLoader /> : <AuditTable items={aud.items} />)}
      <Modal open={dlg === "pw"} onClose={() => setDlg(null)} title="Set a new password" footer={<><Button variant="secondary" onClick={() => setDlg(null)}>Cancel</Button><Button onClick={() => act(() => api.post(`${base}/set-password`, { password: pw }), "Password set; patient signed out")}>Save</Button></>}>
        <Input label="New password" type="text" value={pw} onChange={(e) => setPw(e.target.value)} hint="10+ characters, letters and numbers. Share it securely; the patient should change it." /></Modal>
      <Confirm open={dlg === "del"} danger title="Delete this patient?" confirmLabel="Delete permanently" message="All of this patient's data is erased and cannot be recovered." onClose={() => setDlg(null)} onConfirm={async () => { await api.del(base); toast.success("Patient deleted"); nav("/admin/patients"); }} />
      <Modal open={reface} onClose={() => setReface(false)} title="Capture patient face"><FaceCapture mode="enroll" compact onCancel={() => setReface(false)} onDone={async (d) => { await api.put(`${base}/face`, d); setReface(false); setFace(await api.get(`${base}/face`)); toast.success("Face updated"); }} /></Modal>
    </div>);
}

function AuditTable({ items }) {
  return (<Card className="overflow-hidden"><div className="scroll-x"><table className="w-full min-w-[640px] text-sm"><thead className="bg-raised text-left text-xs uppercase tracking-wide text-muted"><tr><th className="px-4 py-2.5">When</th><th className="px-4 py-2.5">Who</th><th className="px-4 py-2.5">Action</th><th className="px-4 py-2.5">Details</th></tr></thead>
    <tbody className="divide-y divide-line">{items.map((r) => (<tr key={r.id}><td className="whitespace-nowrap px-4 py-2.5 text-muted">{fmtDateTime(r.created_at)}</td><td className="px-4 py-2.5">{r.actor_email || "-"}<span className="ml-1 text-xs text-muted">{r.actor_role}</span></td><td className="px-4 py-2.5 font-mono text-xs">{r.action}</td>
      <td className="max-w-xs truncate px-4 py-2.5 text-xs text-muted" title={JSON.stringify(r.details)}>{r.table_name ? `${r.table_name} ${r.row_id || ""} ` : ""}{r.details ? JSON.stringify(r.details) : ""}</td></tr>))}</tbody></table></div>
    {items.length === 0 && <EmptyState icon={ScrollText} title="No audit entries" />}</Card>);
}

export function Audit() {
  const [d, setD] = useState(null); const [page, setPage] = useState(1); const [actor, setActor] = useState(""); const [action, setAction] = useState("");
  useEffect(() => { const t = setTimeout(() => api.get(`/admin/audit?page=${page}&page_size=50&actor=${encodeURIComponent(actor)}&action=${encodeURIComponent(action)}`).then(setD), 250); return () => clearTimeout(t); }, [page, actor, action]);
  return (<div className="space-y-5"><div><h1 className="h-display text-3xl font-extrabold">Audit log</h1><p className="text-muted">Immutable record of sign-ins and every doctor access or change to patient data.</p></div>
    <div className="grid gap-3 sm:grid-cols-2"><Input placeholder="Filter by user email" value={actor} onChange={(e) => { setActor(e.target.value); setPage(1); }} /><Input placeholder="Filter by action (e.g. login, explorer:update)" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} /></div>
    {!d ? <PageLoader /> : <><AuditTable items={d.items} /><Card><Pager page={page} total={d.total} size={50} onPage={setPage} /></Card></>}</div>);
}

/* ---------------------------------------------------------------- generic data explorer */
function RowForm({ cols, row, onSave, onClose, creating }) {
  const [d, setD] = useState(() => Object.fromEntries(cols.map((c) => [c.name, row?.[c.name] ?? (c.kind === "bool" ? false : "")]))); const [busy, setBusy] = useState(false); const [swap, setSwap] = useState({ a: "", b: "" });
  const editable = cols.filter((c) => c.editable); const set = (k, v) => setD((s) => ({ ...s, [k]: v }));
  const submit = async () => {
    setBusy(true);
    const body = {}; editable.forEach((c) => { let v = d[c.name]; if (c.kind === "json" && typeof v === "string" && v.trim()) { try { v = JSON.parse(v); } catch { v = v; } } if (c.kind === "json" && typeof v === "object") { /* ok */ } if (creating && (v === "" || v == null) && !["string", "text"].includes(c.kind)) return; body[c.name] = v === "" ? null : v; });
    if (creating) cols.filter((c) => c.fk && !c.editable && d[c.name]).forEach((c) => (body[c.name] = d[c.name]));
    try { await onSave(body); } finally { setBusy(false); }
  };
  const same = useMemo(() => editable.filter((c) => ["string", "text"].includes(c.kind)), [cols]); // eslint-disable-line
  return (<Modal open onClose={onClose} title={creating ? "Add row" : "Edit row"} wide footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={submit}>Save</Button></>}>
    <div className="grid gap-4 sm:grid-cols-2">{cols.filter((c) => c.editable || (creating && c.fk) || (!creating && (c.pk || c.fk))).map((c) => {
      const ro = !c.editable && !(creating && c.fk); const label = `${c.name}${c.nullable ? "" : " *"}`; const common = { label, value: d[c.name] ?? "", disabled: ro, onChange: (e) => set(c.name, e.target.value) };
      if (c.enum && c.kind === "string") return <Select key={c.name} {...common} placeholder="-" options={c.enum} />;
      if (c.kind === "bool") return <div key={c.name} className="flex items-end"><Switch label={c.name} checked={!!d[c.name]} disabled={ro} onChange={(v) => set(c.name, v)} /></div>;
      if (c.kind === "json") return <Textarea key={c.name} wrap="sm:col-span-2" {...common} value={typeof d[c.name] === "string" ? d[c.name] : JSON.stringify(d[c.name] ?? null, null, 1)} className="font-mono text-xs" />;
      if (c.kind === "text") return <Textarea key={c.name} wrap="sm:col-span-2" {...common} />;
      return <Input key={c.name} {...common} type={c.kind === "int" || c.kind === "float" ? "number" : c.kind === "date" ? "date" : "text"} step={c.kind === "float" ? "any" : undefined} />; })}</div>
    {!creating && same.length > 1 && <div className="mt-6 rounded-2xl border border-line p-4"><div className="mb-2 flex items-center gap-2 text-sm font-bold"><ArrowLeftRight className="h-4 w-4" />Swap two columns in this row</div><div className="flex flex-col gap-2 sm:flex-row sm:items-end">
      <Select wrap="flex-1" label="Column A" value={swap.a} onChange={(e) => setSwap({ ...swap, a: e.target.value })} placeholder="-" options={same.map((c) => c.name)} /><Select wrap="flex-1" label="Column B" value={swap.b} onChange={(e) => setSwap({ ...swap, b: e.target.value })} placeholder="-" options={same.filter((c) => c.name !== swap.a).map((c) => c.name)} />
      <Button variant="secondary" disabled={!swap.a || !swap.b} onClick={() => { setD((s) => ({ ...s, [swap.a]: s[swap.b], [swap.b]: s[swap.a] })); }}>Swap values</Button></div><p className="mt-2 text-xs text-muted">Swaps the values in the form - press Save to apply.</p></div>}
  </Modal>);
}

export function Explorer() {
  const toast = useToast(); const init = new URLSearchParams(window.location.search);
  const [tables, setTables] = useState(null); const [name, setName] = useState(init.get("table") || "users"); const [data, setData] = useState(null); const [page, setPage] = useState(1); const [q, setQ] = useState("");
  const [form, setForm] = useState(null); const [del, setDel] = useState(null); const [sel, setSel] = useState([]); const [swap, setSwap] = useState(null); const [fields, setFields] = useState([]);
  useEffect(() => { api.get("/admin/tables").then(setTables).catch((e) => toast.error(e.message)); }, []); // eslint-disable-line
  const t = tables?.find((x) => x.name === name);
  const load = useCallback(() => { setData(null); return api.get(`/admin/tables/${name}?page=${page}&page_size=20&q=${encodeURIComponent(q)}`).then(setData).catch((e) => toast.error(e.message)); }, [name, page, q]); // eslint-disable-line
  useEffect(() => { const x = setTimeout(load, 250); return () => clearTimeout(x); }, [load]);
  useEffect(() => { setPage(1); setQ(""); setSel([]); }, [name]);
  if (!tables) return <PageLoader />;
  const cols = data?.columns || t.columns; const show = cols.filter((c) => !["json"].includes(c.kind) || c.name === "tags" || c.name === "synonyms").slice(0, 9);
  const short = (v, c) => (v == null ? <span className="text-muted/60">null</span> : typeof v === "boolean" ? (v ? "true" : "false") : c.kind === "json" ? JSON.stringify(v).slice(0, 40) : String(v).length > 48 ? String(v).slice(0, 48) + "…" : String(v));
  const pk = (r) => r.id;
  return (
    <div className="space-y-5">
      <div><h1 className="h-display text-3xl font-extrabold">Data explorer</h1><p className="text-muted">View, add, edit, delete and swap data in every table. All changes are audit-logged.</p></div>
      <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
        <div className="lg:hidden"><Select value={name} onChange={(e) => setName(e.target.value)} options={tables.map((x) => [x.name, `${x.name} (${x.count})`])} /></div>
        <nav className="hidden space-y-1 lg:block">{tables.map((x) => (<button key={x.name} onClick={() => setName(x.name)} className={cx("flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm font-semibold", name === x.name ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-raised hover:text-ink")}><span className="truncate">{x.name}</span><span className="text-xs">{x.count}</span></button>))}</nav>
        <div className="min-w-0 space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row"><div className="relative flex-1"><Search className="pointer-events-none absolute left-3.5 top-3.5 h-[18px] w-[18px] text-muted" /><input className="input pl-10" placeholder={`Search ${name}`} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div>
            <div className="flex gap-2">{sel.length === 2 && <Button variant="secondary" icon={ArrowLeftRight} onClick={() => { setSwap(sel); setFields([]); }}>Swap rows</Button>}
              {t.create && <Button icon={Plus} onClick={() => setForm({ creating: true })}>Add row</Button>}<Button variant="secondary" icon={RefreshCw} onClick={load} aria-label="Refresh" /></div></div>
          <Card className="overflow-hidden">{!data ? <PageLoader /> : data.items.length === 0 ? <EmptyState icon={Database} title="No rows" /> : (<>
            <div className="scroll-x"><table className="w-full min-w-[640px] text-sm"><thead className="bg-raised text-left text-xs uppercase tracking-wide text-muted"><tr><th className="w-10 px-3 py-2.5" />{show.map((c) => <th key={c.name} className="whitespace-nowrap px-3 py-2.5">{c.name}</th>)}<th className="px-3 py-2.5" /></tr></thead>
              <tbody className="divide-y divide-line">{data.items.map((r) => (<tr key={pk(r)} className="hover:bg-raised/60"><td className="px-3 py-2"><input type="checkbox" className="h-4 w-4 accent-[rgb(var(--b600))]" checked={sel.includes(pk(r))} onChange={() => setSel((s) => s.includes(pk(r)) ? s.filter((x) => x !== pk(r)) : [...s.slice(-1), pk(r)])} aria-label="Select row" /></td>
                {show.map((c) => <td key={c.name} className="max-w-[260px] truncate whitespace-nowrap px-3 py-2" title={String(r[c.name] ?? "")}>{short(r[c.name], c)}</td>)}
                <td className="whitespace-nowrap px-2 py-1 text-right"><button className="btn btn-ghost !min-h-[36px] !px-2" aria-label="Edit" onClick={() => setForm({ row: r })}><Pencil className="h-4 w-4" /></button>{t.delete && <button className="btn btn-ghost !min-h-[36px] !px-2 hover:!text-sev-crit" aria-label="Delete" onClick={() => setDel(r)}><Trash2 className="h-4 w-4" /></button>}</td></tr>))}</tbody></table></div>
            <Pager page={page} total={data.total} size={20} onPage={setPage} /></>)}</Card>
          {!t.delete && <p className="text-xs text-muted">Rows in this table are immutable by design.</p>}</div></div>
      {form && <RowForm cols={cols} row={form.row} creating={form.creating} onClose={() => setForm(null)} onSave={async (body) => { try { form.creating ? await api.post(`/admin/tables/${name}`, body) : await api.put(`/admin/tables/${name}/${pk(form.row)}`, body); toast.success("Saved"); setForm(null); load(); api.get("/admin/tables").then(setTables); } catch (e) { toast.error(e.message); } }} />}
      <Confirm open={!!del} danger title="Delete this row?" message={`This permanently removes row ${del ? pk(del) : ""} from ${name}.`} confirmLabel="Delete" onClose={() => setDel(null)} onConfirm={async () => { try { await api.del(`/admin/tables/${name}/${pk(del)}`); setDel(null); toast.success("Deleted"); load(); api.get("/admin/tables").then(setTables); } catch (e) { toast.error(e.message); } }} />
      <Modal open={!!swap} onClose={() => setSwap(null)} title="Swap values between two rows" footer={<><Button variant="secondary" onClick={() => setSwap(null)}>Cancel</Button><Button disabled={!fields.length} onClick={async () => { try { await api.post(`/admin/tables/${name}/swap`, { mode: "rows", id_a: swap[0], id_b: swap[1], fields }); toast.success("Swapped"); setSwap(null); setSel([]); load(); } catch (e) { toast.error(e.message); } }}>Swap selected fields</Button></>}>
        <p className="mb-3 text-sm text-muted">Choose which fields exchange values between the two selected rows.</p><div className="grid gap-2 sm:grid-cols-2">{cols.filter((c) => c.editable).map((c) => (<label key={c.name} className="flex items-center gap-2 rounded-xl border border-line p-3 text-sm"><input type="checkbox" className="h-4 w-4 accent-[rgb(var(--b600))]" checked={fields.includes(c.name)} onChange={() => setFields((f) => f.includes(c.name) ? f.filter((x) => x !== c.name) : [...f, c.name])} />{c.name}</label>))}</div></Modal>
    </div>);
}
