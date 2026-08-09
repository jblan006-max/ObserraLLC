import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { ShieldAlert, TrendingUp, Sparkles, Loader2, Lock, Clock } from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const Tile = ({ label, v, suffix = "", accent = "199 89% 60%", raw, testid }) => (
  <div className="rounded-xl bg-white/[0.04] border border-white/10 p-4" data-testid={testid}>
    <div className="font-black text-3xl leading-none" style={{ color: raw || `hsl(${accent})` }}>
      {v}<span className="text-sm font-normal text-white/50">{suffix}</span>
    </div>
    <div className="text-xs text-white/60 mt-1.5 leading-tight">{label}</div>
  </div>
);

export default function ShareDigest() {
  const { token } = useParams();
  const [snap, setSnap] = useState(null);
  const [meta, setMeta] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/sap/public/digest-share/${token}`)
      .then(({ data }) => { setSnap(data.snapshot); setMeta({ created_at: data.created_at, expires_at: data.expires_at }); })
      .catch((e) => setErr(e?.response?.data?.detail || "This shared digest link is invalid or has expired."))
      .finally(() => setLoading(false));
  }, [token]);

  const brand = snap?.brand || {};
  const accent = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(brand.accent || "") ? brand.accent : "";
  const logo = brand.logo || `${BACKEND}/brand-lockup.png`;

  return (
    <div className="min-h-screen bg-[#0a1226] text-white px-4 py-10 sm:py-16" data-testid="share-digest-page">
      {accent && <div style={{ height: 4, background: accent }} data-testid="share-accent-bar" />}
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <img src={logo} alt="brand" className="h-9 w-auto max-w-[180px] object-contain"
               onError={(e) => { e.currentTarget.style.display = "none"; }} data-testid="share-brand" />
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/40">SAP UAC</span>
        </div>

        {loading && (
          <div className="flex items-center gap-3 text-white/60" data-testid="share-loading">
            <Loader2 className="w-5 h-5 animate-spin" /> Loading the live governance snapshot…
          </div>
        )}

        {!loading && err && (
          <div className="rounded-xl border border-white/10 bg-white/[0.04] p-8 text-center" data-testid="share-error">
            <Lock className="w-8 h-8 mx-auto text-white/40 mb-3" />
            <div className="text-lg font-semibold">Link unavailable</div>
            <p className="text-sm text-white/60 mt-1">{err}</p>
          </div>
        )}

        {!loading && snap && (
          <div className="space-y-6" data-testid="share-content">
            <div>
              <div className="text-[11px] font-mono uppercase tracking-widest text-white/40">Read-only snapshot</div>
              <h1 className="font-black text-3xl sm:text-4xl tracking-tight mt-1">SAP Access Governance Digest</h1>
              <p className="text-sm text-white/60 mt-2">
                A point-in-time executive snapshot of the SAP access posture. No login required.
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <Tile testid="share-score" label="Governance score" v={snap.scorecard?.current?.governance_score} suffix="/100" raw={accent || undefined} accent="142 70% 55%" />
              <Tile testid="share-open-sod" label="Open SoD conflicts" v={snap.digest?.open_sod} accent="0 84% 65%" />
              <Tile testid="share-sev" label="Critical / High / Medium"
                    v={`${snap.digest?.sev?.Critical ?? 0}/${snap.digest?.sev?.High ?? 0}/${snap.digest?.sev?.Medium ?? 0}`} accent="35 90% 60%" />
              <Tile testid="share-residual" label="Terminated w/ residual access" v={snap.digest?.residual_count} accent="35 90% 60%" />
              <Tile testid="share-autorem" label="Auto-remediated (24h)" v={snap.digest?.autorem_24h} accent="190 90% 60%" />
              <Tile testid="share-risk" label="Avg SAP access risk" v={snap.digest?.avg_risk} suffix="/100" accent="199 89% 60%" />
            </div>

            <div className="rounded-xl border border-white/10 bg-white/[0.04] p-5" data-testid="share-why">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-4 h-4" style={{ color: "hsl(199 89% 60%)" }} />
                <span className="text-[10px] font-mono uppercase tracking-wider text-white/50">AI summary</span>
                {snap.scorecard?.forecast?.next_week_score != null && (
                  <span className="ml-auto text-[11px] font-mono px-2 py-0.5 rounded-full"
                        style={{ background: (snap.scorecard.forecast.delta >= 0 ? "hsl(142 70% 45% / 0.18)" : "hsl(0 84% 60% / 0.18)"),
                                 color: (snap.scorecard.forecast.delta >= 0 ? "hsl(142 70% 65%)" : "hsl(0 84% 68%)") }}>
                    Forecast next wk {snap.scorecard.forecast.next_week_score}/100 ({snap.scorecard.forecast.delta >= 0 ? "+" : ""}{snap.scorecard.forecast.delta})
                  </span>
                )}
              </div>
              <p className="text-sm text-white/85 leading-relaxed" data-testid="share-why-text">{snap.why || "—"}</p>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="rounded-xl border border-white/10 bg-white/[0.04] p-5" data-testid="share-areas">
                <div className="flex items-center gap-2 mb-3"><ShieldAlert className="w-4 h-4" style={{ color: "hsl(0 84% 65%)" }} />
                  <span className="text-sm font-semibold">Open conflicts by risk area</span></div>
                <div className="space-y-2">
                  {Object.entries(snap.open_conflicts_by_area || {}).slice(0, 6).map(([a, n]) => (
                    <div key={a} className="flex items-center justify-between text-sm">
                      <span className="text-white/75">{a}</span>
                      <span className="font-mono text-white/90">{n}</span>
                    </div>
                  ))}
                  {!Object.keys(snap.open_conflicts_by_area || {}).length && <div className="text-sm text-white/50">No open conflicts ✓</div>}
                </div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.04] p-5" data-testid="share-systems">
                <div className="flex items-center gap-2 mb-3"><TrendingUp className="w-4 h-4" style={{ color: "hsl(190 90% 60%)" }} />
                  <span className="text-sm font-semibold">Open conflicts by SAP system</span></div>
                <div className="space-y-2">
                  {Object.entries(snap.open_conflicts_by_system || {}).slice(0, 6).map(([s, n]) => (
                    <div key={s} className="flex items-center justify-between text-sm">
                      <span className="text-white/75 font-mono">{s}</span>
                      <span className="font-mono text-white/90">{n}</span>
                    </div>
                  ))}
                  {!Object.keys(snap.open_conflicts_by_system || {}).length && <div className="text-sm text-white/50">No open conflicts ✓</div>}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-[11px] text-white/40 pt-4 border-t border-white/10">
              <Clock className="w-3.5 h-3.5" />
              <span>Snapshot generated {snap.generated_at ? new Date(snap.generated_at).toLocaleString() : "—"}</span>
              {meta?.expires_at && <span>· link expires {new Date(meta.expires_at).toLocaleDateString()}</span>}
              <span className="ml-auto">Obserra — Executive Protection &amp; Intelligence LLC · Confidential</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
