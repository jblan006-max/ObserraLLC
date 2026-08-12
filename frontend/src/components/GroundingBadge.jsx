import { useState } from "react";
import { ShieldCheck, ShieldAlert, ShieldQuestion, ChevronDown } from "lucide-react";

const STYLE = {
  "Grounded": { icon: ShieldCheck, cls: "text-low border-low/40 bg-low/10" },
  "Partially grounded": { icon: ShieldQuestion, cls: "text-med border-med/40 bg-med/10" },
  "Unverified": { icon: ShieldAlert, cls: "text-crit border-crit/40 bg-crit/10" },
};

const DOT = { supported: "bg-low", unsupported: "bg-crit", uncertain: "bg-muted-foreground" };

export const GroundingBadge = ({ grounding }) => {
  const [open, setOpen] = useState(false);
  if (!grounding) return null;
  const s = STYLE[grounding.label] || STYLE["Unverified"];
  const Icon = s.icon;
  const flagged = grounding.flagged || (grounding.claims || []).filter((c) => c.status === "unsupported");
  return (
    <div className="mt-2" data-testid="grounding-badge">
      <button
        onClick={() => setOpen((v) => !v)}
        data-testid="grounding-badge-toggle"
        title="How well this answer is grounded in your live control data"
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-head font-bold ${s.cls}`}
      >
        <Icon className="w-3 h-3" /> {grounding.label} · {grounding.score}
        {flagged.length > 0 && <span className="opacity-80">· {flagged.length} flagged</span>}
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div data-testid="grounding-claims" className="mt-1 rounded-md border border-border bg-background/60 p-2 text-[10px] space-y-1">
          {(grounding.claims || []).length === 0 ? (
            <div className="text-muted-foreground">No specific factual claims to verify.</div>
          ) : (
            grounding.claims.map((c, i) => (
              <div key={i} data-testid={`grounding-claim-${i}`} className="flex items-start gap-1.5">
                <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${DOT[c.status] || "bg-muted-foreground"}`} />
                <span>
                  <span className="font-mono uppercase text-[8px] text-muted-foreground mr-1">{c.status}</span>
                  {c.claim}{c.note ? ` — ${c.note}` : ""}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
