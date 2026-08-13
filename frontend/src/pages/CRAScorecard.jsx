import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Download, Landmark, Loader2, ShieldAlert, TriangleAlert, Clock3 } from "lucide-react";
import { api } from "@/lib/api";

const STATUS_TONE = {
  Implemented: "border-low/25 bg-low/10 text-low",
  Partial: "border-high/25 bg-high/10 text-high",
  Gap: "border-crit/25 bg-crit/10 text-crit",
  "Not Started": "border-border bg-secondary text-muted-foreground",
};
const RISK_TONE = {
  Low: "border-low/25 bg-low/10 text-low",
  Medium: "border-high/25 bg-high/10 text-high",
  High: "border-crit/25 bg-crit/10 text-crit",
  Unknown: "border-border bg-secondary text-muted-foreground",
};

function Tag({ map, value }) {
  return <span className={`px-2 py-0.5 rounded-full border text-[10px] font-mono ${map[value] || "border-border bg-secondary text-muted-foreground"}`}>{value}</span>;
}

export default function CRAScorecard() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [dl, setDl] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const response = await api.get(`/cra-public/scorecard/${token}`);
        setData(response.data);
        setError("");
      } catch (e) {
        setError(e.response?.data?.detail || "This compliance scorecard link is invalid or has expired.");
      }
    })();
  }, [token]);

  const downloadPdf = async () => {
    setDl(true);
    try {
      const response = await api.get(`/cra-public/scorecard/${token}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = url; a.download = "obserra-eu-cra-compliance-scorecard.pdf";
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    } catch { /* noop */ } finally { setDl(false); }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-6">
        <div className="max-w-lg bg-card fact-border rounded-xl p-8 text-center" data-testid="cra-scorecard-error">
          <TriangleAlert className="w-10 h-10 text-crit mx-auto" />
          <h1 className="font-head font-black text-2xl mt-4">Scorecard unavailable</h1>
          <p className="text-sm text-muted-foreground mt-2">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="min-h-screen bg-background flex items-center justify-center"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>;
  }

  const o = data.overall || {};
  const pct = o.percentage || 0;
  const chips = [
    ["Implemented", o.implemented || 0, "text-low"],
    ["Partial", o.partial || 0, "text-high"],
    ["Gaps", o.gaps || 0, "text-crit"],
    ["Not started", o.not_started || 0, "text-muted-foreground"],
    ["High risk", o.high_risk || 0, "text-crit"],
    ["Requirements", o.requirements_total || 0, "text-primary"],
  ];

  return (
    <div className="min-h-screen bg-background" data-testid="cra-scorecard-page">
      <header className="border-b border-border bg-card">
        <div className="max-w-6xl mx-auto px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-mono text-primary uppercase tracking-wider"><Landmark className="w-3.5 h-3.5" /> Obserra Compliance Scorecard</div>
            <h1 className="font-head font-black text-2xl mt-1">{data.organization}</h1>
            <div className="text-xs text-muted-foreground mt-1">{data.regulation} · read-only · expires {new Date(data.expires_at).toLocaleDateString()}</div>
          </div>
          <div className="flex items-center gap-2">
            {data.next_deadline && (
              <div className="inline-flex items-center gap-2 rounded-full border border-high/30 bg-high/10 px-3.5 py-1.5 text-xs font-head font-bold text-high">
                <Clock3 className="w-3.5 h-3.5" /> {data.next_deadline.days_remaining} days to next CRA deadline
              </div>
            )}
            <button onClick={downloadPdf} disabled={dl} data-testid="cra-scorecard-download" className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">
              {dl ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Download PDF
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-5 space-y-5">
        <section className="grid lg:grid-cols-4 gap-4">
          <div className="bg-card fact-border rounded-xl p-5">
            <div className="text-[10px] font-mono uppercase text-muted-foreground">Overall CRA compliance</div>
            <div className="font-head font-black text-5xl mt-2" data-testid="cra-scorecard-overall">{pct}%</div>
            <div className="mt-3 h-2 rounded-full bg-secondary overflow-hidden"><div className="h-full bg-low" style={{ width: `${pct}%` }} /></div>
            <div className="text-[10px] text-muted-foreground mt-2">{o.products_assessed || 0}/{o.products_total || 0} products assessed</div>
          </div>
          <div className="lg:col-span-3 grid grid-cols-2 sm:grid-cols-3 gap-3">
            {chips.map(([label, value, cls]) => (
              <div key={label} className="bg-card fact-border rounded-xl p-4">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">{label}</div>
                <div className={`font-head font-black text-2xl mt-1 ${cls}`}>{value}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-card fact-border rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-high" />
            <div>
              <h2 className="font-head font-black text-lg">Top gaps to close</h2>
              <p className="text-xs text-muted-foreground">Requirements with the lowest coverage or highest risk. Product names and internal records are not exposed.</p>
            </div>
          </div>
          <div className="p-5 overflow-x-auto">
            <table className="w-full min-w-[720px] text-xs">
              <thead className="font-mono uppercase text-[9px] text-muted-foreground border-b border-border">
                <tr><th className="text-left py-3">Control</th><th className="text-left py-3">Legal basis</th><th className="text-left py-3">Compliance</th><th className="text-left py-3">Status</th><th className="text-left py-3">Risk</th></tr>
              </thead>
              <tbody data-testid="cra-scorecard-gaps">
                {(data.top_gaps || []).map((g) => (
                  <tr key={g.requirement_id} className="border-b border-border/60">
                    <td className="py-3 pr-3"><div className="font-mono text-[10px] text-ai">{g.requirement_id}</div><div className="font-head font-bold mt-0.5">{g.title}</div><div className="text-[10px] text-muted-foreground">{g.domain}{g.assessed ? ` · ${g.conforming}/${g.assessed} conforming` : ""}</div></td>
                    <td className="py-3 pr-3 text-muted-foreground">{(g.legal_refs || []).join(", ")}</td>
                    <td className="py-3 pr-3">{g.compliance_rate === null || g.compliance_rate === undefined ? "Not assessed" : `${g.compliance_rate}%`}</td>
                    <td className="py-3 pr-3"><Tag map={STATUS_TONE} value={g.status} /></td>
                    <td className="py-3"><Tag map={RISK_TONE} value={g.risk} /></td>
                  </tr>
                ))}
                {!(data.top_gaps || []).length && <tr><td colSpan={5} className="py-4 text-low">No open gaps — every assessed control is fully implemented.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <div className="rounded-lg border border-border bg-secondary/20 p-4 text-xs text-muted-foreground">
          Generated {new Date(data.generated_at).toLocaleString()} · link expires {new Date(data.expires_at).toLocaleString()}. {data.note}
        </div>
      </main>
    </div>
  );
}
