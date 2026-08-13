import { useEffect, useState } from "react";
import {
  BadgeCheck,
  BookOpenCheck,
  Boxes,
  Building2,
  CheckCircle2,
  Clock3,
  Copy,
  Download,
  FileCheck2,
  FileJson,
  Fingerprint,
  Gauge,
  Globe2,
  Landmark,
  Lightbulb,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useCRAData } from "@/hooks/useCRAData";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  assessmentStats,
  cls,
  clsStatus,
  productReadiness,
  reportBlocks,
  vulnerabilityDeadline,
} from "@/lib/craModels";
import { CraTabAnalyst, CraExplain, CraExplainToggle, AiAssurance } from "@/components/cra/CraAI";

const TABS = [
  ["mission", "Mission Control", Gauge],
  ["products", "Products & Classification", Boxes],
  ["certification", "Certification Portal", Globe2],
  ["ledger", "Regulatory Ledger", ScrollText],
  ["sbom", "SBOM & Components", FileJson],
  ["vulnerability", "Vulnerability & ENISA", TriangleAlert],
  ["conformity", "Labs & Notified Bodies", Building2],
  ["declaration", "Declaration & CE", BadgeCheck],
  ["regulation", "Regulation Map", Landmark],
  ["controls", "Control Dashboard", FileCheck2],
  ["nist", "NIST Alignment", ShieldCheck],
  ["assurance", "AI Assurance", Fingerprint],
];

