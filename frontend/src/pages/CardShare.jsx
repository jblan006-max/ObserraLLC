import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { ShieldCheck, Plug, FileText, AlertTriangle, Loader2, Wrench } from "lucide-react";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const money = (n) => (n == null ? "—" : n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}k` : `$${Math.round(n)}`);
const RATE = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };
const CONN_TONE = { ok: "142 70% 45%", healthy: "142 70% 45%", warn: "35 90% 55%", "action-capable": "35 90% 55%", degraded: "35 90% 55%", down: "0 84% 60%", unavailable: "0 84% 60%" };

export default function CardShare() {
  const { token } = useParams();
  const [snap, setSnap] = useState(null);
  const [meta, setMeta] = useState(null);
  const [sha, setSha] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dlName, setDlName] = useState("");

  useEffect(() => {
    api.get(`/agents/public/card-share/${token}`)
      .then(({ data }) => { setSnap(data.snapshot); setMeta({ created_at: data.created_at, expires_at: data.expires_at, created_by: data.created_by }); setSha(data.snapshot_sha256 || ""); })
      .catch((e) => setError(e?.response?.data?.detail || "This shared card link is invalid or has expired."))
      .finally(() => setLoading(false));
  }, [token]);

  const pdfUrl = `${process.env.REACT_APP_BACKEND_URL}/api/agents/public/card-share/${token}/card.pdf${dlName ? `?who=${encodeURIComponent(dlName)}` : ""}`;

  if (loading) return <div className="min-h-screen bg-[#050810] text-white flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-ai" /></div>;
  if (error) return (
    <div className="min-h-screen bg-[#050810] text-white flex items-center justify-center p-6" data-testid="card-share-error">
      <div className="max-w-md text-center space-y-3"><AlertTriangle className="w-10 h-10 mx-auto text-crit" /><h1 className="font-head font-black text-2xl">Shared card unavailable</h1><p className="text-sm text-white/60">{error}</p></div>
    </div>
  );

  const rc = RATE[snap.rating] || "190 80% 50%";
  return (
    <div className="min-h-screen bg-[#050810] text-white" data-testid="card-share">
      <div className="max-w-3xl mx-auto px-5 py-10 space-y-8">
        <header className="space-y-2">
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/40">OBSERRA · READ-ONLY SHARED DETAIL CARD</span>
          <div className="text-[11px] font-mono text-white/40">{snap.ref || "Detail card"}</div>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="card-share-title">{snap.title}</h1>
          <p className="text-sm text-white/60">{snap.org_name || "Organization"} · generated {fmtDT(snap.generated_at)} · link expires {fmtDT(meta?.expires_at)}</p>

          <div className="flex flex-wrap items-center gap-2 pt-1" data-testid="card-share-scores">
            {snap.rating && <span className="text-xs font-mono font-bold px-3 py-1 rounded-full" style={{ background: `hsl(${rc} / 0.15)`, color: `hsl(${rc})` }}>{snap.rating} RISK</span>}
            {snap.score != null && <span className="text-xs font-mono px-3 py-1 rounded-full bg-white/[0.08]">Score {snap.score}/100</span>}
            {snap.ale != null && <span className="text-xs font-mono font-bold px-3 py-1 rounded-full" style={{ background: "hsl(15 80% 55% / 0.15)", color: "hsl(15 80% 55%)" }}>ALE {money(snap.ale)}</span>}
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-3">
            <input data-testid="card-share-dl-name" value={dlName} onChange={(e) => setDlName(e.target.value)} placeholder="Your name (stamped on the PDF)" className="bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-ai/60 w-56" />
            <a href={pdfUrl} data-testid="card-share-download" className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-ai text-[#050810] font-head font-bold text-sm hover:opacity-90 transition-opacity"><FileText className="w-4 h-4" /> Download signed PDF</a>
          </div>
          <p className="text-[11px] text-white/30">Each download is watermarked with your name + timestamp, a QR back to this live card, and a "Verified by Obserra" integrity seal (SHA-256{sha ? ` · ${sha.slice(0, 12)}` : ""}).</p>
        </header>

        {(snap.compliance_refs || []).length > 0 && (
          <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4" data-testid="card-share-compliance">
            <div className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-1.5 flex items-center gap-1.5"><ShieldCheck className="w-3 h-3" /> Compliance alignment{snap.compliance_pct != null && <span className="text-white/60"> · {snap.compliance_pct}% area coverage</span>}</div>
            <div className="flex flex-wrap gap-1.5">
              {snap.compliance_refs.map((c) => <span key={c} className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-white/[0.06]">{c}</span>)}
            </div>
          </section>
        )}

        {(snap.facets || []).length > 0 && (
          <section className="grid grid-cols-1 sm:grid-cols-2 gap-2" data-testid="card-share-facets">
            {snap.facets.map((f, i) => (
              <div key={`${f.label}-${i}`} className="rounded-lg bg-white/[0.03] border border-white/10 p-3">
                <div className="text-[9px] font-mono uppercase tracking-wider text-white/40">{f.label}</div>
                <div className="text-sm mt-0.5 break-words text-white/85">{f.value || "—"}</div>
              </div>
            ))}
          </section>
        )}

        {(snap.connectors || []).length > 0 && (
          <section data-testid="card-share-connectors">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-white/40 mb-1.5"><Plug className="w-3 h-3" /> Connectors &amp; data sources</div>
            <div className="flex flex-wrap gap-1.5">
              {snap.connectors.map((c, i) => {
                const tone = c.status ? (CONN_TONE[String(c.status).toLowerCase()] || "215 15% 60%") : "215 15% 60%";
                return (
                  <span key={i} className="inline-flex items-center gap-1.5 text-[11px] font-mono px-2.5 py-1 rounded-full border" style={{ borderColor: `hsl(${tone} / 0.4)`, background: `hsl(${tone} / 0.1)` }}>
                    {c.status && <span className="w-1.5 h-1.5 rounded-full" style={{ background: `hsl(${tone})` }} />}
                    <span className="text-white/90">{c.name}</span>
                    {c.detail && <span className="text-white/45">· {c.detail}</span>}
                  </span>
                );
              })}
            </div>
          </section>
        )}

        {snap.summary && (
          <section className="rounded-xl border border-white/10 bg-white/[0.03] p-4" data-testid="card-share-summary">
            <div className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-1.5">AI strategic brief</div>
            <p className="text-sm text-white/80 whitespace-pre-line">{snap.summary}</p>
          </section>
        )}

        {(snap.recommendations || []).length > 0 && (
          <section data-testid="card-share-recommendations">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-white/40 mb-1.5"><Wrench className="w-3 h-3" /> Recommendations &amp; fixes</div>
            <ul className="space-y-1.5">
              {snap.recommendations.map((r, i) => <li key={i} className="text-sm text-white/80 flex items-start gap-2"><span className="text-ai">→</span> {r}</li>)}
            </ul>
          </section>
        )}

        <footer className="text-center text-[11px] text-white/30 pt-6 border-t border-white/10">Read-only evidence — generated by Obserra Control Intelligence. Link expires {fmtDT(meta?.expires_at)}.</footer>
      </div>
    </div>
  );
}
