import { useEffect, useState, useMemo } from "react";
import ReactFlow, { Background, Controls } from "reactflow";
import "reactflow/dist/style.css";
import { api } from "@/lib/api";
import { Network, Loader2, Sparkle, Send, X } from "lucide-react";
import { AIInsight } from "@/components/AIInsight";
import { AIFix } from "@/components/AIFix";
import { AIExplain } from "@/components/AIExplain";

const KG_ACCENT = "225 70% 60%";

const TYPE = {
  ai: { color: "190 90% 50%", x: 3 }, data: { color: "280 70% 60%", x: 5 },
  vendor: { color: "35 90% 55%", x: 4 }, risk: { color: "0 84% 60%", x: 2 },
  bu: { color: "225 70% 60%", x: 0 }, regulation: { color: "142 70% 45%", x: 1 },
};

const PRESETS = [
  { id: "conf_risky_vendor", label: "AI touching confidential data via risky vendors" },
  { id: "shadow_exposure", label: "Shadow AI exposure paths" },
  { id: "critical_risks", label: "Critical residual risks" },
];

export default function KnowledgeGraph() {
  const [graph, setGraph] = useState(null);
  const [highlight, setHighlight] = useState(null);
  const [explanation, setExplanation] = useState("");
  const [busy, setBusy] = useState("");
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [sel, setSel] = useState(null);

  const labelOf = (id) => (graph?.nodes.find((n) => n.id === id)?.label) || id;
  const onNodeClick = (_e, node) => { const n = graph?.nodes.find((x) => x.id === node.id); if (n) setSel(n); };

  const ask = async () => {
    if (!question.trim()) return;
    setAsking(true);
    try {
      const { data } = await api.post("/advisor/graph-ask", { question });
      setHighlight(new Set(data.highlight)); setExplanation(data.answer);
    } catch { setExplanation("Could not answer that from the graph."); }
    setAsking(false);
  };

  useEffect(() => { api.get("/knowledge-graph").then((r) => setGraph(r.data)); }, []);

  const runQuery = async (preset) => {
    setBusy(preset);
    try {
      const { data } = await api.post("/knowledge-graph/query", { preset });
      setHighlight(new Set(data.highlight)); setExplanation(data.explanation);
    } catch { setExplanation("Query failed."); }
    setBusy("");
  };

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };
    const counts = {};
    const nodes = graph.nodes.map((n) => {
      const t = TYPE[n.type] || TYPE.risk;
      counts[n.type] = (counts[n.type] || 0);
      const y = counts[n.type] * 78 + 20; counts[n.type] += 1;
      const dim = highlight && !highlight.has(n.id);
      return {
        id: n.id, position: { x: t.x * 235, y },
        data: { label: <div className="text-[10px] leading-tight"><div className="font-mono opacity-60">{n.type}</div><div className="font-medium">{n.label}</div></div> },
        style: {
          background: "hsl(215 38% 10%)", color: "hsl(210 40% 90%)",
          border: `1.5px solid hsl(${t.color} / ${dim ? 0.15 : 0.85})`, borderRadius: 8,
          width: 150, padding: 6, fontSize: 10, opacity: dim ? 0.3 : 1,
          boxShadow: highlight && highlight.has(n.id) ? `0 0 0 2px hsl(${t.color} / 0.4)` : "none",
        },
      };
    });
    const edges = graph.edges.map((e, i) => {
      const on = highlight && highlight.has(e.source) && highlight.has(e.target);
      return { id: `e${i}`, source: e.source, target: e.target, label: e.label, animated: on,
        style: { stroke: on ? "hsl(190 90% 50%)" : "hsl(215 30% 22%)", strokeWidth: on ? 2 : 1 },
        labelStyle: { fill: "hsl(215 20% 62%)", fontSize: 8 } };
    });
    return { nodes, edges };
  }, [graph, highlight]);

  if (!graph) return <div className="flex items-center justify-center h-96"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

  return (
    <div className="rise space-y-4">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Network className="w-7 h-7 text-primary" /> Enterprise Knowledge Graph</h1>
        <p className="text-sm text-muted-foreground mt-1">Business units ↔ AI ↔ data ↔ vendors ↔ risks ↔ regulations. Ask a question to trace real dependency paths.</p>
      </div>

      <AIInsight dashboard="Enterprise Knowledge Graph" accent={KG_ACCENT} auto slug="knowledge-graph" />

      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button key={p.id} data-testid={`kg-query-${p.id}`} disabled={!!busy} onClick={() => runQuery(p.id)}
            className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-md bg-ai/10 border border-ai/30 hover:bg-ai/20 transition-colors disabled:opacity-50">
            {busy === p.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkle className="w-3.5 h-3.5 text-ai" />} {p.label}
          </button>
        ))}
        {highlight && <button onClick={() => { setHighlight(null); setExplanation(""); }} className="text-xs px-3 py-2 rounded-md bg-secondary/60 hover:bg-secondary">Clear</button>}
      </div>

      <div className="flex items-center gap-2">
        <input data-testid="kg-ask-input" value={question} onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") ask(); }}
          placeholder="Ask the graph… e.g. which AI systems touch confidential data via risky vendors?"
          className="flex-1 bg-card border border-border rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-ai" />
        <button data-testid="kg-ask-btn" onClick={ask} disabled={asking}
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-md bg-ai text-background font-head font-bold text-sm hover:opacity-90 transition-opacity disabled:opacity-50">
          {asking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Ask
        </button>
      </div>

      {explanation && <div data-testid="kg-explanation" className="ai-border rounded-lg p-3 text-sm text-foreground bg-ai/5">{explanation}</div>}

      <div className="bg-card fact-border rounded-xl overflow-hidden" style={{ height: "62vh" }}>
        <ReactFlow nodes={nodes} edges={edges} onNodeClick={onNodeClick} fitView proOptions={{ hideAttribution: true }} nodesDraggable={false} nodesConnectable={false} minZoom={0.3}>
          <Background color="hsl(215 30% 18%)" gap={22} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      {sel && (() => {
        const neighbors = (graph?.edges || []).filter((e) => e.source === sel.id || e.target === sel.id)
          .map((e) => ({ label: e.label, other: e.source === sel.id ? e.target : e.source }));
        const tc = (TYPE[sel.type] || TYPE.risk).color;
        return (
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setSel(null)}>
            <div data-testid="kg-node-modal" onClick={(e) => e.stopPropagation()} className="w-full max-w-lg max-h-[86vh] overflow-y-auto bg-card border rounded-2xl p-6 space-y-4 rise" style={{ borderColor: `hsl(${KG_ACCENT} / 0.4)`, boxShadow: `inset 0 1px 0 hsl(${KG_ACCENT} / 0.3)` }}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-mono text-[11px] uppercase" style={{ color: `hsl(${tc})` }}>{sel.type} · {sel.id}</div>
                  <div className="font-head font-black text-xl tracking-tight break-words">{sel.label}</div>
                </div>
                <button data-testid="kg-node-close" onClick={() => setSel(null)} className="shrink-0 text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
              </div>
              {neighbors.length > 0 && (
                <div className="bg-secondary/20 rounded-lg p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">Connections ({neighbors.length})</div>
                  <div className="flex flex-wrap gap-1.5">
                    {neighbors.map((n, i) => <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-ai/10 text-ai border border-ai/20">{n.label} → {labelOf(n.other)}</span>)}
                  </div>
                </div>
              )}
              {sel.type === "risk"
                ? <AIFix entity="risk" refId={sel.id} accent={KG_ACCENT} />
                : <AIExplain title={sel.label} kind={`graph-${sel.type}`} accent={KG_ACCENT}
                    context={{ type: sel.type, id: sel.id, meta: sel.meta, connections: neighbors.map((n) => `${n.label} ${labelOf(n.other)}`) }} />}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
