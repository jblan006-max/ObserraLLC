import { useEffect, useState } from "react";
import { CheckCircle2, FlaskConical, Loader2, Plug, Power, Save, Trash2, XCircle, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

// Agent Runtime Connector — the webhook Kill Switch enforcement is dispatched to.
export function RuntimeConnectorCard() {
  const [url, setUrl] = useState("");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [secret, setSecret] = useState("");
  const [secretSet, setSecretSet] = useState(false);
  const [secretDirty, setSecretDirty] = useState(false);
  const [sim, setSim] = useState(null);
  const [simBusy, setSimBusy] = useState(false);

  const loadWebhook = () => api.get("/agents/runtime/webhook")
    .then(({ data }) => { setUrl(data.webhook || ""); setConnected(!!data.webhook); setSecretSet(!!data.secret_set); })
    .catch(() => {});
  const loadSim = () => api.get("/agents/runtime/simulator").then(({ data }) => setSim(data)).catch(() => {});
  useEffect(() => { loadWebhook().finally(() => setLoading(false)); loadSim(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload = { webhook: url.trim() };
      if (secretDirty) payload.secret = secret;
      const { data } = await api.put("/agents/runtime/webhook", payload);
      setConnected(!!data.webhook);
      setUrl(data.webhook || "");
      setSecretSet(!!data.secret_set);
      setSecret(""); setSecretDirty(false);
      toast.success(data.webhook ? "Agent runtime connector saved." : "Agent runtime connector cleared.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Invalid webhook URL.");
    } finally {
      setSaving(false);
    }
  };

  const sendTest = async () => {
    setTesting(true); setTestResult(null);
    try {
      const { data } = await api.post("/agents/runtime/webhook/test");
      setTestResult(data);
      loadSim();
      if (data.ok) toast.success(`Runtime received the test event — HTTP ${data.status_code} · ${data.latency_ms}ms`);
      else toast.error(data.status_code ? `Runtime responded HTTP ${data.status_code}` : `No response: ${data.error || "unreachable"}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Test failed.");
    } finally {
      setTesting(false);
    }
  };

  const toggleSim = async (on) => {
    setSimBusy(true);
    try {
      const { data } = await api.post(`/agents/runtime/simulator/${on ? "enable" : "disable"}`);
      setSim(data);
      await loadWebhook();
      toast.success(on
        ? "Live enforcement simulator enabled — enforcement now round-trips through a signed webhook."
        : "Simulator disabled.");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not toggle the simulator."); }
    finally { setSimBusy(false); }
  };
  const clearSim = async () => {
    try { const { data } = await api.post("/agents/runtime/simulator/clear"); setSim(data); toast.success("Simulator inbox cleared."); }
    catch { toast.error("Clear failed."); }
  };

  if (loading) return null;

  return (
    <div className="bg-card fact-border rounded-xl p-6 space-y-4" data-testid="runtime-connector-settings">
      <div className="flex items-center gap-2">
        <Plug className="w-4 h-4 text-ai" />
        <h2 className="font-head font-bold text-lg">Agent Runtime Connector (Kill Switch)</h2>
        <span className={`ml-auto text-[10px] font-mono px-2 py-0.5 rounded-full border ${connected ? "bg-low/10 text-low border-low/25" : "bg-secondary/60 text-muted-foreground border-border"}`}>
          {connected ? "Connected" : "Not connected"}
        </span>
        {secretSet && (
          <span data-testid="runtime-webhook-signed" className="text-[10px] font-mono px-2 py-0.5 rounded-full border bg-ai/10 text-ai border-ai/25">
            Signed
          </span>
        )}
      </div>
      <p className="text-sm text-muted-foreground">
        Paste your agent execution environment's enforcement webhook. When set, Suspend / Kill / Resume in the Control Intelligence control plane are POSTed to this URL as <span className="text-foreground font-mono">{"{agent_ref, action, mode, org_id}"}</span> so
        enforcement reaches the live runtime — not just the Obserra control plane. Leave blank to enforce in the control plane only.
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <input
          data-testid="runtime-webhook-input"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://runtime.yourco.com/obserra/enforce"
          className="flex-1 min-w-[240px] bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary"
        />
        <button
          data-testid="runtime-webhook-save"
          disabled={saving}
          onClick={save}
          className="px-4 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save
        </button>
        {connected && (
          <button
            data-testid="runtime-webhook-test"
            disabled={testing}
            onClick={sendTest}
            className="px-4 py-2.5 rounded-md border border-ai/40 text-ai hover:bg-ai/10 font-head font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition-colors"
          >
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />} Send test event
          </button>
        )}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <input
          data-testid="runtime-webhook-secret"
          type="password"
          value={secret}
          onChange={(e) => { setSecret(e.target.value); setSecretDirty(true); }}
          placeholder={secretSet ? "•••••••• (signing secret set — type to replace)" : "Optional HMAC signing secret"}
          className="flex-1 min-w-[240px] bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary"
        />
        <span className="text-[11px] text-muted-foreground max-w-[280px]">
          Signs each enforcement with HMAC-SHA256 (<span className="font-mono">X-Obserra-Signature</span>) so your runtime can verify it genuinely came from Obserra.
        </span>
      </div>
      {testResult && (
        <div
          data-testid="runtime-webhook-test-result"
          className={`text-xs font-mono rounded-md px-3 py-2 border ${testResult.ok ? "bg-low/10 border-low/25 text-low" : "bg-crit/10 border-crit/25 text-crit"}`}
        >
          {testResult.ok
            ? `✓ Runtime received the test event — HTTP ${testResult.status_code} · ${testResult.latency_ms}ms`
            : testResult.status_code
              ? `✗ Runtime responded HTTP ${testResult.status_code} · ${testResult.latency_ms}ms`
              : `✗ No response — ${testResult.error || "unreachable"} · ${testResult.latency_ms}ms`}
        </div>
      )}

      {sim && (
        <div className="rounded-lg border border-ai/25 bg-ai/[0.03] p-4 space-y-3" data-testid="runtime-simulator">
          <div className="flex items-center gap-2 flex-wrap">
            <FlaskConical className="w-4 h-4 text-ai" />
            <span className="font-head font-bold text-sm">Live Enforcement Simulator</span>
            <span data-testid="simulator-status" className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${sim.active ? "bg-low/10 text-low border-low/25" : "bg-secondary/60 text-muted-foreground border-border"}`}>
              {sim.active ? "Active" : "Off"}
            </span>
            <button
              data-testid="simulator-toggle"
              disabled={simBusy}
              onClick={() => toggleSim(!sim.enabled)}
              className={`ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-head font-bold disabled:opacity-50 transition-colors ${sim.enabled ? "border border-crit/30 text-crit hover:bg-crit/10" : "bg-ai text-white hover:bg-ai/90"}`}
            >
              {simBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Power className="w-3.5 h-3.5" />}
              {sim.enabled ? "Disable simulator" : "Enable simulator"}
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            No agent runtime yet? Enable Obserra's built-in receiver to prove the full enforcement path end-to-end. Every
            Suspend / Kill / Resume is POSTed to a first-party HTTPS endpoint over the real ingress, HMAC-signed, and the
            receipt is verified below — no customer runtime required.
          </p>
          {sim.enabled && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md bg-secondary/40 p-2.5"><div className="text-[10px] font-mono uppercase text-muted-foreground">Events received</div><div className="font-head font-black text-xl" data-testid="simulator-received">{sim.received}</div></div>
                <div className="rounded-md bg-secondary/40 p-2.5"><div className="text-[10px] font-mono uppercase text-muted-foreground">Signature verified</div><div className="font-head font-black text-xl text-low" data-testid="simulator-verified">{sim.verified}</div></div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Received enforcement events</span>
                {sim.events?.length > 0 && (
                  <button data-testid="simulator-clear" onClick={clearSim} className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-crit"><Trash2 className="w-3 h-3" /> Clear</button>
                )}
              </div>
              {sim.events?.length ? (
                <div className="space-y-1 max-h-44 overflow-y-auto" data-testid="simulator-events">
                  {sim.events.map((ev, i) => (
                    <div key={i} data-testid={`simulator-event-${i}`} className="flex items-center gap-2 text-[11px] rounded-md border border-border px-2.5 py-1.5">
                      {ev.signature_valid ? <CheckCircle2 className="w-3.5 h-3.5 text-low shrink-0" /> : <XCircle className="w-3.5 h-3.5 text-crit shrink-0" />}
                      <span className="font-mono">{ev.action || "—"}</span>
                      <span className="font-head font-bold truncate">{ev.agent_ref || "—"}</span>
                      <span className={`ml-auto font-mono text-[10px] shrink-0 ${ev.signature_valid ? "text-low" : "text-crit"}`}>{ev.signature_valid ? "signature ✓" : "unsigned"}{ev.at ? ` · ${new Date(ev.at).toLocaleTimeString()}` : ""}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-muted-foreground" data-testid="simulator-empty">No events yet. Click <span className="font-medium text-foreground">Send test event</span> above, or run a Suspend / Kill from the Toxicity Map — it lands here with a verified signature.</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
