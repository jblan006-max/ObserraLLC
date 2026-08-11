import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { AlertTriangle, FileText, Gavel, Layers, Loader2, ShieldCheck, Target } from "lucide-react";

const fmtDT = (s) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const CRIT = { Critical: "0 84% 60%", High: "15 80% 55%", Medium: "35 90% 55%", Low: "142 70% 45%" };
const effColor = (v) => (v >= 75 ? "142 70% 45%" : v >= 55 ? "35 90% 55%" : "0 84% 60%");

function Tile({ label, value }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <div className="text-[9px] font-mono uppercase tracking-wider text-white/40">{label}</div>
      <div className="font-head font-black text-2xl mt-1">{value}</div>
    </div>
  );
}

export default function CIAuditorPortal() {
  const { token } = useParams();
  const [meta, setMeta] = useState(null);
  const [data, setData] = useState(null);
  const [dlName, setDlName] = useState("");
  const [viewerName, setViewerName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const enterPortal = (who) => {
    setLoading(true);
    api
      .get(`/control-intelligence/public/auditor-link/${token}${who ? `?who=${encodeURIComponent(who)}` : ""}`)
      .then(({ data }) => setData(data))
      .catch((e) => setError(e?.response?.data?.detail || "This auditor link is invalid or has expired."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    api
      .get(`/control-intelligence/public/auditor-link/${token}/meta`)
      .then(({ data }) => {
        if (!data.valid) {
          setError("This auditor link is invalid or has expired.");
          setLoading(false);
          return;
        }
        setMeta(data);
        if (data.ask_name) setLoading(false);
        else enterPortal("");
      })
      .catch(() => {
        setError("This auditor link is invalid or has expired.");
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (loading)
    return (
      <div className="min-h-screen bg-[#050810] text-white flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
      </div>
    );

  if (error)
    return (
      <div className="min-h-screen bg-[#050810] text-white flex items-center justify-center p-6" data-testid="ci-auditor-error">
        <div className="max-w-md text-center space-y-3">
          <AlertTriangle className="w-10 h-10 mx-auto text-red-500" />
          <h1 className="font-head font-black text-2xl">Auditor link unavailable</h1>
          <p className="text-sm text-white/60">{error}</p>
        </div>
      </div>
    );

  if (meta?.ask_name && !data)
    return (
      <div className="min-h-screen bg-[#050810] text-white flex items-center justify-center p-6" data-testid="ci-auditor-namegate">
        <div className="max-w-sm w-full space-y-4 text-center">
          <Gavel className="w-9 h-9 mx-auto text-emerald-400" />
          <h1 className="font-head font-black text-2xl">{meta.org_name} — Control Assurance</h1>
          <p className="text-sm text-white/60">For the access record, please enter your name before viewing this read-only evidence.</p>
          <input
            data-testid="ci-auditor-viewer-name"
            value={viewerName}
            onChange={(e) => setViewerName(e.target.value)}
            placeholder="Your name"
            className="w-full bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-emerald-400/60 text-center"
          />
          <button
            data-testid="ci-auditor-enter"
            disabled={!viewerName.trim()}
            onClick={() => enterPortal(viewerName.trim())}
            className="w-full px-4 py-2.5 rounded-lg bg-emerald-400 text-[#050810] font-head font-bold text-sm disabled:opacity-40"
          >
            View assurance evidence
          </button>
          <button data-testid="ci-auditor-skip" onClick={() => enterPortal("")} className="block w-full text-[11px] text-white/40 hover:text-white/70">
            Continue anonymously
          </button>
        </div>
      </div>
    );

  const pdfUrl = `${process.env.REACT_APP_BACKEND_URL}/api/control-intelligence/public/auditor-link/${token}/brief.pdf${
    dlName ? `?who=${encodeURIComponent(dlName)}` : ""
  }`;

  return (
    <div className="min-h-screen bg-[#050810] text-white" data-testid="ci-auditor-portal">
      <div className="max-w-4xl mx-auto px-5 py-10 space-y-8">
        <header className="space-y-2">
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/40 flex items-center gap-2">
            <Gavel className="w-3.5 h-3.5" /> OBSERRA · READ-ONLY CONTROL ASSURANCE FOR AUDIT
          </span>
          <h1 className="font-head font-black text-3xl lg:text-4xl tracking-tight" data-testid="ci-auditor-title">
            {data.org_name} — Control Intelligence
          </h1>
          <p className="text-sm text-white/60">
            Generated {fmtDT(data.generated_at)} · link expires {fmtDT(data.expires_at)}
          </p>
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <input
              data-testid="ci-auditor-dl-name"
              value={dlName}
              onChange={(e) => setDlName(e.target.value)}
              placeholder="Your name (stamped on the PDF)"
              className="bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-emerald-400/60 w-60"
            />
            <a
              href={pdfUrl}
              data-testid="ci-auditor-download"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-400 text-[#050810] font-head font-bold text-sm hover:opacity-90 transition-opacity"
            >
              <FileText className="w-4 h-4" /> Download signed PDF
            </a>
          </div>
          <p className="text-[11px] text-white/30">
            The PDF is watermarked with your name + timestamp, a QR back to this live link, and a "Verified by Obserra" SHA-256 integrity seal.
          </p>
        </header>

        <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="ci-auditor-tiles">
          <Tile label="Control health" value={`${data.health}/100`} />
          <Tile label="Controls" value={data.total} />
          <Tile label="Passing" value={data.passing} />
          <Tile label="Avg effectiveness" value={`${data.avg_eff}%`} />
          <Tile label="Coverage" value={`${data.coverage}%`} />
        </section>

        <section data-testid="ci-auditor-frameworks">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-white/40 mb-2">
            <Layers className="w-3.5 h-3.5" /> Framework readiness
          </div>
          {(data.frameworks || []).length === 0 ? (
            <p className="text-sm text-white/50">No framework coverage returned.</p>
          ) : (
            <div className="grid sm:grid-cols-2 gap-2">
              {data.frameworks.map((f) => (
                <div key={f.framework} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-head font-bold text-sm">{f.framework}</span>
                    <span className="text-xs font-mono" style={{ color: `hsl(${effColor(f.coverage)})` }}>
                      {f.coverage}%
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${f.coverage}%`, background: `hsl(${effColor(f.coverage)})` }} />
                  </div>
                  <div className="text-[10px] text-white/40 mt-1.5">{f.passing}/{f.controls} passing</div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section data-testid="ci-auditor-weak">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-white/40 mb-2">
            <Target className="w-3.5 h-3.5" /> Lowest-effectiveness controls
          </div>
          <div className="space-y-2">
            {(data.weak_controls || []).map((c) => {
              const cc = CRIT[c.criticality] || "190 80% 50%";
              return (
                <div key={c.control_id} className="rounded-lg border border-white/10 bg-white/[0.03] p-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <span className="font-mono text-[10px] text-emerald-300">{c.control_id}</span>
                    <div className="text-sm truncate">{c.name}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full" style={{ background: `hsl(${cc} / 0.15)`, color: `hsl(${cc})` }}>
                      {c.criticality || "—"}
                    </span>
                    <span className="text-xs font-mono" style={{ color: `hsl(${effColor(c.effectiveness)})` }}>
                      {c.effectiveness}%
                    </span>
                    <span className="text-[10px] font-mono text-white/50">{c.status}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <footer className="text-center text-[11px] text-white/30 pt-6 border-t border-white/10 flex items-center justify-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5" />
          Read-only control-assurance evidence — Obserra Control Intelligence. Effectiveness, evidence and coverage are FACT values; health &amp; coverage roll-ups are MODELLED.
        </footer>
      </div>
    </div>
  );
}
