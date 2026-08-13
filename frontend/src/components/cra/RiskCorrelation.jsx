import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { CraExplainToggle } from "@/components/cra/CraAI";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from "recharts";
import {
  AlertOctagon, Loader2, ShieldAlert, Link2, Boxes, Wrench, Clock3, GitBranch, Lightbulb,
  FileText, FileSpreadsheet, UserPlus, TrendingUp, TrendingDown, Minus, Save, X, Target,
  Users, ListFilter, LayoutList,
} from "lucide-react";

const RATING_TONE = {
  Critical: "border-crit/30 bg-crit/10 text-crit",
  High: "border-high/30 bg-high/10 text-high",
  Medium: "border-med/30 bg-med/10 text-med",
  Low: "border-low/30 bg-low/10 text-low",
};
const RATING_BG = { Critical: "bg-crit", High: "bg-high", Medium: "bg-med", Low: "bg-low" };
const RATING_TEXT = { Critical: "text-crit", High: "text-high", Medium: "text-med", Low: "text-low" };
const RATING_ORDER = ["Critical", "High", "Medium", "Low"];
const RANK = { Critical: 0, High: 1, Medium: 2, Low: 3 };

function ratingFromScore(s) {
  if (s >= 20) return "Critical";
  if (s >= 12) return "High";
  if (s >= 6) return "Medium";
  return "Low";
}

