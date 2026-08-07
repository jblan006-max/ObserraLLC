import { useEffect, useState } from "react";
import ReactFlow, { Background, Controls } from "reactflow";
import "reactflow/dist/style.css";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { DataTypeBadge } from "@/components/badges";

const STAGE_LABEL = {
  source: "Source", observation: "Observation", recommendation: "Recommendation",
  decision: "Decision", action: "Action", outcome: "Outcome",
};

export function EvidenceLineageModal({ riskRef, onClose }) {
  const [chain, setChain] = useState(null);

  useEffect(() => {
    if (riskRef) api.get(`/evidence-lineage/${riskRef}`).then((r) => setChain(r.data.chain)).catch(() => setChain([]));
  }, [riskRef]);

  if (!riskRef) return null;

  const nodes = (chain || []).map((c, i) => ({
    id: String(i),
    position: { x: i * 250, y: (i % 2) * 60 },
    data: {
      label: (
        <div className="text-left w-[190px]">
          <div className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground mb-1">{STAGE_LABEL[c.stage]}</div>
          <div className="text-xs font-medium text-foreground mb-1.5 leading-snug">{c.label}</div>
          <div className="text-[10px] text-muted-foreground leading-snug mb-1.5">{c.detail}</div>
          <DataTypeBadge type={c.type} />
        </div>
      ),
    },
    style: {
      background: "hsl(215 38% 10%)",
      border: c.type === "ai_recommendation" ? "1px solid hsl(190 90% 50% / 0.5)" : "1px solid hsl(215 30% 18%)",
      borderRadius: 8, padding: 10, width: 210,
    },
  }));
  const edges = (chain || []).slice(1).map((_, i) => ({
    id: `e${i}`, source: String(i), target: String(i + 1), animated: true,
    style: { stroke: "hsl(190 90% 50% / 0.4)" },
  }));

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div data-testid="lineage-modal" onClick={(e) => e.stopPropagation()}
        className="w-full max-w-5xl h-[70vh] bg-card border border-border rounded-lg overflow-hidden flex flex-col rise">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div>
            <div className="font-head font-bold">Evidence Lineage · <span className="font-mono text-ai">{riskRef}</span></div>
            <div className="text-[10px] text-muted-foreground">source → observation → recommendation → decision → action → outcome</div>
          </div>
          <button data-testid="lineage-close" onClick={onClose} className="p-1.5 rounded-md hover:bg-secondary"><X className="w-4 h-4" /></button>
        </div>
        <div className="flex-1">
          {chain && (
            <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}
              nodesDraggable={false} nodesConnectable={false}>
              <Background color="hsl(215 30% 18%)" gap={20} />
              <Controls showInteractive={false} />
            </ReactFlow>
          )}
        </div>
      </div>
    </div>
  );
}
