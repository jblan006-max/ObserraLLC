import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { APP_VERSION_LABEL } from "@/version";
import { useCRAData } from "@/hooks/useCRAData";
import { CraTabAnalyst } from "@/components/cra/CraAI";
import { toast } from "sonner";
import {
  Boxes, BadgeCheck, ShieldCheck, TriangleAlert, FileCheck2, Fingerprint,
  Building2, Download, RefreshCw, ArrowRight, Clock3, Loader2,
} from "lucide-react";

const pct = (n, d) => (d ? Math.round((n / d) * 100) : 0);

function toneFor(score) {
  if (score == null) return "text-muted-foreground border-border";
  if (score >= 80) return "text-low border-low/30";
  if (score >= 50) return "text-high border-high/30";
  return "text-crit border-crit/30";
}

function KpiCard({ label, value, sub, Icon, tone = "text-primary border-primary/25", onClick, testid }) {
  return (
    <button
      onClick={onClick}
      data-testid={testid}
      className={`text-left rounded-xl border bg-card p-4 hover:bg-secondary/30 transition-colors ${tone}`}
    >
      <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider opacity-80">
        <Icon className="w-3.5 h-3.5" /> {label}
      </div>
      <div className="font-head font-black text-3xl mt-1 text-foreground">{value}</div>
      {sub && <div className="text-[11px] font-mono text-muted-foreground mt-0.5">{sub}</div>}
    </button>
  );
}

function Panel({ title, subtitle, children, testid }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5" data-testid={testid}>
      <div className="font-head font-bold text-sm">{title}</div>
      {subtitle && <div className="text-[11px] font-mono text-muted-foreground mb-3">{subtitle}</div>}
      <div className={subtitle ? "" : "mt-3"}>{children}</div>
    </div>
  );
}

function Bar({ label, value, total, tone = "bg-primary" }) {
  const p = total ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-foreground/90">{label}</span>
        <span className="font-mono text-muted-foreground">{value}{total ? ` / ${total}` : ""}</span>
      </div>
      <div className="h-2 rounded-full bg-secondary/60 overflow-hidden">
        <div className={`h-full ${tone}`} style={{ width: `${p}%` }} />
      </div>
    </div>
  );
}

const NIST_TONE = { Low: "bg-low", Medium: "bg-high", High: "bg-crit", Unknown: "bg-secondary" };

