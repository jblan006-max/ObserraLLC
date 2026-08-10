import { useState } from "react";
import { Loader2, X } from "lucide-react";

export default function RegisterAgentModal({ busy, onClose, onSubmit }) {
  const [form, setForm] = useState({
    name: "",
    owner: "",
    model: "",
    tools: "",
    permissions: "",
    risk_class: "Medium",
  });

  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const submit = (event) => {
    event.preventDefault();
    onSubmit({
      name: form.name.trim(),
      owner: form.owner.trim(),
      model: form.model.trim(),
      tools: form.tools.split(",").map((value) => value.trim()).filter(Boolean),
      permissions: form.permissions.split(",").map((value) => value.trim()).filter(Boolean),
      risk_class: form.risk_class,
    });
  };

  return (
    <div className="fixed inset-0 z-[75] bg-black/65 backdrop-blur-sm flex items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-xl bg-card fact-border rounded-xl p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-head font-black text-xl">Register AI Agent</h2>
            <p className="text-xs text-muted-foreground mt-1">
              Uses the existing Obserra POST /agents API.
            </p>
          </div>
          <button type="button" onClick={onClose} className="p-2 rounded-md hover:bg-secondary">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid md:grid-cols-2 gap-3 mt-5">
          <label className="text-xs">
            <span className="text-muted-foreground">Name</span>
            <input
              required
              value={form.name}
              onChange={(event) => set("name", event.target.value)}
              className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 outline-none focus:ring-1 focus:ring-primary"
            />
          </label>
          <label className="text-xs">
            <span className="text-muted-foreground">Owner</span>
            <input
              required
              value={form.owner}
              onChange={(event) => set("owner", event.target.value)}
              className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 outline-none focus:ring-1 focus:ring-primary"
            />
          </label>
          <label className="text-xs">
            <span className="text-muted-foreground">Model</span>
            <input
              required
              value={form.model}
              onChange={(event) => set("model", event.target.value)}
              placeholder="gpt-5.6"
              className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 outline-none focus:ring-1 focus:ring-primary"
            />
          </label>
          <label className="text-xs">
            <span className="text-muted-foreground">Risk class</span>
            <select
              value={form.risk_class}
              onChange={(event) => set("risk_class", event.target.value)}
              className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5"
            >
              <option>Critical</option>
              <option>High</option>
              <option>Medium</option>
              <option>Low</option>
            </select>
          </label>
        </div>

        <label className="text-xs block mt-3">
          <span className="text-muted-foreground">Tools, comma separated</span>
          <input
            value={form.tools}
            onChange={(event) => set("tools", event.target.value)}
            placeholder="sql.read, email.send, erp.write"
            className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 outline-none focus:ring-1 focus:ring-primary"
          />
        </label>

        <label className="text-xs block mt-3">
          <span className="text-muted-foreground">Permissions, comma separated</span>
          <input
            value={form.permissions}
            onChange={(event) => set("permissions", event.target.value)}
            placeholder="finance.read, finance.write"
            className="mt-1 w-full bg-secondary/60 rounded-md px-3 py-2.5 outline-none focus:ring-1 focus:ring-primary"
          />
        </label>

        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full px-4 py-3 rounded-md bg-primary text-primary-foreground font-head font-bold flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {busy && <Loader2 className="w-4 h-4 animate-spin" />}
          Register Agent
        </button>
      </form>
    </div>
  );
}