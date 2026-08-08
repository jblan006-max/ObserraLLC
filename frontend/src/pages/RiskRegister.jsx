import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useUrlState } from "@/hooks/useUrlState";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { EvidenceLineageModal } from "@/components/EvidenceLineageModal";
import { SourceBadge, FreshnessBadge, ConfidenceBadge, DataTypeBadge, ScorePill } from "@/components/badges";
import { Loader2, Search, Info, DollarSign, X } from "lucide-react";
import { EvidenceModal } from "@/components/EvidenceModal";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const STATUS = ["Open", "In Progress", "Remediated", "Accepted"];

export default function RiskRegister() {
  const { mode } = useAuth();
  const isExec = mode === "executive";
  const [risks, setRisks] = useState(null);
  const [lineage, setLineage] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [selected, setSelected] = useState(null);
  const [q, setQ] = useUrlState("q", "");
  const [cat, setCat] = useUrlState("cat", "all");

  const load = () => api.get("/risks").then((r) => setRisks(r.data));
  useEffect(() => { load(); }, []);

  const updateStatus = async (ref, status) => {
    await api.patch(`/risks/${ref}`, { status });
    toast.success(`${ref} → ${status}`);
    load();
  };

  if (!risks) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  const categories = ["all", ...Array.from(new Set(risks.map((r) => r.category)))];
  const filtered = risks.filter((r) =>
    (cat === "all" || r.category === cat) &&
    (r.title.toLowerCase().includes(q.toLowerCase()) || r.ref.toLowerCase().includes(q.toLowerCase())));

  return (
    <div className="rise space-y-5">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight">Cyber Risk Register</h1>
        <p className="text-sm text-muted-foreground mt-1">{isExec ? "Business-impact view of the cyber risk register — exposure and residual severity by risk (read-only)." : "Taxonomy, inherent vs residual scoring, ownership, treatment & KRIs. Click any row for evidence lineage."}</p>
      </div>

      {risks.length === 0 ? (
        <div data-testid="risk-empty" className="bg-card fact-border rounded-xl p-8 text-center space-y-2">
          <div className="font-head font-bold text-lg">No live risks yet</div>
          <p className="text-sm text-muted-foreground">Risks auto-populate from your live self-scan. Run a scan on the <a href="/app/security" className="text-ai underline">Security Scanner</a>, or connect a source.</p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 grid grid-cols-2 lg:grid-cols-4 gap-3 content-start" data-testid="risk-kpis">
            <div className="bg-card fact-border rounded-xl p-4"><div className="text-[10px] font-mono uppercase text-muted-foreground">Total risks</div><div className="font-head font-black text-3xl mt-1">{risks.length}</div></div>
            <div className="bg-card fact-border rounded-xl p-4"><div className="text-[10px] font-mono uppercase text-muted-foreground">Open</div><div className="font-head font-black text-3xl mt-1">{risks.filter((r) => r.status !== "Remediated").length}</div></div>
            <div className="bg-card fact-border rounded-xl p-4" style={{ borderLeft: "3px solid hsl(0 84% 60%)" }}><div className="text-[10px] font-mono uppercase text-muted-foreground">Critical</div><div className="font-head font-black text-3xl mt-1">{risks.filter((r) => r.residual >= 16).length}</div></div>
            <div className="bg-card fact-border rounded-xl p-4"><div className="text-[10px] font-mono uppercase text-muted-foreground">$ Exposure</div><div className="font-head font-black text-2xl mt-1 text-high">{fmtM(risks.reduce((s, r) => s + riskExposure(r), 0))}</div></div>
          </div>
          <RiskMatrix risks={risks} onPick={(c) => setSelected(c[0])} />
        </div>
      )}

      <div className="flex flex-wrap gap-3 sticky top-16 z-20 -mx-4 px-4 sm:mx-0 sm:px-0 py-2 bg-background/90 backdrop-blur">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input data-testid="risk-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search risks…"
            className="w-full bg-card border border-border rounded-md pl-9 pr-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <Select value={cat} onValueChange={setCat}>
          <SelectTrigger data-testid="risk-category-filter" className="w-52 bg-card"><SelectValue /></SelectTrigger>
          <SelectContent>
            {categories.map((c) => <SelectItem key={c} value={c}>{c === "all" ? "All categories" : c}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="md:flex md:gap-5 md:items-start">
      <div className="min-w-0 flex-1 space-y-4">
      <div className="md:hidden space-y-3" data-testid="risk-cards-mobile">
        {filtered.map((r) => (
          <div key={r.ref} data-testid={`risk-card-${r.ref}`} onClick={() => setLineage(r.ref)}
            className="bg-card fact-border rounded-lg p-4 space-y-2 active:bg-secondary/40 transition-colors">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-mono text-[11px] text-ai">{r.ref}</div>
                <div className="font-medium text-sm">{r.title}</div>
                <div className="text-[11px] text-high">{r.business_impact}</div>
              </div>
              <div className="shrink-0" onClick={(e) => e.stopPropagation()}>
                {isExec ? (
                  <span className="text-[10px] px-2 py-0.5 rounded-md bg-secondary/60">{r.status}</span>
                ) : (
                  <Select value={r.status} onValueChange={(v) => updateStatus(r.ref, v)}>
                    <SelectTrigger className="w-28 h-8 text-xs bg-secondary/60"><SelectValue /></SelectTrigger>
                    <SelectContent>{STATUS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                  </Select>
                )}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>{r.category}</span>
              <span className="flex items-center gap-1">Inh <ScorePill value={r.inherent} /></span>
              <span className="flex items-center gap-1">Res <ScorePill value={r.residual} /></span>
            </div>
            <button data-testid={`evidence-m-${r.ref}`} onClick={(e) => { e.stopPropagation(); setEvidence(r.ref); }}
              className="flex items-center gap-1 text-xs font-mono text-high">
              <DollarSign className="w-3 h-3" />{Math.round((SLE_BY_IMPACT[r.impact] || 1e6) * (r.likelihood / 5) * (r.residual / r.inherent) / 1000)}k exposure <Info className="w-3 h-3 opacity-60" />
            </button>
          </div>
        ))}
      </div>

      <div className="hidden md:block bg-card fact-border rounded-lg overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr>
              <th className="text-left px-4 py-3">Ref / Risk</th>
              <th className="text-left px-4 py-3">Category</th>
              <th className="text-left px-4 py-3">Inh.</th>
              <th className="text-left px-4 py-3">Res.</th>
              <th className="text-left px-4 py-3">$ Exposure</th>
              <th className="text-left px-4 py-3">Owner</th>
              <th className="text-left px-4 py-3">KRI</th>
              <th className="text-left px-4 py-3">Evidence</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.ref} data-testid={`risk-row-${r.ref}`} onClick={() => setSelected(r)} className={`border-b border-border/60 hover:bg-secondary/40 transition-colors cursor-pointer ${selected?.ref === r.ref ? "bg-secondary/50" : ""}`}>
                <td className="px-4 py-3">
                  <div className="font-mono text-xs text-ai">{r.ref}</div>
                  <div className="font-medium max-w-xs">{r.title}</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{r.business_impact}</div>
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{r.category}</td>
                <td className="px-4 py-3"><ScorePill value={r.inherent} /></td>
                <td className="px-4 py-3"><ScorePill value={r.residual} /></td>
                <td className="px-4 py-3">
                  <button data-testid={`evidence-${r.ref}`} onClick={(e) => { e.stopPropagation(); setEvidence(r.ref); }}
                    className="flex items-center gap-1 text-xs font-mono text-high hover:text-foreground transition-colors">
                    <DollarSign className="w-3 h-3" />{Math.round((SLE_BY_IMPACT[r.impact] || 1e6) * (r.likelihood / 5) * (r.residual / r.inherent) / 1000)}k
                    <Info className="w-3 h-3 opacity-60" />
                  </button>
                </td>
                <td className="px-4 py-3 text-xs">{r.owner}</td>
                <td className="px-4 py-3 text-[11px] font-mono text-muted-foreground max-w-[140px]">{r.kri}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-col gap-1">
                    <SourceBadge source={r.source} />
                    <div className="flex items-center gap-2"><FreshnessBadge freshness={r.freshness} /><DataTypeBadge type={r.data_type} /></div>
                    <ConfidenceBadge value={r.confidence} />
                  </div>
                </td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                  {isExec ? (
                    <span data-testid={`risk-status-badge-${r.ref}`} className="text-xs px-2.5 py-1 rounded-md bg-secondary/60">{r.status}</span>
                  ) : (
                    <Select value={r.status} onValueChange={(v) => updateStatus(r.ref, v)}>
                      <SelectTrigger data-testid={`risk-status-${r.ref}`} className="w-32 h-8 text-xs bg-secondary/60"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {STATUS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </div>

      {selected && (
        <aside data-testid="risk-detail-pane" className="hidden md:block md:w-72 lg:w-80 shrink-0 md:sticky md:top-28 bg-card fact-border rounded-xl p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="font-mono text-[11px] text-ai">{selected.ref}</div>
              <div className="font-head font-bold text-sm">{selected.title}</div>
            </div>
            <button data-testid="risk-detail-close" onClick={() => setSelected(null)} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
          </div>
          <p className="text-xs text-high">{selected.business_impact}</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-secondary/40 rounded-md p-2 space-y-1"><div className="text-[10px] text-muted-foreground">Inherent</div><ScorePill value={selected.inherent} /></div>
            <div className="bg-secondary/40 rounded-md p-2 space-y-1"><div className="text-[10px] text-muted-foreground">Residual</div><ScorePill value={selected.residual} /></div>
          </div>
          <div className="text-xs space-y-1">
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Category</span><span className="text-right">{selected.category}</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Owner</span><span className="text-right">{selected.owner}</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">$ Exposure</span><span className="font-mono text-high">{Math.round((SLE_BY_IMPACT[selected.impact] || 1e6) * (selected.likelihood / 5) * (selected.residual / selected.inherent) / 1000)}k</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Status</span><span className="text-right">{selected.status}</span></div>
          </div>
          <div className="text-[11px] font-mono text-muted-foreground bg-secondary/30 rounded-md p-2">KRI: {selected.kri}</div>
          <div className="flex flex-col gap-1.5">
            <SourceBadge source={selected.source} />
            <div className="flex flex-wrap items-center gap-2"><FreshnessBadge freshness={selected.freshness} /><DataTypeBadge type={selected.data_type} /><ConfidenceBadge value={selected.confidence} /></div>
          </div>
          <div className="flex gap-2 pt-1">
            <button data-testid="risk-detail-lineage" onClick={() => setLineage(selected.ref)} className="flex-1 text-xs px-3 py-2 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 transition-colors">Full lineage</button>
            <button data-testid="risk-detail-evidence" onClick={() => setEvidence(selected.ref)} className="flex-1 text-xs px-3 py-2 rounded-md bg-secondary/60 hover:bg-secondary transition-colors">Evidence</button>
          </div>
        </aside>
      )}
      </div>


      <EvidenceLineageModal riskRef={lineage} onClose={() => setLineage(null)} />
      <EvidenceModal kind="risk" refId={evidence} onClose={() => setEvidence(null)} />
    </div>
  );
}

const SLE_BY_IMPACT = { 5: 8000000, 4: 3000000, 3: 1000000, 2: 300000, 1: 75000 };
const riskExposure = (r) => (SLE_BY_IMPACT[r.impact] || 1e6) * ((r.likelihood || 3) / 5) * ((r.residual || 1) / Math.max(r.inherent || 1, 1));
const fmtM = (n) => `$${(n / 1e6).toFixed(2)}M`;

function RiskMatrix({ risks, onPick }) {
  const cellRisks = (imp, lik) => risks.filter((r) => r.impact === imp && r.likelihood === lik);
  const color = (s) => (s >= 15 ? "0 84% 60%" : s >= 8 ? "35 90% 55%" : "142 70% 45%");
  return (
    <div className="bg-card fact-border rounded-xl p-4" data-testid="risk-matrix">
      <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Risk heat map — Impact × Likelihood (auto-populated)</div>
      <div className="flex gap-2">
        <div className="flex flex-col-reverse justify-between text-[9px] font-mono text-muted-foreground py-0.5">
          {[1, 2, 3, 4, 5].map((i) => <span key={i} className="flex-1 flex items-center">{i}</span>)}
        </div>
        <div className="grid grid-cols-5 gap-1 flex-1">
          {[5, 4, 3, 2, 1].map((imp) => [1, 2, 3, 4, 5].map((lik) => {
            const c = cellRisks(imp, lik);
            const s = imp * lik;
            return (
              <button key={`${imp}-${lik}`} data-testid={`risk-matrix-cell-${imp}-${lik}`}
                onClick={() => c.length && onPick(c)} disabled={!c.length}
                title={`Impact ${imp} × Likelihood ${lik} — ${c.length} risk(s)`}
                style={{ background: `hsl(${color(s)} / ${c.length ? 0.9 : 0.1})` }}
                className="aspect-square rounded-md flex items-center justify-center text-sm font-head font-black text-white/95 disabled:cursor-default transition-transform hover:scale-[1.04]">
                {c.length || ""}
              </button>
            );
          }))}
        </div>
      </div>
      <div className="text-center text-[9px] font-mono text-muted-foreground mt-1.5">Likelihood 1 → 5 · vertical axis = Impact</div>
    </div>
  );
}
