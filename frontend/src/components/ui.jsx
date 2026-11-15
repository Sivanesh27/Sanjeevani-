import { createContext, useCallback, useContext, useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { Loader2, X, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { cx, lvl } from "../lib/utils";

export function Spinner({ className = "" }) { return <Loader2 className={cx("animate-spin", className || "h-5 w-5")} aria-label="Loading" />; }
export function PageLoader({ label = "Loading…" }) {
  return <div className="flex min-h-[40vh] items-center justify-center gap-3 text-muted"><Spinner className="h-6 w-6 text-brand-600" /><span>{label}</span></div>;
}

export function Button({ variant = "primary", loading, className, children, icon: Icon, ...p }) {
  return (
    <button {...p} disabled={p.disabled || loading} className={cx("btn", `btn-${variant}`, className)}>
      {loading ? <Spinner className="h-4 w-4" /> : Icon ? <Icon className="h-4 w-4" /> : null}{children}
    </button>
  );
}

export function Field({ label, hint, error, children, className }) {
  return (
    <label className={cx("block", className)}>
      {label && <span className="label">{label}</span>}
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs font-medium text-sev-crit" role="alert">{error}</span>}
    </label>
  );
}
export const Input = ({ label, hint, error, className, wrap, ...p }) => <Field label={label} hint={hint} error={error} className={wrap}><input {...p} className={cx("input", error && "!border-sev-crit", className)} /></Field>;
export const Textarea = ({ label, hint, error, className, wrap, ...p }) => <Field label={label} hint={hint} error={error} className={wrap}><textarea {...p} className={cx("input py-3 min-h-[96px]", className)} /></Field>;
export const Select = ({ label, hint, error, options, className, wrap, placeholder, ...p }) => (
  <Field label={label} hint={hint} error={error} className={wrap}>
    <select {...p} className={cx("input appearance-none bg-[length:16px] pr-9", className)}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return <option key={v} value={v}>{l}</option>; })}
    </select>
  </Field>
);

export function Switch({ checked, onChange, label, hint, disabled }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div><div className="text-[15px] font-medium">{label}</div>{hint && <div className="mt-0.5 text-sm text-muted">{hint}</div>}</div>
      <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}
        className={cx("relative mt-0.5 h-7 w-12 shrink-0 rounded-full transition disabled:opacity-50", checked ? "bg-brand-600" : "bg-line")}>
        <span className={cx("absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-all", checked ? "left-[22px]" : "left-0.5")} />
      </button>
    </div>
  );
}

export function Card({ className, children, ...p }) { return <div {...p} className={cx("card", className)}>{children}</div>; }
export function CardHeader({ title, subtitle, action, icon: Icon }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
      <div className="flex items-center gap-3">
        {Icon && <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-600"><Icon className="h-[18px] w-[18px]" /></span>}
        <div><h3 className="h-display text-[17px] font-bold leading-tight">{title}</h3>{subtitle && <p className="text-sm text-muted">{subtitle}</p>}</div>
      </div>{action}
    </div>
  );
}

export function LevelBadge({ level, className }) {
  const l = lvl(level);
  return <span className={cx("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", l.soft, l.text, className)}>{l.label}</span>;
}
export const Pill = ({ children, className }) => <span className={cx("inline-flex items-center gap-1 rounded-full bg-raised px-2.5 py-0.5 text-xs font-medium text-muted", className)}>{children}</span>;