const download = async (path, filename) => {
  try {
    const r = await api.get(path, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  } catch { toast.error("Export failed — please try again"); }
};

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

function RiskTrend({ trend }) {
  const series = trend?.series || [];
  const line = series.map((p) => ({ date: p.date?.slice(5), risk_index: p.risk_index }));
  const change = trend?.change ?? 0;
  const Arrow = change > 0 ? TrendingUp : change < 0 ? TrendingDown : Minus;
  const tone = change > 0 ? "text-crit" : change < 0 ? "text-low" : "text-muted-foreground";
  return (
    <div className="rounded-xl border border-border bg-card p-5" data-testid="cra-risk-trend">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Risk index trend</div>
        <span className={`inline-flex items-center gap-1 text-[11px] font-mono font-bold ${tone}`}><Arrow className="w-3.5 h-3.5" />{change > 0 ? "+" : ""}{change} over {trend?.days ?? 30}d</span>
      </div>
      {line.length < 2 ? (
        <div className="text-xs text-muted-foreground mt-6">Trend builds daily — check back tomorrow for movement. Today's index is {trend?.current ?? 0}.</div>
      ) : (
        <div className="h-[130px] mt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={line} margin={{ top: 6, right: 6, left: -22, bottom: 0 }}>
              <defs><linearGradient id="craRiskGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ef4444" stopOpacity={0.35} /><stop offset="100%" stopColor="#ef4444" stopOpacity={0} /></linearGradient></defs>
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} minTickGap={24} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} formatter={(v) => [`${v}/100`, "Risk index"]} />
              <Area type="monotone" dataKey="risk_index" stroke="#ef4444" strokeWidth={2} fill="url(#craRiskGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function BurndownTarget({ isAdmin }) {
  const [bd, setBd] = useState(null);
  const [target, setTarget] = useState(30);
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/cra/risk-target").then((r) => { setBd(r.data); setTarget(r.data.target); }).catch(() => {});
  useEffect(() => { load(); }, []);
  const save = async () => {
    setBusy(true);
    try { const r = await api.put("/cra/risk-target", { target: Number(target) }); setBd(r.data); toast.success("Target saved"); }
    catch { toast.error("Only admins can set the target"); }
    setBusy(false);
  };
  if (!bd) return <div className="rounded-xl border border-border bg-card p-5 flex items-center gap-2 text-sm text-muted-foreground" data-testid="cra-risk-burndown"><Loader2 className="w-4 h-4 animate-spin" /> Loading target…</div>;
  const met = bd.on_track;
  return (
    <div className="rounded-xl border border-border bg-card p-5" data-testid="cra-risk-burndown">
      <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground"><Target className="w-3.5 h-3.5" /> Burndown target</div>
      <div className="flex items-end gap-2 mt-2">
        <div className="font-head font-black text-4xl text-foreground">{bd.current}</div>
        <div className="text-[11px] font-mono text-muted-foreground pb-1.5">/ target {bd.target}</div>
      </div>
      {met ? (
        <div className="mt-1 text-[12px] font-mono text-low font-bold" data-testid="cra-risk-burndown-status">✓ Target met — index at or below {bd.target}</div>
      ) : bd.projected_date ? (
        <div className="mt-1 text-[12px] font-mono text-foreground/90" data-testid="cra-risk-burndown-status">Gap {bd.gap} · on trend, projected to hit {bd.target} by <span className="font-bold text-low">{bd.projected_date}</span> ({bd.days_to_target}d)</div>
      ) : (
        <div className="mt-1 text-[12px] font-mono text-high" data-testid="cra-risk-burndown-status">Gap {bd.gap} · {bd.points < 2 ? "trend builds daily — projection appears once there is history" : "not trending down yet — no projected date"}</div>
      )}
      {isAdmin && (
        <div className="flex items-center gap-2 mt-3">
          <input type="number" min={0} max={100} value={target} onChange={(e) => setTarget(e.target.value)} data-testid="cra-risk-target-input" className="w-20 bg-background border border-border rounded-md px-2 py-1.5 text-xs font-mono outline-none focus:border-ai" />
          <button onClick={save} disabled={busy} data-testid="cra-risk-target-save" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Set target</button>
        </div>
      )}
    </div>
  );
}

function Chip({ tone = "border-border bg-secondary/40 text-muted-foreground", children, onClick, testid, active }) {
  const Cmp = onClick ? "button" : "span";
  return <Cmp onClick={onClick} data-testid={testid} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-mono ${active ? "ring-1 ring-offset-0" : ""} ${tone} ${onClick ? "hover:bg-secondary/70 transition-colors" : ""}`}>{children}</Cmp>;
}

function OwnerForm({ r, onSaved }) {
  const [open, setOpen] = useState(false);
  const [owner, setOwner] = useState(r.owner || "");
  const [email, setEmail] = useState(r.owner_email || "");
  const [due, setDue] = useState(r.due_date || "");
  const [busy, setBusy] = useState(false);
  const fld = "bg-background border border-border rounded-md px-2 py-1.5 text-xs font-mono outline-none focus:border-ai";

  const save = async () => {
    if (!owner.trim()) { toast.error("Enter an owner name"); return; }
    setBusy(true);
    try {
      await api.post("/cra/risk-owner", { risk_key: r.key, risk_title: r.title, owner, owner_email: email, due_date: due });
      toast.success("Owner assigned"); setOpen(false); onSaved && onSaved();
    } catch { toast.error("Could not save owner"); }
    setBusy(false);
  };
  const clear = async () => {
    setBusy(true);
    try { await api.delete(`/cra/risk-owner/${r.key}`); toast.success("Owner cleared"); setOpen(false); onSaved && onSaved(); }
    catch { toast.error("Could not clear owner"); }
    setBusy(false);
  };

  if (!open) {
    return r.owner ? (
      <button onClick={() => setOpen(true)} data-testid={`cra-risk-owner-${r.id}`} className="inline-flex items-center gap-1.5 rounded-full border border-ai/30 bg-ai/10 px-2.5 py-1 text-[10px] font-mono text-ai hover:bg-ai/20 transition-colors">
        <UserPlus className="w-3 h-3" /> {r.owner}{r.due_date ? ` · due ${r.due_date}` : ""}
      </button>
    ) : (
      <button onClick={() => setOpen(true)} data-testid={`cra-risk-assign-${r.id}`} className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-border px-2.5 py-1 text-[10px] font-mono text-muted-foreground hover:text-foreground hover:border-ai/40 transition-colors">
        <UserPlus className="w-3 h-3" /> Assign owner
      </button>
    );
  }
  return (
    <div className="rounded-lg border border-ai/30 bg-ai/5 p-3 w-full" data-testid={`cra-risk-owner-form-${r.id}`}>
      <div className="grid sm:grid-cols-3 gap-2">
        <input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="Owner name" data-testid={`cra-risk-owner-name-${r.id}`} className={fld} />
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="owner@email" data-testid={`cra-risk-owner-email-${r.id}`} className={fld} />
        <input type="date" value={due} onChange={(e) => setDue(e.target.value)} data-testid={`cra-risk-owner-due-${r.id}`} className={fld} />
      </div>
      <div className="flex items-center gap-2 mt-2 flex-wrap">
        <button onClick={save} disabled={busy} data-testid={`cra-risk-owner-save-${r.id}`} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Save</button>
        {r.owner && <button onClick={clear} disabled={busy} className="px-3 py-1.5 rounded-md border border-crit/40 bg-crit/10 text-crit text-xs font-head font-bold">Clear</button>}
        <button onClick={() => setOpen(false)} className="px-3 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold inline-flex items-center gap-1"><X className="w-3.5 h-3.5" /> Cancel</button>
        <span className="text-[10px] font-mono text-muted-foreground">Owner gets auto-reminders as the due date nears.</span>
      </div>
    </div>
  );
}

function RiskCard({ r, openTab, onChanged }) {
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
        <div className="flex items-center gap-2 shrink-0">
          {r.deadline && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-high/30 bg-high/10 px-2.5 py-1 text-[10px] font-mono font-bold text-high">
              <Clock3 className="w-3 h-3" /> {r.deadline.days_remaining}d to {r.deadline.date}
            </span>
          )}
          <OwnerForm r={r} onSaved={onChanged} />
        </div>
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
                    tone="border-ai/30 bg-ai/10 text-ai">
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

function OwnerWorkload({ risks }) {
  const groups = useMemo(() => {
    const g = {};
    risks.forEach((r) => {
      const key = r.owner || "Unassigned";
      if (!g[key]) g[key] = { owner: key, email: r.owner_email, count: 0, score: 0, overdue: 0, counts: { Critical: 0, High: 0, Medium: 0, Low: 0 }, items: [] };
      const grp = g[key];
      grp.count += 1; grp.score += r.score; grp.counts[r.rating] += 1;
      const od = r.due_date && new Date(`${r.due_date}T00:00:00Z`) < new Date();
      if (od) grp.overdue += 1;
      grp.items.push(r);
    });
    return Object.values(g).sort((a, b) => (a.owner === "Unassigned" ? 1 : b.owner === "Unassigned" ? -1 : b.score - a.score));
  }, [risks]);

  return (
    <div className="grid md:grid-cols-2 gap-4" data-testid="cra-risk-owner-workload">
      {groups.map((grp) => (
        <div key={grp.owner} data-testid={`cra-owner-group-${grp.owner.replace(/[^a-zA-Z0-9]+/g, "-")}`} className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="font-head font-bold text-sm flex items-center gap-1.5"><Users className="w-4 h-4 text-ai" /> {grp.owner}</div>
              {grp.email && <div className="text-[10px] font-mono text-muted-foreground">{grp.email}</div>}
            </div>
            <div className="text-right">
              <div className="font-head font-black text-2xl">{grp.count}</div>
              <div className="text-[9px] font-mono uppercase text-muted-foreground">risk(s){grp.overdue ? ` · ${grp.overdue} overdue` : ""}</div>
            </div>
          </div>
          <div className="flex gap-1.5 mt-3">
            {RATING_ORDER.map((k) => grp.counts[k] > 0 && (
              <span key={k} className={`px-2 py-0.5 rounded-full border text-[10px] font-mono font-bold ${RATING_TONE[k]}`}>{grp.counts[k]} {k}</span>
            ))}
          </div>
          <div className="mt-3 space-y-1.5">
            {grp.items.slice(0, 6).map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-2 text-xs border-b border-border/50 pb-1.5 last:border-0">
                <span className="truncate"><span className={`font-mono font-bold ${RATING_TEXT[r.rating]}`}>{r.rating[0]}</span> {r.title}</span>
                <span className={`shrink-0 font-mono text-[10px] ${r.due_date && new Date(`${r.due_date}T00:00:00Z`) < new Date() ? "text-crit font-bold" : "text-muted-foreground"}`}>{r.due_date || "no date"}</span>
              </div>
            ))}
            {grp.items.length > 6 && <div className="text-[10px] font-mono text-muted-foreground">+{grp.items.length - 6} more</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function RiskCorrelation({ openTab }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [d, setD] = useState(null);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("risks");
  const [ratings, setRatings] = useState(new Set());
  const [category, setCategory] = useState("");
  const [owner, setOwner] = useState("");
  const [sort, setSort] = useState("score");

  const load = () => api.get("/cra/risk-correlation").then((r) => { setD(r.data); setLoading(false); }).catch(() => setLoading(false));
  const loadTrend = () => api.get("/cra/risk-trend?days=30").then((r) => setTrend(r.data)).catch(() => {});
  useEffect(() => { load(); loadTrend(); }, []);
  const onChanged = () => { load(); };

  const allRisks = d?.risks || [];
  const categories = useMemo(() => Array.from(new Set(allRisks.map((r) => r.category))), [allRisks]);
  const owners = useMemo(() => Array.from(new Set(allRisks.map((r) => r.owner).filter(Boolean))), [allRisks]);

  const filtered = useMemo(() => {
    let out = allRisks.filter((r) => (ratings.size === 0 || ratings.has(r.rating))
      && (!category || r.category === category)
      && (!owner || (owner === "__unassigned__" ? !r.owner : r.owner === owner)));
    if (sort === "rating") out = [...out].sort((a, b) => RANK[a.rating] - RANK[b.rating] || b.score - a.score);
    else if (sort === "due") out = [...out].sort((a, b) => (a.due_date || "9999-12-31").localeCompare(b.due_date || "9999-12-31"));
    else if (sort === "owner") out = [...out].sort((a, b) => (a.owner || "~").toLowerCase().localeCompare((b.owner || "~").toLowerCase()) || b.score - a.score);
    else out = [...out].sort((a, b) => b.score - a.score);
    return out;
  }, [allRisks, ratings, category, owner, sort]);

  const exportQs = useMemo(() => {
    const p = new URLSearchParams();
    if (ratings.size) p.set("rating", Array.from(ratings).join(","));
    if (category) p.set("category", category);
    if (owner) p.set("owner", owner);
    if (sort) p.set("sort", sort);
    const s = p.toString();
    return s ? `?${s}` : "";
  }, [ratings, category, owner, sort]);

  const toggleRating = (k) => setRatings((prev) => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const fld = "bg-background border border-border rounded-md px-2 py-1.5 text-xs font-mono outline-none focus:border-ai";

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
          <div className="text-[11px] font-mono text-muted-foreground mt-1">{o.total ?? 0} correlated risk(s) · 0–100</div>
          <div className="mt-3 h-2 rounded-full bg-secondary/60 overflow-hidden"><div className={`h-full ${o.risk_index >= 60 ? "bg-crit" : o.risk_index >= 35 ? "bg-high" : "bg-low"}`} style={{ width: `${o.risk_index ?? 0}%` }} /></div>
          {o.most_correlated_control && (
            <div className="mt-3 pt-3 border-t border-border/60 text-[11px] font-mono text-muted-foreground">
              Most-threatened: <span className="text-ai font-bold">{o.most_correlated_control.requirement_id}</span> · {o.most_correlated_control.count} risk(s)
            </div>
          )}
        </div>
        <BurndownTarget isAdmin={isAdmin} />
        <RiskTrend trend={trend} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
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
        </div>
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-3">Severity × Likelihood</div>
          <RiskMatrix risks={allRisks} />
        </div>
      </div>

      {/* Filter + sort + view + export bar */}
      <div className="rounded-xl border border-border bg-card p-3 flex flex-wrap items-center gap-2" data-testid="cra-risk-filterbar">
        <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground mr-1"><ListFilter className="w-3.5 h-3.5" /> Filter</span>
        {RATING_ORDER.map((k) => (
          <button key={k} onClick={() => toggleRating(k)} data-testid={`cra-risk-filter-${k.toLowerCase()}`}
            className={`px-2 py-1 rounded-full border text-[10px] font-mono font-bold transition-colors ${ratings.has(k) ? RATING_TONE[k] + " ring-1 ring-current" : "border-border text-muted-foreground hover:text-foreground"}`}>{k}</button>
        ))}
        <select value={category} onChange={(e) => setCategory(e.target.value)} data-testid="cra-risk-filter-category" className={fld}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={owner} onChange={(e) => setOwner(e.target.value)} data-testid="cra-risk-filter-owner" className={fld}>
          <option value="">All owners</option>
          <option value="__unassigned__">Unassigned</option>
          {owners.map((ow) => <option key={ow} value={ow}>{ow}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} data-testid="cra-risk-sort" className={fld}>
          <option value="score">Sort: score</option>
          <option value="rating">Sort: rating</option>
          <option value="due">Sort: due date</option>
          <option value="owner">Sort: owner</option>
        </select>
        <div className="flex-1" />
        <div className="inline-flex rounded-md border border-border overflow-hidden">
          <button onClick={() => setView("risks")} data-testid="cra-risk-view-risks" className={`px-2.5 py-1.5 text-[11px] font-head font-bold inline-flex items-center gap-1 ${view === "risks" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}><LayoutList className="w-3.5 h-3.5" /> By risk</button>
          <button onClick={() => setView("owners")} data-testid="cra-risk-view-owners" className={`px-2.5 py-1.5 text-[11px] font-head font-bold inline-flex items-center gap-1 ${view === "owners" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}><Users className="w-3.5 h-3.5" /> By owner</button>
        </div>
        <button onClick={() => download(`/cra/risk-register.pdf${exportQs}`, "obserra-cra-risk-register.pdf")} data-testid="cra-risk-export-pdf" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><FileText className="w-3.5 h-3.5" /> PDF</button>
        <button onClick={() => download(`/cra/risk-register.csv${exportQs}`, "obserra-cra-risk-register.csv")} data-testid="cra-risk-export-csv" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><FileSpreadsheet className="w-3.5 h-3.5" /> CSV</button>
      </div>

      <div className="text-[11px] font-mono text-muted-foreground">Showing {filtered.length} of {allRisks.length} risk(s){exportQs ? " · export respects these filters" : ""}</div>

      {view === "owners" ? (
        filtered.length ? <OwnerWorkload risks={filtered} /> : <div className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">No risks match the current filter.</div>
      ) : (
        <div className="space-y-3">
          {filtered.map((r) => <RiskCard key={r.id} r={r} openTab={openTab} onChanged={onChanged} />)}
          {filtered.length === 0 && allRisks.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">No risks match the current filter.</div>
          )}
          {allRisks.length === 0 && (
            <div className="rounded-xl border border-low/25 bg-low/5 p-6 flex items-center gap-3" data-testid="cra-risk-empty">
              <ShieldAlert className="w-5 h-5 text-low" />
              <div className="text-sm text-foreground/90">No correlated CRA risks right now — no overdue reporting, open high-severity vulnerabilities, control gaps or CE blockers were found in the live records.</div>
            </div>
          )}
        </div>
      )}

      <div className="text-[10px] font-mono text-muted-foreground">
        Ratings synthesised from live products, vulnerabilities, assessments, controls and the AI-grounding monitor · Obserra CRA v{d.version} · decision-support, not legal advice.
      </div>
    </div>
  );
}
