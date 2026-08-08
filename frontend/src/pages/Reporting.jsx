import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BoardReportModal } from "@/components/BoardReportModal";
import { toast } from "sonner";
import { FileBarChart, FileText, Loader2, TrendingDown, Download, Coins, ShieldAlert, Package } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

export default function Reporting() {
  const [reports, setReports] = useState(null);
  const [trend, setTrend] = useState(null);
  const [open, setOpen] = useState(false);
  const [pdfBusy, setPdfBusy] = useState("");
  const downloadPersona = async (path, filename, key) => {
    setPdfBusy(key);
    try {
      const res = await api.post(path, {}, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
    } catch { toast.error("Could not generate the PDF"); }
    setPdfBusy("");
  };

  const load = () => api.get("/reports").then((r) => setReports(r.data));
  useEffect(() => { load(); api.get("/financials/trend").then((r) => setTrend(r.data)); }, []);

  return (
    <div className="rise space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><FileBarChart className="w-7 h-7 text-primary" /> Evidence &amp; Reporting</h1>
          <p className="text-sm text-muted-foreground mt-1">Generate board-ready packets, export PDF and email — every claim tied to evidence.</p>
        </div>
        <button data-testid="new-report-btn" onClick={() => setOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-ai/15 border border-ai/40 text-ai font-head font-bold text-sm hover:bg-ai/25 transition-colors">
          <FileText className="w-4 h-4" /> New Board Report
        </button>
      </div>

      <div data-testid="persona-exports" className="bg-card fact-border rounded-xl p-5">
        <h2 className="font-head font-bold text-lg flex items-center gap-2 mb-1"><Package className="w-4 h-4 text-ai" /> Multi-persona exports</h2>
        <p className="text-sm text-muted-foreground mb-4">One-click branded PDFs built live from the Unified Risk Correlation Engine — tailored to each audience.</p>
        <div className="grid sm:grid-cols-3 gap-3">
          {[
            { key: "board", label: "Board Pack", desc: "Cyber risk + financials + FAIR-AIR + NIST coverage", path: "/reports/board-pack.pdf", file: "obserra-board-pack.pdf", icon: FileBarChart },
            { key: "cfo", label: "CFO Brief", desc: "Financial exposure, TPRM premium & security-spend ROI", path: "/reports/cfo-brief.pdf", file: "obserra-cfo-brief.pdf", icon: Coins },
            { key: "soc", label: "SOC Plan", desc: "Prioritized remediation queue, SLAs & fix paths", path: "/reports/soc-plan.pdf", file: "obserra-soc-plan.pdf", icon: ShieldAlert },
          ].map((p) => (
            <button key={p.key} data-testid={`export-${p.key}`} disabled={!!pdfBusy} onClick={() => downloadPersona(p.path, p.file, p.key)}
              className="text-left rounded-lg border border-border bg-secondary/30 hover:border-ai/40 hover:bg-ai/5 transition-colors p-4 disabled:opacity-50">
              <div className="flex items-center gap-2 font-head font-bold text-sm"><p.icon className="w-4 h-4 text-ai" /> {p.label} {pdfBusy === p.key ? <Loader2 className="w-3.5 h-3.5 animate-spin ml-auto" /> : <Download className="w-3.5 h-3.5 text-muted-foreground ml-auto" />}</div>
              <p className="text-[11px] text-muted-foreground mt-1.5 leading-snug">{p.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {trend && (
        <div data-testid="ale-trend" className="bg-card fact-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-head font-bold text-lg flex items-center gap-2"><TrendingDown className="w-4 h-4 text-low" /> Portfolio Exposure Trend</h2>
            <div className="text-right"><div className="text-[10px] font-mono uppercase text-muted-foreground">Residual ALE now</div><div className="font-head font-black text-2xl text-high">${(trend.current / 1e6).toFixed(1)}M</div></div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={trend.series} margin={{ left: 4, right: 4 }}>
              <defs><linearGradient id="ale" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="hsl(15 80% 55%)" stopOpacity={0.5} /><stop offset="100%" stopColor="hsl(15 80% 55%)" stopOpacity={0} /></linearGradient></defs>
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "hsl(215 20% 62%)" }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(v) => `$${(v / 1e6).toFixed(0)}M`} tick={{ fontSize: 11, fill: "hsl(215 20% 62%)" }} axisLine={false} tickLine={false} width={44} />
              <Tooltip formatter={(v) => `$${(v / 1e6).toFixed(2)}M`} contentStyle={{ background: "hsl(215 38% 10%)", border: "1px solid hsl(215 30% 18%)", borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="exposure" stroke="hsl(15 80% 55%)" strokeWidth={2.5} fill="url(#ale)" />
            </AreaChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted-foreground mt-1">Dollars-at-risk trending down as controls take effect (FAIR-style annualized loss expectancy).</p>
        </div>
      )}

      {!reports ? <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div> : (
        <div className="space-y-3">
          {reports.length === 0 && <div className="bg-card fact-border rounded-xl p-8 text-center text-sm text-muted-foreground">No reports yet. Generate your first board packet.</div>}
          {reports.map((r, i) => (
            <div key={i} data-testid={`report-${i}`} className="bg-card fact-border rounded-lg p-4 flex items-center gap-4">
              <FileText className="w-5 h-5 text-ai" />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm">Executive Board Report</div>
                <div className="text-[11px] font-mono text-muted-foreground">{r.model} · by {r.by} · {new Date(r.generated_at).toLocaleString()}</div>
              </div>
              <div className="text-xs text-muted-foreground line-clamp-1 max-w-md hidden md:block">{(r.report || "").replace(/[#*]/g, "").slice(0, 90)}…</div>
            </div>
          ))}
        </div>
      )}

      <BoardReportModal open={open} onClose={() => { setOpen(false); load(); }} />
    </div>
  );
}
