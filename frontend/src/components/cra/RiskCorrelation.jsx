import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CraExplainToggle } from "@/components/cra/CraAI";
import { AlertOctagon, Loader2, ShieldAlert, Link2, Boxes, Wrench, Clock3, GitBranch, Lightbulb } from "lucide-react";

const RATING_TONE = {
  Critical: "border-crit/30 bg-crit/10 text-crit",
  High: "border-high/30 bg-high/10 text-high",
  Medium: "border-med/30 bg-med/10 text-med",
  Low: "border-low/30 bg-low/10 text-low",
};
const RATING_BG = { Critical: "bg-crit", High: "bg-high", Medium: "bg-med", Low: "bg-low" };
const RATING_ORDER = ["Critical", "High", "Medium", "Low"];

function ratingFromScore(s) {
  if (s >= 20) return "Critical";
  if (s >= 12) return "High";
  if (s >= 6) return "Medium";
  return "Low";
}

function RiskMatrix({ risks }) {
  const cells = {};
  risks.forEach((r) => { const k = `${r.severity}-${r.likelihood}`; cells[k] = (cells[k] || 0) + 1; });
  const likes = [5, 4, 3, 2, 1];
  const sevs = [1, 2, 3, 4, 5];
  return (
    <div data-testid="cra-risk-matrix">
      <div className="flex gap-2">
        <div className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground flex items-center" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>Likelihood →</div>
        <div className="flex-1">
          <div className="grid grid-cols-5 gap-1">
            {likes.map((L) => sevs.map((S) => {
              const cnt = cells[`${S}-${L}`] || 0;
              const rating = ratingFromScore(S * L);
              return (
                <div key={`${S}-${L}`} title={`Severity ${S} × Likelihood ${L} — ${cnt} risk(s)`}
                  className={`aspect-square rounded flex items-center justify-center text-xs font-head font-black ${cnt ? `${RATING_BG[rating]} text-white` : "bg-secondary/40 text-muted-foreground/20"}`}>
                  {cnt || ""}
                </div>
              );
            }))}
          </div>
          <div className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground text-center mt-1">Severity →</div>
        </div>
      </div>
    </div>
  );
}

