import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BoardReportModal } from "@/components/BoardReportModal";
import { FileBarChart, FileText, Loader2 } from "lucide-react";

export default function Reporting() {
  const [reports, setReports] = useState(null);
  const [open, setOpen] = useState(false);

  const load = () => api.get("/reports").then((r) => setReports(r.data));
  useEffect(() => { load(); }, []);

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
