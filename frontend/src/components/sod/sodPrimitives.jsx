// Shared SoD presentational primitives (extracted from SodCommandCenter for reuse).
export const SEV = { Critical: "0 84% 60%", High: "35 90% 55%", Medium: "190 90% 50%", Low: "142 70% 45%" };
export const Chip = ({ v, map = SEV }) => <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full" style={{ background: `hsl(${map[v] || "220 10% 55%"} / 0.15)`, color: `hsl(${map[v] || "220 10% 55%"})` }}>{v}</span>;
export const ScoreTile = ({ label, v, suffix = "", accent = "199 89% 48%", testid }) => (
  <div className="rounded-lg bg-secondary/30 p-3" data-testid={testid}>
    <div className="font-head font-black text-2xl" style={{ color: `hsl(${accent})` }}>{v}<span className="text-xs font-normal text-muted-foreground">{suffix}</span></div>
    <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">{label}</div>
  </div>
);
export const ACTION_LABEL = { recertify: "Open recertification", revoke_all: "Revoke all roles", deactivate: "De-provision account", lock: "Emergency lock" };
export const TrendTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const p = payload[0]?.payload || {};
  return (
    <div className="rounded-lg border border-border bg-card p-2.5 text-xs shadow-lg" style={{ maxWidth: 240 }} data-testid="scorecard-trend-tip">
      <div className="font-bold mb-1">{label} · Gov {p.governance_score}/100</div>
      <div className="text-muted-foreground">Open SoD {p.open_sod} · Auto-rem {p.autoremediated} · Movers {p.movers ?? 0} · Residual {p.residual}</div>
      {p.note && <div className="mt-1.5 pt-1.5 border-t border-border text-[11px]">{p.note}</div>}
    </div>
  );
};
