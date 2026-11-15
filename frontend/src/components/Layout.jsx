import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Home, HeartPulse, Activity, UserRound, Settings, LogOut, LayoutDashboard, Users, Database, ScrollText, Stethoscope } from "lucide-react";
import { useAuth } from "../lib/auth";
import { Logo } from "./ui";
import { cx, initials } from "../lib/utils";

const NAV = {
  patient: [["/app", "Home", Home, true], ["/app/medical", "My health", HeartPulse], ["/app/analysis", "Analysis", Activity], ["/app/profile", "Profile", UserRound], ["/app/settings", "Settings", Settings]],
  admin: [["/admin", "Overview", LayoutDashboard, true], ["/admin/patients", "Patients", Users], ["/admin/data", "Data", Database], ["/admin/audit", "Audit", ScrollText]],
};

export default function Layout({ role }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const items = NAV[role];
  const out = async () => { await logout(); nav(role === "admin" ? "/admin/login" : "/login"); };
  return (
    <div className="min-h-[100dvh] lg:grid lg:grid-cols-[264px_1fr]">
      <aside className="no-print sticky top-0 hidden h-[100dvh] flex-col border-r border-line bg-surface px-4 py-6 lg:flex">
        <Logo className="px-2" />
        {role === "admin" && <div className="mx-2 mt-4 flex items-center gap-2 rounded-xl bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700"><Stethoscope className="h-4 w-4" />Doctor console</div>}
        <nav className="mt-6 flex flex-1 flex-col gap-1">
          {items.map(([to, label, Icon, end]) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => cx("flex min-h-[44px] items-center gap-3 rounded-xl px-3 text-[15px] font-semibold transition", isActive ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-raised hover:text-ink")}>
              <Icon className="h-[19px] w-[19px]" />{label}</NavLink>))}
        </nav>
        <div className="flex items-center gap-3 rounded-2xl border border-line p-3">
          <span className="grid h-10 w-10 place-items-center rounded-full bg-brand-600 text-sm font-bold text-onbrand">{initials(user?.display_name || user?.email)}</span>
          <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">{user?.display_name || "Account"}</div><div className="truncate text-xs text-muted">{user?.email}</div></div>
          <button onClick={out} className="btn btn-ghost !min-h-[36px] !px-2" aria-label="Sign out"><LogOut className="h-[18px] w-[18px]" /></button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="no-print safe-t sticky top-0 z-30 flex items-center justify-between border-b border-line bg-surface/85 px-4 py-3 backdrop-blur lg:hidden">
          <Logo size={32} />
          <button onClick={out} className="btn btn-ghost !min-h-[40px] !px-3 text-sm" aria-label="Sign out"><LogOut className="h-[18px] w-[18px]" /></button>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-28 pt-5 sm:px-6 lg:px-8 lg:pb-12 lg:pt-8"><Outlet /></main>
        <nav className="no-print safe-b fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 backdrop-blur lg:hidden" aria-label="Primary">
          <div className="mx-auto flex max-w-lg">
            {items.map(([to, label, Icon, end]) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => cx("flex min-h-[58px] flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-semibold", isActive ? "text-brand-600" : "text-muted")}>
                <Icon className="h-[22px] w-[22px]" />{label}</NavLink>))}
          </div>
        </nav>
      </div>
    </div>
  );
}