function Badge({ children, tone = "primary" }) {
  const map = {
    primary: "border-primary/25 bg-primary/10 text-primary",
    low: "border-low/25 bg-low/10 text-low",
    med: "border-med/25 bg-med/10 text-med",
    high: "border-high/25 bg-high/10 text-high",
    crit: "border-crit/25 bg-crit/10 text-crit",
    ai: "border-ai/25 bg-ai/10 text-ai",
  };
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full border text-[10px] font-mono font-bold ${map[tone] || map.primary}`}>
      {children}
    </span>
  );
}

function Panel({ title, subtitle, actions, children }) {
  return (
    <section className="bg-card fact-border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div>
          <h2 className="font-head font-black text-lg">{title}</h2>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        {actions}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function Metric({ label, value, sub, icon: Icon, tone = "primary" }) {
  const accent = {
    primary: "hsl(var(--primary))",
    low: "hsl(var(--low))",
    med: "hsl(var(--med))",
    high: "hsl(var(--high))",
    crit: "hsl(var(--crit))",
    ai: "hsl(var(--ai))",
  }[tone];
  return (
    <div className="bg-card fact-border rounded-xl p-4" style={{ borderLeft: `3px solid ${accent}` }}>
      <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase text-muted-foreground">
        {Icon && <Icon className="w-3.5 h-3.5" />} {label}
      </div>
      <div className="font-head font-black text-2xl lg:text-3xl mt-2">{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

function PromptDialog({ open, onOpenChange, title, description, fields, submitLabel, onSubmit, testid }) {
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setValues({});
  }, [open]);
  const canSubmit = fields.every((f) => !f.required || (values[f.key] || "").trim());
  const submit = async () => {
    setBusy(true);
    try {
      await onSubmit(values);
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid={testid || "cra-prompt-dialog"}>
        <DialogHeader>
          <DialogTitle className="font-head font-black">{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="space-y-3 py-1">
          {fields.map((f, idx) => {
            const onKeyDown = (e) => {
              if (e.key === "Enter" && (!f.textarea || e.metaKey || e.ctrlKey) && canSubmit && !busy) {
                e.preventDefault();
                submit();
              }
            };
            return (
              <div key={f.key}>
                <label className="text-[10px] font-mono uppercase text-muted-foreground">{f.label}{f.required ? " *" : ""}</label>
                {f.textarea ? (
                  <textarea autoFocus={idx === 0} rows={3} value={values[f.key] || ""} onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))} onKeyDown={onKeyDown} placeholder={f.placeholder} data-testid={`${testid}-${f.key}`} className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                ) : (
                  <input autoFocus={idx === 0} value={values[f.key] || ""} onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))} onKeyDown={onKeyDown} placeholder={f.placeholder} data-testid={`${testid}-${f.key}`} className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
                )}
              </div>
            );
          })}
        </div>
        <DialogFooter>
          <button onClick={() => onOpenChange(false)} className="px-3 py-2 rounded-md border border-border bg-secondary text-xs font-head font-bold">Cancel</button>
          <button disabled={!canSubmit || busy} onClick={submit} data-testid={`${testid}-submit`} className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50 inline-flex items-center gap-1.5">
            {busy && <Loader2 className="w-3.5 h-3.5 animate-spin" />} {submitLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const KIND_TONE = { fact: "primary", estimate: "ai", risk: "crit" };

function AIAnalyst() {
  const [state, setState] = useState({ loading: true, data: null });
  const load = async () => {
    setState((s) => ({ ...s, loading: true }));
    try {
      const response = await api.get("/cra/insight");
      setState({ loading: false, data: response.data });
    } catch {
      setState({ loading: false, data: null });
    }
  };
  useEffect(() => {
    load();
  }, []);
  const d = state.data;
  return (
    <Panel
      title="CRA AI Analyst"
      subtitle="A grounded executive briefing computed live from your product, classification, assessment and Article 14 posture."
      actions={
        <button onClick={load} disabled={state.loading} data-testid="cra-insight-refresh" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-ai/25 bg-ai/10 text-ai text-xs font-head font-bold disabled:opacity-50">
          {state.loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} Regenerate
        </button>
      }
    >
      {state.loading && !d ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Analyzing live CRA posture…</div>
      ) : !d ? (
        <div className="text-sm text-muted-foreground">CRA AI Analyst is temporarily unavailable. Try Regenerate.</div>
      ) : (
        <div className="space-y-4" data-testid="cra-insight">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-ai/10 border border-ai/25 p-2 shrink-0"><Sparkles className="w-5 h-5 text-ai" /></div>
            <div>
              <div className="font-head font-black text-lg leading-snug" data-testid="cra-insight-headline">{d.headline}</div>
              <div className="text-[10px] font-mono text-muted-foreground mt-1">{d.model} · {d.generated_at ? new Date(d.generated_at).toLocaleString() : ""}</div>
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {(d.insights || []).map((it, i) => (
              <div key={i} className="rounded-lg border border-border bg-secondary/20 p-3">
                <Badge tone={KIND_TONE[it.kind] || "primary"}>{(it.kind || "fact").toUpperCase()}</Badge>
                <div className="text-sm mt-2">{it.text}</div>
              </div>
            ))}
          </div>
          {(d.actions || []).length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Recommended actions</div>
              <div className="space-y-2">
                {d.actions.map((a, i) => (
                  <div key={i} className="flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/5 p-3 text-sm">
                    <Lightbulb className="w-4 h-4 text-primary mt-0.5 shrink-0" /> {a}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

function MissionControl({ data, openTab }) {
  const d = data.dashboard || {};
  const byClass = d.classifications || {};
  const products = data.products || [];
  const assessments = data.assessments || [];
  const external = data.externalAssessments || [];
  return (
    <div className="space-y-5">
      {d.next_deadline && (
        <button
          onClick={() => openTab("vulnerability")}
          data-testid="cra-deadline-chip"
          className="inline-flex items-center gap-2 rounded-full border border-high/30 bg-high/10 px-3.5 py-1.5 text-xs font-head font-bold text-high hover:bg-high/20 transition-colors"
        >
          <Clock3 className="w-3.5 h-3.5" />
          {d.next_deadline.days_remaining} days to next CRA deadline
          <span className="font-normal text-muted-foreground normal-case">· {d.next_deadline.label} ({d.next_deadline.date})</span>
        </button>
      )}
      <div className="grid grid-cols-2 xl:grid-cols-6 gap-4">
        <Metric label="Products" value={d.products || 0} sub={`${d.classification_approved || 0} classifications approved`} icon={Boxes} />
        <Metric label="CRA Readiness" value={`${d.average_readiness || 0}%`} sub="Average regulation-mapped assessment score" icon={Gauge} tone="low" />
        <Metric label="Class I / II" value={`${byClass["Class I"] || 0} / ${byClass["Class II"] || 0}`} sub={`${byClass.Critical || 0} critical products`} icon={Fingerprint} tone="high" />
        <Metric label="External Assessments" value={d.open_external_assessments || 0} sub="Labs and notified-body workflows open" icon={Building2} tone="ai" />
        <Metric label="Article 14 Overdue" value={d.reporting_overdue || 0} sub="24h, 72h, and final-report clocks" icon={Clock3} tone={d.reporting_overdue ? "crit" : "low"} />
        <Metric label="CE Ready" value={d.ce_ready || 0} sub={`General application ${d.general_application_date || "2027-12-11"}`} icon={BadgeCheck} tone="low" />
      </div>

      <AIAnalyst />

      <div className="grid xl:grid-cols-3 gap-5">
        <Panel title="Product regulatory posture" subtitle="Current product readiness and conformity pathway">
          <div className="space-y-2">
            {products.slice(0, 8).map((product) => {
              const ready = productReadiness(product, assessments, external);
              return (
                <button key={product.ref} onClick={() => openTab("products")} className="w-full text-left rounded-lg border border-border bg-secondary/20 p-3 hover:bg-secondary/40">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-mono text-[10px] text-ai">{product.ref}</div>
                      <div className="font-head font-bold text-sm mt-1">{product.name}</div>
                    </div>
                    <Badge tone={ready.classification === "Critical" ? "crit" : ready.classification === "Class II" ? "high" : "primary"}>
                      {ready.classification}
                    </Badge>
                  </div>
                  <div className="flex justify-between mt-3 text-xs text-muted-foreground">
                    <span>Readiness {ready.score}%</span>
                    <span>{ready.classificationApproved ? "classification approved" : "approval pending"}</span>
                  </div>
                </button>
              );
            })}
            {!products.length && <div className="text-sm text-muted-foreground">No CRA products registered.</div>}
          </div>
        </Panel>

        <Panel title="Certification pipeline" subtitle="Vendor self-assessment through external conformity sign-off">
          <div className="space-y-3">
            {[
              ["Product Registration", products.length, Boxes],
              ["Readiness Assessments", assessments.length, FileCheck2],
              ["External Assessments", external.length, Building2],
              ["CE Ready", d.ce_ready || 0, BadgeCheck],
            ].map(([label, value, Icon]) => (
              <button key={label} onClick={() => openTab(label === "External Assessments" ? "conformity" : label === "CE Ready" ? "declaration" : "certification")} className="w-full flex items-center justify-between rounded-lg border border-border p-3 hover:bg-secondary/30">
                <span className="flex items-center gap-2 text-sm"><Icon className="w-4 h-4 text-primary" />{label}</span>
                <span className="font-head font-black text-xl">{value}</span>
              </button>
            ))}
          </div>
        </Panel>

        <Panel title="Regulatory milestones" subtitle="Current CRA applicability dates">
          <div className="space-y-3">
            <div className="rounded-lg border border-high/20 bg-high/5 p-4">
              <div className="font-mono text-[10px] text-high">11 SEP 2026</div>
              <div className="font-head font-bold mt-1">Article 14 reporting obligations</div>
              <div className="text-xs text-muted-foreground mt-1">Actively exploited vulnerabilities and severe incidents.</div>
            </div>
            <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
              <div className="font-mono text-[10px] text-primary">11 DEC 2027</div>
              <div className="font-head font-bold mt-1">General CRA application</div>
              <div className="text-xs text-muted-foreground mt-1">Product cybersecurity, conformity, technical documentation and market-placement requirements.</div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function ProductClassification({ data, reload, isAdmin }) {
  const [showCreate, setShowCreate] = useState(false);
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState({
    name: "",
    version: "",
    manufacturer_name: "",
    description: "",
    core_functionality: "",
    category_codes: [],
    support_period_years: 5,
  });
  const categories = [
    ...(data.regulation?.categories?.class_i || []),
    ...(data.regulation?.categories?.class_ii || []),
    ...(data.regulation?.categories?.critical || []),
  ];

  const create = async (event) => {
    event.preventDefault();
    setBusy("create");
    try {
      const response = await api.post("/cra/products", form);
      await api.post(`/cra/products/${response.data.ref}/classify`);
      toast.success("CRA product registered and proposed classification generated.");
      setShowCreate(false);
      await reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to register CRA product.");
    } finally {
      setBusy("");
    }
  };

  const classify = async (product) => {
    setBusy(product.ref);
    try {
      await api.post(`/cra/products/${product.ref}/classify`);
      toast.success(`${product.ref} classification refreshed.`);
      await reload();
    } finally {
      setBusy("");
    }
  };

  const [approveTarget, setApproveTarget] = useState(null);
  const approveSubmit = async (values) => {
    const product = approveTarget;
    setBusy(product.ref);
    try {
      await api.post(`/cra/products/${product.ref}/classification/approve`, {
        decision: "Approve",
        rationale: values.rationale,
      });
      toast.success(`${product.ref} classification approved.`);
      await reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to approve classification.");
    } finally {
      setBusy("");
    }
  };

  const seedSamples = async () => {
    setBusy("seed");
    try {
      const response = await api.post("/cra/demo/seed");
      toast.success(response.data.created ? `${response.data.created} sample products loaded.` : response.data.note || "Sample products already present.");
      await reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to load sample products.");
    } finally {
      setBusy("");
    }
  };

  const clearSamples = async () => {
    setBusy("clear");
    try {
      const response = await api.delete("/cra/demo/seed");
      toast.success(`${response.data.removed} sample products removed.`);
      await reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to clear sample products.");
    } finally {
      setBusy("");
    }
  };

  return (
    <Panel
      title="Product classification engine"
      subtitle="Deterministic category selection plus explainable heuristic matching. Final classification requires authorized regulatory approval."
      actions={
        <div className="flex gap-2">
          {isAdmin && (
            <>
              <button onClick={seedSamples} disabled={busy === "seed"} data-testid="cra-seed-samples" className="px-3 py-2 rounded-md border border-ai/25 bg-ai/10 text-ai text-xs font-head font-bold inline-flex items-center gap-1.5">
                {busy === "seed" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Boxes className="w-3.5 h-3.5" />} Load Samples
              </button>
              {(data.products || []).some((p) => p.sample) && (
                <button onClick={clearSamples} disabled={busy === "clear"} data-testid="cra-clear-samples" className="px-3 py-2 rounded-md border border-border bg-secondary text-xs font-head font-bold inline-flex items-center gap-1.5">
                  {busy === "clear" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />} Clear Samples
                </button>
              )}
            </>
          )}
          <button onClick={() => setShowCreate(!showCreate)} data-testid="cra-register-toggle" className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold inline-flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5" /> Register Product
          </button>
        </div>
      }
    >
      {showCreate && (
        <form onSubmit={create} className="rounded-xl border border-border bg-secondary/20 p-4 mb-5 grid md:grid-cols-2 gap-3">
          <input required placeholder="Product name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
          <input placeholder="Version" value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
          <input required placeholder="Manufacturer legal name" value={form.manufacturer_name} onChange={(e) => setForm({ ...form, manufacturer_name: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm md:col-span-2" />
          <textarea rows={3} placeholder="Product description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
          <textarea rows={3} placeholder="Core functionality" value={form.core_functionality} onChange={(e) => setForm({ ...form, core_functionality: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
          <div className="md:col-span-2">
            <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Known Annex III / IV categories</div>
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-2 max-h-64 overflow-y-auto">
              {categories.map((item) => {
                const checked = form.category_codes.includes(item.code);
                return (
                  <label key={item.code} className={`rounded-lg border p-2.5 text-xs cursor-pointer ${checked ? "border-primary/40 bg-primary/10" : "border-border"}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() =>
                        setForm({
                          ...form,
                          category_codes: checked
                            ? form.category_codes.filter((code) => code !== item.code)
                            : [...form.category_codes, item.code],
                        })
                      }
                      className="mr-2"
                    />
                    <span className="font-mono text-ai">{item.code}</span> {item.name}
                  </label>
                );
              })}
            </div>
          </div>
          <button disabled={busy === "create"} data-testid="cra-register-submit" className="md:col-span-2 px-4 py-3 rounded-md bg-primary text-primary-foreground font-head font-bold">
            {busy === "create" ? "Registering..." : "Register and Classify"}
          </button>
        </form>
      )}

      <div className="space-y-3">
        {(data.products || []).map((product) => (
          <div key={product.ref} className="rounded-xl border border-border bg-secondary/20 p-4">
            <div className="grid xl:grid-cols-[1.5fr_.55fr_.65fr_.8fr_auto] gap-4 items-center">
              <div>
                <div className="font-mono text-[10px] text-ai">{product.ref}</div>
                <div className="font-head font-bold mt-1">{product.name} {product.version}</div>
                <div className="text-xs text-muted-foreground mt-1">{product.manufacturer_name}</div>
              </div>
              <div>
                <div className="text-[9px] font-mono uppercase text-muted-foreground">Classification</div>
                <div className="mt-2"><Badge tone={cls(product) === "Critical" ? "crit" : cls(product) === "Class II" ? "high" : "primary"}>{cls(product)}</Badge></div>
              </div>
              <div>
                <div className="text-[9px] font-mono uppercase text-muted-foreground">Status</div>
                <div className="mt-2"><Badge tone={clsStatus(product) === "Approved" ? "low" : "med"}>{clsStatus(product)}</Badge></div>
              </div>
              <div>
                <div className="text-[9px] font-mono uppercase text-muted-foreground">Conformity route</div>
                <div className="text-xs mt-1">{product.classification?.pathway?.pathway || "Run classification"}</div>
              </div>
              <div className="flex gap-2">
                <button disabled={busy === product.ref} onClick={() => classify(product)} className="px-3 py-2 rounded-md border border-border bg-secondary text-xs font-head font-bold">Reclassify</button>
                {isAdmin && clsStatus(product) !== "Approved" && (
                  <button disabled={busy === product.ref} onClick={() => setApproveTarget(product)} data-testid={`cra-approve-${product.ref}`} className="px-3 py-2 rounded-md bg-low/15 border border-low/25 text-low text-xs font-head font-bold">Approve</button>
                )}
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-border/60">
              <CraExplainToggle
                title={`${product.ref} · ${product.name}`}
                kind="cra-product"
                context={{ ref: product.ref, name: product.name, classification: cls(product), classification_status: clsStatus(product), pathway: product.classification?.pathway?.pathway, risk: cls(product) === "Critical" ? "High" : cls(product) === "Class II" ? "Medium" : "Low" }}
              />
            </div>
          </div>
        ))}
      </div>
      <PromptDialog
        open={!!approveTarget}
        onOpenChange={(o) => !o && setApproveTarget(null)}
        title="Approve classification"
        description={approveTarget ? `Record the authorized regulatory approval for ${approveTarget.ref} · ${approveTarget.name}.` : ""}
        fields={[{ key: "rationale", label: "Regulatory approval rationale", placeholder: "Basis for approving this classification…", required: true, textarea: true }]}
        submitLabel="Approve classification"
        onSubmit={approveSubmit}
        testid="cra-approve-dialog"
      />
    </Panel>
  );
}

