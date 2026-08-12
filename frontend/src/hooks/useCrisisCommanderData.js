import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { crisisScore, highestSeverity } from "@/lib/crisisCommanderModels";

const SOURCES = [
  ["risks", "/risks", []],
  ["incidents", "/ai-incidents", []],
  ["recommendations", "/recommendations", []],
  ["decisions", "/decisions", []],
  ["audit", "/audit-logs", []],
  ["controls", "/controls", []],
  ["compliance", "/controls/compliance", { frameworks: [], gaps: [] }],
  ["strategic", "/risk-engine/strategic", {}],
  ["tactical", "/risk-engine/tactical", {}],
  ["workflows", "/workflows", []],
  ["connectorHealth", "/connectors/health", { connectors: [], summary: {} }],
  ["cases", "/crisis/cases", []],
];

async function fetchSource(name, path, fallback) {
  try {
    const response = await api.get(path);
    return { name, ok: true, data: response.data, error: "" };
  } catch (error) {
    return {
      name,
      ok: false,
      data: fallback,
      error: error.response?.data?.detail || error.message || "Unavailable",
    };
  }
}

function unwrap(value, keys = []) {
  if (Array.isArray(value)) return value;
  for (const key of keys) {
    if (Array.isArray(value?.[key])) return value[key];
  }
  return [];
}

export function useCrisisCommanderData() {
  const [state, setState] = useState({
    loading: true,
    refreshing: false,
    error: "",
    data: null,
    sourceStatus: {},
  });

  const load = useCallback(async (refreshing = false) => {
    setState((current) => ({
      ...current,
      loading: current.data ? false : true,
      refreshing,
      error: "",
    }));

    const results = await Promise.all(
      SOURCES.map(([name, path, fallback]) => fetchSource(name, path, fallback))
    );

    const raw = {};
    const sourceStatus = {};
    for (const result of results) {
      raw[result.name] = result.data;
      sourceStatus[result.name] = { ok: result.ok, error: result.error };
    }

    const risks = unwrap(raw.risks, ["risks"]);
    const incidents = unwrap(raw.incidents, ["incidents", "items"]);
    const recommendations = unwrap(raw.recommendations, ["recommendations", "items"]);
    const decisions = unwrap(raw.decisions, ["decisions", "items"]);
    const audit = unwrap(raw.audit, ["audit", "logs", "items"]);
    const controls = unwrap(raw.controls, ["controls"]);
    const workflows = unwrap(raw.workflows, ["workflows", "items"]);
    const cases = unwrap(raw.cases, ["cases"]);

    const data = {
      risks,
      incidents,
      recommendations,
      decisions,
      audit,
      controls,
      compliance: raw.compliance || {},
      strategic: raw.strategic || {},
      tactical: raw.tactical || {},
      workflows,
      connectorHealth: raw.connectorHealth || { connectors: [], summary: {} },
      cases,
      severity: highestSeverity(incidents, risks),
      crisisScore: crisisScore({ incidents, risks, controls, actions: [] }),
      generatedAt: new Date().toISOString(),
    };

    setState({
      loading: false,
      refreshing: false,
      error:
        sourceStatus.risks?.ok &&
        sourceStatus.controls?.ok &&
        sourceStatus.cases?.ok
          ? ""
          : "One or more crisis intelligence sources are unavailable. Cyber Crisis Commander does not generate substitute incident, risk, control, or crisis case data.",
      data,
      sourceStatus,
    });
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  return {
    ...state,
    reload: () => load(true),
  };
}

export async function fetchCrisisCase(ref) {
  const response = await api.get(`/crisis/cases/${ref}`);
  return response.data;
}
