import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useUrlState } from "@/hooks/useUrlState";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Building, Loader2, Layers, ShieldAlert, PlayCircle, Search, X, Plus } from "lucide-react";

const TIER = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };
const KIND_COLOR = { remediation: "#3b82f6", evidence: "#22c55e", note: "#94a3b8" };

export default function VendorRisk() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");
  const [q, setQ] = useUrlState("q", "");
  const [tierF, setTierF] = useUrlState("tierF", "all");
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState([]);
  const [noteText, setNoteText] = useState("");
  const [noteKind, setNoteKind] = useState("remediation");
  const [noteBusy, setNoteBusy] = useState(false);

  const load = () => api.get("/vendors").then((r) => setData(r.data));
  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!selected) { setHistory([]); return; }
    setNoteText("");
    api.get(`/vendors/${selected.ref}/history`).then((r) => setHistory(r.data)).catch(() => setHistory([]));
  }, [selected]);

  const addNote = async () => {
    if (!noteText.trim() || !selected) return;
    setNoteBusy(true);
    try {
      await api.post(`/vendors/${selected.ref}/notes`, { kind: noteKind, text: noteText.trim() });
      setNoteText("");
      const r = await api.get(`/vendors/${selected.ref}/history`);
      setHistory(r.data);
      toast.success("Added to vendor log");
    } catch { toast.error("Could not add to log"); }
    setNoteBusy(false);
  };

  const assess = async (ref) => {
    setBusy(ref);
    try { const { data: r } = await api.post(`/vendors/${ref}/assess`); toast.success(`${ref}: ${r.risk_tier} (${r.risk_score})`); load(); }
    catch { toast.error("Assess failed"); }
    setBusy("");
  };

  if (!data) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const shownVendors = data.vendors.filter((v) => (tierF === "all" || v.risk_tier === tierF) && `${v.name} ${v.ref}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="rise space-y-6">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Building className="w-7 h-7 text-primary" /> Third-Party Risk</h1>
        <p className="text-sm text-muted-foreground mt-1">Vendor risk management — the second standalone app composed on the Obserra kernel.</p>
        <div data-testid="tpr-composition" className="flex flex-wrap items-center gap-2 mt-3">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1"><Layers className="w-3.5 h-3.5" /> Composed on:</span>
          {data.composition.map((c) => <span key={c} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{c}</span>)}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 max-w-md">
        <div className="bg-card fact-border rounded-xl p-4"><div className="text-[10px] font-mono uppercase text-muted-foreground">Portfolio risk</div><div className="font-head font-black text-3xl">{data.portfolio_risk}</div></div>
        <div className="bg-card fact-border rounded-xl p-4" style={{ borderLeft: "3px solid hsl(0 84% 60%)" }}><div className="text-[10px] font-mono uppercase text-muted-foreground">High / Critical</div><div className="font-head font-black text-3xl text-crit">{data.high_risk}</div></div>
      </div>

      <div className="flex flex-wrap gap-2" data-testid="vendor-filters">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input data-testid="vendor-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search vendors..." className="w-full bg-secondary/60 rounded-md pl-9 pr-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
        </div>
        <select data-testid="vendor-filter" value={tierF} onChange={(e) => setTierF(e.target.value)} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary">
          <option value="all">All tiers</option><option value="Critical">Critical</option><option value="High">High</option><option value="Medium">Medium</option><option value="Low">Low</option>
        </select>
      </div>
      <div className="md:flex md:gap-5 md:items-start">
      <div className="min-w-0 flex-1 space-y-4">
      <div className="md:hidden space-y-3" data-testid="vendor-cards-mobile">
        {shownVendors.map((v) => (
          <div key={v.ref} data-testid={`vendor-card-${v.ref}`} onClick={() => setSelected(v)} className="bg-card fact-border rounded-xl p-4 space-y-2 active:bg-secondary/40 transition-colors">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0"><div className="font-mono text-[11px] text-ai">{v.ref}</div><div className="font-medium text-sm">{v.name}</div><div className="text-[11px] text-muted-foreground">{v.category} · {v.data_access}</div></div>
              <span className="text-[10px] px-2 py-0.5 rounded-sm font-mono font-bold shrink-0" style={{ background: `hsl(${TIER[v.risk_tier]} / 0.15)`, color: `hsl(${TIER[v.risk_tier]})` }}>{v.risk_tier} · {v.risk_score}</span>
            </div>
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Attested {v.attestation}% · {v.incidents > 0 ? <span className="text-crit">{v.incidents} incidents</span> : "0 incidents"}</span>
              {isAdmin && <button data-testid={`assess-m-${v.ref}`} disabled={!!busy} onClick={(e) => { e.stopPropagation(); assess(v.ref); }} className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-primary/10 border border-primary/30 disabled:opacity-50">{busy === v.ref ? <Loader2 className="w-3 h-3 animate-spin" /> : <PlayCircle className="w-3 h-3" />} Assess</button>}
            </div>
          </div>
        ))}
      </div>

      <div className="hidden md:block bg-card fact-border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[820px]">
          <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr><th className="text-left px-4 py-3">Vendor</th><th className="text-left px-4 py-3">Category</th><th className="text-left px-4 py-3">Data access</th><th className="text-left px-4 py-3">Attested</th><th className="text-left px-4 py-3">Incidents</th><th className="text-left px-4 py-3">Risk</th><th className="text-right px-4 py-3">Action</th></tr>
          </thead>
          <tbody>
            {shownVendors.map((v) => (
              <tr key={v.ref} data-testid={`vendor-row-${v.ref}`} onClick={() => setSelected(v)} className={`border-b border-border/60 hover:bg-secondary/40 transition-colors cursor-pointer ${selected?.ref === v.ref ? "bg-secondary/50" : ""}`}>
                <td className="px-4 py-3"><div className="font-mono text-xs text-ai">{v.ref}</div><div className="font-medium">{v.name}</div></td>
                <td className="px-4 py-3 text-muted-foreground">{v.category}</td>
                <td className="px-4 py-3">{v.data_access}</td>
                <td className="px-4 py-3">{v.attestation}%</td>
                <td className="px-4 py-3">{v.incidents > 0 ? <span className="text-crit flex items-center gap-1"><ShieldAlert className="w-3.5 h-3.5" />{v.incidents}</span> : "0"}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${TIER[v.risk_tier]} / 0.15)`, color: `hsl(${TIER[v.risk_tier]})` }}>{v.risk_tier} · {v.risk_score}</span></td>
                <td className="px-4 py-3 text-right">
                  {isAdmin && <button data-testid={`assess-${v.ref}`} disabled={!!busy} onClick={(e) => { e.stopPropagation(); assess(v.ref); }} className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 disabled:opacity-50">{busy === v.ref ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />} Assess</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </div>

      {selected && (
        <aside data-testid="vendor-detail-pane" className="hidden md:block md:w-72 lg:w-80 shrink-0 md:sticky md:top-28 bg-card fact-border rounded-xl p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0"><div className="font-mono text-[11px] text-ai">{selected.ref}</div><div className="font-head font-bold text-sm">{selected.name}</div></div>
            <button data-testid="vendor-detail-close" onClick={() => setSelected(null)} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
          </div>
          <span className="inline-block text-[10px] px-2 py-0.5 rounded-sm font-mono font-bold" style={{ background: `hsl(${TIER[selected.risk_tier]} / 0.15)`, color: `hsl(${TIER[selected.risk_tier]})` }}>{selected.risk_tier} · {selected.risk_score}</span>
          <div className="text-xs space-y-1">
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Category</span><span className="text-right">{selected.category}</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Data access</span><span className="text-right">{selected.data_access}</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Attestation</span><span>{selected.attestation}%</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Incidents</span><span className={selected.incidents > 0 ? "text-crit" : ""}>{selected.incidents}</span></div>
          </div>
          {isAdmin && <button data-testid="vendor-detail-assess" disabled={!!busy} onClick={() => assess(selected.ref)} className="w-full text-xs px-3 py-2 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 transition-colors disabled:opacity-50 flex items-center justify-center gap-1">{busy === selected.ref ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5" />} Re-assess vendor</button>}
          <div className="pt-2 border-t border-border/60 space-y-2" data-testid="vendor-history">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Remediation &amp; evidence log</div>
            <select data-testid="vendor-note-kind" value={noteKind} onChange={(e) => setNoteKind(e.target.value)} className="w-full bg-secondary/60 rounded-md px-2 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary">
              <option value="remediation">Remediation action</option>
              <option value="evidence">Evidence</option>
              <option value="note">Note</option>
            </select>
            <textarea data-testid="vendor-note-text" value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={2} placeholder="Log a remediation action or attach evidence…" className="w-full bg-secondary/60 rounded-md px-2 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary resize-none" />
            <button data-testid="vendor-note-add" disabled={noteBusy || !noteText.trim()} onClick={addNote} className="w-full text-xs px-3 py-1.5 rounded-md bg-ai/10 border border-ai/30 text-ai hover:bg-ai/20 transition-colors disabled:opacity-50 flex items-center justify-center gap-1">{noteBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />} Add to log</button>
            <div className="space-y-1.5 max-h-52 overflow-y-auto" data-testid="vendor-history-list">
              {history.length === 0 ? <p className="text-[11px] text-muted-foreground">No entries yet.</p> : history.map((h, i) => (
                <div key={i} data-testid="vendor-history-item" className="text-[11px] bg-secondary/30 rounded-md p-2 space-y-0.5">
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
      <p className="text-[11px] text-muted-foreground">Assessing a High/Critical vendor opens a remediation workflow and alerts owners — proving the kernel loop.</p>
    </div>
  );
}