export function Modal({ open, onClose, title, children, footer, wide }) {
  useEffect(() => {
    if (!open) return;
    const k = (e) => e.key === "Escape" && onClose?.();
    document.addEventListener("keydown", k); document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", k); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-slate-950/50 backdrop-blur-[2px]" onClick={onClose} />
      <div className={cx("sheet relative flex max-h-[92dvh] w-full flex-col rounded-t-3xl border border-line bg-surface shadow-pop sm:rounded-2xl", wide ? "sm:max-w-3xl" : "sm:max-w-lg")}>
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h3 className="h-display text-lg font-bold">{title}</h3>
          <button onClick={onClose} className="btn-ghost btn !min-h-[36px] !px-2" aria-label="Close"><X className="h-5 w-5" /></button>
        </div>
        <div className="overflow-y-auto px-5 py-5">{children}</div>
        {footer && <div className="safe-b flex flex-col-reverse gap-2 border-t border-line px-5 py-4 sm:flex-row sm:justify-end">{footer}</div>}
      </div>
    </div>, document.body);
}

export function Confirm({ open, title, message, confirmLabel = "Confirm", danger, onConfirm, onClose, children }) {
  const [busy, setBusy] = useState(false);
  return (
    <Modal open={open} onClose={onClose} title={title} footer={<>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button variant={danger ? "danger" : "primary"} loading={busy} onClick={async () => { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } }}>{confirmLabel}</Button></>}>
      <p className="text-[15px] text-ink/80">{message}</p>{children}
    </Modal>
  );
}

const ToastCtx = createContext(null);
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((kind, text) => {
    const id = Math.random(); setItems((s) => [...s, { id, kind, text }]); setTimeout(() => setItems((s) => s.filter((x) => x.id !== id)), 4500);
  }, []);
  const api = { success: (t) => push("ok", t), error: (t) => push("err", t), info: (t) => push("info", t) };
  return (
    <ToastCtx.Provider value={api}>{children}
      <div className="pointer-events-none fixed inset-x-0 top-3 z-[60] flex flex-col items-center gap-2 px-3 safe-t" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className="fade-up pointer-events-auto flex max-w-md items-start gap-2.5 rounded-xl border border-line bg-surface px-4 py-3 text-sm font-medium shadow-pop">
            {t.kind === "ok" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-sev-low" /> : t.kind === "err" ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-sev-crit" /> : <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />}
            <span>{t.text}</span>
          </div>))}
      </div>
    </ToastCtx.Provider>
  );
}

export function EmptyState({ icon: Icon, title, text, action }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      {Icon && <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600"><Icon className="h-6 w-6" /></span>}
      <div className="h-display text-base font-bold">{title}</div>{text && <p className="max-w-sm text-sm text-muted">{text}</p>}{action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function Tabs({ tabs, value, onChange, className }) {
  return (
    <div className={cx("scroll-x -mx-1 flex gap-1 rounded-2xl bg-raised p-1", className)} role="tablist">
      {tabs.map(([k, label, Icon]) => (
        <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)}
          className={cx("flex min-h-[40px] flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-xl px-3.5 text-sm font-semibold transition", value === k ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink")}>
          {Icon && <Icon className="h-4 w-4" />}{label}
        </button>))}
    </div>
  );
}

export function Stat({ label, value, sub, icon: Icon, tone }) {
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-center justify-between"><span className="text-[13px] font-medium text-muted">{label}</span>{Icon && <Icon className={cx("h-4 w-4", tone || "text-brand-600")} />}</div>
      <div className="h-display mt-2 text-3xl font-extrabold">{value}</div>{sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </Card>
  );
}

export function Logo({ size = 36, text = true, className }) {
  const id = useId();
  return (
    <span className={cx("inline-flex items-center gap-2.5", className)}>
      <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true"><defs><linearGradient id={id} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#14b8a6" /><stop offset="1" stopColor="#0f766e" /></linearGradient></defs>
        <rect width="48" height="48" rx="13" fill={`url(#${id})`} /><path d="M24 9c-6.5 3.7-10.5 9.2-10.5 15 0 5.8 4.7 10.5 10.5 10.5S34.5 29.8 34.5 24C34.5 18.2 30.5 12.7 24 9z" fill="#ecfdf5" />
        <path d="M24 14v19M24 22c-2.8-.6-4.9-2.2-5.8-4.7M24 27c2.8-.6 4.9-2.2 5.8-4.7" stroke="#0f766e" strokeWidth="1.9" strokeLinecap="round" fill="none" /></svg>
      {text && <span className="h-display text-[19px] font-extrabold tracking-tight">Sanjeevani <span className="text-brand-600">AI</span></span>}
    </span>
  );
}
