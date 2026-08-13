import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Landmark, Loader2, TriangleAlert, Clock3, Boxes, BadgeCheck, ShieldCheck, FileCheck2, Fingerprint, Building2, AlertOctagon, ArrowUpRight, ArrowDownRight, Camera } from "lucide-react";
import { api } from "@/lib/api";

const NIST_TONE = { Low: "bg-low", Medium: "bg-high", High: "bg-crit", Unknown: "bg-secondary" };
const RATING_TEXT = { Critical: "text-crit", High: "text-high", Medium: "text-med", Low: "text-low" };
const GOOD_DOWN = new Set(["article14_overdue", "ce_blockers"]);
const PCT_KEYS = new Set(["classification_approved_pct", "ce_ready_pct", "control_compliance_pct", "nist_alignment_pct", "ai_grounding_score"]);
const DELTA_ROWS = [["Classification", "classification_approved_pct"], ["CE-ready", "ce_ready_pct"], ["Control", "control_compliance_pct"], ["NIST", "nist_alignment_pct"], ["AI grounding", "ai_grounding_score"], ["Art.14 overdue", "article14_overdue"]];

function toneCls(score) {
  if (score == null) return "text-muted-foreground";
  if (score >= 80) return "text-low";
  if (score >= 50) return "text-high";
  return "text-crit";
}

function Delta({ k, v }) {
  if (v == null || v === 0) return <span className="text-[10px] font-mono text-muted-foreground">±0</span>;
  const up = v > 0;
  const good = GOOD_DOWN.has(k) ? !up : up;
  const Arrow = up ? ArrowUpRight : ArrowDownRight;
  return <span className={`inline-flex items-center gap-0.5 text-[11px] font-mono font-bold ${good ? "text-low" : "text-crit"}`}><Arrow className="w-3 h-3" />{up ? "+" : ""}{v}{PCT_KEYS.has(k) ? "" : ""}</span>;
}

function Bar({ label, value, total, tone = "bg-primary" }) {
  const p = total ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-foreground/90">{label}</span>
        <span className="font-mono text-muted-foreground">{value}{total ? ` / ${total}` : ""}</span>
      </div>
      <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className={`h-full ${tone}`} style={{ width: `${p}%` }} /></div>
    </div>
  );
}

