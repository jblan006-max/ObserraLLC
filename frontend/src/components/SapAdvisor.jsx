import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Send, X, Zap, CheckCircle2, ArrowRight } from "lucide-react";

// Obserrian Advisor for SAP UAC — floating eye that answers governed, grounded questions over
// the LIVE SAP access model (POST /api/sap/advisor). Same brand/UX as the Obserra advisor.
const ACTION_RE = /\b(deactivate|disable|revoke|offboard|suspend|pause|hold|resume|unsuspend|reinstate|activate|reactivate|enable|restore|provision|create|onboard)\b/i;
const QUESTION_RE = /^(who|what|which|how|why|when|where|are|is|do|does|did|can|could|would|should|list|show|summar|explain|tell|give|report)\b/i;
const V = { activate: "activated", deactivate: "deactivated", suspend: "suspended", resume: "resumed" };

function PlanCard({ plan }) {
  const [state, setState] = useState("proposed"); // proposed | running | done
  const [result, setResult] = useState(null);
  const run = async () => {
    setState("running");
    try {
      const { data } = await api.post("/sap/activation/set", {
        person_refs: plan.person_refs, action: plan.action,
        reason: "Advisor-initiated automated workflow", work_note: "Executed by the Obserrian Advisor", notify: false,
      });
      const nums = (data.tickets || []).map((t) => t.number).slice(0, 6).join(", ");
      setResult({ changed: data.changed, nums });
      setState("done");
      toast.success(`${data.changed} user(s) ${V[plan.action] || "updated"}`, { description: nums ? `ServiceNow ${nums} auto-closed` : undefined });
      window.dispatchEvent(new Event("sap-data-changed"));
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Workflow failed");
      setState("proposed");
    }
  };
  return (
    <div data-testid="sap-advisor-plan" className="rounded-2xl border border-amber/40 bg-amber/5 px-3.5 py-3 text-[13px] max-w-[92%]">
      <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-amber mb-1"><Zap className="w-3 h-3" /> Automated workflow · {plan.action}</div>
      {state !== "done" && (
        <>
          <p className="leading-relaxed">{plan.message}</p>
          {plan.affected?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {plan.affected.slice(0, 8).map((a) => (
                <span key={a.ref} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-background/60 border border-border">{a.name} · {a.status}</span>
              ))}
              {plan.count > 8 && <span className="text-[10px] font-mono text-muted-foreground">+{plan.count - 8} more</span>}
            </div>
          )}
          <div className="mt-2.5">
            <button data-testid="sap-advisor-plan-execute" disabled={state === "running"} onClick={run}
              className="flex items-center gap-1.5 text-[12px] font-head font-bold px-3 py-1.5 rounded-full bg-amber text-[#050810] disabled:opacity-50 active:scale-95 transition-transform">
              {state === "running" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ArrowRight className="w-3.5 h-3.5" />}
              {state === "running" ? "Running workflow…" : `Execute — ${plan.action} ${plan.count}`}
            </button>
          </div>
        </>
      )}
      {state === "done" && result && (
        <div className="flex items-start gap-2 text-low">
          <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
          <div><div className="font-medium">{result.changed} user(s) {V[plan.action]}</div>{result.nums && <div className="text-[10px] font-mono text-muted-foreground">ServiceNow {result.nums} · auto-closed across HR → SAP → AD/Entra</div>}</div>
        </div>
      )}
    </div>
  );
}

