import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate, useLocation, Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { AIAdvisor } from "@/components/AIAdvisor";
import { NotificationBell } from "@/components/NotificationBell";
import ForcePasswordReset from "@/pages/ForcePasswordReset";
import { Footer } from "@/components/Footer";
import {
  LayoutDashboard, ListChecks, Cpu, GitBranch, ScrollText, CreditCard, LogOut, Presentation,
  Wrench, Globe, Radar, Boxes, FileBarChart, Store, Lock, Loader2, Clock, Network, ShieldCheck, Users, Layers, Settings, Bot, Building2, Building, BarChart3, ShieldAlert, Sparkles, Wallet, Plug,
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

const NAV = [
  { to: "/app", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/app/situation-room", label: "Situation Room", icon: Radar, ent: "situation_room" },
  { to: "/app/risks", label: "Risk Register", icon: ListChecks },
  { to: "/app/ai-governance", label: "AI Governance", icon: Cpu },
  { to: "/app/controls", label: "Control Monitoring", icon: ShieldCheck },
  { to: "/app/compliance", label: "Compliance Posture", icon: ShieldCheck },
  { to: "/app/assets", label: "Asset Intelligence", icon: Boxes, ent: "asset_intelligence" },
  { to: "/app/knowledge-graph", label: "Knowledge Graph", icon: Network },
  { to: "/app/decisions", label: "Recommendations", icon: GitBranch },
  { to: "/app/reporting", label: "Evidence & Reporting", icon: FileBarChart, ent: "evidence_reporting" },
  { to: "/app/audit", label: "Audit Log", icon: ScrollText },
  { to: "/app/agents", label: "AI Agents", icon: Bot },
  { to: "/app/vendors", label: "Third-Party Risk", icon: Building },
  { to: "/app/cyber-risk", label: "Cyber Risk", icon: ShieldAlert },
  { to: "/app/studio", label: "Studio", icon: Sparkles },
  { to: "/app/benchmark", label: "Benchmarking", icon: BarChart3 },
  { to: "/app/kernel", label: "Platform Kernel", icon: Layers, admin: true },
  { to: "/app/team", label: "Team", icon: Users, admin: true },
  { to: "/app/enterprise", label: "Enterprise", icon: Building2, admin: true },
  { to: "/app/connectors", label: "Available Connectors", icon: Plug, admin: true },
  { to: "/app/spend-governance", label: "AI Spend", icon: Wallet, admin: true },
  { to: "/app/settings", label: "Settings", icon: Settings },
  { to: "/app/marketplace", label: "Marketplace", icon: Store },
  { to: "/app/billing", label: "Billing", icon: CreditCard },
];

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

export default function AppShell() {
  const { user, sub, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [paywall, setPaywall] = useState(false);

  useEffect(() => {
    const h = () => setPaywall(true);
    window.addEventListener("eios-paywall", h);
    return () => window.removeEventListener("eios-paywall", h);
  }, []);

  const doLogout = async () => { await logout(); navigate("/"); };
  const ents = sub?.entitlements || [];
  const enterprise = sub?.plan === "enterprise";
  const owns = (ent) => !ent || enterprise || ents.includes(ent);
  const allowedWhenInactive = ["/app/billing", "/app/marketplace"];
  const inactive = (sub && !sub.active) || paywall;
  const blocked = inactive && !allowedWhenInactive.includes(location.pathname);

  if (user?.must_change_password) return <ForcePasswordReset />;

  return (
    <div className="min-h-screen grain flex">
      <aside className="hidden md:flex w-60 flex-col border-r border-border bg-card/40 sticky top-0 h-screen">
        <div className="flex items-center px-4 h-16 border-b border-border">
          <img src="/logo.png" alt="Obserra — Executive Protection & Intelligence LLC" className="h-9 w-auto object-contain" />
        </div>
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV.filter((n) => !n.admin || user?.role === "admin").map((n) => {
            const locked = !owns(n.ent);
            return (
              <NavLink key={n.to} to={locked ? "/app/marketplace" : n.to} end={n.end}
                data-testid={`nav-${n.label.toLowerCase().replace(/ &/g, "").replace(/ /g, "-")}`}
                className={({ isActive }) => `flex items-center justify-between gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-200 ${
                  isActive && !locked ? "bg-primary/15 text-foreground border border-primary/30" : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"}`}>
                <span className="flex items-center gap-3"><n.icon className="w-4 h-4" /> {n.label}</span>
                {locked && <Lock className="w-3 h-3 text-muted-foreground" />}
              </NavLink>
            );
          })}
        </nav>
        <div className="p-3 border-t border-border">
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
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 h-16 flex items-center justify-between gap-4 px-6 border-b border-border/40 backdrop-blur-xl bg-background/70">
          <div className="text-xs font-mono text-muted-foreground uppercase tracking-widest truncate hidden lg:block">
            {sub?.org_name || "Obserra — Executive Protection & Intelligence LLC"}
          </div>
          <div className="flex-1 max-w-md">
            <div className="flex items-center gap-2 rounded-full border border-ai/30 bg-ai/5 px-3 py-1.5 focus-within:ring-1 focus-within:ring-ai transition-shadow">
              <img src="/logo.png" alt="Obserra Advisor" className="h-5 w-5 rounded-full object-cover shrink-0" style={{ objectPosition: "left center" }} />
              <input data-testid="header-advisor-input" placeholder="Ask the Obserra Advisor…"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.currentTarget.value.trim()) {
                    window.dispatchEvent(new CustomEvent("open-advisor", { detail: e.currentTarget.value.trim() }));
                    e.currentTarget.value = "";
                  }
                }}
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <NotificationBell />
            <DualModeToggle />
          </div>
        </header>
        <main className="flex-1 p-6 lg:p-8 max-w-[1500px] w-full">
          {blocked ? <Paywall /> : <Outlet />}
        </main>
        <Footer />
      </div>

      <AIAdvisor />
    </div>
  );
}
