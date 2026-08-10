import { useEffect, useState } from "react";
import { CheckCircle2, Clock, Copy, Database, DoorOpen, Loader2, Plus, ShieldCheck, Trash2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { DataClassBadge, Panel } from "@/components/agentic-ai/shared";
import { api } from "@/lib/api";

const SOURCE_LABEL = {
  agents: "AI Agent Governance",
  analytics: "AI Analytics",
  systems: "AI System Inventory",
  incidents: "AI Incidents",
  workflows: "Workflow Engine",
  connectorHealth: "Connector Health",
};

const fmtDT = (s) => (s ? new Date(s).toLocaleDateString(undefined, { dateStyle: "medium" }) : "—");

// Read-only, expiring Auditor Room — generates a shareable link external auditors can open (no login)
// to view the live AI Enforcement Evidence Pack + signed PDF. Admin only.
function AuditorRoomCard() {
  const [rooms, setRooms] = useState([]);
  const [busy, setBusy] = useState(false);
  const [latest, setLatest] = useState(null);

  const load = () =>
    api.get("/agents/runtime/evidence-rooms").then(({ data }) => setRooms(data.rooms || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const copy = async (url) => {
    try { await navigator.clipboard.writeText(url); toast.success("Link copied"); }
    catch { toast.error("Copy failed — select and copy manually."); }
  };

  const create = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/agents/runtime/evidence-room", { days: 14 });
      setLatest(data);
      try { await navigator.clipboard.writeText(data.url); toast.success("Auditor room link created & copied"); }
      catch { toast.success("Auditor room link created"); }
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not create auditor room.");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (token) => {
    if (!window.confirm("Revoke this auditor room link? External auditors will lose access immediately.")) return;
    try {
      await api.post("/agents/runtime/evidence-room/revoke", { token });
      if (latest?.token === token) setLatest(null);
      toast.success("Auditor room revoked");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Revoke failed.");
    }
  };

  return (
    <Panel
      title="Read-only Auditor Room"
      subtitle="Generate an expiring, no-login link for external auditors to view the live AI Enforcement Evidence Pack (agent toxicity snapshot, runtime enforcement audit trail) and download the signed PDF. Every open is tracked."
      testid="agentic-auditor-room"
      actions={
        <button
          data-testid="auditor-room-create-btn"
          onClick={create}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50"
        >
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
          Create auditor room
        </button>
      }
    >
      {latest && (
        <div
          data-testid="auditor-room-latest"
          className="mb-4 rounded-lg border border-ai/30 bg-ai/5 p-3"
        >
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-ai mb-1.5">
            <DoorOpen className="w-3 h-3" /> New link — share with your auditor · expires {fmtDT(latest.expires_at)}
          </div>
          <div className="flex items-center gap-2">
            <input
              readOnly
              data-testid="auditor-room-latest-url"
              value={latest.url}
              onFocus={(e) => e.target.select()}
              className="flex-1 min-w-0 bg-secondary/50 rounded-md px-2.5 py-2 text-xs font-mono outline-none"
            />
            <button
              data-testid="auditor-room-latest-copy"
              onClick={() => copy(latest.url)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/40 text-ai text-xs font-head font-bold hover:bg-ai/10 transition-colors shrink-0"
            >
              <Copy className="w-3.5 h-3.5" /> Copy
            </button>
          </div>
        </div>
      )}

      {rooms.length === 0 ? (
        <div className="text-sm text-muted-foreground" data-testid="auditor-room-empty">
          No active auditor rooms. Create one to share a read-only evidence link with an external auditor.
        </div>
      ) : (
        <div className="space-y-2" data-testid="auditor-room-list">
          {rooms.map((room) => (
            <div
              key={room.token}
              data-testid={`auditor-room-${room.token}`}
              className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-secondary/20 px-3 py-2.5"
            >
              <DoorOpen className={`w-4 h-4 shrink-0 ${room.expired ? "text-muted-foreground" : "text-ai"}`} />
              <span className="font-mono text-xs truncate max-w-[42%]">{room.url}</span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${room.expired ? "bg-crit/10 text-crit" : "bg-low/10 text-low"}`}>
                {room.expired ? "expired" : `expires ${fmtDT(room.expires_at)}`}
              </span>
              <span className="text-[10px] font-mono text-muted-foreground inline-flex items-center gap-1">
                <Clock className="w-3 h-3" /> {room.opens} open(s)
              </span>
              <div className="ml-auto flex items-center gap-1.5">
                <button
                  data-testid={`auditor-room-copy-${room.token}`}
                  onClick={() => copy(room.url)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded border border-border text-xs hover:bg-secondary transition-colors"
                >
                  <Copy className="w-3 h-3" /> Copy
                </button>
                <button
                  data-testid={`auditor-room-revoke-${room.token}`}
                  onClick={() => revoke(room.token)}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded border border-crit/30 text-crit text-xs hover:bg-crit/10 transition-colors"
                >
                  <Trash2 className="w-3 h-3" /> Revoke
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

export default function DefensibilityDashboard({ data, sourceStatus, isAdmin }) {
  const connectors = data?.connectorHealth?.connectors || [];
  const summary = data?.connectorHealth?.summary || {};

  return (
    <div className="space-y-5">
      {isAdmin && <AuditorRoomCard />}

      <div className="grid xl:grid-cols-3 gap-5">
        <Panel
          title="Data source status"
          subtitle="Unavailable sources are surfaced rather than replaced with synthetic data."
          testid="agentic-source-status"
        >
          <div className="space-y-2">
            {Object.entries(sourceStatus || {}).map(([key, status]) => (
              <div key={key} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
                <div className="flex items-center gap-2 min-w-0">
                  {status.ok ? (
                    <CheckCircle2 className="w-4 h-4 text-low shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-crit shrink-0" />
                  )}
                  <div>
                    <div className="text-sm font-medium">{SOURCE_LABEL[key] || key}</div>
                    {!status.ok && <div className="text-[10px] text-muted-foreground">{status.error}</div>}
                  </div>
                </div>
                <span className={`text-[10px] font-mono ${status.ok ? "text-low" : "text-crit"}`}>
                  {status.ok ? "LIVE" : "UNAVAILABLE"}
                </span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Evidence classification"
          subtitle="The app explicitly separates source facts from derived intelligence."
          testid="agentic-evidence-class"
        >
          <div className="space-y-4">
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="FACT" />
              <p className="text-xs text-muted-foreground mt-2">
                Agent inventory, tools, permissions, guardrails, governance status, AI systems, incidents, usage analytics and connector health returned by the existing backend.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="MODELLED" />
              <p className="text-xs text-muted-foreground mt-2">
                Agent risk score, delegated authority tier and action-capable tool classification calculated in the browser from existing records.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="HEURISTIC BASELINE" />
              <p className="text-xs text-muted-foreground mt-2">
                Existing red-team results are deterministic checks against recorded guardrails. They are not live adversarial runtime tests.
              </p>
            </div>
            <div className="rounded-lg border border-border p-4">
              <DataClassBadge kind="AI RECOMMENDATION" />
              <p className="text-xs text-muted-foreground mt-2">
                Obserra Advisor interpretation, analysis and recommended executive actions.
              </p>
            </div>
          </div>
        </Panel>

        <Panel
          title="Runtime enforcement boundary"
          subtitle="Governance state is not confused with external runtime control."
          testid="agentic-runtime-boundary"
        >
          <div className="space-y-3 text-sm">
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Toggling a guardrail updates the existing Obserra governance record.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Sanctioning a system updates its governance status in Obserra.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              No external model, agent runtime or cloud service is claimed to be blocked unless a connected execution control verifies that action.
            </div>
            <div className="flex gap-2">
              <ShieldCheck className="w-4 h-4 text-low shrink-0 mt-0.5" />
              Future live red-team and kill-switch capabilities require explicit runtime connectors.
            </div>
          </div>
        </Panel>
      </div>

      <Panel
        title="Connector health context"
        subtitle={`${summary.healthy || 0} healthy · ${summary.degraded || 0} degraded. Existing connector health only.`}
        testid="agentic-connectors"
      >
        {connectors.length === 0 ? (
          <div className="py-8 text-center">
            <Database className="w-8 h-8 text-muted-foreground mx-auto" />
            <div className="text-sm text-muted-foreground mt-2">No connector health records are available.</div>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {connectors.map((connector) => (
              <div key={`${connector.id}:${connector.name}`} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="font-head font-bold text-sm">{connector.name}</div>
                    <div className="text-[10px] text-muted-foreground mt-1">{connector.category}</div>
                  </div>
                  <span className={`text-[10px] font-mono ${connector.health === "healthy" ? "text-low" : connector.health === "degraded" ? "text-high" : "text-muted-foreground"}`}>
                    {connector.health || connector.state || "unknown"}
                  </span>
                </div>
                <div className="text-[10px] text-muted-foreground mt-3">
                  Last checked: {connector.checked_at ? new Date(connector.checked_at).toLocaleString() : "not available"}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
