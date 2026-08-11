import { useState } from "react";
import {
  Download,
  FileCheck2,
  FlaskConical,
  Gauge,
  Layers,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Target,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";
import { AIInsight } from "@/components/AIInsight";
import {
  ErrorBanner,
  LoadingState,
} from "@/components/control-intelligence/shared";
import MissionControlDashboard from "@/components/control-intelligence/MissionControlDashboard";
import EffectivenessDashboard from "@/components/control-intelligence/EffectivenessDashboard";
import FrameworksDashboard from "@/components/control-intelligence/FrameworksDashboard";
import EvidenceDashboard from "@/components/control-intelligence/EvidenceDashboard";
import RemediationDashboard from "@/components/control-intelligence/RemediationDashboard";
import DefensibilityDashboard from "@/components/control-intelligence/DefensibilityDashboard";
import ControlDetailModal from "@/components/control-intelligence/ControlDetailModal";
import { useControlIntelligenceData } from "@/hooks/useControlIntelligenceData";
import { api } from "@/lib/api";
import { boardReportBlocks } from "@/lib/controlIntelligenceModels";
import { useAuth } from "@/context/AuthContext";

const TABS = [
  { id: "mission", label: "Mission Control", icon: Gauge },
  { id: "effectiveness", label: "Control Effectiveness", icon: Target },
  { id: "frameworks", label: "Framework Intelligence", icon: Layers },
  { id: "evidence", label: "Evidence Assurance", icon: FileCheck2 },
  { id: "remediation", label: "Remediation & Drift", icon: Wrench },
  { id: "defensibility", label: "Defensibility", icon: ShieldCheck },
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

export default function ControlIntelligence() {
  const { user, mode } = useAuth();
  const isAdmin = user?.role === "admin";
  const [demo, setDemo] = useState(false);
  const { data, loading, refreshing, error, sourceStatus, reload } =
    useControlIntelligenceData(demo);

  const [activeTab, setActiveTab] = useState(
    () => localStorage.getItem("control-intelligence-tab") || "mission"
  );
  const [selectedControl, setSelectedControl] = useState(null);
  const [busyId, setBusyId] = useState("");
  const [reportBusy, setReportBusy] = useState(false);
  const [briefBusy, setBriefBusy] = useState(false);

  const openTab = (tab) => {
    setActiveTab(tab);
    localStorage.setItem("control-intelligence-tab", tab);
  };

  const evidencePack = async (control) => {
    setBusyId(control.control_id);
    try {
      const response = await api.post(
        "/reports/evidence-pack",
        { control_id: control.control_id },
        { responseType: "blob" }
      );
      downloadBlob(
        response.data,
        `obserra-evidence-pack-${control.control_id}.pdf`
      );
      toast.success(`Evidence pack generated for ${control.control_id}.`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to generate evidence pack.");
    } finally {
      setBusyId("");
    }
  };

  const exportLog = async (control) => {
    setBusyId(control.control_id);
    try {
      const response = await api.get(
        `/reports/control-log/${control.control_id}.pdf`,
        { responseType: "blob" }
      );
      downloadBlob(
        response.data,
        `obserra-control-log-${control.control_id}.pdf`
      );
      toast.success(`Control log exported for ${control.control_id}.`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to export control log.");
    } finally {
      setBusyId("");
    }
  };

  const executiveReport = async () => {
    if (!data) return;
    setReportBusy(true);
    try {
      const blocks = boardReportBlocks({
        controls: data.controls,
        compliance: data.compliance,
        crosswalk: data.crosswalk,
      });

      const response = await api.post(
        "/studio/report/pdf",
        {
          title: "Control Intelligence Executive Assurance Brief",
          ai_narrative:
            "This Obserra Control Intelligence brief uses the existing control catalog, effectiveness, maturity, evidence freshness, compliance framework and crosswalk data. Control health, priority scoring and cross-framework convergence are modeled client-side and are presented separately from source facts.",
          blocks,
        },
        { responseType: "blob" }
      );

      downloadBlob(
        response.data,
        "obserra-control-intelligence-executive-assurance-brief.pdf"
      );
      toast.success("Control Intelligence executive brief generated.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to generate executive brief.");
    } finally {
      setReportBusy(false);
    }
  };

  const emailBrief = async () => {
    setBriefBusy(true);
    try {
      const r = await api.post("/control-intelligence/email-brief");
      toast.success(`Assurance brief emailed to ${r.data.sent} recipient(s).`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to email the brief.");
    } finally {
      setBriefBusy(false);
    }
  };

  if (loading && !data) return <LoadingState />;

  return (
    <div className="rise space-y-6" data-testid="control-intelligence-page">
      <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <ShieldCheck className="w-7 h-7 text-primary" />
            <h1 className="font-head font-black text-3xl tracking-tight">
              Control Intelligence Mission Control
            </h1>
            <span className="px-2 py-1 rounded-full border border-low/25 bg-low/10 text-low text-[10px] font-mono">
              CONTINUOUS ASSURANCE
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-2 max-w-4xl">
            {mode === "executive"
              ? "Continuous control effectiveness and assurance — translate effectiveness, evidence freshness, framework coverage and drift into executive assurance and prioritized control decisions."
              : "Inspect every control, effectiveness score, maturity level, evidence expiry, cross-framework mapping, audit history and remediation priority using the live Obserra control backend."}
          </p>
          <div className="text-[10px] font-mono text-muted-foreground mt-2">
            Generated:{" "}
            {data?.generatedAt
              ? new Date(data.generatedAt).toLocaleString()
              : "not available"}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {isAdmin && (
            <button
              onClick={() => setDemo((v) => !v)}
              data-testid="control-intel-demo-toggle"
              className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-md border text-xs font-head font-bold transition-colors ${
                demo
                  ? "border-med/40 bg-med/15 text-med"
                  : "border-border bg-secondary/40 text-muted-foreground"
              }`}
            >
              <FlaskConical className="w-3.5 h-3.5" />
              {demo ? "Demo: At-risk ON" : "Demo mode"}
            </button>
          )}
          <button
            onClick={reload}
            disabled={refreshing}
            data-testid="control-intel-refresh"
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
            onClick={executiveReport}
            disabled={reportBusy}
            data-testid="control-intel-exec-brief"
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
        dashboard="Control Intelligence"
        accent="168 76% 46%"
        auto
        slug="control-intelligence"
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
                data-testid={`control-intel-tab-${tab.id}`}
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
          onSelectControl={setSelectedControl}
          onExecutiveReport={executiveReport}
          reportBusy={reportBusy}
          onEmailBrief={emailBrief}
          briefBusy={briefBusy}
        />
      )}

      {activeTab === "effectiveness" && (
        <EffectivenessDashboard
          controls={data?.controls || []}
          onSelectControl={setSelectedControl}
        />
      )}

      {activeTab === "frameworks" && (
        <FrameworksDashboard
          compliance={data?.compliance || {}}
          crosswalk={data?.crosswalk || {}}
          controls={data?.controls || []}
          isAdmin={isAdmin}
        />
      )}

      {activeTab === "evidence" && (
        <EvidenceDashboard
          controls={data?.controls || []}
          busyId={busyId}
          onSelectControl={setSelectedControl}
          onEvidencePack={evidencePack}
          onExportLog={exportLog}
        />
      )}

      {activeTab === "remediation" && (
        <RemediationDashboard
          controls={data?.controls || []}
          gaps={data?.gaps || []}
          onSelectControl={setSelectedControl}
          isAdmin={isAdmin}
          demo={demo}
        />
      )}

      {activeTab === "defensibility" && (
        <DefensibilityDashboard data={data} sourceStatus={sourceStatus} isAdmin={isAdmin} />
      )}

      {selectedControl && (
        <ControlDetailModal
          control={selectedControl}
          isAdmin={isAdmin}
          onClose={() => setSelectedControl(null)}
          onEvidencePack={evidencePack}
          onExportLog={exportLog}
        />
      )}
    </div>
  );
}