export function SapAdvisor() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const endRef = useRef(null);

  const ask = useCallback(async (question) => {
    const text = (question || "").trim();
    if (!text || busy) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setQ("");
    setBusy(true);
    try {
      const isCmd = !QUESTION_RE.test(text) && ACTION_RE.test(text);
      if (isCmd) {
        const { data } = await api.post("/sap/advisor/plan", { instruction: text });
        if (data.actionable) setMsgs((m) => [...m, { role: "plan", plan: data }]);
        else setMsgs((m) => [...m, { role: "ai", text: data.message, model: "advisor · action" }]);
      } else {
        const { data } = await api.post("/sap/advisor", { question: text });
        setMsgs((m) => [...m, { role: "ai", text: data.answer, model: data.model, citations: data.citations }]);
      }
    } catch (e) {
      setMsgs((m) => [...m, { role: "ai", text: "The advisor is unavailable right now. Please try again.", model: "error" }]);
    }
    setBusy(false);
  }, [busy]);

  useEffect(() => {
    const h = (e) => { setOpen(true); if (e.detail) ask(e.detail); };
    window.addEventListener("open-advisor", h);
    return () => window.removeEventListener("open-advisor", h);
  }, [ask]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, open]);

  const SUGGESTED = [
    "Which users have the highest SAP access risk and why?",
    "Summarize the critical SoD conflicts and who holds them.",
    "Deactivate all terminated workers still holding SAP access",
  ];

  return (
    <>
      {!open && (
        <button data-testid="sap-advisor-fab" onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full bg-[#0f1e3d] border border-ai/40 shadow-lg shadow-ai/20 flex items-center justify-center hover:scale-105 transition-transform">
          <span className="absolute inset-0 rounded-full animate-ping bg-ai/20" />
          <img src="/brand-mark.png" alt="Obserrian Advisor" className="w-7 h-7 object-contain relative" />
        </button>
      )}
      {open && (
        <div data-testid="sap-advisor-panel" className="fixed bottom-6 right-6 z-40 w-[92vw] max-w-md h-[70vh] max-h-[560px] bg-card border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden rise">
          <div className="flex items-center justify-between px-4 h-14 border-b border-border bg-[#0f1e3d]">
            <div className="flex items-center gap-2 min-w-0">
              <img src="/brand-mark.png" alt="" className="w-6 h-6 object-contain" />
              <div className="min-w-0">
                <div className="font-head font-bold text-sm text-white truncate">Obserrian Advisor</div>
                <div className="text-[10px] font-mono text-ai/80">SAP Access Intelligence · grounded</div>
              </div>
            </div>
            <button data-testid="sap-advisor-close" onClick={() => setOpen(false)} className="text-white/70 hover:text-white"><X className="w-5 h-5" /></button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {msgs.length === 0 && (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">Ask about SoD conflicts, privileged access, joiners/leavers or any identity's risk — or <span className="text-amber font-medium">tell me to act</span> (e.g. “deactivate all terminated workers”) and I'll run the automated ServiceNow → HR → SAP → AD/Entra workflow.</p>
                {SUGGESTED.map((s) => (
                  <button key={s} data-testid="sap-advisor-suggested" onClick={() => ask(s)}
                    className="block w-full text-left text-xs px-3 py-2 rounded-lg border border-border hover:border-ai/50 hover:bg-ai/5 transition-colors">{s}</button>
                ))}
              </div>
            )}
            {msgs.map((m, i) => (
              m.role === "plan" ? (
                <div key={i} className="flex justify-start"><PlanCard plan={m.plan} /></div>
              ) : (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed ${m.role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary/60 border border-border"}`}>
                  <p className="whitespace-pre-wrap">{m.text}</p>
                  {m.citations?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.citations.map((c, j) => <span key={j} className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-background/60">{c}</span>)}
                    </div>
                  )}
                </div>
              </div>
              )
            ))}
            {busy && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Analyzing the live access model…</div>}
            <div ref={endRef} />
          </div>
          <div className="p-3 border-t border-border">
            <div className="flex items-center gap-2 rounded-full border border-border bg-background/50 px-3 py-1.5">
              <input data-testid="sap-advisor-input" value={q} onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") ask(q); }}
                placeholder="Ask the Obserrian Advisor…" className="flex-1 bg-transparent text-sm outline-none" />
              <button data-testid="sap-advisor-send" disabled={busy || !q.trim()} onClick={() => ask(q)} className="text-ai disabled:opacity-40"><Send className="w-4 h-4" /></button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