function Chip({ tone = "border-border bg-secondary/40 text-muted-foreground", children, onClick, testid }) {
  const Cmp = onClick ? "button" : "span";
  return <Cmp onClick={onClick} data-testid={testid} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-mono ${tone} ${onClick ? "hover:bg-secondary/70 transition-colors" : ""}`}>{children}</Cmp>;
}

function RiskCard({ r, openTab }) {
  return (
    <div data-testid={`cra-risk-card-${r.id}`} className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span data-testid={`cra-risk-rating-${r.id}`} className={`px-2 py-0.5 rounded-full border text-[10px] font-mono font-bold ${RATING_TONE[r.rating]}`}>{r.rating.toUpperCase()}</span>
            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">{r.category}</span>
            <span className="text-[10px] font-mono text-muted-foreground">score {r.score}/25 · sev {r.severity} × likelihood {r.likelihood}</span>
          </div>
          <div className="font-head font-bold text-base mt-1.5">{r.title}</div>
        </div>
        {r.deadline && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-high/30 bg-high/10 px-2.5 py-1 text-[10px] font-mono font-bold text-high shrink-0">
            <Clock3 className="w-3 h-3" /> {r.deadline.days_remaining}d to {r.deadline.date}
          </span>
        )}
      </div>

      {r.drivers?.length > 0 && (
        <div className="mt-3">
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1"><GitBranch className="w-3 h-3" /> Correlated drivers</div>
          <ul className="space-y-1">
            {r.drivers.map((d, i) => <li key={i} className="text-xs text-foreground/90 flex items-start gap-2"><span className="text-crit mt-0.5">•</span> {d}</li>)}
          </ul>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4 mt-4">
        <div className="space-y-3">
          {r.recommendation && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-0.5 flex items-center gap-1"><Lightbulb className="w-3 h-3 text-ai" /> Recommendation</div>
              <p className="text-sm text-foreground/90">{r.recommendation}</p>
            </div>
          )}
          {r.fixes?.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1"><Wrench className="w-3 h-3" /> Fixes needed</div>
              <ul className="space-y-1" data-testid={`cra-risk-fixes-${r.id}`}>
                {r.fixes.map((f, i) => <li key={i} className="text-xs flex items-start gap-2"><span className="text-ai mt-0.5">→</span> {f}</li>)}
              </ul>
            </div>
          )}
        </div>
        <div className="space-y-3">
          {r.affected?.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1"><Boxes className="w-3 h-3" /> Affected products</div>
              <div className="flex flex-wrap gap-1.5">
                {r.affected.map((a, i) => <Chip key={i} testid={`cra-risk-affected-${r.id}-${i}`}>{a.name || a.ref}</Chip>)}
              </div>
            </div>
          )}
          {r.mapped_controls?.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1 flex items-center gap-1"><Link2 className="w-3 h-3" /> Mapped CRA controls</div>
              <div className="flex flex-wrap gap-1.5">
                {r.mapped_controls.map((m, i) => (
                  <Chip key={i} onClick={() => openTab && openTab("controls")} testid={`cra-risk-control-${r.id}-${m.requirement_id}`}
                    tone="border-ai/30 bg-ai/10 text-ai" >
                    {m.requirement_id}{m.csf?.length ? ` · ${m.csf.join("/")}` : ""}
                  </Chip>
                ))}
              </div>
              <div className="text-[10px] text-muted-foreground mt-1">{r.mapped_controls.map((m) => (m.legal_refs || []).join(", ")).filter(Boolean).join(" · ")}</div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-border/60">
        <CraExplainToggle
          title={r.title}
          kind="risk-correlation"
          label="AI analysis, risk detail & fixes"
          context={{ rating: r.rating, score: r.score, severity: r.severity, likelihood: r.likelihood, category: r.category, drivers: r.drivers, affected: r.affected, recommendation: r.recommendation, fixes: r.fixes, mapped_controls: r.mapped_controls, deadline: r.deadline }}
        />
      </div>
    </div>
  );
}

export function RiskCorrelation({ openTab }) {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/cra/risk-correlation").then((r) => { setD(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading && !d) {
    return <div className="flex items-center gap-2 text-sm text-muted-foreground p-6" data-testid="cra-risk-loading"><Loader2 className="w-4 h-4 animate-spin" /> Correlating the live EU CRA risk picture…</div>;
  }
  if (!d) {
    return <div className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground" data-testid="cra-risk-unavailable">Risk correlation is temporarily unavailable.</div>;
  }

  const o = d.overall || {};
  const idxTone = o.risk_index >= 60 ? "text-crit" : o.risk_index >= 35 ? "text-high" : "text-low";

  return (
    <div className="space-y-5" data-testid="cra-risk-correlation">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border bg-card p-5" data-testid="cra-risk-index">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground"><AlertOctagon className="w-3.5 h-3.5" /> Correlated risk index</div>
          <div className={`font-head font-black text-5xl mt-2 ${idxTone}`}>{o.risk_index ?? 0}</div>
          <div className="text-[11px] font-mono text-muted-foreground mt-1">{o.total ?? 0} correlated risk(s) · weighted exposure 0–100</div>
          <div className="mt-3 h-2 rounded-full bg-secondary/60 overflow-hidden"><div className={`h-full ${o.risk_index >= 60 ? "bg-crit" : o.risk_index >= 35 ? "bg-high" : "bg-low"}`} style={{ width: `${o.risk_index ?? 0}%` }} /></div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5" data-testid="cra-risk-distribution">
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-3">Rating distribution</div>
          <div className="grid grid-cols-4 gap-2 text-center">
            {RATING_ORDER.map((k) => (
              <div key={k} className={`rounded-lg border p-2 ${RATING_TONE[k]}`} data-testid={`cra-risk-count-${k.toLowerCase()}`}>
                <div className="font-head font-black text-2xl">{o.counts?.[k] ?? 0}</div>
                <div className="text-[9px] font-mono uppercase">{k}</div>
              </div>
            ))}
          </div>
          {o.most_correlated_control && (
            <div className="mt-3 pt-3 border-t border-border/60 text-[11px] font-mono text-muted-foreground">
              Most-threatened control: <span className="text-ai font-bold">{o.most_correlated_control.requirement_id}</span> across {o.most_correlated_control.count} risk(s)
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-3">Severity × Likelihood matrix</div>
          <RiskMatrix risks={d.risks || []} />
        </div>
      </div>

      <div className="space-y-3">
        {(d.risks || []).map((r) => <RiskCard key={r.id} r={r} openTab={openTab} />)}
        {(!d.risks || d.risks.length === 0) && (
          <div className="rounded-xl border border-low/25 bg-low/5 p-6 flex items-center gap-3" data-testid="cra-risk-empty">
            <ShieldAlert className="w-5 h-5 text-low" />
            <div className="text-sm text-foreground/90">No correlated CRA risks right now — no overdue reporting, open high-severity vulnerabilities, control gaps or CE blockers were found in the live records.</div>
          </div>
        )}
      </div>

      <div className="text-[10px] font-mono text-muted-foreground">
        Ratings synthesised from live products, vulnerabilities, assessments, controls and the AI-grounding monitor · Obserra CRA v{d.version} · decision-support, not legal advice.
      </div>
    </div>
  );
}
