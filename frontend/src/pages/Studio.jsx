import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { LayoutDashboard, FileText, Loader2, Save, Sparkles, Check, Download, Mail, CalendarClock } from "lucide-react";

const TABS = [["dashboard", "Dashboard Builder", LayoutDashboard], ["report", "Report Builder", FileText]];

export default function Studio() {
  const [tab, setTab] = useState("dashboard");
  return (
    <div className="rise space-y-6" data-testid="studio-page">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Sparkles className="w-7 h-7 text-primary" /> Studio</h1>
        <p className="text-sm text-muted-foreground mt-1">Build custom dashboards and compose reports from live kernel data.</p>
      </div>
      <div className="flex gap-1 border-b border-border">
        {TABS.map(([id, label, Icon]) => (
          <button key={id} data-testid={`studio-tab-${id}`} onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
      </div>
      {tab === "dashboard" ? <DashboardBuilder /> : <ReportBuilder />}
    </div>
  );
}

function DashboardBuilder() {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/studio/dashboard").then((r) => { setData(r.data); setSelected(r.data.selected); }); }, []);
  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const save = async () => {
    setBusy(true);
    try { await api.put("/studio/dashboard", { selected }); toast.success("Dashboard saved"); }
    catch { toast.error("Save failed"); }
    setBusy(false);
  };
  if (!data) return <Spinner />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground">Toggle widgets to build your live dashboard.</div>
        <button data-testid="studio-dashboard-save" disabled={busy} onClick={save} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save</button>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {data.available.map((w) => {
          const on = selected.includes(w.id);
          return (
            <button key={w.id} data-testid={`widget-${w.id}`} onClick={() => toggle(w.id)}
              className={`text-left bg-card rounded-xl p-4 border transition-colors ${on ? "border-primary/50 bg-primary/5" : "fact-border opacity-60 hover:opacity-100"}`}>
              <div className="flex items-center justify-between">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">{w.title}</div>
                <span className={`w-4 h-4 rounded-sm flex items-center justify-center ${on ? "bg-primary text-primary-foreground" : "border border-border"}`}>{on && <Check className="w-3 h-3" />}</span>
              </div>
              <div className="font-head font-black text-3xl mt-1">{w.value}{w.unit}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ReportBuilder() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [sections, setSections] = useState(null);
  const [picked, setPicked] = useState([]);
  const [title, setTitle] = useState("Custom Report");
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState("");
  const [schedule, setSchedule] = useState(null);
  const [savingSched, setSavingSched] = useState(false);

  useEffect(() => { api.get("/studio/report/sections").then((r) => { setSections(r.data); setPicked(r.data.map((s) => s.id)); }); }, []);
  useEffect(() => { if (isAdmin) api.get("/studio/schedule").then((r) => setSchedule(r.data)).catch(() => {}); }, [isAdmin]);
  const toggle = (id) => setPicked((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const compose = async () => {
    if (picked.length === 0) { toast.error("Pick at least one section"); return; }
    setBusy(true);
    try { const { data } = await api.post("/studio/report/compose", { title, sections: picked }); setReport(data); toast.success("Report composed"); }
    catch { toast.error("Compose failed"); }
    setBusy(false);
  };
  const exportPdf = async () => {
    setExporting("pdf");
    try {
      const { data } = await api.post("/studio/report/pdf", { title: report.title, ai_narrative: report.ai_narrative, blocks: report.blocks }, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
      const a = document.createElement("a"); a.href = url; a.download = `${report.title.replace(/ /g, "-")}.pdf`; a.click(); URL.revokeObjectURL(url);
      toast.success("PDF downloaded");
    } catch { toast.error("Export failed"); }
    setExporting("");
  };
  const emailBoard = async () => {
    setExporting("email");
    try { const { data } = await api.post("/studio/report/email", { title: report.title, ai_narrative: report.ai_narrative, blocks: report.blocks }); toast.success(`Emailed to ${data.to.length} board member(s)`); }
    catch (e) { toast.error(e.response?.data?.detail ? "Email failed" : "Email failed"); }
    setExporting("");
  };
  const saveSchedule = async (patch) => {
    setSavingSched(true);
    try {
      const body = { enabled: schedule?.enabled || false, title, sections: picked, cadence: schedule?.cadence || "monthly", ...patch };
      const { data } = await api.put("/studio/schedule", body);
      setSchedule(data);
      toast.success(data.enabled ? `Scheduled (${data.cadence}) to board` : "Schedule turned off");
    } catch { toast.error("Could not save schedule"); }
    setSavingSched(false);
  };
  if (!sections) return <Spinner />;

  return (
    <div className="grid lg:grid-cols-[340px_1fr] gap-6">
      <div className="bg-card fact-border rounded-xl p-4 space-y-4 h-fit">
        <label className="block"><span className="text-xs text-muted-foreground mb-1.5 block">Report title</span>
          <input data-testid="report-title" value={title} onChange={(e) => setTitle(e.target.value)} className="w-full bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary" /></label>
        <div className="space-y-2">
          <div className="text-xs text-muted-foreground">Sections</div>
          {sections.map((s) => {
            const on = picked.includes(s.id);
            return (
              <button key={s.id} data-testid={`section-${s.id}`} onClick={() => toggle(s.id)} className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors ${on ? "bg-primary/10 border border-primary/30" : "bg-secondary/40 border border-transparent text-muted-foreground"}`}>
                <span className={`w-4 h-4 rounded-sm flex items-center justify-center ${on ? "bg-primary text-primary-foreground" : "border border-border"}`}>{on && <Check className="w-3 h-3" />}</span>
                {s.title}
              </button>
            );
          })}
        </div>
        <button data-testid="report-compose" disabled={busy} onClick={compose} className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm disabled:opacity-50">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />} Compose with AI</button>
        {isAdmin && schedule && (
          <div data-testid="report-schedule" className="pt-3 mt-1 border-t border-border/60 space-y-2">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground"><CalendarClock className="w-3.5 h-3.5" /> Auto-email to board</div>
            <p className="text-[11px] text-muted-foreground">Emails this report (current title + sections) to the board on your chosen cadence.</p>
            <div className="grid grid-cols-3 gap-1.5">
              {["weekly", "monthly", "quarterly"].map((c) => (
                <button key={c} data-testid={`schedule-cadence-${c}`} disabled={savingSched}
                  onClick={() => saveSchedule({ cadence: c })}
                  className={`text-[11px] font-bold capitalize py-1.5 rounded-md border transition-colors disabled:opacity-50 ${(schedule.cadence || "monthly") === c ? "bg-primary/15 text-foreground border-primary/40" : "bg-secondary/50 text-muted-foreground border-border"}`}>
                  {c}
                </button>
              ))}
            </div>
            <button data-testid="report-schedule-toggle" disabled={savingSched} onClick={() => saveSchedule({ enabled: !schedule.enabled })}
              className={`w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-sm font-bold transition-colors disabled:opacity-50 ${schedule.enabled ? "bg-ai/15 text-ai border border-ai/30" : "bg-secondary/60 text-muted-foreground border border-border"}`}>
              {savingSched ? <Loader2 className="w-4 h-4 animate-spin" /> : <CalendarClock className="w-4 h-4" />} {schedule.enabled ? "Scheduled — turn off" : "Schedule to board"}
            </button>
            {schedule.enabled && <div className="text-[10px] font-mono text-ai capitalize">ON · {schedule.cadence || "monthly"} · "{schedule.title}" · {schedule.sections?.length || 0} section(s)</div>}
          </div>
        )}
      </div>

      <div className="bg-card fact-border rounded-xl p-6 min-h-[300px]" data-testid="report-output">
        {!report ? (
          <div className="text-sm text-muted-foreground flex items-center justify-center h-full">Pick sections and compose to preview your report.</div>
        ) : (
          <div className="space-y-5">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <h2 className="font-head font-black text-2xl">{report.title}</h2>
                <div className="text-[10px] font-mono text-muted-foreground uppercase mt-1">Generated {new Date(report.generated_at).toLocaleString()} · {report.model}</div>
              </div>
              <div className="flex items-center gap-2">
                <button data-testid="report-export-pdf" disabled={!!exporting} onClick={exportPdf} className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20 disabled:opacity-50">{exporting === "pdf" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Export PDF</button>
                <button data-testid="report-email-board" disabled={!!exporting} onClick={emailBoard} className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-md bg-ai/10 border border-ai/30 text-ai hover:bg-ai/20 disabled:opacity-50">{exporting === "email" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />} Email board</button>
              </div>
            </div>
            {report.ai_narrative && (
              <div className="bg-ai/5 border border-ai/20 rounded-lg p-4" data-testid="report-narrative">
                <div className="text-[10px] font-mono uppercase text-ai flex items-center gap-1.5 mb-1.5"><Sparkles className="w-3.5 h-3.5" /> AI Executive Narrative</div>
                <p className="text-sm leading-relaxed">{report.ai_narrative}</p>
              </div>
            )}
            {report.blocks.map((b, i) => (
              <div key={i} data-testid={`report-block-${i}`}>
                <h3 className="font-head font-bold text-sm text-primary uppercase tracking-wide">{b.heading}</h3>
                <ul className="mt-1.5 space-y-1 text-sm text-muted-foreground list-disc pl-5">
                  {b.lines.map((ln, j) => <li key={j}>{ln}</li>)}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const Spinner = () => <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
