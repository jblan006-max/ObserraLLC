import { useState } from "react";
import { X, FileText, Loader2, Download, Sparkle, Mail } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

function renderReport(text) {
  return text.split("\n").map((line, i) => {
    if (line.startsWith("## ")) return <h3 key={i} className="font-head font-bold text-ai text-base mt-4 mb-1.5">{line.slice(3)}</h3>;
    if (line.startsWith("# ")) return <h2 key={i} className="font-head font-black text-lg mt-2 mb-2">{line.slice(2)}</h2>;
    if (!line.trim()) return <div key={i} className="h-1.5" />;
    const parts = line.split(/(\[(?:CR|AI|AII|REC|DEC)-\d{3}\])/g);
    return <p key={i} className="text-sm leading-relaxed text-foreground/90">
      {parts.map((p, j) => /^\[(CR|AI|AII|REC|DEC)-\d{3}\]$/.test(p)
        ? <span key={j} className="font-mono text-ai bg-ai/10 px-1 rounded-sm">{p}</span> : <span key={j}>{p}</span>)}
    </p>;
  });
}

export function BoardReportModal({ open, onClose }) {
  const [loading, setLoading] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [report, setReport] = useState("");
  const [meta, setMeta] = useState(null);

  const emailReport = async () => {
    setEmailing(true);
    try {
      const { data } = await api.post("/reports/email", { report, title: "Executive Board Report" });
      toast.success(`Report emailed to ${data.to}`);
    } catch { toast.error("Could not send email"); }
    setEmailing(false);
  };

  const downloadPdf = async () => {
    try {
      const res = await api.post("/reports/pdf", { report, title: "Executive Board Report" }, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = "obserra-board-report.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Could not generate PDF"); }
  };

  const generate = async () => {
    setLoading(true); setReport(""); setMeta(null);
    try {
      const { data } = await api.post("/advisor/board-report");
      setReport(data.report); setMeta(data);
    } catch { setReport("Could not generate the board report right now."); }
    setLoading(false);
  };

  if (open && !report && !loading) generate();
  if (!open) return null;

  const download = () => {
    const blob = new Blob([report], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `obserra-board-report-${new Date().toISOString().slice(0, 10)}.txt`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div data-testid="board-report-modal" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-2xl max-h-[82vh] bg-card border border-ai/30 rounded-lg flex flex-col rise">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-ai" />
            <span className="font-head font-bold">Board Report</span>
            {meta && <span className="text-[10px] font-mono text-muted-foreground">· {meta.model}</span>}
          </div>
          <div className="flex items-center gap-2">
            {report && !loading && (
              <>
                <button data-testid="report-download" onClick={downloadPdf} className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-secondary/60 hover:bg-secondary transition-colors">
                  <Download className="w-3.5 h-3.5" /> PDF
                </button>
                <button data-testid="report-email" onClick={emailReport} disabled={emailing} className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/15 border border-primary/30 hover:bg-primary/25 transition-colors disabled:opacity-50">
                  {emailing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />} Email me
                </button>
              </>
            )}
            <button data-testid="report-close" onClick={() => { onClose(); setReport(""); }} className="p-1.5 rounded-md hover:bg-secondary"><X className="w-4 h-4" /></button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted-foreground">
              <div className="relative"><Sparkle className="w-8 h-8 text-ai animate-pulse" /></div>
              <p className="text-sm">Synthesizing evidence into a board-ready report…</p>
              <p className="text-[10px] font-mono">Claude Sonnet 5 · grounded on your live posture</p>
            </div>
          ) : renderReport(report)}
        </div>
      </div>
    </div>
  );
}