export default function CRAExecutiveOverview() {
  const navigate = useNavigate();
  const { data, loading, error, reload, refreshing } = useCRAData();
  const [assurance, setAssurance] = useState(null);
  const [briefBusy, setBriefBusy] = useState(false);

  useEffect(() => {
    api.get("/cra/ai-monitor?days=30").then((r) => setAssurance(r.data)).catch(() => {});
  }, []);

  // Deep-link each KPI to the exact governance tab it summarizes (CRAGovernance reads this key on mount).
  const goTab = (tab) => {
    localStorage.setItem("cra-governance-tab", tab);
    navigate("/app/cra-governance");
  };

  const downloadBrief = async () => {
    setBriefBusy(true);
    try {
      const r = await api.get("/cra/executive-overview.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = "obserra-eu-cra-executive-overview.pdf";
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    } catch {
      toast.error("Could not generate the executive overview PDF");
    }
    setBriefBusy(false);
  };

  if (loading && !data) {
    return <div className="flex items-center gap-2 text-sm text-muted-foreground p-8"><Loader2 className="w-4 h-4 animate-spin" /> Loading the EU CRA executive posture…</div>;
  }

  const dash = data?.dashboard || {};
  const controls = data?.controls?.overall || {};
  const nist = data?.nist?.overall || {};
  const nistFns = data?.nist?.functions || [];
  const cls = dash.classifications || {};
  const products = dash.products || 0;
  const nd = dash.next_deadline;

  const kpis = [
    { label: "Products under CRA", value: products, sub: `${cls["Critical"] || 0} critical · ${cls["Class II"] || 0} Class II`, Icon: Boxes, tone: "text-primary border-primary/25", tab: "products" },
    { label: "Classification approved", value: `${pct(dash.classification_approved || 0, products)}%`, sub: `${dash.classification_approved || 0} / ${products} approved`, Icon: BadgeCheck, tone: toneFor(pct(dash.classification_approved || 0, products)), tab: "products" },
    { label: "CE market-ready", value: `${pct(dash.ce_ready || 0, products)}%`, sub: `${dash.ce_ready || 0} / ${products} ready`, Icon: ShieldCheck, tone: toneFor(pct(dash.ce_ready || 0, products)), tab: "declaration" },
    { label: "Article 14 overdue", value: dash.reporting_overdue ?? 0, sub: "24h / 72h / final clocks", Icon: TriangleAlert, tone: (dash.reporting_overdue || 0) > 0 ? "text-crit border-crit/30" : "text-low border-low/30", tab: "vulnerability" },
    { label: "Control compliance", value: `${controls.percentage ?? 0}%`, sub: `${controls.implemented ?? 0} implemented · ${controls.partial ?? 0} partial`, Icon: FileCheck2, tone: toneFor(controls.percentage), tab: "controls" },
    { label: "NIST CSF alignment", value: `${nist.alignment_percentage ?? 0}%`, sub: `${nist.functions_aligned ?? 0} / ${nist.functions_total ?? 6} functions aligned`, Icon: ShieldCheck, tone: toneFor(nist.alignment_percentage), tab: "nist" },
    { label: "External assessments", value: dash.open_external_assessments ?? 0, sub: "open notified-body reviews", Icon: Building2, tone: "text-primary border-primary/25", tab: "conformity" },
    { label: "AI grounding score", value: assurance?.avg_score == null ? "—" : `${assurance.avg_score}%`, sub: assurance ? `${assurance.total_checks} answers checked · ${assurance.flagged_total} flagged` : "hallucination monitor", Icon: Fingerprint, tone: toneFor(assurance?.avg_score), tab: "assurance" },
  ];

  return (
    <div className="rise space-y-6" data-testid="cra-executive-overview">
      <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="font-head font-black text-3xl tracking-tight">EU CRA Executive Overview</h1>
            <span className="px-2 py-1 rounded-full border border-primary/25 bg-primary/10 text-primary text-[10px] font-mono font-bold">REGULATION (EU) 2024/2847</span>
            <span data-testid="cra-exec-version" className="px-2 py-1 rounded-full border border-border bg-secondary/60 text-muted-foreground text-[10px] font-mono font-bold">Obserra CRA {APP_VERSION_LABEL}</span>
          </div>
          <p className="text-sm text-muted-foreground mt-2 max-w-3xl">
            A board-ready rollup of the whole EU Cyber Resilience Act posture — product classification, CE market
            readiness, essential-requirement control compliance, NIST CSF alignment, Article 14 reporting clocks and
            AI-answer grounding. Every card opens the exact governance tab it summarizes.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={reload} disabled={refreshing} data-testid="cra-exec-refresh" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} /> Refresh</button>
          <button onClick={downloadBrief} disabled={briefBusy} data-testid="cra-exec-brief" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold">{briefBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Executive Brief PDF</button>
          <button onClick={() => goTab("mission")} data-testid="cra-exec-open-governance" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Open Governance <ArrowRight className="w-3.5 h-3.5" /></button>
        </div>
      </div>

      {error && <div className="rounded-xl border border-crit/25 bg-crit/5 p-4 text-sm">{error}</div>}

      {nd && (
        <div data-testid="cra-exec-deadline" className={`rounded-xl border p-4 flex items-center gap-3 ${nd.days_remaining <= 120 ? "border-crit/30 bg-crit/5" : "border-high/25 bg-high/5"}`}>
          <Clock3 className={`w-5 h-5 shrink-0 ${nd.days_remaining <= 120 ? "text-crit" : "text-high"}`} />
          <div className="text-sm">
            <span className="font-head font-bold">{nd.days_remaining} days to the next CRA deadline</span>
            <span className="text-muted-foreground"> · {nd.label} ({nd.date})</span>
          </div>
        </div>
      )}

      <CraTabAnalyst tab="mission" />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {kpis.map((k) => (
          <KpiCard key={k.label} {...k} onClick={() => goTab(k.tab)} testid={`cra-exec-kpi-${k.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel title="Product classification split" subtitle="EU CRA risk categories across the registered portfolio" testid="cra-exec-classification">
          <div className="space-y-3">
            <Bar label="Default" value={cls["Default"] || 0} total={products} tone="bg-primary" />
            <Bar label="Class I (important)" value={cls["Class I"] || 0} total={products} tone="bg-high" />
            <Bar label="Class II (important)" value={cls["Class II"] || 0} total={products} tone="bg-high" />
            <Bar label="Critical" value={cls["Critical"] || 0} total={products} tone="bg-crit" />
          </div>
          <div className="mt-4 pt-3 border-t border-border grid grid-cols-2 gap-3 text-sm">
            <div><div className="text-[10px] font-mono uppercase text-muted-foreground">Avg readiness</div><div className="font-head font-bold text-lg">{dash.average_readiness ?? 0}%</div></div>
            <div><div className="text-[10px] font-mono uppercase text-muted-foreground">Products assessed</div><div className="font-head font-bold text-lg">{controls.products_assessed ?? 0} / {controls.products_total ?? products}</div></div>
          </div>
        </Panel>

        <Panel title="NIST CSF 2.0 alignment" subtitle={nist.framework || "NIST CSF 2.0 · SP 800-218 (SSDF)"} testid="cra-exec-nist">
          <div className="space-y-2.5">
            {nistFns.map((f) => (
              <div key={f.code}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-foreground/90"><span className="font-mono text-muted-foreground">{f.code}</span> {f.name}</span>
                  <span className="font-mono text-muted-foreground">{f.compliance_rate}%</span>
                </div>
                <div className="h-2 rounded-full bg-secondary/60 overflow-hidden">
                  <div className={`h-full ${NIST_TONE[f.risk] || "bg-primary"}`} style={{ width: `${f.compliance_rate}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Essential-requirement control posture" subtitle={`${controls.requirements_total ?? 0} CRA requirements assessed`} testid="cra-exec-controls">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg border border-low/25 bg-low/5 p-3"><div className="font-head font-black text-2xl text-low">{controls.implemented ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Implemented</div></div>
            <div className="rounded-lg border border-high/25 bg-high/5 p-3"><div className="font-head font-black text-2xl text-high">{controls.partial ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Partial</div></div>
            <div className="rounded-lg border border-crit/25 bg-crit/5 p-3"><div className="font-head font-black text-2xl text-crit">{(controls.gaps ?? 0) + (controls.not_started ?? 0)}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Gap / not started</div></div>
          </div>
          <div className="mt-4"><Bar label="Overall control compliance" value={controls.percentage ?? 0} total={100} tone={(controls.percentage ?? 0) >= 80 ? "bg-low" : (controls.percentage ?? 0) >= 50 ? "bg-high" : "bg-crit"} /></div>
        </Panel>

        <Panel title="AI assurance & grounding" subtitle="Hallucination monitor across every Obserrian CRA AI answer" testid="cra-exec-assurance">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className={`rounded-lg border p-3 ${toneFor(assurance?.avg_score)}`}><div className="font-head font-black text-2xl">{assurance?.avg_score == null ? "—" : `${assurance.avg_score}%`}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Avg score</div></div>
            <div className="rounded-lg border border-border p-3"><div className="font-head font-black text-2xl text-foreground">{assurance?.total_checks ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Checked</div></div>
            <div className={`rounded-lg border p-3 ${(assurance?.flagged_total || 0) > 0 ? "border-crit/25 text-crit" : "border-low/25 text-low"}`}><div className="font-head font-black text-2xl">{assurance?.flagged_total ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Flagged</div></div>
          </div>
          <button onClick={() => goTab("assurance")} className="mt-4 inline-flex items-center gap-1.5 text-[11px] font-head font-bold text-ai hover:underline" data-testid="cra-exec-open-assurance">Open the AI Assurance monitor <ArrowRight className="w-3 h-3" /></button>
        </Panel>
      </div>

      <div className="text-[10px] font-mono text-muted-foreground">
        Article 14 reporting applies {dash.reporting_effective_date} · General CRA application {dash.general_application_date} · Live figures — Obserra never substitutes synthetic regulatory data.
      </div>
    </div>
  );
}
