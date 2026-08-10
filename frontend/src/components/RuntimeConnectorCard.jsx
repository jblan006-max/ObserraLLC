import { useEffect, useState } from "react";
import { Loader2, Plug, Save, Zap } from "lucide-react";
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

  useEffect(() => {
    api.get("/agents/runtime/webhook")
      .then(({ data }) => { setUrl(data.webhook || ""); setConnected(!!data.webhook); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/agents/runtime/webhook", { webhook: url.trim() });
      setConnected(!!data.webhook);
      setUrl(data.webhook || "");
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
      if (data.ok) toast.success(`Runtime received the test event — HTTP ${data.status_code} · ${data.latency_ms}ms`);
      else toast.error(data.status_code ? `Runtime responded HTTP ${data.status_code}` : `No response: ${data.error || "unreachable"}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Test failed.");
    } finally {
      setTesting(false);
    }
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
      </div>
      <p className="text-sm text-muted-foreground">
        Paste your agent execution environment's enforcement webhook. When set, Suspend / Kill / Resume in the Agentic AI
        Security control plane are POSTed to this URL as <span className="text-foreground font-mono">{"{agent_ref, action, mode, org_id}"}</span> so
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
    </div>
  );
}
