const sevHsl = (s) => (s >= 20 ? "0 84% 60%" : s >= 12 ? "15 80% 55%" : s >= 6 ? "35 90% 55%" : "142 70% 45%");

export function RiskHeatmap({ matrix, onSelect }) {
  const cell = (l, i) => matrix.find((m) => m.likelihood === l && m.impact === i);
  return (
    <div data-testid="risk-heatmap">
      <div className="flex">
        <div className="flex flex-col justify-around pr-2 text-[9px] font-mono text-muted-foreground uppercase" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>
          Impact →
        </div>
        <div className="flex-1 space-y-1">
          {[5, 4, 3, 2, 1].map((i) => (
            <div key={i} className="flex items-center gap-1">
              <span className="w-3 text-[10px] font-mono text-muted-foreground text-right">{i}</span>
              {[1, 2, 3, 4, 5].map((l) => {
                const c = cell(l, i);
                const s = l * i;
                const hsl = sevHsl(s);
                const filled = c && c.count > 0;
                return (
                  <button key={l} data-testid={`heat-${l}-${i}`} disabled={!filled}
                    onClick={() => filled && onSelect?.(c.top)}
                    className="flex-1 h-11 rounded-sm flex items-center justify-center font-mono text-sm font-bold transition-transform duration-150 hover:scale-[1.06] disabled:cursor-default"
                    style={{
                      backgroundColor: filled ? `hsl(${hsl} / 0.85)` : `hsl(${hsl} / 0.07)`,
                      color: filled ? "hsl(222 40% 8%)" : "transparent",
                      border: `1px solid hsl(${hsl} / ${filled ? 0.9 : 0.15})`,
                    }}
                    title={filled ? `L${l}×I${i} · ${c.count} risk(s): ${c.refs.join(", ")}` : `L${l}×I${i}`}>
                    {filled ? c.count : ""}
                  </button>
                );
              })}
            </div>
          ))}
          <div className="flex gap-1 pl-4 pt-1">
            {[1, 2, 3, 4, 5].map((l) => (
              <span key={l} className="flex-1 text-center text-[10px] font-mono text-muted-foreground">{l}</span>
            ))}
          </div>
          <div className="text-center text-[9px] font-mono text-muted-foreground uppercase mt-0.5">Likelihood →</div>
        </div>
      </div>
    </div>
  );
}
