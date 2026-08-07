import { useState, useRef, useEffect } from "react";
import { Sparkle, X, Send, Loader2 } from "lucide-react";
import { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

function renderMarkdownish(text) {
  // Highlight refs like CR-001, AI-002, REC-001 and RECOMMENDATION prefix
  const parts = text.split(/(\b(?:CR|AI|AII|REC|DEC)-\d{3}\b|RECOMMENDATION:)/g);
  return parts.map((p, i) => {
    if (/^(CR|AI|AII|REC|DEC)-\d{3}$/.test(p))
      return <span key={i} className="font-mono text-ai bg-ai/10 px-1 rounded-sm">{p}</span>;
    if (p === "RECOMMENDATION:")
      return <span key={i} className="font-mono text-ai font-semibold">{p}</span>;
    return <span key={i}>{p}</span>;
  });
}

export function AIAdvisor() {
  const { mode } = useAuth();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [modelTag, setModelTag] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming]);

  const send = async () => {
    if (!input.trim() || streaming) return;
    const q = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }, { role: "ai", text: "" }]);
    setStreaming(true);
    try {
      const res = await fetch(`${API}/advisor/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message: q, mode }),
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n\n");
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = JSON.parse(line.slice(6));
          if (payload.delta) {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { role: "ai", text: copy[copy.length - 1].text + payload.delta };
              return copy;
            });
          }
          if (payload.model) setModelTag(payload.model);
        }
      }
    } catch (e) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "ai", text: "Advisor unavailable right now." };
        return copy;
      });
    }
    setStreaming(false);
  };

  const suggestions = mode === "executive"
    ? ["Summarize our top enterprise risks for the board", "What is driving the AI Governance score?"]
    : ["Which risks need remediation this week?", "Detail the shadow AI exposure and next steps"];

  return (
    <>
      <button data-testid="advisor-toggle" onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-5 py-3 rounded-full bg-ai text-background font-head font-bold text-sm shadow-lg hover:-translate-y-0.5 transition-transform duration-200">
        <Sparkle className="w-4 h-4" /> Advisor
      </button>

      {open && (
        <div data-testid="advisor-panel" className="fixed inset-y-0 right-0 z-50 w-full sm:w-[440px] bg-popover border-l border-ai/30 flex flex-col rise">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <div>
              <div className="flex items-center gap-2 font-head font-bold text-ai"><Sparkle className="w-4 h-4" /> Evidence-Grounded Advisor</div>
              <div className="text-[10px] font-mono text-muted-foreground mt-0.5">
                {mode} mode · {modelTag || "claude-sonnet-5"}
              </div>
            </div>
            <button data-testid="advisor-close" onClick={() => setOpen(false)} className="p-1.5 rounded-md hover:bg-secondary">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">Ask about your risk posture or AI governance. Every answer cites your evidence with confidence and data-type separation.</p>
                {suggestions.map((s) => (
                  <button key={s} onClick={() => setInput(s)}
                    className="block w-full text-left text-xs px-3 py-2 rounded-md border border-border hover:border-ai/50 hover:bg-ai/5 transition-colors duration-200">
                    {s}
                  </button>
                ))}
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-right" : ""}>
                <div className={`inline-block max-w-[92%] text-sm leading-relaxed rounded-lg px-3.5 py-2.5 whitespace-pre-wrap ${
                  m.role === "user" ? "bg-primary text-primary-foreground" : "bg-card ai-border text-foreground"}`}>
                  {m.role === "ai" ? renderMarkdownish(m.text || "") : m.text}
                  {m.role === "ai" && streaming && i === messages.length - 1 && (
                    <Loader2 className="inline w-3 h-3 ml-1 animate-spin text-ai" />
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-border">
            <div className="flex items-end gap-2">
              <textarea data-testid="advisor-input" value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                rows={1} placeholder="Ask the advisor…"
                className="flex-1 resize-none bg-secondary/60 rounded-md px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ai" />
              <button data-testid="advisor-send" onClick={send} disabled={streaming}
                className="p-2.5 rounded-md bg-ai text-background disabled:opacity-40 hover:opacity-90 transition-opacity">
                {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
