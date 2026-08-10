import { useState, useRef, useEffect } from "react";
import { X, Send, Loader2, Zap, Brain, Download, Cpu, ChevronDown, Check } from "lucide-react";
import { API, api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

const MARK = (cls = "w-6 h-6") => (
  <span className={`inline-flex items-center justify-center ${cls} align-middle shrink-0`}>
    <img src="/brand-mark.png" alt="Obserra" className="h-full w-full object-contain" />
  </span>
);

const AVATAR = (cls = "w-6 h-6") => (
  <span className={`inline-flex items-center justify-center ${cls} rounded-full shrink-0`} style={{ backgroundColor: "#0f1e3d" }}>
    <img src="/brand-mark.png" alt="Obserra" className="h-3/5 w-3/5 object-contain" />
  </span>
);

function parseMessage(text) {
  const lines = text.split("\n");
  const actions = [];
  const body = [];
  for (const line of lines) {
    const m = line.match(/^ACTION:\s*([a-z_]+)\s*—?\s*(.*)$/);
    if (m) actions.push({ id: m[1].trim(), label: m[2].trim() || m[1] });
    else body.push(line);
  }
  return { text: body.join("\n").trim(), actions };
}

function renderRefs(text) {
  const parts = text.split(/(\b(?:CR|AI|AII|REC|DEC)-\d{3}\b|RECOMMENDATION:)/g);
  return parts.map((p, i) => {
    if (/^(CR|AI|AII|REC|DEC)-\d{3}$/.test(p)) return <span key={i} className="font-mono text-ai bg-ai/10 px-1 rounded-sm">{p}</span>;
    if (p === "RECOMMENDATION:") return <span key={i} className="font-mono text-ai font-semibold">{p}</span>;
    return <span key={i}>{p}</span>;
  });
}

const WORKER_CHIPS = [
  { id: "entra_enforce_pim", label: "Enforce PIM" },
  { id: "casb_quarantine_shadow", label: "Quarantine shadow AI" },
  { id: "tenable_patch_critical", label: "Patch critical CVEs" },
];

export function AIAdvisor() {
  const { mode, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [modelTag, setModelTag] = useState("");
  const [models, setModels] = useState([]);
  const [modelDefault, setModelDefault] = useState(null);
  const [modelMenu, setModelMenu] = useState(false);
  const [working, setWorking] = useState(null);
  const [deep, setDeep] = useState(false);
  const [spend, setSpend] = useState(null);
  const [budgetInput, setBudgetInput] = useState("");
  const [savingBudget, setSavingBudget] = useState(false);
  const [drillUser, setDrillUser] = useState(null);
  const [drillPrompts, setDrillPrompts] = useState([]);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [promptThemes, setPromptThemes] = useState(null);
  const [auditOpen, setAuditOpen] = useState(null);
  const scrollRef = useRef(null);
  const sendRef = useRef(null);
  const hintKey = `obserra-advisor-hint-${user?.id || user?.email || "anon"}`;
  const [showHint, setShowHint] = useState(false);
  const [bubbleOn, setBubbleOn] = useState(true);
  const [nudgeIdx, setNudgeIdx] = useState(0);
  const [topRisk, setTopRisk] = useState(null);

  useEffect(() => {
    if (typeof window !== "undefined" && !localStorage.getItem(hintKey)) setShowHint(true);
  }, [hintKey]);

  useEffect(() => {
    api.get("/overview").then((r) => setTopRisk((r.data?.top_risks || [])[0] || null)).catch(() => {});
    try { if (sessionStorage.getItem("advisor-bubble-off")) setBubbleOn(false); } catch {}
  }, []);

  useEffect(() => {
    if (open) return;
    const t = setInterval(() => setNudgeIdx((i) => (i + 1) % 4), 7000);
    return () => clearInterval(t);
  }, [open]);

  const dismissHint = () => {
    setShowHint(false);
    try { localStorage.setItem(hintKey, "1"); } catch {}
  };

  const hideBubble = () => {
    setBubbleOn(false);
    dismissHint();
    try { sessionStorage.setItem("advisor-bubble-off", "1"); } catch {}
  };

  const openFromHint = () => {
    if (showHint) api.post("/advisor/hint-open").catch(() => {});
    setOpen(true);
    dismissHint();
  };

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }); }, [messages, streaming]);

  useEffect(() => {
    if (open && isAdmin) {
      api.get("/advisor/usage").then((r) => setSpend(r.data)).catch(() => {});
      api.get("/advisor/prompts/insights").then((r) => setPromptThemes(r.data)).catch(() => {});
    }
  }, [open, isAdmin]);

  useEffect(() => {
    if (open) api.get("/advisor/models").then((r) => { setModels(r.data.models || []); setModelDefault(r.data.default || null); }).catch(() => {});
  }, [open]);

  useEffect(() => {
    const h = (e) => { setOpen(true); if (e.detail) sendRef.current?.(e.detail); };
    window.addEventListener("open-advisor", h);
    return () => window.removeEventListener("open-advisor", h);
  }, []);

  const execute = async (action_id, label) => {
    setWorking(action_id);
    try {
      const { data } = await api.post("/actions/run", { action_id });
      toast.success(data.message || "Executed", { duration: 5000 });
      setMessages((m) => [...m, { role: "ai", text: `✓ Executed: ${label || action_id}. ${data.message || ""}` }]);
    } catch { toast.error("Execution failed"); }
    setWorking(null);
  };

  const send = async (preset) => {
    const q = (preset || input).trim();
    if (!q || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }, { role: "ai", text: "" }]);
    setStreaming(true);
    try {
      const res = await fetch(`${API}/advisor/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
        body: JSON.stringify({ message: q, mode, deep, model: modelDefault }),
      });
      if (res.status === 429) {
        const j = await res.json().catch(() => ({}));
        setMessages((m) => { const c = [...m]; c[c.length - 1] = { role: "ai", text: j.detail || "Advisor paused: monthly spend cap reached." }; return c; });
        setStreaming(false);
        if (isAdmin) api.get("/advisor/usage").then((r) => setSpend(r.data)).catch(() => {});
        return;
      }
      const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = "";
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n\n"); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const p = JSON.parse(line.slice(6));
          if (p.delta) setMessages((m) => { const c = [...m]; c[c.length - 1] = { ...c[c.length - 1], role: "ai", text: c[c.length - 1].text + p.delta }; return c; });
          if (p.model) setModelTag(p.model);
          if (p.usage) setMessages((m) => { const c = [...m]; c[c.length - 1] = { ...c[c.length - 1], usage: p.usage }; return c; });
        }
      }
      if (isAdmin) api.get("/advisor/usage").then((r) => setSpend(r.data)).catch(() => {});
    } catch { setMessages((m) => { const c = [...m]; c[c.length - 1] = { role: "ai", text: "Advisor unavailable right now." }; return c; }); }
    setStreaming(false);
  };
  sendRef.current = send;

  const selectModel = async (id) => {
    setModelDefault(id); setModelMenu(false);
    try {
      await api.put("/advisor/model", { model: id });
      toast.success(id ? `Connected · ${models.find((m) => m.id === id)?.label || id}` : "Advisor set to Auto routing");
    } catch { toast.error("Could not connect model"); }
  };

  const saveBudget = async () => {
    const v = parseFloat(budgetInput);
    if (isNaN(v) || v < 0) { toast.error("Enter a valid monthly budget"); return; }
    setSavingBudget(true);
    try {
      await api.put("/advisor/budget", { monthly_usd: v });
      const { data } = await api.get("/advisor/usage");
      setSpend(data); setBudgetInput("");
      toast.success(`Monthly advisor budget set to $${v.toFixed(2)}`);
    } catch { toast.error("Could not save budget"); }
    setSavingBudget(false);
  };

  const toggleAutoPause = async () => {
    if (!spend) return;
    setSavingBudget(true);
    try {
      await api.put("/advisor/budget", { monthly_usd: spend.budget_usd || 0, auto_pause: !spend.auto_pause });
      const { data } = await api.get("/advisor/usage");
      setSpend(data);
      toast.success(`Auto-pause ${data.auto_pause ? "on" : "off"}`);
    } catch { toast.error("Could not update auto-pause"); }
    setSavingBudget(false);
  };

  const saveThreshold = async (t) => {
    if (!spend) return;
    setSavingBudget(true);
    try {
      await api.put("/advisor/budget", { monthly_usd: spend.budget_usd || 0, alert_threshold: t });
      const { data } = await api.get("/advisor/usage");
      setSpend(data);
      toast.success(`Alert threshold set to ${t}%`);
    } catch { toast.error("Could not update threshold"); }
    setSavingBudget(false);
  };

  const exportUsageCsv = async (scope = "month") => {
    try {
      const { data } = await api.get("/advisor/usage/export", { params: { scope }, responseType: "blob" });
      const url = URL.createObjectURL(new Blob([data], { type: "text/csv" }));
      const a = document.createElement("a"); a.href = url; a.download = scope === "all" ? "advisor-spend-all.csv" : "advisor-spend.csv"; a.click(); URL.revokeObjectURL(url);
      toast.success("Spend CSV downloaded");
    } catch { toast.error("Export failed"); }
  };

  const openDrill = async (u) => {
    if (drillUser === u) { setDrillUser(null); return; }
    setDrillUser(u); setDrillPrompts([]);
    try { const { data } = await api.get("/advisor/usage/prompts", { params: { member: u } }); setDrillPrompts(data); }
    catch { toast.error("Could not load prompts"); }
  };

  const searchPrompts = async (q) => {
    if (!q || q.trim().length < 2) { setSearchResults(null); return; }
    try { const { data } = await api.get("/advisor/prompts/search", { params: { q } }); setSearchResults(data); }
    catch { toast.error("Search failed"); }
  };

  const suggestions = mode === "executive"
    ? ["Summarize our top enterprise risks for the board", "What is driving the AI Governance score?"]
    : ["Which risks need remediation this week?", "Detail the shadow AI exposure and fix it"];

  const nudges = [
    "Need a hand? Ask me anything about your risk posture.",
    "I can summarize your top board risks in one tap.",
    topRisk ? `Heads up — ${topRisk.ref} “${topRisk.title}” is your highest residual risk. Want me to break it down?` : "I can execute remediations via your integrations.",
    "Want to know what's driving your AI Governance score?",
  ];

  return (
    <>
      {!open && (
        <div data-testid="ai-advisor-launcher" className="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-2.5">
          {bubbleOn && (
            <div data-testid="advisor-hint" onClick={openFromHint}
              className="relative w-[min(15rem,calc(100vw-2rem))] rounded-2xl bg-popover border border-ai/30 shadow-xl p-3.5 text-xs leading-relaxed text-foreground cursor-pointer rise">
              <button data-testid="advisor-hint-dismiss" onClick={(e) => { e.stopPropagation(); hideBubble(); }}
                className="absolute top-1.5 right-1.5 p-0.5 rounded hover:bg-secondary text-muted-foreground"><X className="w-3.5 h-3.5" /></button>
              <div className="flex items-center gap-1.5 font-head font-bold text-ai mb-1 pr-4">{MARK("w-4 h-4")} Obserrian Advisor</div>
              <div className="text-foreground/90">{nudges[nudgeIdx % nudges.length]}</div>
              <div className="absolute -bottom-1.5 right-7 w-3 h-3 rotate-45 bg-popover border-r border-b border-ai/30" />
            </div>
          )}
          <button data-testid="advisor-toggle" onClick={openFromHint} title="Obserrian Advisor"
            style={{ backgroundColor: "#0f1e3d" }}
            className="relative flex items-center justify-center w-14 h-14 rounded-full shadow-xl ring-1 ring-ai/30 hover:-translate-y-0.5 transition-transform duration-200">
            <span className="absolute inset-0 rounded-full ring-2 ring-ai/50 animate-ping pointer-events-none" />
            <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-ai animate-pulse ring-2 ring-popover" />
            {MARK("w-8 h-8")}
          </button>
        </div>
      )}

      {open && (
        <div data-testid="advisor-panel" className="fixed inset-y-0 right-0 z-50 w-full sm:w-[440px] bg-popover border-l border-ai/30 flex flex-col rise">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <div className="flex items-center gap-2.5">
              {AVATAR("w-8 h-8")}
              <div>
                <div className="font-head font-bold text-ai">Obserrian Advisor</div>
                <div className="text-[10px] font-mono text-muted-foreground">{mode} · helper + worker</div>
                <div className="relative mt-1">
                  <button data-testid="advisor-connect-model" onClick={() => setModelMenu((v) => !v)}
                    className="flex items-center gap-1.5 text-[10px] font-mono px-2 py-0.5 rounded-full border border-ai/30 bg-ai/10 text-ai hover:bg-ai/20 transition-colors">
                    <Cpu className="w-3 h-3" />
                    {modelDefault ? (models.find((m) => m.id === modelDefault)?.label || modelDefault) : `Auto · ${mode}`}
                    <ChevronDown className="w-3 h-3" />
                  </button>
                  {modelMenu && (
                    <div data-testid="advisor-model-menu" className="absolute left-0 top-7 z-50 w-64 max-h-80 overflow-y-auto rounded-lg bg-popover border border-border shadow-xl p-1.5">
                      <div className="px-2.5 pt-1 pb-1.5 text-[9px] font-mono uppercase tracking-wider text-muted-foreground">Connect the advisor to a model</div>
                      <button data-testid="advisor-model-auto" onClick={() => selectModel(null)}
                        className={`w-full flex items-center justify-between gap-2 text-left px-2.5 py-1.5 rounded-md text-xs hover:bg-secondary/60 transition-colors ${!modelDefault ? "text-ai" : "text-foreground"}`}>
                        <span><span className="font-medium">Auto</span> <span className="text-muted-foreground">· routes by mode</span></span>
                        {!modelDefault && <Check className="w-3.5 h-3.5 shrink-0" />}
                      </button>
                      {[["openai", "OpenAI"], ["anthropic", "Anthropic"], ["gemini", "Google"]].map(([prov, label]) => (
                        <div key={prov}>
                          <div className="px-2.5 pt-2 pb-1 text-[9px] font-mono uppercase tracking-wider text-muted-foreground/70">{label}</div>
                          {models.filter((m) => m.provider === prov).map((m) => (
                            <button key={m.id} data-testid={`advisor-model-${m.id}`} onClick={() => selectModel(m.id)}
                              className={`w-full flex items-center justify-between gap-2 text-left px-2.5 py-1.5 rounded-md text-xs hover:bg-secondary/60 transition-colors ${modelDefault === m.id ? "text-ai" : "text-foreground"}`}>
                              <span className="min-w-0"><span className="font-medium">{m.label}</span><span className="block text-[10px] text-muted-foreground truncate">{m.tier} · {m.note}</span></span>
                              {modelDefault === m.id && <Check className="w-3.5 h-3.5 shrink-0" />}
                            </button>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {isAdmin && spend && (
                  <div data-testid="advisor-spend" className="text-[10px] font-mono text-ai mt-0.5">
                    spend: ${spend.total_cost_usd?.toFixed(4)} · {spend.total_tokens?.toLocaleString()} tok · {spend.queries}q
                  </div>
                )}
                {isAdmin && spend?.hint_opens > 0 && (
                  <div data-testid="advisor-hint-stat" className="text-[10px] font-mono text-muted-foreground mt-0.5">
                    intro-hint opens: {spend.hint_opens} · {spend.hint_unique} exec{spend.hint_unique === 1 ? "" : "s"}
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <button data-testid="advisor-deep-toggle" onClick={() => setDeep((d) => !d)} title="Deep analysis mode"
                className={`flex items-center gap-1 text-[11px] font-head font-bold px-2.5 py-1.5 rounded-full border transition-colors ${deep ? "bg-ai text-background border-ai" : "bg-transparent text-muted-foreground border-border hover:text-ai"}`}>
                <Brain className="w-3.5 h-3.5" /> Deep
              </button>
              <button data-testid="advisor-close" onClick={() => setOpen(false)} className="p-1.5 rounded-md hover:bg-secondary"><X className="w-4 h-4" /></button>
            </div>
          </div>

          {isAdmin && spend && (
            <div data-testid="advisor-budget" className="px-5 py-2.5 border-b border-border space-y-1.5">
              <div className="flex items-center justify-between text-[10px] font-mono">
                <span className="uppercase tracking-wider text-muted-foreground">Monthly budget</span>
                <span className={spend.budget_status === "over" ? "text-crit" : spend.budget_status === "warning" ? "text-med" : "text-ai"}>
                  {spend.budget_usd > 0 ? `$${spend.month_cost_usd?.toFixed(2)} / $${spend.budget_usd?.toFixed(2)} · ${spend.budget_pct}%` : "no cap set"}
                </span>
              </div>
              {spend.budget_usd > 0 && (
                <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                  <div className={`h-full ${spend.budget_status === "over" ? "bg-crit" : spend.budget_status === "warning" ? "bg-med" : "bg-ai"}`} style={{ width: `${Math.min(spend.budget_pct, 100)}%` }} />
                </div>
              )}
              {spend.budget_status === "over" && <div className="text-[10px] text-crit">Over the monthly cap — advisor spend has exceeded budget.</div>}
              {spend.budget_status === "warning" && <div className="text-[10px] text-med">Nearing the monthly cap.</div>}
              {spend.paused && <div data-testid="advisor-paused-banner" className="text-[10px] text-crit font-bold">Advisor auto-paused for this month — cap reached.</div>}
              <div className="flex items-center justify-between pt-0.5">
                <span className="text-[10px] font-mono text-muted-foreground">Auto-pause at cap</span>
                <button data-testid="advisor-autopause-toggle" disabled={savingBudget} onClick={toggleAutoPause}
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full border transition-colors disabled:opacity-50 ${spend.auto_pause ? "bg-crit/15 text-crit border-crit/30" : "bg-secondary/60 text-muted-foreground border-border"}`}>
                  {spend.auto_pause ? "On" : "Off"}
                </button>
              </div>
              <div className="flex items-center gap-1.5 pt-0.5">
                <input data-testid="advisor-budget-input" type="number" min="0" step="1"
                  placeholder={spend.budget_usd > 0 ? `current $${spend.budget_usd}` : "set $ monthly cap"}
                  value={budgetInput} onChange={(e) => setBudgetInput(e.target.value)}
                  className="flex-1 bg-secondary/60 rounded-md px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-ai" />
                <button data-testid="advisor-budget-save" disabled={savingBudget} onClick={saveBudget}
                  className="text-[11px] px-3 py-1 rounded-md bg-ai text-background font-bold disabled:opacity-50">
                  {savingBudget ? "…" : "Set"}
                </button>
              </div>
              <div className="flex items-center justify-between pt-0.5">
                <span className="text-[10px] font-mono text-muted-foreground">Alert at</span>
                <div className="flex items-center gap-1">
                  {[75, 80, 90].map((t) => (
                    <button key={t} data-testid={`advisor-threshold-${t}`} disabled={savingBudget} onClick={() => saveThreshold(t)}
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border transition-colors disabled:opacity-50 ${Math.round(spend.alert_threshold || 80) === t ? "bg-ai/15 text-ai border-ai/30" : "bg-secondary/60 text-muted-foreground border-border"}`}>
                      {t}%
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <button data-testid="advisor-export-csv" onClick={() => exportUsageCsv("month")}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 text-[11px] px-3 py-1.5 rounded-md bg-secondary/60 border border-border hover:bg-secondary text-muted-foreground transition-colors">
                  <Download className="w-3 h-3" /> This month
                </button>
                <button data-testid="advisor-export-csv-all" onClick={() => exportUsageCsv("all")}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 text-[11px] px-3 py-1.5 rounded-md bg-secondary/60 border border-border hover:bg-secondary text-muted-foreground transition-colors">
                  <Download className="w-3 h-3" /> All months
                </button>
              </div>
              {promptThemes?.themes?.length > 0 && (
                <div data-testid="advisor-themes" className="pt-1">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1">Top prompt themes</div>
                  <div className="flex flex-wrap gap-1">
                    {promptThemes.themes.map((t) => (
                      <button key={t.term} data-testid={`theme-${t.term}`}
                        onClick={() => { setSearchQ(t.term); searchPrompts(t.term); }}
                        className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-ai/10 text-ai border border-ai/20 hover:bg-ai/20 transition-colors">
                        {t.term} · {t.count}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="pt-1">
                <input data-testid="advisor-prompt-search" placeholder="Search all advisor prompts…"
                  value={searchQ}
                  onChange={(e) => setSearchQ(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") searchPrompts(searchQ); }}
                  className="w-full bg-secondary/60 rounded-md px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-ai" />
                {searchResults && (
                  <div data-testid="advisor-search-results" className="mt-1 space-y-1 max-h-56 overflow-y-auto">
                    {searchResults.length === 0 ? (
                      <div className="text-[10px] text-muted-foreground">No matching prompts.</div>
                    ) : searchResults.map((r, i) => (
                      <div key={i} className="text-[10px] border-l border-ai/30 pl-2">
                        <button data-testid={`audit-row-${i}`} onClick={() => setAuditOpen(auditOpen === i ? null : i)}
                          className="w-full text-left hover:bg-secondary/40 rounded px-1 -ml-1 transition-colors">
                          <div className="text-foreground/90 truncate">{r.prompt}</div>
                          <div className="font-mono text-muted-foreground">{r.user} · {new Date(r.ts).toLocaleDateString()}{r.cost_usd != null ? ` · $${r.cost_usd.toFixed(4)}` : ""}</div>
                        </button>
                        {auditOpen === i && (
                          <div data-testid={`audit-answer-${i}`} className="mt-1 mb-1 p-1.5 rounded bg-secondary/50 text-foreground/80 whitespace-pre-wrap leading-relaxed">
                            {r.response ? r.response : <span className="text-muted-foreground">No stored answer for this prompt.</span>}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {spend.trend?.length > 0 && (() => {
                const max = Math.max(...spend.trend.map((t) => t.cost_usd), 0.0001);
                return (
                  <div data-testid="advisor-trend" className="pt-1">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1">6-month spend</div>
                    <div className="flex items-end gap-1 h-9">
                      {spend.trend.map((t) => (
                        <div key={t.month} className="flex-1 flex flex-col items-center gap-0.5" title={`${t.month}: $${t.cost_usd.toFixed(2)}`}>
                          <div className="w-full bg-ai/60 rounded-sm transition-[height] duration-300" style={{ height: `${Math.max(2, (t.cost_usd / max) * 26)}px` }} />
                          <span className="text-[8px] font-mono text-muted-foreground">{t.month.slice(5)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}
              {spend.by_user?.length > 0 && (
                <div data-testid="advisor-by-user" className="pt-1">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1">This month by teammate</div>
                  <div className="space-y-0.5">
                    {spend.by_user.slice(0, 4).map((u) => (
                      <div key={u.user}>
                        <button data-testid={`by-user-${u.user}`} onClick={() => openDrill(u.user)}
                          className={`w-full flex items-center justify-between text-[10px] font-mono px-1 py-0.5 rounded transition-colors ${drillUser === u.user ? "bg-ai/10" : "hover:bg-secondary/60"}`}>
                          <span className="truncate text-muted-foreground max-w-[58%]">{u.user}</span>
                          <span className="text-ai">${u.cost_usd.toFixed(4)} · {u.queries}q</span>
                        </button>
                        {drillUser === u.user && (
                          <div data-testid={`drill-${u.user}`} className="mt-1 mb-1.5 pl-2 border-l border-ai/30 space-y-1">
                            {drillPrompts.length === 0 ? (
                              <div className="text-[10px] text-muted-foreground">Loading recent prompts…</div>
                            ) : drillPrompts.map((p, i) => (
                              <div key={i} className="text-[10px]">
                                <div className="text-foreground/90 truncate">{p.prompt}</div>
                                <div className="font-mono text-muted-foreground">{new Date(p.ts).toLocaleDateString()} · ${p.cost_usd.toFixed(4)} · {p.tokens} tok</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="px-5 py-2.5 border-b border-border flex flex-wrap gap-1.5">
            {WORKER_CHIPS.map((c) => (
              <button key={c.id} data-testid={`worker-${c.id}`} disabled={!!working} onClick={() => execute(c.id, c.label)}
                className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-full bg-primary/10 border border-primary/30 hover:bg-primary/20 transition-colors disabled:opacity-50">
                {working === c.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3 text-primary" />} {c.label}
              </button>
            ))}
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">I cite your evidence, separate fact vs estimate, and can <span className="text-ai">execute remediation</span> via your integrations.</p>
                {suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)} className="block w-full text-left text-xs px-3 py-2 rounded-md border border-border hover:border-ai/50 hover:bg-ai/5 transition-colors">{s}</button>
                ))}
              </div>
            )}
            {messages.map((m, i) => {
              const parsed = m.role === "ai" ? parseMessage(m.text || "") : { text: m.text, actions: [] };
              return (
                <div key={i} className={m.role === "user" ? "text-right" : "flex gap-2"}>
                  {m.role === "ai" && AVATAR("w-6 h-6")}
                  <div className={`inline-block max-w-[88%] text-sm leading-relaxed rounded-lg px-3.5 py-2.5 whitespace-pre-wrap ${m.role === "user" ? "bg-primary text-primary-foreground" : "bg-card ai-border text-foreground"}`}>
                    {m.role === "ai" ? renderRefs(parsed.text) : m.text}
                    {m.role === "ai" && streaming && i === messages.length - 1 && <Loader2 className="inline w-3 h-3 ml-1 animate-spin text-ai" />}
                    {m.role === "ai" && m.usage && isAdmin && (
                      <div data-testid="advisor-msg-cost" className="mt-1.5 text-[10px] font-mono text-muted-foreground">~{m.usage.total_tokens?.toLocaleString()} tok · ${m.usage.cost_usd?.toFixed(4)}</div>
                    )}
                    {parsed.actions.map((a) => (
                      <button key={a.id} data-testid={`exec-${a.id}`} disabled={!!working} onClick={() => execute(a.id, a.label)}
                        className="mt-2 flex items-center gap-1.5 text-xs font-head font-bold px-3 py-1.5 rounded-md bg-ai text-background hover:opacity-90 transition-opacity disabled:opacity-50">
                        {working === a.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />} Execute: {a.label}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="p-4 border-t border-border">
            <div className="flex items-end gap-2">
              <textarea data-testid="advisor-input" value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                rows={1} placeholder="Ask or command the advisor…"
                className="flex-1 resize-none bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ai" />
              <button data-testid="advisor-send" onClick={() => send()} disabled={streaming} className="p-2.5 rounded-md bg-ai text-background disabled:opacity-40 hover:opacity-90 transition-opacity">
                {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
