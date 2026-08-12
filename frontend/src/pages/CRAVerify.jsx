import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  BadgeCheck,
  Fingerprint,
  Landmark,
  Loader2,
  ShieldCheck,
  ShieldX,
  TriangleAlert,
} from "lucide-react";
import { api } from "@/lib/api";

function Pill({ children, good = false, bad = false }) {
  const tone = bad
    ? "border-crit/25 bg-crit/10 text-crit"
    : good
    ? "border-low/25 bg-low/10 text-low"
    : "border-primary/25 bg-primary/10 text-primary";
  return <span className={`px-2 py-0.5 rounded-full border text-[10px] font-mono ${tone}`}>{children}</span>;
}

export default function CRAVerify() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const response = await api.get(`/cra-public/verify/${token}`);
        setData(response.data);
        setError("");
      } catch (e) {
        setError(e.response?.data?.detail || "This auditor verification link is invalid or has expired.");
      }
    })();
  }, [token]);

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-6">
        <div className="max-w-lg bg-card fact-border rounded-xl p-8 text-center" data-testid="cra-verify-error">
          <TriangleAlert className="w-10 h-10 text-crit mx-auto" />
          <h1 className="font-head font-black text-2xl mt-4">Verification unavailable</h1>
          <p className="text-sm text-muted-foreground mt-2">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-7 h-7 animate-spin text-primary" />
      </div>
    );
  }

  const p = data.product;
  const intact = data.integrity?.chain_intact;

  return (
    <div className="min-h-screen bg-background" data-testid="cra-verify-page">
      <header className="border-b border-border bg-card">
        <div className="max-w-7xl mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-mono text-primary uppercase tracking-wider">
              <Landmark className="w-3.5 h-3.5" /> Obserra Auditor Verification
            </div>
            <h1 className="font-head font-black text-2xl mt-1">{p.name} {p.version}</h1>
            <div className="text-xs text-muted-foreground mt-1">{p.manufacturer_name}</div>
          </div>
          <div className="flex gap-2">
            <Pill>{p.ref}</Pill>
            <Pill good>EU CRA</Pill>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-5 space-y-5">
        <section
          className={`rounded-xl p-5 border ${intact ? "border-low/25 bg-low/5" : "border-crit/25 bg-crit/5"}`}
          data-testid="cra-verify-integrity"
        >
          <div className="flex items-center gap-4">
            {intact ? <ShieldCheck className="w-10 h-10 text-low" /> : <ShieldX className="w-10 h-10 text-crit" />}
            <div>
              <div className="font-head font-black text-xl">
                {intact ? "Hash-chain integrity verified" : "Hash-chain integrity FAILED"}
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                {data.integrity?.records_verified} regulatory records independently re-hashed
                {intact ? " — the compliance timeline is tamper-evident and intact." : ` — chain breaks at sequence ${data.integrity?.break_at_sequence}.`}
              </div>
            </div>
          </div>
        </section>

        <section className="grid md:grid-cols-4 gap-4">
          <div className="bg-card fact-border rounded-xl p-4">
            <ShieldCheck className="w-4 h-4 text-primary" />
            <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">Classification</div>
            <div className="font-head font-black text-xl mt-1">{p.classification || "Pending"}</div>
            <div className="text-xs text-muted-foreground mt-1">{p.classification_status}</div>
          </div>
          <div className="bg-card fact-border rounded-xl p-4">
            <Fingerprint className="w-4 h-4 text-ai" />
            <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">Conformity route</div>
            <div className="font-head font-bold text-sm mt-2">{p.pathway || "Not determined"}</div>
          </div>
          <div className="bg-card fact-border rounded-xl p-4">
            <BadgeCheck className="w-4 h-4 text-low" />
            <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">CE readiness</div>
            <div className="font-head font-black text-xl mt-1">{p.ce_status || "Not Ready"}</div>
            <div className="text-xs text-muted-foreground mt-1">Declaration: {p.declaration_status || "Not approved"}</div>
          </div>
          <div className="bg-card fact-border rounded-xl p-4">
            <Landmark className="w-4 h-4 text-high" />
            <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">Legal basis</div>
            <div className="text-xs mt-2">{data.regulation}</div>
            <div className="text-xs text-muted-foreground mt-1">{data.classification_implementing_regulation}</div>
          </div>
        </section>

        <section className="bg-card fact-border rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <h2 className="font-head font-black text-lg">Tamper-evident compliance timeline</h2>
            <p className="text-xs text-muted-foreground mt-1">
              Read-only event metadata and hash-chain values for this product. Private ledger payloads are never exposed.
            </p>
          </div>
          <div className="p-5 overflow-x-auto">
            <table className="w-full min-w-[900px] text-xs">
              <thead className="font-mono uppercase text-[9px] text-muted-foreground border-b border-border">
                <tr>
                  <th className="text-left py-3">Seq</th>
                  <th className="text-left py-3">Timestamp</th>
                  <th className="text-left py-3">Event</th>
                  <th className="text-left py-3">Object</th>
                  <th className="text-left py-3">Legal basis</th>
                  <th className="text-left py-3">Record hash</th>
                </tr>
              </thead>
              <tbody data-testid="cra-verify-timeline">
                {(data.timeline || []).map((item) => (
                  <tr key={`${item.sequence}:${item.record_hash}`} className="border-b border-border/60">
                    <td className="py-3 font-mono">{item.sequence}</td>
                    <td className="py-3">{new Date(item.ts).toLocaleString()}</td>
                    <td className="py-3 font-medium">{item.event_type}</td>
                    <td className="py-3"><span className="font-mono text-ai">{item.object_ref}</span></td>
                    <td className="py-3 max-w-[240px]">{(item.legal_refs || []).join(", ")}</td>
                    <td className="py-3 font-mono text-[9px]">{String(item.record_hash).slice(0, 18)}…</td>
                  </tr>
                ))}
                {!(data.timeline || []).length && (
                  <tr><td colSpan={6} className="py-4 text-muted-foreground">No ledger events recorded for this product yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <div className="rounded-lg border border-border bg-secondary/20 p-4 text-xs text-muted-foreground">
          Verified at {new Date(data.verified_at).toLocaleString()} · link expires {new Date(data.expires_at).toLocaleString()}. {data.note}
        </div>
      </main>
    </div>
  );
}
