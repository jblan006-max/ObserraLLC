import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "@/lib/api";
import { Loader2, Send, X } from "lucide-react";

// Obserrian Advisor for SAP UAC — floating eye that answers governed, grounded questions over
// the LIVE SAP access model (POST /api/sap/advisor). Same brand/UX as the Obserra advisor.
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
      const { data } = await api.post("/sap/advisor", { question: text });
      setMsgs((m) => [...m, { role: "ai", text: data.answer, model: data.model, citations: data.citations }]);
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
    "Are any terminated workers still holding active SAP access?",
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
                <p className="text-xs text-muted-foreground">Ask about SoD conflicts, privileged access, joiners/leavers, HR data conflicts or any identity's risk — grounded in your live access model.</p>
                {SUGGESTED.map((s) => (
                  <button key={s} data-testid="sap-advisor-suggested" onClick={() => ask(s)}
                    className="block w-full text-left text-xs px-3 py-2 rounded-lg border border-border hover:border-ai/50 hover:bg-ai/5 transition-colors">{s}</button>
                ))}
              </div>
            )}
            {msgs.map((m, i) => (
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
