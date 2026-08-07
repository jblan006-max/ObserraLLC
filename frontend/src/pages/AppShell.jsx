import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { AIAdvisor } from "@/components/AIAdvisor";
import { ShieldHalf, LayoutDashboard, ListChecks, Cpu, GitBranch, ScrollText, CreditCard, LogOut, Presentation, Wrench } from "lucide-react";

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
  { to: "/app/risks", label: "Risk Register", icon: ListChecks },
  { to: "/app/ai-governance", label: "AI Governance", icon: Cpu },
  { to: "/app/decisions", label: "Recommendations", icon: GitBranch },
  { to: "/app/audit", label: "Audit Log", icon: ScrollText },
  { to: "/app/billing", label: "Billing", icon: CreditCard },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const doLogout = async () => { await logout(); navigate("/"); };

  return (
    <div className="min-h-screen grain flex">
      <aside className="hidden md:flex w-60 flex-col border-r border-border bg-card/40 sticky top-0 h-screen">
        <div className="flex items-center px-4 h-16 border-b border-border">
          <img src="/logo.png" alt="Obserra — Executive Protection & Intelligence LLC" className="h-9 w-auto object-contain" />
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} data-testid={`nav-${n.label.toLowerCase().replace(/ /g, "-")}`}
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors duration-200 ${
                isActive ? "bg-primary/15 text-foreground border border-primary/30" : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"}`}>
              <n.icon className="w-4 h-4" /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-border">
          <div className="px-2 py-1 mb-2">
            <div className="text-sm font-medium truncate">{user?.name}</div>
            <div className="text-[10px] font-mono text-muted-foreground uppercase">{user?.role}</div>
          </div>
          <button data-testid="logout-btn" onClick={doLogout}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-crit hover:bg-crit/10 transition-colors duration-200">
            <LogOut className="w-4 h-4" /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 h-16 flex items-center justify-between px-6 border-b border-border/40 backdrop-blur-xl bg-background/70">
          <div className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
            Obserra — Executive Protection &amp; Intelligence LLC
          </div>
          <DualModeToggle />
        </header>
        <main className="flex-1 p-6 lg:p-8 max-w-[1500px] w-full">
          <Outlet />
        </main>
      </div>

      <AIAdvisor />
    </div>
  );
}
