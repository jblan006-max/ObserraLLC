import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { CardShell } from "@/components/dash";
import { Loader2, Zap, ShieldX, Play, Cpu } from "lucide-react";

const CAPS = [
  ["enabled", "Autonomous engine", "Continuously scan, review & act on live findings"],
  ["auto_apply_config", "Auto-apply safe config fixes", "Non-breaking hardening applied without approval"],
  ["auto_promote", "Auto-promote verified upgrades", "Sandbox-verified dependency upgrades go live automatically"],
  ["auto_rollback", "Auto-rollback on outage", "Revert instantly if a change degrades the endpoint"],
];

// Controls for auto-action WITHIN CAPABILITY — the autonomous remediation engine that acts on
// the org's network/endpoints and devices. Admin toggles persist to /self-scan/engine; quick
// actions execute cycles, AI autofix and threat containment.
export function AutoActions({ accent = "199 89% 48%" }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [eng, setEng] = useState(null);
  const [endpoint, setEndpoint] = useState("");
  const [busy, setBusy] = useState("");

  const load = () => api.get("/self-scan/engine")
    .then((r) => { setEng(r.data.engine); setEndpoint(r.data.endpoint); })
    .catch(() => setEng(null));
  useEffect(() => { load(); }, []);

  const toggle = async (field) => {
    if (!isAdmin || !eng || busy) return;
    const next = !eng[field];
    setEng({ ...eng, [field]: next });
    try { await api.put("/self-scan/engine", { [field]: next }); }
    catch { toast.error("Update failed"); load(); }
  };

  const act = async (kind, url, done) => {
    setBusy(kind);
    try { const { data } = await api.post(url); toast.success(done(data)); }
    catch (e) { toast.error(e.response?.data?.detail || "Action failed"); }
    setBusy(""); load();
  };

  const on = (f) => !!(eng && eng[f]);
  const active = on("enabled") && !on("paused");

  const Toggle = ({ f, testid }) => (
    <button data-testid={testid} disabled={!isAdmin || !!busy} onClick={() => toggle(f)}
      className="relative w-9 h-5 rounded-full transition-colors disabled:opacity-50 shrink-0"
      style={{ background: on(f) ? `hsl(${accent})` : "hsl(215 15% 30%)" }}>
      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${on(f) ? "left-[18px]" : "left-0.5"}`} />
    </button>
  );

  return (
    <CardShell testid="auto-actions" title="Autonomous action controls" icon={Cpu} accent={accent}
      right={<span data-testid="auto-engine-status" className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${active ? "bg-low/15 text-low" : "bg-secondary/60 text-muted-foreground"}`}>{eng ? (active ? "ACTIVE" : on("paused") ? "PAUSED" : "OFF") : "…"}</span>}>
      <p className="text-[11px] text-muted-foreground -mt-2 mb-3">Acts within capability on <span className="font-mono">{endpoint || "your endpoint"}</span> — every change is sandbox-verified before going live. {isAdmin ? "" : "Read-only — admin required to change."}</p>
      <div className="grid sm:grid-cols-2 gap-2 mb-3">
        {CAPS.map(([f, label, desc]) => (
          <div key={f} className="flex items-start justify-between gap-2 bg-secondary/30 rounded-md px-3 py-2">
            <div className="min-w-0"><div className="text-xs font-medium">{label}</div><div className="text-[10px] text-muted-foreground leading-tight">{desc}</div></div>
            <Toggle f={f} testid={`auto-toggle-${f}`} />
          </div>
        ))}
      </div>
      {isAdmin && (
        <div className="flex flex-wrap gap-2">
          <button data-testid="auto-run-cycle" disabled={!!busy} onClick={() => act("run", "/self-scan/engine/run", () => "Autonomous cycle complete")}
            className="flex items-center gap-1.5 text-[11px] font-head font-bold px-3 py-1.5 rounded-full bg-secondary/60 hover:bg-secondary disabled:opacity-50">
            {busy === "run" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} Run cycle now
          </button>
          <button data-testid="auto-autofix" disabled={!!busy} onClick={() => act("fix", "/self-scan/autofix", (d) => d.message || "AI Autofix launched")}
            className="flex items-center gap-1.5 text-[11px] font-head font-bold px-3 py-1.5 rounded-full disabled:opacity-50" style={{ background: `hsl(${accent})`, color: "#050810" }}>
            {busy === "fix" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />} AI Autofix now
          </button>
          <button data-testid="auto-contain" disabled={!!busy} onClick={() => act("contain", "/self-scan/containment/scan", (d) => `Containment evaluated — ${d.active ?? 0} active response(s)`)}
            className="flex items-center gap-1.5 text-[11px] font-head font-bold px-3 py-1.5 rounded-full border border-crit/40 text-crit hover:bg-crit/10 disabled:opacity-50">
            {busy === "contain" ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldX className="w-3 h-3" />} Evaluate containment
          </button>
        </div>
      )}
    </CardShell>
  );
}
