import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate, useLocation, Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { AIAdvisor } from "@/components/AIAdvisor";
import { OnboardingTour } from "@/components/OnboardingTour";
import { LockedGate } from "@/components/LockedGate";
import { FirstRunWizard } from "@/components/FirstRunWizard";
import { NotificationBell } from "@/components/NotificationBell";
import ForcePasswordReset from "@/pages/ForcePasswordReset";
import { Footer } from "@/components/Footer";
import {
  LayoutDashboard, ListChecks, Cpu, GitBranch, ScrollText, CreditCard, LogOut, Presentation,
  Wrench, Globe, Radar, Boxes, FileBarChart, Store, Lock, Loader2, Clock, Network, ShieldCheck, Users, Layers, Settings, Bot, Building2, Building, BarChart3, ShieldAlert, Sparkles, Wallet, Plug, Menu, X, Smartphone, ChevronDown, ChevronRight, ChevronUp,
} from "lucide-react";

function DualModeToggle() {
  const { mode, switchMode } = useAuth();
  return (
    <div data-testid="mode-toggle" className="flex items-center p-0.5 rounded-full bg-secondary/70 border border-border text-xs font-head font-bold">
      <button data-testid="mode-toggle-executive" onClick={() => switchMode("executive")}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-colors duration-200 ${mode === "executive" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
        <Presentation className="w-3.5 h-3.5" /> Executive
      </button>
      <button data-testid="mode-toggle-operational" onClick={() => switchMode("operational")}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-colors duration-200 ${mode === "operational" ? "bg-ai text-background" : "text-muted-foreground"}`}>
        <Wrench className="w-3.5 h-3.5" /> Operational
      </button>
    </div>
  );
}

const NAV_SECTIONS = [
  { section: null, items: [
    { to: "/app", label: "Overview", icon: LayoutDashboard, end: true },
  ]},
  { section: "Risk", ent: "cyber_risk", cat: true, color: "crit", items: [
    { to: "/app/cyber-risk", label: "Risk (FAIR)", icon: ShieldAlert },
    { to: "/app/risks", label: "Risk Register", icon: ListChecks },
    { to: "/app/compliance", label: "Compliance Posture", icon: ShieldCheck, ent: "reporting_board" },
  ]},
  { section: "Cyber", ent: "cyber_risk", cat: true, color: "crit", items: [
    { to: "/app/situation-room", label: "Situation Room", icon: Radar },
    { to: "/app/controls", label: "Control Monitoring", icon: ShieldCheck },
    { to: "/app/security", label: "Security Scanner", icon: ShieldAlert },
    { to: "/app/decisions", label: "Remediations", icon: GitBranch },
    { to: "/app/assets", label: "Asset Intelligence", icon: Boxes, ent: "asset_intelligence" },
  ]},
  { section: "AI Governance", ent: "ai_governance", cat: true, color: "ai", items: [
    { to: "/app/ai-governance", label: "AI Governance", icon: Cpu },
    { to: "/app/agents", label: "AI Agents", icon: Bot },
  ]},
  { section: "Third-Party Risk", ent: "third_party_risk", cat: true, color: "high", items: [
    { to: "/app/vendors", label: "Third-Party Risk", icon: Building },
  ]},
  { section: "Reporting", ent: "reporting_board", cat: true, color: "low", items: [
    { to: "/app/reporting", label: "Evidence & Reporting", icon: FileBarChart },
    { to: "/app/studio", label: "Studio", icon: Sparkles },
    { to: "/app/benchmark", label: "Benchmarking", icon: BarChart3 },
    { to: "/app/knowledge-graph", label: "Knowledge Graph", icon: Network },
    { to: "/app/snapshot", label: "Exec Snapshot", icon: Smartphone },
  ]},
  { section: "Audit & Evidence", ent: "audit_evidence", cat: true, color: "med", items: [
    { to: "/app/audit", label: "Audit Log", icon: ScrollText },
  ]},
  { section: "Admin", admin: true, items: [
    { to: "/app/kernel", label: "Platform Kernel", icon: Layers },
    { to: "/app/team", label: "Team", icon: Users },
    { to: "/app/enterprise", label: "Enterprise", icon: Building2 },
    { to: "/app/connectors", label: "Available Connectors", icon: Plug },
    { to: "/app/spend-governance", label: "AI Spend", icon: Wallet },
  ]},
  { section: "Account", items: [
    { to: "/app/settings", label: "Settings", icon: Settings },
    { to: "/app/marketplace", label: "Marketplace", icon: Store },
    { to: "/app/billing", label: "Billing", icon: CreditCard },
  ]},
];

const NAV = NAV_SECTIONS.flatMap((s) =>
  s.items.map((it) => ({ ...it, ent: it.ent ?? s.ent, admin: it.admin ?? s.admin })));

function Paywall() {
  const navigate = useNavigate();
  return (
    <div className="flex items-center justify-center h-[70vh]">
      <div className="max-w-md text-center bg-card fact-border rounded-xl p-8 rise">
        <Lock className="w-10 h-10 text-med mx-auto mb-4" />
        <h1 className="font-head font-black text-2xl">Subscription required</h1>
        <p className="text-sm text-muted-foreground mt-2 mb-6">Your trial or subscription is inactive. Choose a plan to restore access to your risk and AI governance intelligence.</p>
        <button data-testid="paywall-cta" onClick={() => navigate("/app/billing")} className="px-6 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm">View plans</button>
      </div>
    </div>
  );
}

const CAT_STYLE = {
  ai: { text: "text-ai", dot: "bg-ai", border: "border-ai/30", glow: "bg-ai/5" },
  crit: { text: "text-crit", dot: "bg-crit", border: "border-crit/30", glow: "bg-crit/5" },
  high: { text: "text-high", dot: "bg-high", border: "border-high/30", glow: "bg-high/5" },
  primary: { text: "text-primary", dot: "bg-primary", border: "border-primary/30", glow: "bg-primary/5" },
  med: { text: "text-med", dot: "bg-med", border: "border-med/30", glow: "bg-med/5" },
  low: { text: "text-low", dot: "bg-low", border: "border-low/30", glow: "bg-low/5" },
};

function SidebarInner({ user, sub, owns, doLogout, onNav, onClose }) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return JSON.parse(localStorage.getItem("obserra-nav-collapsed") || "{}"); } catch { return {}; }
  });
  const toggle = (key) => setCollapsed((c) => {
    const next = { ...c, [key]: !c[key] };
    localStorage.setItem("obserra-nav-collapsed", JSON.stringify(next));
    return next;
  });
  const sectionKeys = NAV_SECTIONS.filter((s) => s.section).map((s) => s.section);
  const allCollapsed = sectionKeys.every((k) => collapsed[k]);
  const setAll = (val) => {
    const next = {}; sectionKeys.forEach((k) => { next[k] = val; });
    localStorage.setItem("obserra-nav-collapsed", JSON.stringify(next));
    setCollapsed(next);
  };
  return (
    <>
      <div className="flex items-center justify-between px-4 h-16 border-b border-border shrink-0">
        <img src="/brand-lockup.png" alt="Obserra — Executive Protection & Intelligence LLC" className="h-7 w-auto object-contain" />
        {onClose && <button data-testid="mobile-nav-close" onClick={onClose} className="md:hidden p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary/50"><X className="w-5 h-5" /></button>}
      </div>
      <nav className="flex-1 p-3 space-y-4 overflow-y-auto">
        <div className="flex justify-end -mt-1 mb-1">
          <button data-testid="nav-collapse-all" onClick={() => setAll(!allCollapsed)}
            className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground/60 hover:text-foreground transition-colors">
            {allCollapsed ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
            {allCollapsed ? "Expand all" : "Collapse all"}
          </button>
        </div>
        {NAV_SECTIONS.filter((s) => !s.admin || user?.role === "admin").map((sec, si) => {
          const cs = sec.cat ? CAT_STYLE[sec.color] : null;
          const key = sec.section || `s${si}`;
          const isColl = sec.section ? !!collapsed[key] : false;
          const Chevron = isColl ? ChevronRight : ChevronDown;
          return (
            <div key={key} className="space-y-1">
              {sec.section && (
                cs ? (
                  <button type="button" data-testid={`nav-section-${key.toLowerCase().replace(/ &/g, "").replace(/ /g, "-")}`} onClick={() => toggle(key)}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 mb-1 rounded-md border ${cs.border} ${cs.glow} transition-colors`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${cs.dot} shadow-[0_0_6px] shadow-current`} />
                    <span className={`text-[11px] font-head font-black uppercase tracking-[0.12em] ${cs.text}`}>{sec.section}</span>
                    <Chevron className={`w-3.5 h-3.5 ml-auto ${cs.text}`} />
                  </button>
                ) : (
                  <button type="button" data-testid={`nav-section-${key.toLowerCase().replace(/ &/g, "").replace(/ /g, "-")}`} onClick={() => toggle(key)}
                    className="w-full flex items-center px-3 pt-1 pb-1 text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-muted-foreground/50 hover:text-muted-foreground transition-colors">
                    {sec.section}
                    <Chevron className="w-3 h-3 ml-auto" />
                  </button>
                )
              )}
              {!isColl && (
                <div className={cs ? `ml-2.5 pl-2 border-l ${cs.border} space-y-1` : "space-y-1"}>
                  {sec.items.map((n) => {
                    const ent = n.ent ?? sec.ent;
                    const locked = !owns(ent);
                    return (
                      <NavLink key={n.to} to={n.to} end={n.end} onClick={onNav}
                        data-testid={`nav-${n.label.toLowerCase().replace(/ &/g, "").replace(/ /g, "-")}`}
                        className={({ isActive }) => `flex items-center justify-between gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-200 ${
                          isActive && !locked ? "bg-primary/15 text-foreground border border-primary/30" : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"}`}>
                        <span className="flex items-center gap-3"><n.icon className="w-4 h-4" /> {n.label}</span>
                        {locked && <Lock className="w-3 h-3 text-muted-foreground" />}
                      </NavLink>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>
      <div className="p-3 border-t border-border shrink-0">
        {sub && (
          <div className="mb-2 px-2 py-1.5 rounded-md bg-secondary/40 text-[10px] font-mono flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${sub.active ? "bg-low" : "bg-crit"}`} />
            <span className="uppercase text-muted-foreground">{sub.plan}</span>
            {sub.plan === "trial" && sub.trial_end && <span className="text-muted-foreground flex items-center gap-1 ml-auto"><Clock className="w-3 h-3" />trial</span>}
          </div>
        )}
        <div className="px-2 py-1 mb-2">
          <div className="text-sm font-medium truncate">{user?.name}</div>
          <div className="text-[10px] font-mono text-muted-foreground uppercase">{user?.role}</div>
        </div>
        <button data-testid="logout-btn" onClick={doLogout} className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-crit hover:bg-crit/10 transition-colors duration-200">
          <LogOut className="w-4 h-4" /> Sign out
        </button>
        <a data-testid="visit-site-link-nav" href="https://www.obserrallc.com/" target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-2 w-full px-3 py-2 mt-1 rounded-md text-xs text-muted-foreground hover:text-ai transition-colors duration-200">
          <Globe className="w-3.5 h-3.5" /> obserrallc.com
        </a>
      </div>
    </>
  );
}

export default function AppShell() {
  const { user, sub, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [paywall, setPaywall] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);

  useEffect(() => {
    const h = () => setPaywall(true);
    window.addEventListener("eios-paywall", h);
    return () => window.removeEventListener("eios-paywall", h);
  }, []);

  const doLogout = async () => { await logout(); navigate("/"); };
  const ents = sub?.entitlements || [];
  const enterprise = !sub?.restricted && sub?.plan === "enterprise";
  const owns = (ent) => !ent || enterprise || ents.includes(ent);
  const allowedWhenInactive = ["/app/billing", "/app/marketplace"];
  const inactive = (sub && !sub.active) || paywall;
  const blocked = inactive && !allowedWhenInactive.includes(location.pathname);
  const routeEnt = Object.fromEntries(NAV.filter((n) => n.ent).map((n) => [n.to, n.ent]));
  const currentEnt = routeEnt[location.pathname];
  const locked = currentEnt && !owns(currentEnt);

  if (user?.must_change_password) return <ForcePasswordReset />;

  return (
    <div className="min-h-screen grain flex">
      <aside className="hidden md:flex w-60 flex-col border-r border-border bg-card/40 sticky top-0 h-screen">
        <SidebarInner user={user} sub={sub} owns={owns} doLogout={doLogout} />
      </aside>

      {mobileNav && (
        <div className="md:hidden fixed inset-0 z-[60] flex" data-testid="mobile-nav-overlay">
          <div className="absolute inset-0 bg-background/70 backdrop-blur-sm" onClick={() => setMobileNav(false)} />
          <aside data-testid="mobile-nav-drawer" className="relative w-64 max-w-[82%] flex flex-col border-r border-border bg-card h-full rise" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
            <SidebarInner user={user} sub={sub} owns={owns} doLogout={doLogout} onNav={() => setMobileNav(false)} onClose={() => setMobileNav(false)} />
          </aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 h-16 flex items-center justify-between gap-3 px-4 sm:px-6 border-b border-border/40 backdrop-blur-xl bg-background/70">
          <div className="flex items-center gap-2 min-w-0">
            <button data-testid="mobile-nav-toggle" onClick={() => setMobileNav(true)} className="md:hidden p-2 -ml-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary/50">
              <Menu className="w-5 h-5" />
            </button>
            <img src="/brand-lockup.png" alt="Obserra" className="h-6 w-auto object-contain md:hidden" />
            <div className="text-xs font-mono text-muted-foreground uppercase tracking-widest truncate hidden lg:block">
              {sub?.org_name || "Obserra — Executive Protection & Intelligence LLC"}
            </div>
          </div>
          <div className="flex-1 max-w-md hidden sm:block">
            <div className="flex items-center gap-2 rounded-full border border-ai/30 bg-ai/5 px-3 py-1.5 focus-within:ring-1 focus-within:ring-ai transition-shadow">
              <img src="/brand-mark.png" alt="Obserrian Advisor" className="h-5 w-5 object-contain shrink-0" />
              <input data-testid="header-advisor-input" placeholder="Ask the Obserrian Advisor…"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.currentTarget.value.trim()) {
                    window.dispatchEvent(new CustomEvent("open-advisor", { detail: e.currentTarget.value.trim() }));
                    e.currentTarget.value = "";
                  }
                }}
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <NotificationBell />
            <DualModeToggle />
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-[1500px] w-full min-w-0 overflow-x-hidden pb-28 md:pb-8">
          {blocked ? <Paywall /> : locked ? <LockedGate ent={currentEnt} /> : <Outlet />}
        </main>
        <Footer />
      </div>

      <AIAdvisor />
      <OnboardingTour />
      <FirstRunWizard />
    </div>
  );
}
