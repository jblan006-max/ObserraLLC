import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  BadgeCheck,
  Building2,
  CheckCircle2,
  FileCheck2,
  Loader2,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

function Pill({ children, good = false }) {
  return (
    <span
      className={`px-2 py-0.5 rounded-full border text-[10px] font-mono ${
        good
          ? "border-low/25 bg-low/10 text-low"
          : "border-primary/25 bg-primary/10 text-primary"
      }`}
    >
      {children}
    </span>
  );
}

export default function CRACertificationPortal() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [answers, setAnswers] = useState([]);
  const [signoff, setSignoff] = useState({
    decision: "Conforming",
    assessor_name: "",
    provider_reference: "",
    findings: "",
    artifact_refs: "",
    comment: "",
  });

  const load = async () => {
    try {
      const response = await api.get(`/cra-public/portal/${token}`);
      setData(response.data);
      setAnswers(response.data.assessment?.answers || []);
      setError("");
    } catch (e) {
      setError(
        e.response?.data?.detail ||
          "Certification Portal link is invalid or unavailable."
      );
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const requirementIndex = useMemo(() => {
    const index = {};
    for (const item of data?.regulation?.requirements || []) {
      index[item.requirement_id] = item;
    }
    return index;
  }, [data]);

  const updateAnswer = (id, patch) => {
    setAnswers((current) =>
      current.map((item) =>
        item.requirement_id === id ? { ...item, ...patch } : item
      )
    );
  };

  const saveAssessment = async () => {
    setBusy(true);
    try {
      await api.put(`/cra-public/portal/${token}/assessment`, { answers });
      toast.success("CRA readiness assessment saved.");
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to save assessment.");
    } finally {
      setBusy(false);
    }
  };

  const external = data?.external_assessments?.[0];

  const saveSignoff = async () => {
    if (!external) return;
    setBusy(true);
    try {
      await api.post(
        `/cra-public/portal/${token}/signoff/${external.ref}`,
        {
          ...signoff,
          findings: signoff.findings
            .split("\n")
            .map((value) => value.trim())
            .filter(Boolean),
          artifact_refs: signoff.artifact_refs
            .split("\n")
            .map((value) => value.trim())
            .filter(Boolean),
        }
      );
      toast.success("External conformity assessment sign-off recorded.");
      await load();
    } catch (e) {
      toast.error(
        e.response?.data?.detail || "Unable to record external sign-off."
      );
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-6">
        <div className="max-w-lg bg-card fact-border rounded-xl p-8 text-center">
          <TriangleAlert className="w-10 h-10 text-crit mx-auto" />
          <h1 className="font-head font-black text-2xl mt-4">
            Certification Portal unavailable
          </h1>
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

  const product = data.product;
  const isVendor = data.role === "vendor";

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="max-w-7xl mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <div>
            <div className="text-[10px] font-mono text-primary uppercase tracking-wider">
              Obserra Secure Certification Portal
            </div>
            <h1 className="font-head font-black text-2xl mt-1">
              {product.name} {product.version}
            </h1>
            <div className="text-xs text-muted-foreground mt-1">
              {product.manufacturer_name}
            </div>
          </div>
          <div className="flex gap-2">
            <Pill>{data.role.replaceAll("_", " ")}</Pill>
            <Pill good>EU CRA</Pill>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-5 space-y-5">
        <section className="grid md:grid-cols-4 gap-4">
          <div className="bg-card fact-border rounded-xl p-4">
            <ShieldCheck className="w-4 h-4 text-primary" />
            <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">
              Classification
            </div>
            <div className="font-head font-black text-xl mt-1">
              {product.classification?.classification || "Pending"}
            </div>
          </div>
          <div className="bg-card fact-border rounded-xl p-4">
            <FileCheck2 className="w-4 h-4 text-low" />
            <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">
              Assessment
            </div>
            <div className="font-head font-black text-xl mt-1">
              {data.assessment?.score ?? "—"}%
            </div>
          </div>
          <div className="bg-card fact-border rounded-xl p-4">
            <Building2 className="w-4 h-4 text-ai" />
            <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">
              Provider
            </div>
            <div className="font-head font-bold text-sm mt-2">
              {data.provider?.name || "Vendor self-assessment"}
            </div>
          </div>
          <div className="bg-card fact-border rounded-xl p-4">
            <BadgeCheck className="w-4 h-4 text-high" />
            <div className="text-[10px] font-mono uppercase text-muted-foreground mt-2">
              Legal basis
            </div>
            <div className="text-xs mt-2">Regulation (EU) 2024/2847</div>
          </div>
        </section>

        {isVendor ? (
          <section className="bg-card fact-border rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="font-head font-black text-lg">
                CRA Product Readiness Assessment
              </h2>
              <p className="text-xs text-muted-foreground mt-1">
                Every question is mapped to the regulation. Evidence remains
                tenant controlled.
              </p>
            </div>
            <div className="p-5 space-y-3">
              {answers.map((answer) => {
                const req = requirementIndex[answer.requirement_id] || {};
                return (
                  <div
                    key={answer.requirement_id}
                    className="rounded-xl border border-border p-4"
                  >
                    <div className="grid xl:grid-cols-[1.4fr_.5fr_1fr] gap-4">
                      <div>
                        <div className="font-mono text-[10px] text-primary">
                          {answer.requirement_id}
                        </div>
                        <div className="font-head font-bold mt-1">
                          {req.title}
                        </div>
                        <div className="text-xs text-muted-foreground mt-2">
                          {(req.legal_refs || []).join(" · ")}
                        </div>
                      </div>
                      <select
                        value={answer.status}
                        onChange={(e) =>
                          updateAnswer(answer.requirement_id, {
                            status: e.target.value,
                          })
                        }
                        className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm h-fit"
                      >
                        <option>Not Assessed</option>
                        <option>Conforming</option>
                        <option>Partial</option>
                        <option>Nonconforming</option>
                        <option>Not Applicable</option>
                      </select>
                      <textarea
                        rows={3}
                        value={answer.comment || ""}
                        onChange={(e) =>
                          updateAnswer(answer.requirement_id, {
                            comment: e.target.value,
                          })
                        }
                        placeholder="Evidence explanation / reference"
                        className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm"
                      />
                    </div>
                  </div>
                );
              })}
              <button
                onClick={saveAssessment}
                disabled={busy}
                className="w-full px-4 py-3 rounded-md bg-primary text-primary-foreground font-head font-bold"
              >
                {busy ? "Saving..." : "Save CRA Readiness Assessment"}
              </button>
            </div>
          </section>
        ) : (
          <section className="grid xl:grid-cols-2 gap-5">
            <div className="bg-card fact-border rounded-xl p-5">
              <h2 className="font-head font-black text-lg">
                External Assessment Package
              </h2>
              {external ? (
                <div className="mt-4 space-y-2">
                  <div className="rounded-lg border border-border p-3">
                    <div className="font-mono text-[10px] text-primary">
                      {external.ref}
                    </div>
                    <div className="font-head font-bold mt-1">
                      {external.module}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {external.scope}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border p-3">
                    <div className="text-[10px] font-mono uppercase text-muted-foreground">
                      Current status
                    </div>
                    <div className="font-head font-black text-xl mt-1">
                      {external.status}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground mt-3">
                  No external assessment request is associated with this link.
                </p>
              )}
            </div>

            <div className="bg-card fact-border rounded-xl p-5">
              <h2 className="font-head font-black text-lg">
                Lab / Notified Body Sign-Off
              </h2>
              <div className="space-y-3 mt-4">
                <select
                  value={signoff.decision}
                  onChange={(e) =>
                    setSignoff({ ...signoff, decision: e.target.value })
                  }
                  className="w-full bg-secondary/60 rounded-md px-3 py-2.5"
                >
                  <option>Conforming</option>
                  <option>Conditional</option>
                  <option>Nonconforming</option>
                </select>
                <input
                  value={signoff.assessor_name}
                  onChange={(e) =>
                    setSignoff({ ...signoff, assessor_name: e.target.value })
                  }
                  placeholder="Assessor name"
                  className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm"
                />
                <input
                  value={signoff.provider_reference}
                  onChange={(e) =>
                    setSignoff({
                      ...signoff,
                      provider_reference: e.target.value,
                    })
                  }
                  placeholder="Provider certificate / assessment reference"
                  className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm"
                />
                <textarea
                  rows={4}
                  value={signoff.findings}
                  onChange={(e) =>
                    setSignoff({ ...signoff, findings: e.target.value })
                  }
                  placeholder="Findings, one per line"
                  className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm"
                />
                <textarea
                  rows={3}
                  value={signoff.artifact_refs}
                  onChange={(e) =>
                    setSignoff({
                      ...signoff,
                      artifact_refs: e.target.value,
                    })
                  }
                  placeholder="Evidence / certificate references, one per line"
                  className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm"
                />
                <textarea
                  rows={3}
                  value={signoff.comment}
                  onChange={(e) =>
                    setSignoff({ ...signoff, comment: e.target.value })
                  }
                  placeholder="Assessment comment"
                  className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm"
                />
                <button
                  onClick={saveSignoff}
                  disabled={busy || !external || !signoff.assessor_name}
                  className="w-full px-4 py-3 rounded-md bg-primary text-primary-foreground font-head font-bold disabled:opacity-50"
                >
                  {busy ? "Recording..." : "Record External Sign-Off"}
                </button>
              </div>
            </div>
          </section>
        )}

        <div className="rounded-lg border border-border bg-secondary/20 p-4 text-xs text-muted-foreground">
          <CheckCircle2 className="w-4 h-4 text-low inline mr-2" />
          This external portal exposes only the invited product assessment
          context. The manufacturer's private Internal Regulatory Ledger is
          never exposed through this portal.
        </div>
      </main>
    </div>
  );
}
