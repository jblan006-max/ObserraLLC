import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useUrlState } from "@/hooks/useUrlState";
import { toast } from "sonner";
import { ShieldCheck, Loader2, AlertTriangle, Clock, FileDown, TrendingDown, Search, X, Plus } from "lucide-react";

const statusHsl = { Passing: "142 70% 45%", Drifting: "35 90% 55%", Failing: "0 84% 60%", "Evidence Stale": "15 80% 55%" };
const KIND_COLOR = { remediation: "#3b82f6", evidence: "#22c55e", note: "#94a3b8" };

export default function ControlMonitoring() {
  const [controls, setControls] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [busy, setBusy] = useState("");
  const [q, setQ] = useUrlState("q", "");
  const [statusF, setStatusF] = useUrlState("statusF", "all");
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState([]);
  const [noteText, setNoteText] = useState("");
  const [noteKind, setNoteKind] = useState("remediation");
  const [noteBusy, setNoteBusy] = useState(false);

  useEffect(() => {
    api.get("/controls").then((r) => setControls(r.data));
    api.get("/controls/compliance").then((r) => setCompliance(r.data.frameworks)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) { setHistory([]); return; }
    setNoteText("");
    api.get(`/controls/${selected.control_id}/history`).then((r) => setHistory(r.data)).catch(() => setHistory([]));
  }, [selected]);

  const addNote = async () => {
    if (!noteText.trim() || !selected) return;
    setNoteBusy(true);
    try {
      await api.post(`/controls/${selected.control_id}/notes`, { kind: noteKind, text: noteText.trim() });
      setNoteText("");
      const r = await api.get(`/controls/${selected.control_id}/history`);
      setHistory(r.data);
      toast.success("Added to control log");
    } catch { toast.error("Could not add to log"); }
    setNoteBusy(false);
  };

  const pack = async (id) => {
    setBusy(id);
    try {
      const res = await api.post("/reports/evidence-pack", { control_id: id }, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `evidence-pack-${id}.pdf`; a.click();
      URL.revokeObjectURL(url);
      toast.success(`Evidence pack generated for ${id}`);
    } catch { toast.error("Could not generate pack"); }
    setBusy("");
  };

  if (!controls) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const flagged = controls.filter((c) => c.stale || c.drift || c.status === "Failing");
  const shown = controls.filter((c) => (statusF === "all" || c.status === statusF) && `${c.control_id} ${c.name} ${c.category}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="rise space-y-5">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><ShieldCheck className="w-7 h-7 text-primary" /> Continuous Control Monitoring</h1>
        <p className="text-sm text-muted-foreground mt-1">Control effectiveness, maturity, evidence freshness & drift — auto-flagged the moment proof goes stale.</p>
      </div>

      {flagged.length > 0 && (
        <div className="rounded-lg p-4 flex items-center gap-3 border border-high/40 bg-high/5">
          <AlertTriangle className="w-5 h-5 text-high" />
          <div className="text-sm"><span className="font-semibold text-high">{flagged.length} control(s) need attention</span> — expired evidence or effectiveness drift detected.</div>
        </div>
      )}

      {compliance && compliance.length > 0 && (
        <div data-testid="compliance-panel">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground mb-3">Framework alignment · NIST · ISO · SOC 2 · CISA</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {compliance.map((f) => {
              const col = f.coverage >= 75 ? "142 70% 45%" : f.coverage >= 55 ? "35 90% 55%" : "0 84% 60%";
              return (
                <div key={f.framework} data-testid={`compliance-${f.framework.replace(/[^a-zA-Z0-9]/g, "-")}`} className="bg-card fact-border rounded-xl p-4">
                  <div className="text-xs font-head font-bold truncate">{f.framework}</div>
                  <div className="font-head font-black text-2xl mt-1" style={{ color: `hsl(${col})` }}>{f.coverage}%</div>
                  <div className="text-[10px] text-muted-foreground">{f.passing}/{f.controls} controls passing</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2" data-testid="control-filters">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input data-testid="control-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search controls..." className="w-full bg-secondary/60 rounded-md pl-9 pr-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <select data-testid="control-filter" value={statusF} onChange={(e) => setStatusF(e.target.value)} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary">
          <option value="all">All statuses</option><option value="Passing">Passing</option><option value="Drifting">Drifting</option><option value="Failing">Failing</option><option value="Evidence Stale">Evidence Stale</option>
        </select>
      </div>
      <div className="md:flex md:gap-5 md:items-start">
      <div className="min-w-0 flex-1 space-y-4">
      <div className="md:hidden space-y-3" data-testid="control-cards-mobile">
        {shown.map((c) => (
          <div key={c.control_id} data-testid={`control-card-${c.control_id}`} onClick={() => setSelected(c)} className="bg-card fact-border rounded-xl p-4 space-y-2 active:bg-secondary/40 transition-colors">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-mono text-[11px] text-ai">{c.control_id}</div>
                <div className="font-medium text-sm">{c.name}</div>
                <div className="text-[10px] text-muted-foreground">{c.category} · {c.framework}</div>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-sm font-mono font-bold shrink-0" style={{ background: `hsl(${statusHsl[c.status]} / 0.15)`, color: `hsl(${statusHsl[c.status]})` }}>{c.status}</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${c.effectiveness}%`, background: c.effectiveness >= 75 ? "hsl(142 70% 45%)" : c.effectiveness >= 55 ? "hsl(35 90% 55%)" : "hsl(0 84% 60%)" }} /></div>
              <span className="font-mono w-8">{c.effectiveness}%</span>
              <span className="font-mono text-muted-foreground">M{c.maturity}/5</span>
            </div>
            <div className="flex items-center justify-between">
              <span className={`flex items-center gap-1 text-[11px] font-mono ${c.stale ? "text-crit" : c.days_to_expiry < 14 ? "text-med" : "text-muted-foreground"}`}>
                <Clock className="w-3 h-3" />{c.stale ? `expired ${-c.days_to_expiry}d` : `${c.days_to_expiry}d left`}
              </span>
              <button data-testid={`pack-m-${c.control_id}`} disabled={busy === c.control_id} onClick={(e) => { e.stopPropagation(); pack(c.control_id); }}
                className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 transition-colors disabled:opacity-50">
                {busy === c.control_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />} Pack
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="hidden md:block bg-card fact-border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr><th className="text-left px-4 py-3">Control</th><th className="text-left px-4 py-3">Framework</th><th className="text-left px-4 py-3">Effectiveness</th><th className="text-left px-4 py-3">Maturity</th><th className="text-left px-4 py-3">Evidence</th><th className="text-left px-4 py-3">Status</th><th className="text-left px-4 py-3">Owner</th><th className="text-left px-4 py-3">Pack</th></tr>
          </thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.control_id} data-testid={`control-${c.control_id}`} onClick={() => setSelected(c)} className={`border-b border-border/60 hover:bg-secondary/40 transition-colors cursor-pointer ${selected?.control_id === c.control_id ? "bg-secondary/50" : ""}`}>
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{c.control_id}</div><div className="font-medium">{c.name}</div><div className="text-[10px] text-muted-foreground">{c.category}</div></td>
                <td className="px-4 py-3 text-xs">
                  <div className="font-medium">{c.framework}</div>
                  {c.frameworks && Object.keys(c.frameworks).length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1 max-w-[220px]">
                      {Object.entries(c.frameworks).map(([fw, refs]) => (
                        <span key={fw} data-testid={`control-framework-tag-${fw.replace(/[^a-zA-Z0-9]/g, "-")}`} title={refs.join(", ")} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{fw}</span>
                      ))}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 w-40">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${c.effectiveness}%`, background: c.effectiveness >= 75 ? "hsl(142 70% 45%)" : c.effectiveness >= 55 ? "hsl(35 90% 55%)" : "hsl(0 84% 60%)" }} /></div>
                    <span className="font-mono text-xs w-8">{c.effectiveness}%</span>
                  </div>
                  {c.drift && <span className="text-[10px] text-high flex items-center gap-0.5 mt-0.5"><TrendingDown className="w-3 h-3" />{c.drift_delta} pts drift</span>}
                </td>
                <td className="px-4 py-3 font-mono text-xs">{c.maturity}/5</td>
                <td className="px-4 py-3">
                  <span className={`flex items-center gap-1 text-[11px] font-mono ${c.stale ? "text-crit" : c.days_to_expiry < 14 ? "text-med" : "text-muted-foreground"}`}>
                    <Clock className="w-3 h-3" />{c.stale ? `expired ${-c.days_to_expiry}d` : `${c.days_to_expiry}d left`}
                  </span>
                </td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${statusHsl[c.status]} / 0.15)`, color: `hsl(${statusHsl[c.status]})` }}>{c.status}</span></td>
                <td className="px-4 py-3 text-xs">{c.owner}</td>
                <td className="px-4 py-3">
                  <button data-testid={`pack-${c.control_id}`} disabled={busy === c.control_id} onClick={(e) => { e.stopPropagation(); pack(c.control_id); }}
                    className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 transition-colors disabled:opacity-50">
                    {busy === c.control_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />} Pack
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </div>

      {selected && (
        <aside data-testid="control-detail-pane" className="hidden md:block md:w-72 lg:w-80 shrink-0 md:sticky md:top-28 bg-card fact-border rounded-xl p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0"><div className="font-mono text-[11px] text-ai">{selected.control_id}</div><div className="font-head font-bold text-sm">{selected.name}</div><div className="text-[10px] text-muted-foreground">{selected.category} · {selected.framework}</div></div>
            <button data-testid="control-detail-close" onClick={() => setSelected(null)} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
          </div>
          <span className="inline-block text-[10px] px-2 py-0.5 rounded-sm font-mono font-bold" style={{ background: `hsl(${statusHsl[selected.status]} / 0.15)`, color: `hsl(${statusHsl[selected.status]})` }}>{selected.status}</span>
          <div className="flex items-center gap-2 text-xs">
            <div className="flex-1 h-2 rounded-full bg-secondary overflow-hidden"><div className="h-full" style={{ width: `${selected.effectiveness}%`, background: selected.effectiveness >= 75 ? "hsl(142 70% 45%)" : selected.effectiveness >= 55 ? "hsl(35 90% 55%)" : "hsl(0 84% 60%)" }} /></div>
            <span className="font-mono w-8">{selected.effectiveness}%</span>
          </div>
          <div className="text-xs space-y-1">
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Maturity</span><span className="font-mono">{selected.maturity}/5</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Owner</span><span className="text-right">{selected.owner}</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Evidence</span><span className={selected.stale ? "text-crit" : ""}>{selected.stale ? `expired ${-selected.days_to_expiry}d` : `${selected.days_to_expiry}d left`}</span></div>
          </div>
          <button data-testid="control-detail-pack" disabled={busy === selected.control_id} onClick={() => pack(selected.control_id)} className="w-full text-xs px-3 py-2 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 transition-colors disabled:opacity-50 flex items-center justify-center gap-1">{busy === selected.control_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />} Evidence pack</button>
          <div className="pt-2 border-t border-border/60 space-y-2" data-testid="control-history">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Remediation &amp; evidence log</div>
            <select data-testid="control-note-kind" value={noteKind} onChange={(e) => setNoteKind(e.target.value)} className="w-full bg-secondary/60 rounded-md px-2 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary">
              <option value="remediation">Remediation action</option>
              <option value="evidence">Evidence</option>
              <option value="note">Note</option>
            </select>
            <textarea data-testid="control-note-text" value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={2} placeholder="Log a remediation action or attach evidence…" className="w-full bg-secondary/60 rounded-md px-2 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary resize-none" />
            <button data-testid="control-note-add" disabled={noteBusy || !noteText.trim()} onClick={addNote} className="w-full text-xs px-3 py-1.5 rounded-md bg-ai/10 border border-ai/30 text-ai hover:bg-ai/20 transition-colors disabled:opacity-50 flex items-center justify-center gap-1">{noteBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />} Add to log</button>
            <div className="space-y-1.5 max-h-52 overflow-y-auto" data-testid="control-history-list">
              {history.length === 0 ? <p className="text-[11px] text-muted-foreground">No entries yet.</p> : history.map((h, i) => (
                <div key={i} data-testid="control-history-item" className="text-[11px] bg-secondary/30 rounded-md p-2 space-y-0.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono uppercase text-[9px] px-1.5 py-0.5 rounded-sm" style={{ background: `${KIND_COLOR[h.kind]}26`, color: KIND_COLOR[h.kind] }}>{h.kind}</span>
                    <span className="text-muted-foreground">{new Date(h.ts).toLocaleDateString()}</span>
                  </div>
                  <div>{h.text}</div>
                  <div className="text-[10px] text-muted-foreground">{h.author}</div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      )}
      </div>
      <p className="text-xs text-muted-foreground">Evidence packs map one control across its aligned frameworks (NIST CSF/800-53/SSDF/AI RMF, EU AI Act, GDPR, SOC 2, ISO 27001/42001) as a downloadable PDF.</p>
    </div>
  );
}
