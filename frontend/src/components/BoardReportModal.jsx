import { useState, useEffect } from "react";
import { X, FileText, Loader2, Download, Sparkle, Mail, MessageSquare, Sun, Moon, Presentation, Eye } from "lucide-react";
import { api, API } from "@/lib/api";
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
  const [sharing, setSharing] = useState(false);
  const [report, setReport] = useState("");
  const [meta, setMeta] = useState(null);
  const [theme, setTheme] = useState("dark");
  const [coverDate, setCoverDate] = useState("");
  const [version, setVersion] = useState("");

  const shareTeams = async () => {
    setSharing(true);
    try {
      await api.post("/enterprise/live/teams/share", { title: "Obserra — Executive Board Report", text: report });
      toast.success("Board report shared to Microsoft Teams");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not share to Teams");
    }
    setSharing(false);
  };

  const emailReport = async () => {
    setEmailing(true);
    try {
      const { data } = await api.post("/reports/email", { report, title: "Executive Board Report" });
      toast.success(`Report emailed to ${data.to}`);
    } catch { toast.error("Could not send email"); }
    setEmailing(false);
  };

  const downloadPdf = async (layout = "report") => {
    try {
      const res = await api.post("/reports/pdf", { report, title: "Executive Board Report", theme, layout, cover_date: coverDate, version }, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url;
      a.download = layout === "deck" ? "obserra-board-deck.pdf" : "obserra-board-report.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Could not generate PDF"); }
  };

  const generate = async () => {
    setLoading(true); setReport(""); setMeta(null);
    try {
      const { data } = await api.post("/advisor/board-report");
      const jobId = data.job_id;
      let done = false;
      for (let tries = 0; tries < 90 && !done; tries++) {
        await new Promise((r) => setTimeout(r, 2000));
        const { data: job } = await api.get(`/advisor/board-report/${jobId}`);
        if (job.status === "done") { setReport(job.report); setMeta(job); done = true; }
        else if (job.status === "error") { setReport("Could not generate the board report right now."); done = true; }
      }
      if (!done) setReport("The board report is taking longer than expected — please try again.");
    } catch { setReport("Could not generate the board report right now."); }
    setLoading(false);
  };

  useEffect(() => {
    if (open && !report && !loading) generate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
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
                <div className="flex items-center rounded-md bg-secondary/60 p-0.5" data-testid="cover-theme-toggle" title="Cover theme">
                  <button data-testid="theme-dark" onClick={() => setTheme("dark")} className={`px-2 py-1 rounded text-[11px] flex items-center gap-1 transition-colors ${theme === "dark" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                    <Moon className="w-3 h-3" /> Dark
                  </button>
                  <button data-testid="theme-light" onClick={() => setTheme("light")} className={`px-2 py-1 rounded text-[11px] flex items-center gap-1 transition-colors ${theme === "light" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                    <Sun className="w-3 h-3" /> Light
                  </button>
                </div>
                <button data-testid="report-download" onClick={() => downloadPdf("report")} className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-secondary/60 hover:bg-secondary transition-colors">
                  <Download className="w-3.5 h-3.5" /> PDF
                </button>
                <button data-testid="report-download-deck" onClick={() => downloadPdf("deck")} className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-secondary/60 hover:bg-secondary transition-colors">
                  <Presentation className="w-3.5 h-3.5" /> Deck
                </button>
                <button data-testid="report-email" onClick={emailReport} disabled={emailing} className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-primary/15 border border-primary/30 hover:bg-primary/25 transition-colors disabled:opacity-50">
                  {emailing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />} Email me
                </button>
                <button data-testid="report-share-teams" onClick={shareTeams} disabled={sharing} className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-ai/15 border border-ai/30 text-ai hover:bg-ai/25 transition-colors disabled:opacity-50">
                  {sharing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <MessageSquare className="w-3.5 h-3.5" />} Share to Teams
                </button>
              </>
            )}
            <button data-testid="report-close" onClick={() => { onClose(); setReport(""); }} className="p-1.5 rounded-md hover:bg-secondary"><X className="w-4 h-4" /></button>
          </div>
        </div>
        {report && !loading && (
          <div className="flex flex-wrap items-center gap-3 px-5 py-2.5 border-b border-border/60 bg-secondary/20" data-testid="cover-options">
            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Cover</span>
            <input data-testid="cover-date-input" value={coverDate} onChange={(e) => setCoverDate(e.target.value)} placeholder="Date (e.g. Q2 2026 · June 30, 2026)"
              className="flex-1 min-w-[150px] bg-secondary/60 rounded-md px-2.5 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary" />
            <input data-testid="cover-version-input" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="Version / revision (e.g. v1.2 — Rev C)"
              className="flex-1 min-w-[150px] bg-secondary/60 rounded-md px-2.5 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary" />
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted-foreground">
              <div className="relative"><Sparkle className="w-8 h-8 text-ai animate-pulse" /></div>
              <p className="text-sm">Synthesizing evidence into a board-ready report…</p>
              <p className="text-[10px] font-mono">Claude Opus 4.8 · deep FAIR analysis on your live posture</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-[160px_1fr] gap-5">
              {report && (
                <div className="hidden md:block" data-testid="modal-cover-preview">
                  <div className="flex items-center gap-1.5 text-[10px] font-head font-bold uppercase tracking-wide text-muted-foreground mb-1.5">
                    <Eye className="w-3 h-3 text-ai" /> Cover
                  </div>
                  <img key={`${theme}`} data-testid="modal-cover-preview-img"
                    src={`${API}/reports/branding/preview?theme=${theme}`}
                    alt="Board report cover preview"
                    className="w-full rounded-md border border-border shadow-sm bg-secondary/40 sticky top-0" />
                  <p className="text-[10px] text-muted-foreground mt-1.5 leading-snug">This is the branded cover the board will receive.</p>
                </div>
              )}
              <div>{renderReport(report)}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
