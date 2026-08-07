import { useState, useRef, useEffect } from "react";
import { X, Send, Loader2, Zap, Brain } from "lucide-react";
import { API, api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

const AVATAR = (cls = "w-6 h-6") => (
  <span className={`inline-flex ${cls} rounded-full overflow-hidden bg-background align-middle shrink-0`}>
    <img src="/logo.png" alt="Obserra" className="h-full w-auto max-w-none object-cover" style={{ objectPosition: "left center" }} />
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
  const [working, setWorking] = useState(null);
  const [deep, setDeep] = useState(false);
  const [spend, setSpend] = useState(null);
  const [budgetInput, setBudgetInput] = useState("");
  const [savingBudget, setSavingBudget] = useState(false);
  const scrollRef = useRef(null);
  const sendRef = useRef(null);

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }); }, [messages, streaming]);

  useEffect(() => { if (open && isAdmin) api.get("/advisor/usage").then((r) => setSpend(r.data)).catch(() => {}); }, [open, isAdmin]);

  useEffect(() => {
    if (!sessionStorage.getItem("advisor-opened")) { setOpen(true); sessionStorage.setItem("advisor-opened", "1"); }
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
        body: JSON.stringify({ message: q, mode, deep }),
      });
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

  const suggestions = mode === "executive"
    ? ["Summarize our top enterprise risks for the board", "What is driving the AI Governance score?"]
    : ["Which risks need remediation this week?", "Detail the shadow AI exposure and fix it"];

  return (
    <>
      <button data-testid="advisor-toggle" onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 pl-2 pr-4 py-2 rounded-full bg-ai text-background font-head font-bold text-sm shadow-lg hover:-translate-y-0.5 transition-transform duration-200">
        {AVATAR("w-7 h-7")} Advisor
      </button>

      {open && (
        <div data-testid="advisor-panel" className="fixed inset-y-0 right-0 z-50 w-full sm:w-[440px] bg-popover border-l border-ai/30 flex flex-col rise">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <div className="flex items-center gap-2.5">
              {AVATAR("w-8 h-8")}
              <div>
                <div className="font-head font-bold text-ai">Obserra Advisor</div>
                <div className="text-[10px] font-mono text-muted-foreground">{mode} · helper + worker · {modelTag || "claude-opus-4-8"}</div>
                {isAdmin && spend && (
                  <div data-testid="advisor-spend" className="text-[10px] font-mono text-ai mt-0.5">
                    spend: ${spend.total_cost_usd?.toFixed(4)} · {spend.total_tokens?.toLocaleString()} tok · {spend.queries}q
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
