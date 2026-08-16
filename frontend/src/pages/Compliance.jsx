import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  LineChart,
  Line,
} from 'recharts';

const COLORS = ["#0A5B7A", "#10B981", "#E11D48", "#F59E0B", "#A78BFA"];

export default function Compliance() {
  const [controls, setControls] = useState([]);
  const [mapping, setMapping] = useState(null);
  const [cra, setCra] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState("All");
  const [selectedControl, setSelectedControl] = useState(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      api.get("/nist/controls").then((r) => r.data.controls).catch(() => []),
      api.get("/nist/eu-cra").then((r) => r.data.requirements).catch(() => []),
      api.get("/nist/mapping").then((r) => r.data).catch(() => null),
    ]).then(([ctls, craReq, map]) => {
      if (!mounted) return;
      setControls(ctls || []);
      setCra(craReq || []);
      setMapping(map || null);
      setLoading(false);
    });
    return () => { mounted = false; };
  }, []);

  async function refresh() {
    setLoading(true);
    try {
      const res = await api.post("/nist/map-me");
      setMapping(res.data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }

  function exportCsv() {
    if (!mapping) return;
    const rows = mapping.mapping.map(m => ({ id: m.id, title: m.title, family: m.family, satisfied: m.satisfied }));
    const csv = [Object.keys(rows[0]).join(','), ...rows.map(r => `${r.id},"${(r.title||'').replace(/"/g,'""')}",${r.family||''},${r.satisfied}`)].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'nist_mapping.csv'; a.click();
    URL.revokeObjectURL(url);
  }

  const families = useMemo(() => {
    const set = new Set();
    controls.forEach(c => set.add((c.family || 'Other')));
    return ["All", ...Array.from(set).sort()];
  }, [controls]);

  const filteredControls = useMemo(() => {
    const q = query.trim().toLowerCase();
    return controls.filter(c => {
      if (family !== 'All' && (c.family || 'Other') !== family) return false;
      if (!q) return true;
      return (c.id || '').toLowerCase().includes(q) || (c.title || '').toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q);
    });
  }, [controls, query, family]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <img src="/brand-mark.png" alt="Obserra" className="h-8 w-auto" />
          <h1 className="text-2xl font-head font-bold">Obserra — Compliance & Controls</h1>
        </div>
        <div className="flex gap-3 items-center">
          <input placeholder="Search id, title, description" value={query} onChange={(e) => setQuery(e.target.value)} className="px-3 py-2 border rounded-md" style={{ borderColor: 'hsl(var(--brand))' }} />
          <select value={family} onChange={e => setFamily(e.target.value)} className="px-3 py-2 border rounded-md">
            {families.map(f => <option key={f} value={f}>{f}</option>)}
          </select>
          <button onClick={refresh} className="px-4 py-2 rounded-md bg-brand text-brand-foreground">Refresh</button>
        </div>
      </div>

      {loading && <div className="text-sm text-muted-foreground">Loading…</div>}

      {!loading && mapping && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <StatCard title="Controls" value={mapping.total_controls} color="bg-white" />
          <StatCard title="Satisfied" value={mapping.satisfied} color="bg-white" />
          <StatCard title="Score" value={`${mapping.score_percent}%`} color="bg-white" />
        </div>
      )}

      {!loading && mapping && (
        <div className="flex gap-3 mb-6">
          <button onClick={exportCsv} className="px-4 py-2 rounded-md bg-secondary text-secondary-foreground">Export CSV</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card p-4 rounded-md">
          <h2 className="font-bold mb-3">NIST Controls</h2>
          <div className="flex gap-4 mb-4">
            <div style={{ width: 220, height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={[{ name: 'Satisfied', value: mapping.satisfied || 0 }, { name: 'Unmet', value: (mapping.total_controls || 0) - (mapping.satisfied || 0) }]} dataKey="value" innerRadius={40} outerRadius={70} paddingAngle={4}>
                    <Cell fill={COLORS[0]} />
                    <Cell fill={COLORS[1]} />
                  </Pie>
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div style={{ flex: 1 }}>
              <div className="text-sm text-muted-foreground">Score</div>
              <div className="mt-2 font-head font-bold text-4xl">{mapping.score_percent}%</div>
              <div className="mt-4">
                <Sparkline data={mapping.mapping || []} />
              </div>
            </div>
          </div>

          <div className="space-y-2 max-h-[60vh] overflow-auto">
            {filteredControls.map((c) => {
              const matched = mapping?.mapping?.find((m) => m.id === c.id)?.satisfied;
              return (
                <div key={c.id} onClick={() => setSelectedControl({ ...c, satisfied: matched })} className={`p-3 rounded-md border hover:shadow cursor-pointer ${matched ? 'border-green-200 bg-green-50' : 'border-muted-200 bg-white'}`}>
                  <div className="flex items-center justify-between">
                    <div><strong>{c.id}</strong> — {c.title}</div>
                    <div className={`text-sm ${matched ? 'text-green-600' : 'text-muted-foreground'}`}>{matched ? 'Satisfied' : 'Unmet'}</div>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">{c.description}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-card p-4 rounded-md">
          <h2 className="font-bold mb-3">EU CRA Requirements</h2>
          <div className="space-y-2 max-h-[70vh] overflow-auto">
            {cra.map((r) => {
              const mappedNist = r.mapped_nist || [];
              const satisfiedCount = mappedNist.filter((id) => mapping?.mapping?.find((m) => m.id === id && m.satisfied)).length;
              const allSatisfied = mappedNist.length > 0 && satisfiedCount === mappedNist.length;
              return (
                <div key={r.id} className={`p-3 rounded-md border ${allSatisfied ? 'border-green-200 bg-green-50' : 'border-muted-200 bg-white'}`}>
                  <div className="flex items-center justify-between">
                    <div><strong>{r.id}</strong> — {r.title}</div>
                    <div className={`text-sm ${allSatisfied ? 'text-green-600' : 'text-muted-foreground'}`}>{allSatisfied ? 'Compliant' : 'Non-compliant'}</div>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">{r.description}</div>
                  <div className="text-xs mt-2">Mapped NIST: {mappedNist.join(', ') || '—'}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {selectedControl && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/40">
          <div className="w-11/12 md:w-2/3 lg:w-1/2 bg-white p-6 rounded-md">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-lg font-bold">{selectedControl.id} — {selectedControl.title}</h3>
                <div className="text-xs text-muted-foreground">{selectedControl.family}</div>
              </div>
              <button onClick={() => setSelectedControl(null)} className="text-sm px-2 py-1">Close</button>
            </div>
            <div className="mt-4 text-sm text-muted-foreground">{selectedControl.description}</div>
            <div className="mt-4">
              <h4 className="font-semibold">Evidence</h4>
              <ul className="text-xs list-disc pl-5 mt-2 text-muted-foreground">
                {/* Show mapped evidence items from mapping if present */}
                {(mapping?.mapping?.find(m => m.id === selectedControl.id)?.evidence || ['No direct evidence recorded']).map((e, i) => (
                  <li key={i}>{typeof e === 'string' ? e : JSON.stringify(e)}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ title, value }) {
  return (
    <div className="p-4 bg-card rounded-md">
      <div className="text-sm text-muted-foreground">{title}</div>
      <div className="mt-2 font-head font-bold text-xl">{value}</div>
    </div>
  );
}

function Sparkline({ data }) {
  // small sparkline showing satisfied trend (best-effort from mapping array)
  const series = (data || []).slice(-20).map((m, i) => ({ x: i, y: m.satisfied ? 1 : 0 }));
  if (!series.length) return null;
  return (
    <div style={{ width: '100%', height: 60 }}>
      <ResponsiveContainer>
        <LineChart data={series}>
          <Line type="monotone" dataKey="y" stroke="#10B981" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
