import { RadialBar, RadialBarChart, PolarAngleAxis, ResponsiveContainer } from "recharts";

export function HealthGauge({ score, grade }) {
  const color = score >= 75 ? "hsl(142 70% 45%)" : score >= 60 ? "hsl(35 90% 55%)" : "hsl(15 80% 55%)";
  const data = [{ name: "health", value: score, fill: color }];
  return (
    <div className="relative w-full h-full flex items-center justify-center">
      <ResponsiveContainer width="100%" height={220}>
        <RadialBarChart innerRadius="72%" outerRadius="100%" data={data} startAngle={220} endAngle={-40}>
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar dataKey="value" cornerRadius={8} background={{ fill: "hsl(215 30% 16%)" }} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pt-4">
        <div className="font-head font-black text-6xl tracking-tight" style={{ color }}>{score}</div>
        <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground mt-1">Health Index · {grade}</div>
      </div>
    </div>
  );
}