function Kpi({ label, value, sub, Icon, tone }) {
  return (
    <div className="bg-card fact-border rounded-xl p-4">
      <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground"><Icon className="w-3.5 h-3.5" /> {label}</div>
      <div className={`font-head font-black text-3xl mt-1 ${tone || "text-foreground"}`}>{value}</div>
      {sub && <div className="text-[11px] font-mono text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

export default function CRAExecOverviewPublic() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get(`/cra-public/exec-overview/${token}`);
        setData(r.data);
        setError("");
      } catch (e) {
        setError(e.response?.data?.detail || "This Executive Overview link is invalid or has expired.");
      }
    })();
  }, [token]);

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-6">
        <div className="max-w-lg bg-card fact-border rounded-xl p-8 text-center" data-testid="cra-exec-public-error">
          <TriangleAlert className="w-10 h-10 text-crit mx-auto" />
          <h1 className="font-head font-black text-2xl mt-4">Executive Overview unavailable</h1>
          <p className="text-sm text-muted-foreground mt-2">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="min-h-screen bg-background flex items-center justify-center"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>;
  }

  const k = data.kpis || {};
  const c = data.controls || {};
  const nist = data.nist?.overall || {};
  const nistFns = data.nist?.functions || [];
  const cls = data.classifications || {};
  const products = k.products || 0;
  const nd = data.next_deadline;
  const risk = data.risk || {};
  const riskTone = risk.risk_index >= 60 ? "text-crit" : risk.risk_index >= 35 ? "text-high" : "text-low";
  const delta = data.snapshot_delta;
  const prev = data.previous_snapshot;

  const kpis = [
    { label: "Products under CRA", value: products, sub: `${cls["Critical"] || 0} critical · ${cls["Class II"] || 0} Class II`, Icon: Boxes },
    { label: "Classification approved", value: `${k.classification_approved_pct ?? 0}%`, sub: `${k.classification_approved ?? 0} / ${products} approved`, Icon: BadgeCheck, tone: toneCls(k.classification_approved_pct) },
    { label: "CE market-ready", value: `${k.ce_ready_pct ?? 0}%`, sub: `${k.ce_ready ?? 0} / ${products} ready`, Icon: ShieldCheck, tone: toneCls(k.ce_ready_pct) },
    { label: "Article 14 overdue", value: k.article14_overdue ?? 0, sub: "24h / 72h / final clocks", Icon: TriangleAlert, tone: (k.article14_overdue || 0) > 0 ? "text-crit" : "text-low" },
    { label: "Control compliance", value: `${k.control_compliance_pct ?? 0}%`, sub: `${c.implemented ?? 0} implemented · ${c.partial ?? 0} partial`, Icon: FileCheck2, tone: toneCls(k.control_compliance_pct) },
    { label: "NIST CSF alignment", value: `${k.nist_alignment_pct ?? 0}%`, sub: `${nist.functions_aligned ?? 0} / ${nist.functions_total ?? 6} functions aligned`, Icon: ShieldCheck, tone: toneCls(k.nist_alignment_pct) },
    { label: "CE blockers", value: k.ce_blockers ?? 0, sub: "open market-readiness blockers", Icon: Building2 },
    { label: "AI grounding score", value: k.ai_grounding_score == null ? "—" : `${k.ai_grounding_score}%`, sub: `${k.ai_checks ?? 0} answers checked`, Icon: Fingerprint, tone: toneCls(k.ai_grounding_score) },
  ];

  return (
    <div className="min-h-screen bg-background" data-testid="cra-exec-public-page">
      <header className="border-b border-border bg-card">
        <div className="max-w-6xl mx-auto px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-mono text-primary uppercase tracking-wider"><Landmark className="w-3.5 h-3.5" /> Obserra EU CRA Executive Overview</div>
            <h1 className="font-head font-black text-2xl mt-1">{data.organization}</h1>
            <div className="text-xs text-muted-foreground mt-1">{data.regulation} · Obserra CRA v{data.version} · read-only · expires {new Date(data.expires_at).toLocaleDateString()}</div>
          </div>
          {nd && (
            <div className="inline-flex items-center gap-2 rounded-full border border-high/30 bg-high/10 px-3.5 py-1.5 text-xs font-head font-bold text-high" data-testid="cra-exec-public-deadline">
              <Clock3 className="w-3.5 h-3.5" /> {nd.days_remaining} days to next CRA deadline
            </div>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-5 space-y-5">
        {/* The single most important number, front and centre */}
        <section className="bg-card fact-border rounded-xl p-5 grid lg:grid-cols-3 gap-5" data-testid="cra-exec-public-risk">
          <div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground"><AlertOctagon className="w-3.5 h-3.5" /> Correlated risk index</div>
            <div className={`font-head font-black text-5xl mt-2 ${riskTone}`}>{risk.risk_index ?? 0}</div>
            <div className="text-[11px] font-mono text-muted-foreground mt-1">{risk.total ?? 0} correlated risk(s) · Critical {risk.counts?.Critical ?? 0} · High {risk.counts?.High ?? 0} · Medium {risk.counts?.Medium ?? 0}</div>
            <div className="mt-3 h-2 rounded-full bg-secondary/60 overflow-hidden"><div className={`h-full ${risk.risk_index >= 60 ? "bg-crit" : risk.risk_index >= 35 ? "bg-high" : "bg-low"}`} style={{ width: `${risk.risk_index ?? 0}%` }} /></div>
            {data.burndown && (
              <div className="mt-2 text-[11px] font-mono text-muted-foreground" data-testid="cra-exec-public-burndown">
                Board target {data.burndown.target} · {data.burndown.on_track ? "✓ target met" : data.burndown.projected_date ? `on track to hit by ${data.burndown.projected_date}` : `gap ${data.burndown.gap}, not trending down yet`}
              </div>
            )}
          </div>
          <div className="lg:col-span-2">
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">Top risks right now</div>
            <div className="space-y-2" data-testid="cra-exec-public-toprisks">
              {(risk.top_risks || []).map((t, i) => (
                <div key={i} className="flex items-center justify-between gap-3 border-b border-border/60 pb-2 last:border-0">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`text-[10px] font-mono font-bold ${RATING_TEXT[t.rating] || "text-foreground"}`}>{t.rating?.toUpperCase()}</span>
                    <span className="text-sm text-foreground/90 truncate">{t.category}</span>
                  </div>
                  <span className="text-[10px] font-mono text-muted-foreground shrink-0">{t.score}/25</span>
                </div>
              ))}
              {(!risk.top_risks || risk.top_risks.length === 0) && <div className="text-sm text-muted-foreground">No correlated risks in the live records.</div>}
            </div>
          </div>
        </section>

        {delta && prev && (
          <section className="bg-card fact-border rounded-xl p-4" data-testid="cra-exec-public-movement">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2"><Camera className="w-3.5 h-3.5" /> Movement since “{prev.label}” ({new Date(prev.at).toLocaleDateString()})</div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
              {DELTA_ROWS.map(([lbl, key]) => (
                <div key={key} className="text-center">
                  <div className="text-[9px] font-mono uppercase text-muted-foreground">{lbl}</div>
                  <div className="mt-0.5"><Delta k={key} v={delta[key]} /></div>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="cra-exec-public-kpis">
          {kpis.map((kp) => <Kpi key={kp.label} {...kp} />)}
        </section>

        <section className="grid lg:grid-cols-2 gap-5">
          <div className="bg-card fact-border rounded-xl p-5">
            <div className="font-head font-bold text-sm mb-3">Product classification split</div>
            <div className="space-y-3">
              <Bar label="Default" value={cls["Default"] || 0} total={products} tone="bg-primary" />
              <Bar label="Class I (important)" value={cls["Class I"] || 0} total={products} tone="bg-high" />
              <Bar label="Class II (important)" value={cls["Class II"] || 0} total={products} tone="bg-high" />
              <Bar label="Critical" value={cls["Critical"] || 0} total={products} tone="bg-crit" />
            </div>
            <div className="mt-4 pt-3 border-t border-border grid grid-cols-2 gap-3 text-sm">
              <div><div className="text-[10px] font-mono uppercase text-muted-foreground">Avg readiness</div><div className="font-head font-bold text-lg">{k.average_readiness_pct ?? 0}%</div></div>
              <div><div className="text-[10px] font-mono uppercase text-muted-foreground">Products assessed</div><div className="font-head font-bold text-lg">{c.products_assessed ?? 0} / {c.products_total ?? products}</div></div>
            </div>
          </div>

          <div className="bg-card fact-border rounded-xl p-5">
            <div className="font-head font-bold text-sm mb-3">{nist.framework || "NIST CSF 2.0 · SP 800-218 (SSDF)"}</div>
            <div className="space-y-2.5">
              {nistFns.map((f) => (
                <div key={f.code}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-foreground/90"><span className="font-mono text-muted-foreground">{f.code}</span> {f.name}</span>
                    <span className="font-mono text-muted-foreground">{f.compliance_rate}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-secondary/60 overflow-hidden"><div className={`h-full ${NIST_TONE[f.risk] || "bg-primary"}`} style={{ width: `${f.compliance_rate}%` }} /></div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-card fact-border rounded-xl p-5">
          <div className="font-head font-bold text-sm mb-3">Essential-requirement control posture</div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg border border-low/25 bg-low/5 p-3"><div className="font-head font-black text-2xl text-low">{c.implemented ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Implemented</div></div>
            <div className="rounded-lg border border-high/25 bg-high/5 p-3"><div className="font-head font-black text-2xl text-high">{c.partial ?? 0}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Partial</div></div>
            <div className="rounded-lg border border-crit/25 bg-crit/5 p-3"><div className="font-head font-black text-2xl text-crit">{(c.gaps ?? 0) + (c.not_started ?? 0)}</div><div className="text-[10px] font-mono uppercase text-muted-foreground">Gap / not started</div></div>
          </div>
          <div className="mt-4"><Bar label="Overall control compliance" value={c.percentage ?? 0} total={100} tone={(c.percentage ?? 0) >= 80 ? "bg-low" : (c.percentage ?? 0) >= 50 ? "bg-high" : "bg-crit"} /></div>
        </section>

        <div className="rounded-lg border border-border bg-secondary/20 p-4 text-xs text-muted-foreground">
          Generated {new Date(data.generated_at).toLocaleString()} · link expires {new Date(data.expires_at).toLocaleString()}. {data.note}
        </div>
      </main>
    </div>
  );
}