function CertificationPortal({ data, reload, isAdmin }) {
  const [selectedProduct, setSelectedProduct] = useState("");
  const [assessmentRef, setAssessmentRef] = useState("");
  const [role, setRole] = useState("vendor");
  const [email, setEmail] = useState("");
  const [providerRef, setProviderRef] = useState("");
  const [lastToken, setLastToken] = useState("");
  const productAssessments = (data.assessments || []).filter((a) => a.product_ref === selectedProduct);

  const initAssessment = async () => {
    if (!selectedProduct) return;
    const response = await api.post(`/cra/products/${selectedProduct}/assessment/init`);
    setAssessmentRef(response.data.ref);
    toast.success("CRA readiness assessment initialized.");
    await reload();
  };

  const issue = async () => {
    if (!selectedProduct) return;
    const response = await api.post("/cra/portal/invites", {
      product_ref: selectedProduct,
      role,
      assessment_ref: role === "vendor" ? assessmentRef || null : null,
      provider_ref: role === "external_assessor" ? providerRef || null : null,
      invited_email: email,
      expires_hours: 168,
    });
    const link = `${window.location.origin}/cra-certification/${response.data.token}`;
    setLastToken(link);
    try { await navigator.clipboard.writeText(link); } catch {}
    toast.success("Secure Certification Portal link created.");
  };

  return (
    <div className="grid xl:grid-cols-2 gap-5">
      <Panel title="Certification Portal orchestration" subtitle="Issue tenant-scoped, time-limited links to vendors or external assessors. Tokens are stored only as hashes.">
        <div className="space-y-3">
          <select value={selectedProduct} onChange={(e) => { setSelectedProduct(e.target.value); setAssessmentRef(""); }} className="w-full bg-secondary/60 rounded-md px-3 py-2.5">
            <option value="">Select product</option>
            {(data.products || []).map((p) => <option key={p.ref} value={p.ref}>{p.ref} · {p.name}</option>)}
          </select>
          <select value={role} onChange={(e) => setRole(e.target.value)} className="w-full bg-secondary/60 rounded-md px-3 py-2.5">
            <option value="vendor">Vendor self-assessment</option>
            <option value="external_assessor">Lab / notified body assessor</option>
          </select>
          {role === "vendor" ? (
            <div className="flex gap-2">
              <select value={assessmentRef} onChange={(e) => setAssessmentRef(e.target.value)} className="flex-1 bg-secondary/60 rounded-md px-3 py-2.5 text-sm">
                <option value="">Select assessment</option>
                {productAssessments.map((a) => <option key={a.ref} value={a.ref}>{a.ref} · {a.score}%</option>)}
              </select>
              <button onClick={initAssessment} className="px-3 py-2 rounded-md border border-border bg-secondary text-xs font-head font-bold">New Assessment</button>
            </div>
          ) : (
            <select value={providerRef} onChange={(e) => setProviderRef(e.target.value)} className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm">
              <option value="">Select lab / notified body</option>
              {(data.providers || []).map((p) => <option key={p.ref} value={p.ref}>{p.ref} · {p.name}</option>)}
            </select>
          )}
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="External participant email" className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
          {isAdmin && <button onClick={issue} className="w-full px-4 py-3 rounded-md bg-primary text-primary-foreground font-head font-bold">Create Secure Portal Link</button>}
          {lastToken && <div className="rounded-lg border border-low/25 bg-low/5 p-3"><div className="text-[10px] font-mono text-low">PORTAL LINK ISSUED</div><div className="text-xs break-all mt-2">{lastToken}</div></div>}
        </div>
      </Panel>

      <Panel title="Readiness assessment pipeline" subtitle="Every readiness item is mapped to CRA Articles and Annexes.">
        <div className="space-y-2">
          {(data.assessments || []).slice(0, 15).map((assessment) => {
            const stats = assessmentStats(assessment);
            return (
              <div key={assessment.ref} className="rounded-lg border border-border p-3">
                <div className="flex justify-between gap-3">
                  <div><div className="font-mono text-[10px] text-ai">{assessment.ref}</div><div className="font-head font-bold text-sm mt-1">{assessment.product_name}</div></div>
                  <div className="font-head font-black text-2xl">{stats.score}%</div>
                </div>
                <div className="flex gap-2 mt-2 text-[10px] font-mono text-muted-foreground"><span>{stats.conforming} conforming</span><span>{stats.partial} partial</span><span>{stats.nonconforming} gaps</span></div>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

function RegulatoryLedger({ data, isAdmin }) {
  const [productRef, setProductRef] = useState("");
  const [link, setLink] = useState(null);
  const [busy, setBusy] = useState(false);
  const generate = async () => {
    if (!productRef) return;
    setBusy(true);
    try {
      const response = await api.post(`/cra/products/${productRef}/verification-link`);
      const url = `${window.location.origin}${response.data.path}`;
      setLink({ url, expires_at: response.data.expires_at });
      try { await navigator.clipboard.writeText(url); } catch {}
      toast.success("Auditor verification link created and copied to clipboard.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to create verification link.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-5">
      {isAdmin && (
        <Panel title="Auditor verification link" subtitle="Issue a read-only, tamper-evident link a notified body or auditor can use to independently verify a product's CRA timeline and hash-chain integrity. Private ledger payloads are never exposed.">
          <div className="flex flex-col md:flex-row gap-2 md:items-center">
            <select value={productRef} onChange={(e) => setProductRef(e.target.value)} data-testid="cra-verify-product" className="flex-1 bg-secondary/60 rounded-md px-3 py-2.5 text-sm">
              <option value="">Select product</option>
              {(data.products || []).map((p) => <option key={p.ref} value={p.ref}>{p.ref} · {p.name}</option>)}
            </select>
            <button onClick={generate} disabled={!productRef || busy} data-testid="cra-verify-generate" className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">
              {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Link2 className="w-3.5 h-3.5" />} Generate verification link
            </button>
            <button onClick={async () => { if (!productRef) return; try { const { data: r } = await api.post(`/cra/products/${productRef}/verification-link/revoke`); toast.success(`Revoked ${r.revoked} link(s).`); setLink(null); } catch (e) { toast.error(e.response?.data?.detail || "Could not revoke links."); } }} disabled={!productRef} data-testid="cra-verify-revoke" className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50"><Trash2 className="w-3.5 h-3.5" /> Revoke links</button>
          </div>
          {link && (
            <div className="mt-3 rounded-lg border border-low/25 bg-low/5 p-3" data-testid="cra-verify-link">
              <div className="flex items-center justify-between gap-2">
                <div className="text-[10px] font-mono text-low uppercase">Auditor verification link issued</div>
                <button
                  onClick={async () => {
                    try { await navigator.clipboard.writeText(link.url); toast.success("Verification link copied to clipboard."); }
                    catch { toast.error("Copy failed — select the link manually."); }
                  }}
                  data-testid="cra-verify-copy"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-primary/25 bg-primary/10 text-primary text-[10px] font-head font-bold hover:bg-primary/20 transition-colors"
                >
                  <Copy className="w-3 h-3" /> Copy link
                </button>
              </div>
              <a href={link.url} target="_blank" rel="noreferrer" className="text-xs break-all mt-2 block underline text-primary">{link.url}</a>
              <div className="text-[10px] font-mono text-muted-foreground mt-1">Expires {new Date(link.expires_at).toLocaleString()}</div>
            </div>
          )}
          {productRef && (() => {
            const sp = (data.products || []).find((p) => p.ref === productRef);
            return (
              <div className="mt-3 flex items-center gap-2 text-[11px] text-muted-foreground" data-testid="cra-verify-access" title={sp?.last_verification_view_at ? new Date(sp.last_verification_view_at).toUTCString() : ""}>
                <Fingerprint className="w-3.5 h-3.5 text-ai" />
                {sp?.last_verification_view_at
                  ? `Auditor last opened this product's link ${relTime(sp.last_verification_view_at)} · ${sp.verification_view_count || 1} view${(sp.verification_view_count || 1) === 1 ? "" : "s"}`
                  : "No auditor has opened this product's verification link yet."}
              </div>
            );
          })()}
        </Panel>
      )}
      <Panel title="Internal Regulatory Ledger" subtitle="Private, append-only, hash-chained regulatory record. No external portal receives ledger access.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] text-xs">
          <thead className="font-mono uppercase text-[9px] text-muted-foreground border-b border-border">
            <tr><th className="text-left py-3">Seq</th><th className="text-left py-3">Timestamp</th><th className="text-left py-3">Event</th><th className="text-left py-3">Object</th><th className="text-left py-3">Legal basis</th><th className="text-left py-3">Actor</th><th className="text-left py-3">Hash</th></tr>
          </thead>
          <tbody>
            {(data.ledger || []).map((item) => (
              <tr key={`${item.sequence}:${item.record_hash}`} className="border-b border-border/60">
                <td className="py-3 font-mono">{item.sequence}</td>
                <td className="py-3">{new Date(item.ts).toLocaleString()}</td>
                <td className="py-3 font-medium">{item.event_type}</td>
                <td className="py-3"><span className="font-mono text-ai">{item.object_ref}</span><div className="text-muted-foreground">{item.object_type}</div></td>
                <td className="py-3 max-w-[300px]">{(item.legal_refs || []).join(", ")}</td>
                <td className="py-3">{item.actor}</td>
                <td className="py-3 font-mono text-[9px]">{String(item.record_hash).slice(0, 16)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
    </div>
  );
}

function SBOMDashboard({ data, reload }) {
  const [productRef, setProductRef] = useState("");
  const [format, setFormat] = useState("cyclonedx-json");
  const [manifestType, setManifestType] = useState("requirements.txt");
  const [manifest, setManifest] = useState("");
  const [result, setResult] = useState(null);
  const generate = async () => {
    if (!productRef || !manifest.trim()) return;
    try {
      const response = await api.post(`/cra/products/${productRef}/sbom/generate`, {
        format,
        manifest_type: manifestType,
        manifest_text: manifest,
        components: [],
      });
      setResult(response.data);
      toast.success(`${response.data.ref} generated with ${response.data.component_count} components.`);
      await reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || "SBOM generation failed.");
    }
  };
  return (
    <div className="grid xl:grid-cols-2 gap-5">
      <Panel title="Automated SBOM generation" subtitle="Generate CycloneDX 1.6 or SPDX 2.3 from supported dependency manifests.">
        <div className="space-y-3">
          <select value={productRef} onChange={(e) => setProductRef(e.target.value)} className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm">
            <option value="">Select product</option>
            {(data.products || []).map((p) => <option key={p.ref} value={p.ref}>{p.ref} · {p.name}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <select value={manifestType} onChange={(e) => setManifestType(e.target.value)} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm">
              <option>requirements.txt</option><option>package.json</option><option>package-lock.json</option><option>pom.xml</option>
            </select>
            <select value={format} onChange={(e) => setFormat(e.target.value)} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm">
              <option value="cyclonedx-json">CycloneDX JSON</option><option value="spdx-json">SPDX JSON</option>
            </select>
          </div>
          <textarea rows={14} value={manifest} onChange={(e) => setManifest(e.target.value)} placeholder="Paste dependency manifest here" className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm font-mono" />
          <button onClick={generate} className="w-full px-4 py-3 rounded-md bg-primary text-primary-foreground font-head font-bold">Generate CRA SBOM</button>
        </div>
      </Panel>
      <Panel title="Latest generated artifact" subtitle="SBOM generation is logged to the Internal Regulatory Ledger and mapped to Annex I Part II(1).">
        {result ? (
          <div>
            <div className="grid grid-cols-2 gap-3"><Metric label="SBOM Reference" value={result.ref} icon={FileJson} /><Metric label="Components" value={result.component_count} icon={Boxes} tone="low" /></div>
            <div className="mt-4">
              <CraExplain
                title={`SBOM · ${result.ref}`}
                kind="cra-sbom"
                context={{ ref: result.ref, product_ref: productRef, format, component_count: result.component_count, risk: result.component_count > 0 ? "Low" : "Medium" }}
              />
            </div>
            <pre className="mt-4 rounded-lg bg-background/70 border border-border p-4 overflow-auto max-h-[450px] text-[10px]">{JSON.stringify(result.document, null, 2)}</pre>
          </div>
        ) : <div className="text-sm text-muted-foreground">Generate an SBOM to preview the machine-readable artifact.</div>}
      </Panel>
    </div>
  );
}

function VulnerabilityDashboard({ data, reload }) {
  const [form, setForm] = useState({
    product_ref: "",
    title: "",
    cve: "",
    description: "",
    severity: "High",
    actively_exploited: true,
    severe_incident: false,
    awareness_at: new Date().toISOString(),
  });
  const create = async (event) => {
    event.preventDefault();
    try {
      await api.post("/cra/vulnerabilities", form);
      toast.success("CRA reporting clock created.");
      await reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Unable to create CRA vulnerability workflow.");
    }
  };
  const [markTarget, setMarkTarget] = useState(null);
  const markSubmit = async (values) => {
    const { item, stage } = markTarget;
    const receipt = (values.receipt || "").trim();
    await api.post(`/cra/vulnerabilities/${item.ref}/submission`, {
      stage,
      state: receipt ? "Receipt Recorded" : "Submitted",
      submitted_at: new Date().toISOString(),
      receipt_id: receipt,
      comment: "Recorded by authorized Obserra user",
    });
    toast.success("Reporting stage recorded.");
    await reload();
  };
  return (
    <div className="space-y-5">
      <Panel title="CRA Article 14 reporting workflow" subtitle="24-hour early warning, 72-hour notification, and final-report clocks. Reporting obligations apply from 11 September 2026.">
        <form onSubmit={create} className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
          <select required value={form.product_ref} onChange={(e) => setForm({ ...form, product_ref: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm">
            <option value="">Select product</option>{(data.products || []).map((p) => <option key={p.ref} value={p.ref}>{p.ref} · {p.name}</option>)}
          </select>
          <input required placeholder="Vulnerability or severe incident title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm xl:col-span-2" />
          <input placeholder="CVE" value={form.cve} onChange={(e) => setForm({ ...form, cve: e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={form.actively_exploited} onChange={(e) => setForm({ ...form, actively_exploited: e.target.checked })} /> Actively exploited vulnerability</label>
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={form.severe_incident} onChange={(e) => setForm({ ...form, severe_incident: e.target.checked })} /> Severe incident</label>
          <input type="datetime-local" value={form.awareness_at.slice(0,16)} onChange={(e) => setForm({ ...form, awareness_at: new Date(e.target.value).toISOString() })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm" />
          <button className="px-4 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm">Start Reporting Clock</button>
        </form>
      </Panel>
      <Panel title="Reporting clock register" subtitle="Obserra prepares and tracks submission packages. It does not claim regulatory submission without a recorded official submission/receipt.">
        <div className="space-y-3">
          {(data.vulnerabilities || []).map((item) => {
            const next = vulnerabilityDeadline(item);
            return (
              <div key={item.ref} className="rounded-xl border border-border bg-secondary/20 p-4">
                <div className="grid xl:grid-cols-[1.4fr_.8fr_1.3fr] gap-4">
                  <div><div className="font-mono text-[10px] text-ai">{item.ref}</div><div className="font-head font-bold mt-1">{item.title}</div><div className="text-xs text-muted-foreground mt-1">{item.product_name} · {item.cve || "No CVE"}</div></div>
                  <div><div className="text-[9px] font-mono uppercase text-muted-foreground">Next deadline</div>{next ? <><div className="font-head font-bold mt-1">{next.stage.replaceAll("_"," ")}</div><Badge tone={next.overdue ? "crit" : next.hours_remaining < 24 ? "high" : "low"}>{next.overdue ? "OVERDUE" : `${next.hours_remaining}h`}</Badge></> : <Badge tone="low">No open deadline</Badge>}</div>
                  <div className="flex flex-wrap gap-2 items-center">
                    {(item.clock?.stages || []).map((stage) => (
                      <button key={stage.stage} disabled={stage.submitted} onClick={() => setMarkTarget({ item, stage: stage.stage })} data-testid={`cra-report-${item.ref}-${stage.stage}`} className="px-3 py-2 rounded-md border border-border bg-secondary text-[10px] font-head font-bold disabled:opacity-50">
                        {stage.submitted ? <CheckCircle2 className="w-3.5 h-3.5 inline mr-1 text-low" /> : null}{stage.stage.replaceAll("_"," ")}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-border/60">
                  <CraExplainToggle
                    title={`${item.ref} · ${item.title}`}
                    kind="cra-vulnerability"
                    context={{ ref: item.ref, product: item.product_name, cve: item.cve, severity: item.severity, actively_exploited: item.actively_exploited, severe_incident: item.severe_incident, next_stage: next ? next.stage : null, hours_remaining: next ? next.hours_remaining : null, overdue: next ? next.overdue : false, risk: next && next.overdue ? "High" : item.severity }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
      <PromptDialog
        open={!!markTarget}
        onOpenChange={(o) => !o && setMarkTarget(null)}
        title="Record reporting submission"
        description={markTarget ? `Record the "${markTarget.stage.replaceAll("_", " ")}" submission for ${markTarget.item.ref}. A receipt/reference is optional but strengthens the audit trail.` : ""}
        fields={[{ key: "receipt", label: "Submission receipt / reference (optional)", placeholder: "e.g. single reporting platform receipt ID", required: false }]}
        submitLabel="Record submission"
        onSubmit={markSubmit}
        testid="cra-report-dialog"
      />
    </div>
  );
}

function ConformityDashboard({ data, reload, isAdmin }) {
  const [providerForm, setProviderForm] = useState({ name:"", provider_type:"notified_body", country:"", nando_id:"", scope:[], contact_email:"", integration_mode:"secure_portal" });
  const [request, setRequest] = useState({ product_ref:"", provider_ref:"", module:"Module B+C", scope:"CRA conformity assessment" });
  const createProvider = async (e) => { e.preventDefault(); await api.post("/cra/providers", providerForm); toast.success("Conformity assessment provider registered."); await reload(); };
  const createAssessment = async () => { if (!request.product_ref || !request.provider_ref) return; await api.post("/cra/external-assessments", request); toast.success("External conformity assessment requested."); await reload(); };
  return (
    <div className="grid xl:grid-cols-2 gap-5">
      <Panel title="External labs and CRA notified bodies" subtitle="Provider-neutral registry. NANDO identity and verification evidence are explicitly tracked.">
        {isAdmin && (
          <form onSubmit={createProvider} className="grid md:grid-cols-2 gap-2 mb-5">
            <input required placeholder="Provider name" value={providerForm.name} onChange={(e) => setProviderForm({ ...providerForm, name:e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2 text-sm" />
            <select value={providerForm.provider_type} onChange={(e) => setProviderForm({ ...providerForm, provider_type:e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2 text-sm"><option value="testing_lab">Testing Lab</option><option value="notified_body">CRA Notified Body</option><option value="certification_body">Certification Body</option></select>
            <input placeholder="Country" value={providerForm.country} onChange={(e) => setProviderForm({ ...providerForm, country:e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2 text-sm" />
            <input placeholder="NANDO ID" value={providerForm.nando_id} onChange={(e) => setProviderForm({ ...providerForm, nando_id:e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2 text-sm" />
            <button className="md:col-span-2 px-3 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Register Provider</button>
          </form>
        )}
        <div className="space-y-2">
          {(data.providers || []).map((p) => (
            <div key={p.ref} className="rounded-lg border border-border p-3">
              <div className="flex justify-between gap-3"><div><div className="font-mono text-[10px] text-ai">{p.ref}</div><div className="font-head font-bold text-sm mt-1">{p.name}</div></div><Badge tone={p.provider_type === "notified_body" ? "ai" : "primary"}>{p.provider_type.replaceAll("_"," ")}</Badge></div>
              <div className="text-xs text-muted-foreground mt-2">{p.country || "Country not recorded"} · NANDO {p.nando_id || "not recorded"} · {p.integration_mode}</div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Conformity assessment requests" subtitle="Supports Module B+C, Module H, EU cybersecurity certification, and testing evidence workflows.">
        <div className="grid gap-2 mb-4">
          <select value={request.product_ref} onChange={(e) => setRequest({ ...request, product_ref:e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm"><option value="">Select product</option>{(data.products || []).map((p) => <option key={p.ref} value={p.ref}>{p.ref} · {p.name}</option>)}</select>
          <select value={request.provider_ref} onChange={(e) => setRequest({ ...request, provider_ref:e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm"><option value="">Select provider</option>{(data.providers || []).map((p) => <option key={p.ref} value={p.ref}>{p.ref} · {p.name}</option>)}</select>
          <select value={request.module} onChange={(e) => setRequest({ ...request, module:e.target.value })} className="bg-secondary/60 rounded-md px-3 py-2.5 text-sm"><option>Module B+C</option><option>Module H</option><option>EU Cybersecurity Certification</option><option>Testing Evidence</option></select>
          {isAdmin && <button onClick={createAssessment} className="px-3 py-2.5 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">Request External Assessment</button>}
        </div>
        <div className="space-y-2">
          {(data.externalAssessments || []).map((item) => (
            <div key={item.ref} className="rounded-lg border border-border p-3">
              <div className="flex justify-between gap-3"><div><div className="font-mono text-[10px] text-ai">{item.ref}</div><div className="font-head font-bold text-sm mt-1">{item.product_name}</div></div><Badge tone={item.decision === "Conforming" ? "low" : item.decision === "Nonconforming" ? "crit" : "med"}>{item.status}</Badge></div>
              <div className="text-xs text-muted-foreground mt-2">{item.provider_name} · {item.module}</div>
              <div className="mt-2 pt-2 border-t border-border/60">
                <CraExplainToggle
                  title={`${item.ref} · ${item.product_name}`}
                  kind="cra-conformity-assessment"
                  context={{ ref: item.ref, product: item.product_name, provider: item.provider_name, module: item.module, status: item.status, decision: item.decision, risk: item.decision === "Nonconforming" ? "High" : item.decision === "Conforming" ? "Low" : "Medium" }}
                />
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function DeclarationDashboard({ data, reload, isAdmin }) {
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState(null);
  const check = async () => { if (!selected) return; const response = await api.get(`/cra/products/${selected}/market-readiness`); setResult(response.data); await reload(); };
  const [approveOpen, setApproveOpen] = useState(false);
  const approveSubmit = async (values) => {
    await api.post(`/cra/products/${selected}/declaration/approve`, { signatory_name: values.name, signatory_title: values.title, declaration_reference: `EU-DOC-${selected}` });
    toast.success("EU Declaration approval recorded.");
    await check();
  };
  return (
    <div className="grid xl:grid-cols-2 gap-5">
      <Panel title="EU Declaration and CE readiness" subtitle="Assessment complete does not equal Declaration approved, CE ready, or placed on the market.">
        <select value={selected} onChange={(e) => { setSelected(e.target.value); setResult(null); }} className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm"><option value="">Select product</option>{(data.products || []).map((p) => <option key={p.ref} value={p.ref}>{p.ref} · {p.name}</option>)}</select>
        <button onClick={check} className="mt-3 w-full px-4 py-3 rounded-md bg-primary text-primary-foreground font-head font-bold">Evaluate Market Readiness</button>
        {isAdmin && selected && <button onClick={() => setApproveOpen(true)} data-testid="cra-declaration-approve" className="mt-2 w-full px-4 py-3 rounded-md border border-low/25 bg-low/10 text-low font-head font-bold">Approve EU Declaration</button>}
      </Panel>
      <Panel title="Market release gates" subtitle="Blockers are based on current Obserra records and CRA workflow state.">
        {result ? (
          <>
            <div className="flex items-center gap-3">{result.ready ? <CheckCircle2 className="w-8 h-8 text-low" /> : <TriangleAlert className="w-8 h-8 text-crit" />}<div><div className="font-head font-black text-2xl">{result.ce_status}</div><div className="text-xs text-muted-foreground">CE readiness status</div></div></div>
            <div className="mt-4 space-y-2">
              {result.blockers.map((item) => <div key={item} className="rounded-lg border border-crit/20 bg-crit/5 p-3 text-sm">{item}</div>)}
              {result.warnings.map((item) => <div key={item} className="rounded-lg border border-high/20 bg-high/5 p-3 text-sm">{item}</div>)}
              {!result.blockers.length && <div className="rounded-lg border border-low/20 bg-low/5 p-3 text-sm">All current Obserra market-readiness gates are satisfied.</div>}
            </div>
            <div className="mt-4">
              <CraExplain
                title={`Market readiness · ${result.product_name || selected}`}
                kind="cra-ce-readiness"
                context={{ product_ref: selected, ce_status: result.ce_status, ready: result.ready, blockers: result.blockers, warnings: result.warnings, risk: result.ready ? "Low" : (result.blockers && result.blockers.length ? "High" : "Medium") }}
              />
            </div>
          </>
        ) : <div className="text-sm text-muted-foreground">Select a product and run the market readiness evaluation.</div>}
      </Panel>
      <PromptDialog
        open={approveOpen}
        onOpenChange={setApproveOpen}
        title="Approve EU Declaration of Conformity"
        description="Record the authorized signatory for the EU Declaration of Conformity. This is written to the Internal Regulatory Ledger."
        fields={[
          { key: "name", label: "Authorized signatory name", placeholder: "e.g. Jane Doe", required: true },
          { key: "title", label: "Signatory title", placeholder: "e.g. Chief Compliance Officer", required: true },
        ]}
        submitLabel="Record declaration approval"
        onSubmit={approveSubmit}
        testid="cra-declaration-dialog"
      />
    </div>
  );
}

const RISK_TONE = { High: "crit", Medium: "high", Low: "low", Unknown: "primary" };
const STATUS_TONE = { Implemented: "low", Partial: "high", Gap: "crit", "Not Started": "primary" };

function relTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60); if (m < 60) return `${m} minute${m === 1 ? "" : "s"} ago`;
  const h = Math.floor(m / 60); if (h < 24) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const dd = Math.floor(h / 24); if (dd < 30) return `${dd} day${dd === 1 ? "" : "s"} ago`;
  return d.toLocaleDateString();
}

const DRILL_TONE = { Conforming: "low", Partial: "high", Nonconforming: "crit", "Not Applicable": "primary", "Not Assessed": "primary" };

function ControlDashboard({ data, isAdmin, reload }) {
  const controls = data.controls?.controls || [];
  const o = data.controls?.overall || {};
  const pct = o.percentage || 0;
  const [drill, setDrill] = useState(null);
  const [briefBusy, setBriefBusy] = useState(false);
  const [scoreLink, setScoreLink] = useState(null);
  const [scoreBusy, setScoreBusy] = useState(false);
  const [form, setForm] = useState({ owner: "", due_date: "", status: "Open", note: "" });
  const [savingAssign, setSavingAssign] = useState(false);
  useEffect(() => {
    if (drill) {
      const a = drill.assignment || {};
      setForm({ owner: a.owner || "", due_date: (a.due_date || "").slice(0, 10), status: a.status || "Open", note: a.note || "" });
    }
  }, [drill]);
  const chips = [
    ["Implemented", o.implemented || 0, "text-low"],
    ["Partial", o.partial || 0, "text-high"],
    ["Gaps", o.gaps || 0, "text-crit"],
    ["Not started", o.not_started || 0, "text-muted-foreground"],
    ["High risk", o.high_risk || 0, "text-crit"],
    ["Requirements", o.requirements_total || controls.length, "text-primary"],
  ];
  const downloadBrief = async () => {
    setBriefBusy(true);
    try {
      const response = await api.get("/cra/digest/brief.pdf", { responseType: "blob" });
      downloadBlob(response.data, "obserra-eu-cra-weekly-brief.pdf");
      toast.success("This week's CRA brief downloaded.");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not download the brief."); }
    finally { setBriefBusy(false); }
  };
  const genScorecard = async () => {
    setScoreBusy(true);
    try {
      const response = await api.post("/cra/scorecard-link");
      const url = `${window.location.origin}${response.data.path}`;
      setScoreLink({ url, expires_at: response.data.expires_at });
      try { await navigator.clipboard.writeText(url); } catch {}
      toast.success("Shareable compliance scorecard link created and copied.");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not create scorecard link."); }
    finally { setScoreBusy(false); }
  };
  const revokeScorecards = async () => {
    try { const { data: r } = await api.post("/cra/scorecard-link/revoke"); toast.success(`Revoked ${r.revoked} scorecard link(s).`); setScoreLink(null); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not revoke links."); }
  };
  const saveAssignment = async () => {
    setSavingAssign(true);
    try {
      await api.put(`/cra/controls/${drill.requirement_id}/assignment`, form);
      toast.success("Control ownership saved.");
      setDrill(null);
      if (reload) await reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save ownership."); }
    finally { setSavingAssign(false); }
  };
  return (
    <div className="space-y-5" data-testid="cra-controls">
      <Panel
        title="CRA Control Dashboard"
        subtitle="Live compliance coverage of every EU CRA essential requirement, computed from the latest assessment on each product."
        actions={
          <div className="flex flex-wrap gap-2">
            <button onClick={downloadBrief} disabled={briefBusy} data-testid="cra-download-brief" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold disabled:opacity-50">{briefBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} This week's brief</button>
            {isAdmin && <button onClick={genScorecard} disabled={scoreBusy} data-testid="cra-scorecard-generate" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold disabled:opacity-50">{scoreBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Link2 className="w-3.5 h-3.5" />} Share scorecard</button>}
            {isAdmin && <button onClick={revokeScorecards} data-testid="cra-scorecard-revoke" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><Trash2 className="w-3.5 h-3.5" /> Revoke links</button>}
          </div>
        }
      >
        {scoreLink && (
          <div className="mb-4 rounded-lg border border-primary/25 bg-primary/5 p-3" data-testid="cra-scorecard-link">
            <div className="flex items-center justify-between gap-2">
              <div className="text-[10px] font-mono text-primary uppercase">Read-only compliance scorecard link (no account needed)</div>
              <button onClick={async () => { try { await navigator.clipboard.writeText(scoreLink.url); toast.success("Scorecard link copied."); } catch { toast.error("Copy failed."); } }} data-testid="cra-scorecard-copy" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-primary/25 bg-primary/10 text-primary text-[10px] font-head font-bold"><Copy className="w-3 h-3" /> Copy</button>
            </div>
            <a href={scoreLink.url} target="_blank" rel="noreferrer" className="text-xs break-all mt-2 block underline text-primary">{scoreLink.url}</a>
            <div className="text-[10px] font-mono text-muted-foreground mt-1">Expires {new Date(scoreLink.expires_at).toLocaleString()}</div>
          </div>
        )}
        <div className="grid lg:grid-cols-4 gap-4">
          <div className="rounded-xl border border-border bg-secondary/20 p-4">
            <div className="text-[10px] font-mono uppercase text-muted-foreground">Overall compliance</div>
            <div className="font-head font-black text-4xl mt-2" data-testid="cra-controls-overall">{pct}%</div>
            <div className="mt-3 h-2 rounded-full bg-secondary overflow-hidden"><div className="h-full bg-low transition-all" style={{ width: `${pct}%` }} /></div>
            <div className="text-[10px] text-muted-foreground mt-2">{o.products_assessed || 0}/{o.products_total || 0} products assessed</div>
          </div>
          <div className="lg:col-span-3 grid grid-cols-2 sm:grid-cols-3 gap-3">
            {chips.map(([label, value, cls]) => (
              <div key={label} className="rounded-xl border border-border bg-secondary/20 p-4">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">{label}</div>
                <div className={`font-head font-black text-2xl mt-1 ${cls}`}>{value}</div>
              </div>
            ))}
          </div>
        </div>
      </Panel>

      <Panel title="Controls & requirements" subtitle="Click any control to see which products conform and to assign an owner and due date to close the gap.">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-xs">
            <thead className="font-mono uppercase text-[9px] text-muted-foreground border-b border-border">
              <tr>
                <th className="text-left py-3">Control</th>
                <th className="text-left py-3">Legal basis</th>
                <th className="text-left py-3 w-[170px]">Compliance</th>
                <th className="text-left py-3">Status</th>
                <th className="text-left py-3">Risk</th>
              </tr>
            </thead>
            <tbody data-testid="cra-controls-table">
              {controls.map((c) => (
                <tr key={c.requirement_id} onClick={() => setDrill(c)} data-testid={`cra-control-row-${c.requirement_id}`} className="border-b border-border/60 align-top cursor-pointer hover:bg-secondary/30 transition-colors">
                  <td className="py-3 pr-3">
                    <div className="font-mono text-[10px] text-ai">{c.requirement_id}</div>
                    <div className="font-head font-bold mt-0.5">{c.title}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{c.domain} · {c.conforming}/{c.assessed || 0} conforming{c.nonconforming ? ` · ${c.nonconforming} non-conforming` : ""}</div>
                    {c.assignment?.owner && <div className="text-[10px] text-primary mt-0.5">Owner: {c.assignment.owner} · {c.assignment.status}{c.assignment.due_date ? ` · due ${String(c.assignment.due_date).slice(0, 10)}` : ""}</div>}
                  </td>
                  <td className="py-3 pr-3 max-w-[200px] text-muted-foreground">{(c.legal_refs || []).join(", ")}</td>
                  <td className="py-3 pr-3">
                    {c.compliance_rate === null || c.compliance_rate === undefined ? (
                      <span className="text-[10px] text-muted-foreground">Not assessed</span>
                    ) : (
                      <div>
                        <div className="text-[10px] mb-1">{c.compliance_rate}%</div>
                        <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                          <div className={`h-full ${c.compliance_rate === 100 ? "bg-low" : c.compliance_rate >= 50 ? "bg-high" : "bg-crit"}`} style={{ width: `${c.compliance_rate}%` }} />
                        </div>
                      </div>
                    )}
                  </td>
                  <td className="py-3 pr-3"><Badge tone={STATUS_TONE[c.status] || "primary"}>{c.status}</Badge></td>
                  <td className="py-3"><Badge tone={RISK_TONE[c.risk] || "primary"}>{c.risk}</Badge></td>
                </tr>
              ))}
              {!controls.length && <tr><td colSpan={5} className="py-4 text-muted-foreground">No controls computed yet — register or load products and complete an assessment.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>

      <Dialog open={!!drill} onOpenChange={(open) => !open && setDrill(null)}>
        <DialogContent data-testid="cra-control-drill">
          <DialogHeader>
            <DialogTitle className="font-head font-black">{drill?.title}</DialogTitle>
            <DialogDescription>{drill?.requirement_id} · {drill?.domain} · {(drill?.legal_refs || []).join(", ")}</DialogDescription>
          </DialogHeader>
          <div className="flex gap-3 flex-wrap text-[10px] font-mono mb-1" data-testid="cra-drill-counts">
            <span className="text-low">{drill?.conforming || 0} Conforming</span>
            <span className="text-high">{drill?.partial || 0} Partial</span>
            <span className="text-crit">{drill?.nonconforming || 0} Non-conforming</span>
            <span className="text-muted-foreground">{drill?.not_assessed || 0} Not assessed</span>
          </div>
          <div className="space-y-2 max-h-[38vh] overflow-y-auto">
            {(drill?.product_status || []).length ? drill.product_status.map((p) => (
              <div key={p.ref} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-secondary/20 px-3 py-2">
                <div><div className="font-mono text-[10px] text-ai">{p.ref}</div><div className="text-sm font-head font-bold">{p.name}</div></div>
                <Badge tone={DRILL_TONE[p.status] || "primary"}>{p.status}</Badge>
              </div>
            )) : <div className="text-sm text-muted-foreground">No assessed products for this control yet.</div>}
          </div>
          <div className="border-t border-border pt-3 mt-1 space-y-2">
            <div className="text-[10px] font-mono uppercase text-muted-foreground">Gap ownership</div>
            <div className="grid sm:grid-cols-2 gap-2">
              <input value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} placeholder="Owner (name or email)" data-testid="cra-assign-owner" className="bg-secondary/60 rounded-md px-3 py-2 text-sm" />
              <input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} data-testid="cra-assign-due" className="bg-secondary/60 rounded-md px-3 py-2 text-sm" />
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} data-testid="cra-assign-status" className="bg-secondary/60 rounded-md px-3 py-2 text-sm">
                <option>Open</option><option>In Progress</option><option>Closed</option>
              </select>
              <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="Note (optional)" data-testid="cra-assign-note" className="bg-secondary/60 rounded-md px-3 py-2 text-sm" />
            </div>
            <button onClick={saveAssignment} disabled={savingAssign} data-testid="cra-assign-save" className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold inline-flex items-center gap-2 disabled:opacity-50">{savingAssign && <Loader2 className="w-3.5 h-3.5 animate-spin" />} Save ownership</button>
          </div>
          {drill && (
            <div className="border-t border-border pt-3 mt-1">
              <CraExplain
                title={`${drill.requirement_id} · ${drill.title}`}
                kind="cra-control"
                context={{ requirement_id: drill.requirement_id, domain: drill.domain, legal_refs: drill.legal_refs, status: drill.status, risk: drill.risk, compliance_rate: drill.compliance_rate, conforming: drill.conforming, partial: drill.partial, nonconforming: drill.nonconforming, not_assessed: drill.not_assessed, assessed: drill.assessed }}
              />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

const CSF_COLORS = { GV: "text-primary", ID: "text-ai", PR: "text-low", DE: "text-high", RS: "text-crit", RC: "text-primary" };

function NistDashboard({ data }) {
  const nist = data.nist || { overall: {}, functions: [] };
  const o = nist.overall || {};
  return (
    <div className="space-y-5" data-testid="cra-nist">
      <Panel title="NIST Alignment" subtitle={`EU CRA controls mapped to ${o.framework || "NIST CSF 2.0 · SP 800-218 (SSDF)"}. Synced live with the Control Dashboard.`}>
        <div className="mb-4 flex items-center gap-4">
          <div>
            <div className="text-[10px] font-mono uppercase text-muted-foreground">Overall NIST alignment</div>
            <div className="font-head font-black text-4xl mt-1" data-testid="cra-nist-overall">{o.alignment_percentage || 0}%</div>
          </div>
          <div className="text-[10px] text-muted-foreground">{o.functions_aligned || 0}/{o.functions_total || 6} CSF functions fully aligned</div>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
          {(nist.functions || []).map((f) => (
            <div key={f.code} className="rounded-xl border border-border bg-secondary/20 p-4" data-testid={`cra-nist-fn-${f.code}`}>
              <div className={`text-[10px] font-mono uppercase ${CSF_COLORS[f.code] || "text-primary"}`}>{f.code} · {f.name}</div>
              <div className="font-head font-black text-2xl mt-1">{f.compliance_rate === null || f.compliance_rate === undefined ? "—" : `${f.compliance_rate}%`}</div>
              <div className="mt-2 h-1.5 rounded-full bg-secondary overflow-hidden"><div className={`h-full ${(f.compliance_rate || 0) >= 100 ? "bg-low" : (f.compliance_rate || 0) >= 50 ? "bg-high" : "bg-crit"}`} style={{ width: `${f.compliance_rate || 0}%` }} /></div>
              <div className="text-[10px] text-muted-foreground mt-2">{f.mapped} controls</div>
              <div className="mt-1"><Badge tone={RISK_TONE[f.risk] || "primary"}>{f.risk}</Badge></div>
            </div>
          ))}
        </div>
      </Panel>
      {(nist.functions || []).map((f) => (
        <Panel key={f.code} title={`${f.code} — ${f.name}`} subtitle={`${(f.categories || []).join(", ") || "—"} · ${f.implemented} implemented · ${f.partial} partial · ${f.gaps} gaps · ${f.not_started} not started`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-xs">
              <thead className="font-mono uppercase text-[9px] text-muted-foreground border-b border-border"><tr><th className="text-left py-2">Control</th><th className="text-left py-2">CSF categories</th><th className="text-left py-2">SSDF</th><th className="text-left py-2">Compliance</th><th className="text-left py-2">Status</th></tr></thead>
              <tbody>
                {f.controls.map((c) => (
                  <tr key={c.requirement_id} className="border-b border-border/60">
                    <td className="py-2 pr-3"><span className="font-mono text-ai">{c.requirement_id}</span> {c.title}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{(c.categories || []).join(", ")}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{(c.ssdf || []).join(", ")}</td>
                    <td className="py-2 pr-3">{c.compliance_rate === null || c.compliance_rate === undefined ? "—" : `${c.compliance_rate}%`}</td>
                    <td className="py-2"><Badge tone={STATUS_TONE[c.status] || "primary"}>{c.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 pt-3 border-t border-border/60">
            <CraExplainToggle
              title={`NIST ${f.code} — ${f.name}`}
              kind="cra-nist-function"
              context={{ function: f.code, name: f.name, compliance_rate: f.compliance_rate, risk: f.risk, mapped: f.mapped, implemented: f.implemented, partial: f.partial, gaps: f.gaps, not_started: f.not_started, categories: f.categories }}
            />
          </div>
        </Panel>
      ))}
    </div>
  );
}

function RegulationMap({ data }) {
  const requirements = data.regulation?.requirements || [];
  return (
    <Panel title="Authoritative CRA requirement map" subtitle="Each workflow object links back to Regulation (EU) 2024/2847 and Commission Implementing Regulation (EU) 2025/2392.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] text-xs">
          <thead className="font-mono uppercase text-[9px] text-muted-foreground border-b border-border"><tr><th className="text-left py-3">Requirement</th><th className="text-left py-3">Domain</th><th className="text-left py-3">Obligation</th><th className="text-left py-3">Legal basis</th><th className="text-left py-3">Evidence</th></tr></thead>
          <tbody>
            {requirements.map((item) => (
              <tr key={item.requirement_id} className="border-b border-border/60">
                <td className="py-3 font-mono text-ai">{item.requirement_id}</td><td className="py-3">{item.domain}</td><td className="py-3 max-w-[430px]">{item.title}</td><td className="py-3 max-w-[300px]">{item.legal_refs.join(", ")}</td><td className="py-3 max-w-[300px]">{item.evidence_types.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function CRAGovernance() {
  const { user, mode } = useAuth();
  const isAdmin = user?.role === "admin";
  const { data, loading, refreshing, error, sourceStatus, reload } = useCRAData();
  const [active, setActive] = useState(() => localStorage.getItem("cra-governance-tab") || "mission");
  const [reportBusy, setReportBusy] = useState(false);
  const [pulse, setPulse] = useState(() => localStorage.getItem("cra-governance-tab-pulse") || null);

  useEffect(() => {
    if (!pulse) return;
    localStorage.removeItem("cra-governance-tab-pulse");
    const t = setTimeout(() => setPulse(null), 2600);
    return () => clearTimeout(t);
  }, [pulse]);

  const openTab = (tab) => {
    setActive(tab);
    setPulse(null);
    localStorage.setItem("cra-governance-tab", tab);
  };

  const generateReport = async () => {
    setReportBusy(true);
    try {
      const response = await api.post("/studio/report/pdf", {
        title: "EU CRA Governance Executive Brief",
        ai_narrative: "Generated from Obserra CRA product, assessment, SBOM, vulnerability, external assessment and regulatory ledger records. Automated classification remains proposed until authorized approval. Obserra provides regulatory workflow and traceability, not legal advice.",
        blocks: reportBlocks(data || {}),
      }, { responseType: "blob" });
      downloadBlob(response.data, "obserra-eu-cra-governance-executive-brief.pdf");
      toast.success("EU CRA Governance Executive Brief generated.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Report generation failed.");
    } finally {
      setReportBusy(false);
    }
  };

  if (loading || !data) {
    return <div className="min-h-[55vh] flex items-center justify-center"><Loader2 className="w-7 h-7 animate-spin text-primary" /></div>;
  }

  return (
    <div className="rise space-y-6" data-testid="cra-governance-page">
      <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap"><Landmark className="w-7 h-7 text-primary" /><h1 className="font-head font-black text-2xl lg:text-3xl tracking-tight" data-testid="cra-page-title">European Union Cyber Resilience Act Governance</h1><Badge tone="primary">REGULATION (EU) 2024/2847</Badge></div>
          <p className="text-sm text-muted-foreground mt-2 max-w-4xl">
            {mode === "executive"
              ? "Multi-tenant EU Cyber Resilience Act product governance, certification readiness, external conformity assessment, SBOM, Article 14 reporting, regulatory ledger, EU declaration and CE readiness."
              : "Operate product classification, regulation-mapped assessments, vendor certification workflows, SBOM generation, vulnerability reporting clocks, notified-body evidence and immutable regulatory records."}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={reload} disabled={refreshing} data-testid="cra-refresh" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-secondary/40 text-xs font-head font-bold"><RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} /> Refresh</button>
          <button onClick={generateReport} disabled={reportBusy} data-testid="cra-executive-brief" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-head font-bold">{reportBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Executive Brief</button>
        </div>
      </div>

      {error && <div className="rounded-xl border border-crit/25 bg-crit/5 p-4 text-sm">{error}</div>}

      <div>
        <div className="flex flex-wrap gap-1 rounded-xl border border-border bg-card p-1">
          {TABS.map(([id, label, Icon]) => (
            <button key={id} data-testid={`cra-tab-${id}`} onClick={() => openTab(id)} className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-head font-bold ${active === id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"} ${pulse === id ? "cra-tab-pulse" : ""}`}><Icon className="w-3.5 h-3.5" /> {label}</button>
          ))}
        </div>
      </div>

      {active !== "mission" && active !== "assurance" && <CraTabAnalyst tab={active} />}

      {active === "assurance" && <AiAssurance />}

      {active === "mission" && <MissionControl data={data} openTab={openTab} />}
      {active === "products" && <ProductClassification data={data} reload={reload} isAdmin={isAdmin} />}
      {active === "certification" && <CertificationPortal data={data} reload={reload} isAdmin={isAdmin} />}
      {active === "ledger" && <RegulatoryLedger data={data} isAdmin={isAdmin} />}
      {active === "sbom" && <SBOMDashboard data={data} reload={reload} />}
      {active === "vulnerability" && <VulnerabilityDashboard data={data} reload={reload} />}
      {active === "conformity" && <ConformityDashboard data={data} reload={reload} isAdmin={isAdmin} />}
      {active === "declaration" && <DeclarationDashboard data={data} reload={reload} isAdmin={isAdmin} />}
      {active === "regulation" && <RegulationMap data={data} />}
      {active === "controls" && <ControlDashboard data={data} isAdmin={isAdmin} reload={reload} />}
      {active === "nist" && <NistDashboard data={data} />}

      <Panel title="Defensibility and legal boundary" subtitle="Operational safeguards for a regulation-driven platform">
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3 text-xs">
          <div className="rounded-lg border border-border p-3"><BookOpenCheck className="w-4 h-4 text-primary" /><div className="font-head font-bold mt-2">Version-aware legal map</div><div className="text-muted-foreground mt-1">{data.regulation.regulation} + {data.regulation.classification_implementing_regulation}</div></div>
          <div className="rounded-lg border border-border p-3"><ShieldCheck className="w-4 h-4 text-low" /><div className="font-head font-bold mt-2">Tenant isolation</div><div className="text-muted-foreground mt-1">Internal records are scoped by the authenticated organization.</div></div>
          <div className="rounded-lg border border-border p-3"><Fingerprint className="w-4 h-4 text-ai" /><div className="font-head font-bold mt-2">Hash-chained ledger</div><div className="text-muted-foreground mt-1">Append-only regulatory events include prior-record and current-record hashes.</div></div>
          <div className="rounded-lg border border-border p-3"><Globe2 className="w-4 h-4 text-high" /><div className="font-head font-bold mt-2">External portal separation</div><div className="text-muted-foreground mt-1">Vendor and assessor portals never expose the private Internal Regulatory Ledger.</div></div>
        </div>
        <div className="mt-4 text-[10px] font-mono text-muted-foreground">Source health: {Object.entries(sourceStatus || {}).map(([key, status]) => `${key}:${status?.ok ? "OK" : "UNAVAILABLE"}`).join(" · ")}</div>
      </Panel>
    </div>
  );
}
