import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { StatCard, Spinner } from "@/components/dash";
import { SapInsight } from "@/components/SapInsight";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Workflow, CheckCircle2, Timer, Zap, ArrowRight, Download, FileText, MessagesSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const SYS_COLOR = { ServiceNow: "150 60% 50%", ADP: "330 82% 60%", IZ8: "265 80% 66%", SAP: "210 92% 62%", "AD/Entra": "35 90% 55%" };
const PFX = { REQ: "142 70% 45%", INC: "0 84% 60%", CHG: "35 90% 55%" };
const SRC = { slack: "265 80% 66%", teams: "210 92% 62%", test: "142 70% 45%", app: "220 10% 55%" };
const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
const Sys = ({ s }) => <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: `hsl(${SYS_COLOR[s] || "220 10% 55%"} / 0.15)`, color: `hsl(${SYS_COLOR[s] || "220 10% 55%"})` }}>{s}</span>;

export default function WorkflowActivity() {
  const [d, setD] = useState(null);
  const [q, setQ] = useState("");
  const [prefix, setPrefix] = useState("all");
  const [system, setSystem] = useState("all");
  const [days, setDays] = useState("0");
  const [detail, setDetail] = useState(null);
  const [askLog, setAskLog] = useState(null);
  const [askAn, setAskAn] = useState(null);

  const load = useCallback(async () => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (prefix !== "all") p.set("prefix", prefix);
    if (system !== "all") p.set("system", system);
    if (days !== "0") p.set("days", days);
    const { data } = await api.get(`/sap/workflow/activity?${p.toString()}`);
    setD(data);
  }, [q, prefix, system, days]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get("/sap/ask-log?limit=25").then((r) => setAskLog(r.data)).catch(() => {});
    api.get("/sap/ask-analytics").then((r) => setAskAn(r.data)).catch(() => {});
  }, []);
  useEffect(() => {
    const h = () => load();
    window.addEventListener("sap-data-changed", h);
    return () => window.removeEventListener("sap-data-changed", h);
  }, [load]);

  const doExport = async (format) => {
    const p = new URLSearchParams();
    p.set("format", format);
    if (q) p.set("q", q);
    if (prefix !== "all") p.set("prefix", prefix);
    if (system !== "all") p.set("system", system);
    if (days !== "0") p.set("days", days);
    try {
      const res = await api.get(`/sap/workflow/activity/export?${p.toString()}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sap-workflow-evidence.${format}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success(`Workflow ${format.toUpperCase()} evidence pack exported`);
    } catch { toast.error("Export failed"); }
  };

  if (!d) return <Spinner />;
  const s = d.summary;

  return (
    <div className="space-y-6" data-testid="workflow-activity-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="wf-title">Workflow Activity</h1>
          <p className="text-sm text-muted-foreground mt-1">Live, filterable stream of every ServiceNow workflow the platform has opened and auto-closed across all dashboards (ServiceNow → ADP/IZ8 → SAP → AD/Entra).</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button size="sm" variant="outline" className="gap-1.5" data-testid="wf-export-csv" onClick={() => doExport("csv")}><Download className="w-3.5 h-3.5" />CSV</Button>
          <Button size="sm" variant="outline" className="gap-1.5" data-testid="wf-export-pdf" onClick={() => doExport("pdf")}><FileText className="w-3.5 h-3.5" />PDF evidence pack</Button>
        </div>
      </div>

      <SapInsight dashboard="Workflow Activity" focus="ServiceNow ticket automation volume, cross-system reach and remediation throughput" accent="265 80% 66%" auto slug="workflow-activity" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total workflows" value={s.total} sub={`${d.by_prefix.REQ || 0} REQ · ${d.by_prefix.INC || 0} INC · ${d.by_prefix.CHG || 0} CHG`} accent="265 80% 66%" icon={Workflow} testid="wf-total" />
        <StatCard label="Auto-closed" value={s.auto_closed} sub="End-to-end, no human touch" accent="142 70% 45%" icon={CheckCircle2} testid="wf-autoclosed" />
        <StatCard label="Last 24 hours" value={s.last_24h} sub="Workflows opened" accent="210 92% 62%" icon={Zap} testid="wf-last24" />
        <StatCard label="Avg fulfilment" value={`${s.avg_duration_sec}s`} sub="Open → auto-close" accent="35 90% 55%" icon={Timer} testid="wf-duration" />
      </div>

      {askLog && askLog.total > 0 && (
        <div className="bg-card fact-border rounded-xl p-4" data-testid="ask-log-card">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <MessagesSquare className="w-4 h-4 text-primary" />
            <h2 className="font-head font-bold text-sm">Ask the Digest — Slack / Teams answers</h2>
            <span className="text-[10px] font-mono text-muted-foreground">{askLog.total} asked · {Object.entries(askLog.by_source || {}).map(([k, v]) => `${v} ${k}`).join(" · ")}</span>
          </div>
          <p className="text-[11px] text-muted-foreground mb-3">Every governance question leaders asked from Slack or Microsoft Teams, answered live from the SAP access snapshot.</p>
          {askAn && ((askAn.top_questions || []).length > 0 || (askAn.top_askers || []).length > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3" data-testid="ask-analytics">
              <div className="rounded-lg border border-border/60 bg-background/40 p-3">
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Most-asked questions</div>
                <div className="space-y-1">
                  {(askAn.top_questions || []).slice(0, 5).map((q, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs" data-testid={`ask-top-q-${i}`}>
                      <span className="font-mono text-[10px] text-primary w-7 shrink-0">{q.count}×</span>
                      <span className="truncate text-foreground/90">{q.question}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/40 p-3">
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Busiest askers</div>
                <div className="space-y-1">
                  {(askAn.top_askers || []).slice(0, 5).map((a, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs" data-testid={`ask-top-user-${i}`}>
                      <span className="font-mono text-[10px] text-primary w-7 shrink-0">{a.count}×</span>
                      <span className="truncate text-foreground/90">{a.user}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          <div className="space-y-2 max-h-[360px] overflow-y-auto" data-testid="ask-log-list">
            {askLog.entries.map((e, i) => (
              <div key={i} className="rounded-lg border border-border/60 bg-background/40 p-2.5" data-testid={`ask-log-${i}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-full" style={{ background: `hsl(${SRC[e.source] || "220 10% 55%"} / 0.15)`, color: `hsl(${SRC[e.source] || "220 10% 55%"})` }}>{e.source}</span>
                  <span className="text-xs font-medium">{e.user_name}</span>
                  <div className="flex-1" />
                  <span className="text-[10px] text-muted-foreground">{fmtDT(e.at)}</span>
                </div>
                <div className="text-xs text-foreground/90"><span className="text-muted-foreground">Q · </span>{e.question}</div>
                <div className="text-xs text-foreground/80 mt-0.5"><span className="text-muted-foreground">A · </span>{e.answer}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-card fact-border rounded-xl">
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background/50 px-2.5 h-9 flex-1 min-w-[180px]">
            <Search className="w-3.5 h-3.5 text-muted-foreground" />
            <input data-testid="wf-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search ticket #, type, person, reason…" className="bg-transparent text-sm outline-none w-full" />
          </div>
          <Select value={prefix} onValueChange={setPrefix}><SelectTrigger data-testid="wf-filter-prefix" className="w-[130px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All types</SelectItem><SelectItem value="REQ">REQ (request)</SelectItem><SelectItem value="INC">INC (incident)</SelectItem><SelectItem value="CHG">CHG (change)</SelectItem></SelectContent></Select>
          <Select value={system} onValueChange={setSystem}><SelectTrigger data-testid="wf-filter-system" className="w-[140px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">All systems</SelectItem>{d.systems.map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent></Select>
          <Select value={days} onValueChange={setDays}><SelectTrigger data-testid="wf-filter-days" className="w-[130px] h-9"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="0">All time</SelectItem><SelectItem value="1">Last 24h</SelectItem><SelectItem value="7">Last 7 days</SelectItem><SelectItem value="30">Last 30 days</SelectItem></SelectContent></Select>
        </div>
        <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
          <table className="w-full text-sm" data-testid="wf-table">
            <thead className="sticky top-0 bg-card"><tr className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
              <th className="p-3">Ticket</th><th className="p-3">Workflow</th><th className="p-3">Subject</th><th className="p-3">Systems</th><th className="p-3">Opened</th><th className="p-3">State</th>
            </tr></thead>
            <tbody>
              {d.tickets.map((t) => (
                <tr key={t.number} onClick={() => setDetail(t)} className="border-b border-border/50 hover:bg-secondary/40 cursor-pointer" data-testid={`wf-row-${t.number}`}>
                  <td className="p-3"><span className="font-mono text-xs font-semibold px-1.5 py-0.5 rounded" style={{ background: `hsl(${PFX[t.number.slice(0, 3)] || "220 10% 55%"} / 0.15)`, color: `hsl(${PFX[t.number.slice(0, 3)] || "220 10% 55%"})` }}>{t.number}</span></td>
                  <td className="p-3 text-xs">{t.type}</td>
                  <td className="p-3 text-xs">{t.person_name || <span className="text-muted-foreground">{t.reason || "—"}</span>}</td>
                  <td className="p-3"><div className="flex flex-wrap gap-1">{(t.systems_touched || []).map((x) => <Sys key={x} s={x} />)}</div></td>
                  <td className="p-3 text-xs whitespace-nowrap">{fmtDT(t.opened_at)}</td>
                  <td className="p-3"><span className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded-full ${t.state === "Closed" ? "bg-low/15 text-low" : "bg-amber/15 text-amber"}`}>{t.state}</span></td>
                </tr>
              ))}
              {d.tickets.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-muted-foreground">No workflows match these filters.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="p-2.5 text-[11px] text-muted-foreground border-t border-border">Showing {d.tickets.length} of {d.total} matching · {d.all_total} total workflows</div>
      </div>

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-lg" data-testid="wf-detail">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <span className="font-mono text-sm font-bold px-2 py-0.5 rounded" style={{ background: `hsl(${PFX[detail.number.slice(0, 3)] || "220 10% 55%"} / 0.15)`, color: `hsl(${PFX[detail.number.slice(0, 3)] || "220 10% 55%"})` }}>{detail.number}</span>
                  {detail.type}
                </DialogTitle>
              </DialogHeader>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm mb-3">
                <div><span className="text-muted-foreground text-xs">Subject</span><div>{detail.person_name || "—"}</div></div>
                <div><span className="text-muted-foreground text-xs">State</span><div>{detail.state}{detail.auto_closed ? " · auto-closed" : ""}</div></div>
                <div><span className="text-muted-foreground text-xs">Opened</span><div>{fmtDT(detail.opened_at)}</div></div>
                <div><span className="text-muted-foreground text-xs">Fulfilment</span><div>{detail.duration_sec}s</div></div>
                <div className="col-span-2"><span className="text-muted-foreground text-xs">Reason</span><div>{detail.reason || "—"}</div></div>
              </div>
              <div className="border-t border-border pt-3">
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Cross-system orchestration</div>
                <div className="space-y-2" data-testid="wf-stages">
                  {(detail.stages || []).map((st, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <ArrowRight className="w-3.5 h-3.5 mt-0.5 shrink-0" style={{ color: `hsl(${SYS_COLOR[st.system] || "220 10% 55%"})` }} />
                      <div><Sys s={st.system} /> <span className="ml-1">{st.note}</span><div className="text-[10px] text-muted-foreground">{fmtDT(st.at)}</div></div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
