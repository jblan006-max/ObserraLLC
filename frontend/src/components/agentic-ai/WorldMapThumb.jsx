// Compact equirectangular world-map thumbnail plotting where a shared card was opened/downloaded.
// Continents are simplified polygons (recognizable at thumbnail scale); dots are actual access points.
const CONTINENTS = [
  [[-168, 66], [-95, 68], [-52, 60], [-80, 25], [-105, 20], [-125, 40], [-140, 60]],
  [[-80, 10], [-60, 5], [-35, -8], [-40, -23], [-65, -55], [-75, -45], [-82, -5]],
  [[-10, 60], [0, 50], [15, 55], [30, 60], [40, 48], [20, 40], [0, 43], [-9, 44]],
  [[-17, 35], [10, 37], [35, 32], [51, 12], [40, -15], [20, -35], [10, -20], [-5, 5], [-16, 15]],
  [[30, 60], [60, 70], [100, 72], [140, 66], [170, 66], [145, 45], [120, 30], [100, 10], [78, 8], [60, 25], [45, 40], [35, 45]],
  [[113, -22], [130, -12], [145, -15], [153, -28], [146, -39], [130, -32], [115, -35]],
];

export function WorldMapThumb({ points = [], width = 300, height = 150, onClusterClick }) {
  const proj = (lon, lat) => [((lon + 180) / 360) * width, ((90 - lat) / 180) * height];
  const poly = (pts) => pts.map(([lon, lat]) => proj(lon, lat).join(",")).join(" ");
  const dots = points.filter((p) => typeof p.lat === "number" && typeof p.lon === "number");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ maxWidth: width }}
      className="rounded-md border border-border bg-[#0a1120]" data-testid="access-log-map">
      {[1, 2, 3].map((i) => <line key={`h${i}`} x1="0" x2={width} y1={(height / 4) * i} y2={(height / 4) * i} stroke="hsl(215 30% 22%)" strokeWidth="0.5" />)}
      {[1, 2, 3, 4, 5].map((i) => <line key={`v${i}`} y1="0" y2={height} x1={(width / 6) * i} x2={(width / 6) * i} stroke="hsl(215 30% 22%)" strokeWidth="0.5" />)}
      {CONTINENTS.map((c, i) => <polygon key={i} points={poly(c)} fill="hsl(215 25% 30% / 0.55)" stroke="hsl(215 25% 42%)" strokeWidth="0.5" />)}
      {(() => {
        const clusters = {};
        dots.forEach((p) => {
          const key = `${p.lat.toFixed(1)},${p.lon.toFixed(1)}`;
          const c = clusters[key] || (clusters[key] = { lat: p.lat, lon: p.lon, count: 0, download: false, anomaly: false, labels: [], points: [] });
          c.count += 1;
          c.points.push(p);
          if (p.kind === "download") c.download = true;
          if (p.anomaly) c.anomaly = true;
          if (p.label) c.labels.push(p.label);
        });
        const clickable = typeof onClusterClick === "function";
        return Object.values(clusters).map((c, i) => {
          const [x, y] = proj(c.lon, c.lat);
          const r = Math.min(15, 3 + 2.8 * Math.sqrt(c.count));
          const color = c.anomaly ? "hsl(0 84% 62%)" : c.download ? "hsl(190 90% 55%)" : "hsl(142 70% 50%)";
          return (
            <g key={i} data-testid={clickable ? `globe-pin-${i}` : undefined}
              style={clickable ? { cursor: "pointer" } : undefined}
              onClick={clickable ? () => onClusterClick({ label: c.labels[0] || "", points: c.points }) : undefined}>
              {clickable && <circle cx={x} cy={y} r={Math.max(r, 9)} fill="transparent" />}
              <circle cx={x} cy={y} r={r} fill={color} opacity="0.22" pointerEvents="none" />
              <circle cx={x} cy={y} r={Math.min(4.5, 2 + c.count * 0.35)} fill={color} pointerEvents="none">
                <title>{`${c.count} access(es)${c.labels[0] ? " · " + c.labels[0] : ""}${clickable ? " · click to inspect" : ""}`}</title>
              </circle>
              {c.count > 1 && <text x={x} y={y + 2.6} textAnchor="middle" fontSize="6.5" fill="#0a1120" fontWeight="700" pointerEvents="none">{c.count}</text>}
            </g>
          );
        });
      })()}
    </svg>
  );
}
