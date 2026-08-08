import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Wallet, Loader2, Download, Search, Brain, Gauge } from "lucide-react";
import { AIInsight } from "@/components/AIInsight";

const SG_ACCENT = "266 85% 66%";

export default function SpendGovernance() {
  const [s, setS] = useState(null);
  const [budgetInput, setBudgetInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [themes, setThemes] = useState(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState(null);
  const [open, setOpen] = useState(null);

  const load = () => api.get("/advisor/usage").then((r) => setS(r.data));
  useEffect(() => { load(); api.get("/advisor/prompts/insights").then((r) => setThemes(r.data)).catch(() => {}); }, []);

  const putBudget = async (patch) => {
    setBusy(true);
    try { await api.put("/advisor/budget", { monthly_usd: s.budget_usd || 0, ...patch }); await load(); toast.success("Saved"); }
    catch { toast.error("Save failed"); }
    setBusy(false);
  };
  const saveCap = () => { const v = parseFloat(budgetInput); if (isNaN(v) || v < 0) return toast.error("Enter a valid cap"); putBudget({ monthly_usd: v }); setBudgetInput(""); };
  const exportCsv = async (scope) => {
    try { const { data } = await api.get("/advisor/usage/export", { params: { scope }, responseType: "blob" });
      const url = URL.createObjectURL(new Blob([data], { type: "text/csv" })); const a = document.createElement("a"); a.href = url; a.download = `advisor-spend-${scope}.csv`; a.click(); URL.revokeObjectURL(url); toast.success("CSV downloaded"); }
    catch { toast.error("Export failed"); }
  };
  const search = async () => { if (q.trim().length < 2) return setResults(null); try { const { data } = await api.get("/advisor/prompts/search", { params: { q } }); setResults(data); } catch { toast.error("Search failed"); } };

  if (!s) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  const statusColor = s.budget_status === "over" ? "text-crit" : s.budget_status === "warning" ? "text-med" : "text-ai";
  const barColor = s.budget_status === "over" ? "bg-crit" : s.budget_status === "warning" ? "bg-med" : "bg-ai";
  const trendMax = Math.max(...(s.trend || []).map((t) => t.cost_usd), 0.0001);

  return (
    <div className="rise space-y-6" data-testid="spend-gov-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Wallet className="w-7 h-7 text-primary" /> AI Spend & Governance</h1>
        <p className="text-sm text-muted-foreground mt-1">Advisor budgets, cost controls, per-teammate spend and prompt audit — powered by Claude Opus 4.8 usage.</p>
      </div>

      <AIInsight dashboard="AI Spend & Governance" accent={SG_ACCENT} auto slug="spend-governance" />

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="bg-card fact-border rounded-xl p-5"><div className="text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1.5"><Gauge className="w-3.5 h-3.5" /> This month</div><div className="font-head font-black text-3xl mt-1">${s.month_cost_usd?.toFixed(2)}</div><div className="text-xs text-muted-foreground mt-1">{s.total_tokens?.toLocaleString()} tokens · {s.queries} queries all-time</div></div>
        <div className="bg-card fact-border rounded-xl p-5 lg:col-span-2">
          <div className="flex items-center justify-between text-xs font-mono mb-1"><span className="uppercase tracking-wider text-muted-foreground">Monthly budget</span><span className={statusColor}>{s.budget_usd > 0 ? `$${s.month_cost_usd?.toFixed(2)} / $${s.budget_usd?.toFixed(2)} · ${s.budget_pct}%` : "no cap set"}</span></div>
          {s.budget_usd > 0 && <div className="h-2 rounded-full bg-secondary overflow-hidden mb-2"><div className={`h-full ${barColor}`} style={{ width: `${Math.min(s.budget_pct, 100)}%` }} /></div>}
          {s.budget_usd > 0 && <div data-testid="sg-forecast" className={`text-[11px] font-mono mb-2 ${s.forecast_over ? "text-crit" : "text-muted-foreground"}`}>Projected month-end: ${s.forecast_usd?.toFixed(2)} ({s.forecast_pct}%){s.forecast_over ? " — on track to exceed cap" : ""}</div>}
          {s.paused && <div data-testid="sg-paused" className="text-[11px] text-crit font-bold mb-2">Advisor auto-paused — cap reached.</div>}
          <div className="flex flex-wrap items-center gap-2">
            <input data-testid="sg-budget-input" type="number" min="0" placeholder={s.budget_usd > 0 ? `current $${s.budget_usd}` : "set $ cap"} value={budgetInput} onChange={(e) => setBudgetInput(e.target.value)} className="w-32 bg-secondary/60 rounded-md px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ai" />
            <button data-testid="sg-budget-save" disabled={busy} onClick={saveCap} className="px-3 py-1.5 rounded-md bg-ai text-background font-bold text-xs disabled:opacity-50">Set cap</button>
            <button data-testid="sg-autopause" disabled={busy} onClick={() => putBudget({ auto_pause: !s.auto_pause })} className={`text-xs px-3 py-1.5 rounded-full border ${s.auto_pause ? "bg-crit/15 text-crit border-crit/30" : "bg-secondary/60 text-muted-foreground border-border"}`}>Auto-pause {s.auto_pause ? "On" : "Off"}</button>
            <span className="text-[10px] font-mono text-muted-foreground">Alert at</span>
            {[75, 80, 90].map((t) => <button key={t} data-testid={`sg-threshold-${t}`} disabled={busy} onClick={() => putBudget({ alert_threshold: t })} className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${Math.round(s.alert_threshold || 80) === t ? "bg-ai/15 text-ai border-ai/30" : "bg-secondary/60 text-muted-foreground border-border"}`}>{t}%</button>)}
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="bg-card fact-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-2"><div className="text-xs font-mono uppercase text-muted-foreground">Spend by teammate (this month)</div><div className="flex gap-2"><button data-testid="sg-csv-month" onClick={() => exportCsv("month")} className="text-[11px] inline-flex items-center gap-1 px-2 py-1 rounded-md bg-secondary/60 border border-border"><Download className="w-3 h-3" /> Month</button><button data-testid="sg-csv-all" onClick={() => exportCsv("all")} className="text-[11px] inline-flex items-center gap-1 px-2 py-1 rounded-md bg-secondary/60 border border-border"><Download className="w-3 h-3" /> All</button></div></div>
          <div className="space-y-1">
            {(s.by_user || []).length === 0 ? <div className="text-xs text-muted-foreground">No spend yet this month.</div> : s.by_user.map((u) => (
              <div key={u.user} data-testid={`sg-user-${u.user}`} className="flex items-center justify-between text-xs font-mono border-b border-border/50 py-1"><span className="truncate max-w-[60%] text-muted-foreground">{u.user}</span><span className="text-ai">${u.cost_usd.toFixed(4)} · {u.queries}q</span></div>
            ))}
          </div>
          {s.trend?.length > 0 && (<div className="mt-4"><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">6-month spend</div><div className="flex items-end gap-1 h-12">{s.trend.map((t) => <div key={t.month} className="flex-1 flex flex-col items-center gap-0.5" title={`${t.month}: $${t.cost_usd.toFixed(2)}`}><div className="w-full bg-ai/60 rounded-sm" style={{ height: `${Math.max(2, (t.cost_usd / trendMax) * 40)}px` }} /><span className="text-[8px] font-mono text-muted-foreground">{t.month.slice(5)}</span></div>)}</div></div>)}
        </div>

        <div className="bg-card fact-border rounded-xl p-5">
          <div className="text-xs font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1.5"><Brain className="w-3.5 h-3.5" /> Prompt audit</div>
          {themes?.themes?.length > 0 && <div className="flex flex-wrap gap-1 mb-2">{themes.themes.map((t) => <button key={t.term} data-testid={`sg-theme-${t.term}`} onClick={() => { setQ(t.term); api.get("/advisor/prompts/search", { params: { q: t.term } }).then((r) => setResults(r.data)); }} className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-ai/10 text-ai border border-ai/20">{t.term} · {t.count}</button>)}</div>}
          <div className="flex gap-2 mb-2"><input data-testid="sg-search" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} placeholder="Search all advisor prompts…" className="flex-1 bg-secondary/60 rounded-md px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ai" /><button data-testid="sg-search-btn" onClick={search} className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-bold inline-flex items-center gap-1"><Search className="w-3 h-3" /> Search</button></div>
          {results && (<div data-testid="sg-results" className="space-y-1 max-h-72 overflow-y-auto">{results.length === 0 ? <div className="text-xs text-muted-foreground">No matches.</div> : results.map((r, i) => (<div key={i} className="text-[11px] border-l border-ai/30 pl-2"><button data-testid={`sg-audit-${i}`} onClick={() => setOpen(open === i ? null : i)} className="text-left w-full hover:bg-secondary/40 rounded px-1 -ml-1"><div className="text-foreground/90 truncate">{r.prompt}</div><div className="font-mono text-muted-foreground">{r.user} · {new Date(r.ts).toLocaleDateString()}{r.cost_usd != null ? ` · $${r.cost_usd.toFixed(4)}` : ""}</div></button>{open === i && <div className="mt-1 mb-1 p-2 rounded bg-secondary/50 text-foreground/80 whitespace-pre-wrap leading-relaxed">{r.response || "No stored answer."}</div>}</div>))}</div>)}
        </div>
      </div>
    </div>
  );
}
