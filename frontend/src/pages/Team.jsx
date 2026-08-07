import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Users, UserPlus, Loader2, Trash2, Copy, KeyRound } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ROLE_LABEL = { admin: "Admin", executive: "Executive", operational: "Operational" };
const ROLE_COLOR = { admin: "225 70% 60%", executive: "142 70% 45%", operational: "190 90% 50%" };

export default function Team() {
  const [members, setMembers] = useState(null);
  const [form, setForm] = useState({ name: "", email: "", role: "operational" });
  const [busy, setBusy] = useState(false);
  const [invited, setInvited] = useState(null);
  const navigate = useNavigate();

  const load = () => api.get("/auth/team/members").then((r) => setMembers(r.data)).catch(() => navigate("/app"));
  useEffect(() => { load(); }, []);

  const invite = async (e) => {
    e.preventDefault();
    setBusy(true); setInvited(null);
    try {
      const { data } = await api.post("/auth/team/invite", form);
      setInvited(data);
      toast.success(`${data.email} invited as ${ROLE_LABEL[data.role]}`);
      setForm({ name: "", email: "", role: "operational" });
      load();
    } catch (e2) { toast.error(e2.response?.data?.detail || "Could not invite"); }
    setBusy(false);
  };

  const remove = async (id, email) => {
    try { await api.delete(`/auth/team/members/${id}`); toast.success(`${email} removed`); load(); }
    catch (e2) { toast.error(e2.response?.data?.detail || "Could not remove"); }
  };

  const copy = (txt) => { navigator.clipboard.writeText(txt); toast.success("Copied"); };

  return (
    <div className="rise space-y-6 max-w-4xl">
      <div>
        <h1 className="font-head font-black text-3xl tracking-tight flex items-center gap-2"><Users className="w-7 h-7 text-primary" /> Team</h1>
        <p className="text-sm text-muted-foreground mt-1">Invite executive & operational teammates into your organization with the right role.</p>
      </div>

      <form onSubmit={invite} data-testid="invite-form" className="bg-card fact-border rounded-xl p-5 grid sm:grid-cols-4 gap-3 items-end">
        <label className="block sm:col-span-1">
          <span className="text-xs font-medium text-muted-foreground mb-1.5 block">Full name</span>
          <input data-testid="invite-name" required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
        </label>
        <label className="block sm:col-span-1">
          <span className="text-xs font-medium text-muted-foreground mb-1.5 block">Work email</span>
          <input data-testid="invite-email" type="email" required value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            className="w-full bg-secondary/60 rounded-md px-3 py-2.5 text-sm outline-none focus:ring-1 focus:ring-primary" />
        </label>
        <div className="block sm:col-span-1">
          <span className="text-xs font-medium text-muted-foreground mb-1.5 block">Role</span>
          <Select value={form.role} onValueChange={(v) => setForm((f) => ({ ...f, role: v }))}>
            <SelectTrigger data-testid="invite-role" className="w-full bg-secondary/60"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="operational">Operational</SelectItem>
              <SelectItem value="executive">Executive</SelectItem>
              <SelectItem value="admin">Admin</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <button data-testid="invite-submit" disabled={busy} type="submit"
          className="flex items-center justify-center gap-2 py-2.5 rounded-md bg-primary text-primary-foreground font-head font-bold text-sm hover:opacity-90 transition-opacity disabled:opacity-50">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />} Invite
        </button>
      </form>

      {invited && (
        <div data-testid="invite-result" className="ai-border rounded-lg p-4 bg-ai/5">
          <div className="flex items-center gap-2 text-sm font-medium mb-2"><KeyRound className="w-4 h-4 text-ai" /> Temporary password for {invited.email}</div>
          <div className="flex items-center gap-2">
            <code data-testid="temp-password" className="flex-1 font-mono text-sm bg-secondary/60 rounded-md px-3 py-2 select-all">{invited.temp_password}</code>
            <button onClick={() => copy(invited.temp_password)} className="flex items-center gap-1 text-xs px-3 py-2 rounded-md bg-primary/10 border border-primary/30 hover:bg-primary/20"><Copy className="w-3.5 h-3.5" /> Copy</button>
          </div>
          <p className="text-[11px] text-muted-foreground mt-2">Share this securely — the teammate signs in with their email and this password.</p>
        </div>
      )}

      {!members ? <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div> : (
        <div className="bg-card fact-border rounded-xl overflow-x-auto">
          <table className="w-full text-sm min-w-[560px]">
            <thead className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border">
              <tr><th className="text-left px-4 py-3">Member</th><th className="text-left px-4 py-3">Email</th><th className="text-left px-4 py-3">Role</th><th className="text-right px-4 py-3">Actions</th></tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id} data-testid={`member-${m.id}`} className="border-b border-border/60 hover:bg-secondary/40 transition-colors">
                  <td className="px-4 py-3 font-medium">{m.name}</td>
                  <td className="px-4 py-3 text-muted-foreground font-mono text-xs">{m.email}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold" style={{ background: `hsl(${ROLE_COLOR[m.role]} / 0.15)`, color: `hsl(${ROLE_COLOR[m.role]})` }}>{ROLE_LABEL[m.role] || m.role}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button data-testid={`remove-${m.id}`} onClick={() => remove(m.id, m.email)}
                      className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md text-muted-foreground hover:text-crit hover:bg-crit/10 transition-colors"><Trash2 className="w-3.5 h-3.5" /> Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
