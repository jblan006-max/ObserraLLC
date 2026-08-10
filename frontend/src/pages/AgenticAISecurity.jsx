import { useState } from "react";
import {
  AlertOctagon,
  Bot,
  Download,
  EyeOff,
  Gauge,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Wrench,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { AIInsight } from "@/components/AIInsight";
import { ErrorBanner, LoadingState } from "@/components/agentic-ai/shared";
import MissionControlDashboard from "@/components/agentic-ai/MissionControlDashboard";
import AgentInventoryDashboard from "@/components/agentic-ai/AgentInventoryDashboard";
import AuthorityDashboard from "@/components/agentic-ai/AuthorityDashboard";
import GuardrailsDashboard from "@/components/agentic-ai/GuardrailsDashboard";
import ShadowAIDashboard from "@/components/agentic-ai/ShadowAIDashboard";
import IncidentsDashboard from "@/components/agentic-ai/IncidentsDashboard";
import DefensibilityDashboard from "@/components/agentic-ai/DefensibilityDashboard";
import AgentDetailModal from "@/components/agentic-ai/AgentDetailModal";
import RegisterAgentModal from "@/components/agentic-ai/RegisterAgentModal";
import { useAgenticAIData } from "@/hooks/useAgenticAIData";
import { api } from "@/lib/api";
import { boardReportBlocks } from "@/lib/agenticAIModels";
import { useAuth } from "@/context/AuthContext";

const TABS = [
  { id: "mission", label: "Mission Control", icon: Gauge },
  { id: "inventory", label: "Agent Inventory", icon: Bot },
  { id: "authority", label: "Authority & Tools", icon: Zap },
  { id: "guardrails", label: "Guardrails & Red Team", icon: ShieldCheck },
  { id: "shadow", label: "Shadow AI", icon: EyeOff },
  { id: "incidents", label: "Incidents", icon: AlertOctagon },
  { id: "defensibility", label: "Defensibility", icon: Wrench },
];

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export default function AgenticAISecurity() {
  const { user, mode } = useAuth();
  const isAdmin = user?.role === "admin";
  const { data, loading, refreshing, error, sourceStatus, reload } = useAgenticAIData();

  const [activeTab, setActiveTab] = useState(
    () => localStorage.getItem("agentic-ai-security-tab") || "mission"
  );
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [busyRef, setBusyRef] = useState("");
  const [busySystem, setBusySystem] = useState("");
  const [registerBusy, setRegisterBusy] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [discovering, setDiscovering] = useState(false);

  const openTab = (tab) => {
    setActiveTab(tab);
    localStorage.setItem("agentic-ai-security-tab", tab);
  };

  const refreshAndReselect = async (ref = "") => {
    await reload();
    if (ref) setSelectedAgent(null);
  };

  const toggleGuard = async (agent, key) => {
    if (!isAdmin) return;
    setBusyRef(agent.ref);
    try {
      await api.patch(`/agents/${agent.ref}`, {
        [key]: !agent.guardrails?.[key],
      });
      toast.success(`${agent.ref} ${key.replaceAll("_", " ")} updated.`);
      await refreshAndReselect(agent.ref);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to update guardrail.");
    } finally {
      setBusyRef("");
    }
  };

  const runRedteam = async (agent) => {
    if (!isAdmin) return;
    setBusyRef(agent.ref);
    try {
      const response = await api.post(`/agents/${agent.ref}/redteam`);
      toast.success(`${agent.ref} heuristic baseline completed at ${response.data.score}%.`);
      await refreshAndReselect(agent.ref);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to run heuristic red-team baseline.");
    } finally {
      setBusyRef("");
    }
  };

  const enforceAgent = async (agent, action) => {
    if (!isAdmin) return;
    setBusyRef(agent.ref);
    try {
      const { data: res } = await api.post(`/agents/${agent.ref}/enforce`, { action });
      const verb = action === "kill" ? "killed" : action === "suspend" ? "suspended" : "resumed";
      const where = res.enforcement?.runtime === "external-webhook"
        ? "dispatched to the agent runtime"
        : "enforced in the control plane";
      toast.success(`${agent.ref} ${verb} — ${where}.`);
      setSelectedAgent((prev) =>
        prev && prev.ref === agent.ref
          ? { ...prev, status: res.agent.status, enforced: res.agent.enforced, enforcement: res.agent.enforcement }
          : prev
      );
      await reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to apply runtime enforcement.");
    } finally {
      setBusyRef("");
    }
  };

  const discoverShadowAI = async () => {
    if (!isAdmin) return;
    setDiscovering(true);
    try {
      const { data: res } = await api.post("/ai-systems/discover");
      toast.success(`Discovery added ${res.added} shadow AI system(s). ${res.shadow_total} in the queue.`);
      await reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Shadow AI discovery failed.");
    } finally {
      setDiscovering(false);
    }
  };

  const registerAgent = async (payload) => {
    if (!isAdmin) return;
    setRegisterBusy(true);
    try {
      await api.post("/agents", payload);
      toast.success("AI agent registered.");
      setRegisterOpen(false);
      await reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to register agent.");
    } finally {
      setRegisterBusy(false);
    }
  };

  const sanctionSystem = async (system) => {
    if (!isAdmin || !system.ref) return;
    setBusySystem(system.ref);
    try {
      await api.patch(`/ai-systems/${system.ref}`, { status: "sanctioned" });
      toast.success(`${system.ref} sanctioned in the Obserra governance record.`);
      await reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to sanction AI system.");
    } finally {
      setBusySystem("");
    }
  };

  const downloadBoardBrief = async () => {
    if (!data) return;
    setReportBusy(true);
    try {
      const blocks = boardReportBlocks({
        agents: data.agents,
        systems: data.systems,
        incidents: data.incidents,
        analytics: data.analytics,
      });

      const response = await api.post(
        "/studio/report/pdf",
        {
          title: "Agentic AI Security Executive Brief",
          ai_narrative:
            "Executive brief generated from the current Obserra AI agent inventory, AI system inventory, guardrail records, incident records and AI analytics. Modeled agent risk and delegated authority classifications are explicitly derived client-side. Existing red-team values are a deterministic heuristic baseline, not live adversarial runtime testing.",
          blocks,
        },
        { responseType: "blob" }
      );

      downloadBlob(response.data, "obserra-agentic-ai-security-executive-brief.pdf");
      toast.success("Executive brief generated.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to generate executive brief.");
    } finally {
      setReportBusy(false);
    }
  };

  if (loading && !data) return <LoadingState />;

  return (
    <div className="rise space-y-6" data-testid="agentic-ai-security-page">
      <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <Bot className="w-7 h-7 text-ai" />
            <h1 className="font-head font-black text-3xl tracking-tight">
              Agentic AI Security Control Plane
            </h1>
            <span className="px-2 py-1 rounded-full border border-ai/25 bg-ai/10 text-ai text-[10px] font-mono">
              MACHINE AUTHORITY INTELLIGENCE
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-2 max-w-4xl">
            {mode === "executive"
              ? "Understand which AI agents exist, what authority has been delegated to them, where guardrails are weak, which systems remain shadow AI, and what requires executive action."
              : "Inspect agent tools, permissions, governance status, guardrail coverage, heuristic red-team evidence, AI incidents, workflows and system inventory using the existing Obserra backend."}
          </p>
          <div className="flex flex-wrap gap-1.5 mt-3">
            {(data?.composition || []).map((item) => (
              <span key={item} className="px-2 py-0.5 rounded-sm bg-ai/10 border border-ai/20 text-ai text-[10px] font-mono">
                {item}
              </span>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={reload}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50"
          >
            {refreshing ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
            Refresh
          </button>
          <button
            onClick={downloadBoardBrief}
            disabled={reportBusy}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50"
          >
            {reportBusy ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Download className="w-3.5 h-3.5" />
            )}
            Executive Brief
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onRetry={reload} refreshing={refreshing} />

      <AIInsight
        dashboard="Agentic AI Security Control Plane"
        accent="330 81% 60%"
        auto
        slug="agentic-ai-security"
      />

      <div className="overflow-x-auto">
        <div className="inline-flex min-w-max rounded-xl border border-border bg-card p-1">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => openTab(tab.id)}
                className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-head font-bold transition-colors ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                }`}
                data-testid={`agentic-tab-${tab.id}`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {activeTab === "mission" && (
        <MissionControlDashboard
          data={data}
          onOpenTab={openTab}
          onSelectAgent={setSelectedAgent}
        />
      )}

      {activeTab === "inventory" && (
        <AgentInventoryDashboard
          agents={data?.agents || []}
          isAdmin={isAdmin}
          onSelectAgent={setSelectedAgent}
          onRegister={() => setRegisterOpen(true)}
        />
      )}

      {activeTab === "authority" && (
        <AuthorityDashboard
          agents={data?.agents || []}
          onSelectAgent={setSelectedAgent}
          isAdmin={isAdmin}
          onReload={reload}
        />
      )}

      {activeTab === "guardrails" && (
        <GuardrailsDashboard
          agents={data?.agents || []}
          isAdmin={isAdmin}
          busyRef={busyRef}
          onToggleGuard={toggleGuard}
          onRunRedteam={runRedteam}
          onSelectAgent={setSelectedAgent}
        />
      )}

      {activeTab === "shadow" && (
        <ShadowAIDashboard
          systems={data?.systems || []}
          analytics={data?.analytics || {}}
          isAdmin={isAdmin}
          busySystem={busySystem}
          onSanction={sanctionSystem}
          onDiscover={discoverShadowAI}
          discovering={discovering}
        />
      )}

      {activeTab === "incidents" && (
        <IncidentsDashboard
          incidents={data?.incidents || []}
          workflows={data?.workflows || []}
        />
      )}

      {activeTab === "defensibility" && (
        <DefensibilityDashboard data={data} sourceStatus={sourceStatus} />
      )}

      {selectedAgent && (
        <AgentDetailModal
          agent={selectedAgent}
          isAdmin={isAdmin}
          busy={busyRef === selectedAgent.ref}
          onClose={() => setSelectedAgent(null)}
          onEnforce={enforceAgent}
        />
      )}

      {registerOpen && (
        <RegisterAgentModal
          busy={registerBusy}
          onClose={() => setRegisterOpen(false)}
          onSubmit={registerAgent}
        />
      )}
    </div>
  );
}