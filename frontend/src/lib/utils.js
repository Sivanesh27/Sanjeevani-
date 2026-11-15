export const cx = (...a) => a.filter(Boolean).join(" ");
export const fmtDate = (d, opts = {}) => (d ? new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric", ...opts }) : "-");
export const fmtDateTime = (d) => (d ? new Date(d).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "-");
export const initials = (n = "") => n.split(" ").filter(Boolean).slice(0, 2).map((x) => x[0]?.toUpperCase()).join("") || "?";
export const LEVEL = {
  Critical: { bar: "bg-sev-crit", text: "text-sev-crit", soft: "bg-sev-crit/10 border-sev-crit/30", label: "Critical" },
  High: { bar: "bg-sev-high", text: "text-sev-high", soft: "bg-sev-high/10 border-sev-high/30", label: "High" },
  Moderate: { bar: "bg-sev-mod", text: "text-sev-mod", soft: "bg-sev-mod/10 border-sev-mod/30", label: "Moderate" },
  Low: { bar: "bg-sev-low", text: "text-sev-low", soft: "bg-sev-low/10 border-sev-low/30", label: "Low" },
  None: { bar: "bg-sev-low", text: "text-sev-low", soft: "bg-sev-low/10 border-sev-low/30", label: "No issues" },
};
export const lvl = (l) => LEVEL[l] || { bar: "bg-muted", text: "text-muted", soft: "bg-raised border-line", label: l || "-" };
export const clean = (obj) => Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v]));
export const num = (v) => (v === "" || v == null ? null : Number(v));
export function downloadJSON(name, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name }); a.click(); URL.revokeObjectURL(url);
}
