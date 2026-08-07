import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { Bell, ShieldAlert, FileText, Users, CheckCheck } from "lucide-react";

const ICON = { control_drift: ShieldAlert, report: FileText, team: Users };

export function NotificationBell() {
  const [data, setData] = useState({ items: [], unread: 0 });
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const load = () => api.get("/notifications").then((r) => setData(r.data)).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 25000); return () => clearInterval(t); }, []);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const markAll = async () => { await api.post("/notifications/read-all"); load(); };
  const openOne = async (id) => { await api.post(`/notifications/${id}/read`); load(); };

  return (
    <div className="relative" ref={ref}>
      <button data-testid="notif-bell" onClick={() => setOpen((v) => !v)}
        className="relative w-9 h-9 flex items-center justify-center rounded-md hover:bg-secondary/60 transition-colors">
        <Bell className="w-4.5 h-4.5 text-muted-foreground" style={{ width: 18, height: 18 }} />
        {data.unread > 0 && (
          <span data-testid="notif-badge" className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-crit text-white text-[9px] font-bold flex items-center justify-center">
            {data.unread > 9 ? "9+" : data.unread}
          </span>
        )}
      </button>
      {open && (
        <div data-testid="notif-panel" className="absolute right-0 mt-2 w-80 max-h-[70vh] overflow-y-auto bg-card fact-border rounded-xl shadow-2xl z-50">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border sticky top-0 bg-card">
            <span className="font-head font-bold text-sm">Notifications</span>
            <button data-testid="notif-mark-all" onClick={markAll} className="flex items-center gap-1 text-[11px] text-ai hover:underline"><CheckCheck className="w-3.5 h-3.5" /> Mark all read</button>
          </div>
          {data.items.length === 0 ? (
            <div className="px-4 py-8 text-center text-xs text-muted-foreground">You're all caught up.</div>
          ) : data.items.map((n) => {
            const Icon = ICON[n.kind] || Bell;
            return (
              <button key={n.id} data-testid={`notif-item-${n.id}`} onClick={() => openOne(n.id)}
                className={`w-full text-left flex gap-3 px-4 py-3 border-b border-border/50 hover:bg-secondary/40 transition-colors ${n.read ? "opacity-60" : ""}`}>
                <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${n.kind === "control_drift" ? "text-high" : "text-ai"}`} />
                <div className="min-w-0">
                  <div className="text-xs font-medium">{n.title}{!n.read && <span className="ml-1.5 inline-block w-1.5 h-1.5 rounded-full bg-ai align-middle" />}</div>
                  <div className="text-[11px] text-muted-foreground line-clamp-2">{n.body}</div>
                  <div className="text-[10px] font-mono text-muted-foreground mt-0.5">{new Date(n.created_at).toLocaleString()}</div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
