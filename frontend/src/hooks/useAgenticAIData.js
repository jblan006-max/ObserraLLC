import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
  incidentSummary,
  normalizeAgents,
  summarizeAgents,
  systemSummary,
} from "@/lib/agenticAIModels";

const SOURCES = [
  ["agents", "/agents", { composition: [], agents: [] }],
  ["analytics", "/dash/ai-analytics", {}],
  ["systems", "/ai-systems", []],
  ["incidents", "/ai-incidents", []],
  ["workflows", "/workflows", []],
  ["connectorHealth", "/connectors/health", { connectors: [], summary: {} }],
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

function unwrapList(value, candidates = []) {
  if (Array.isArray(value)) return value;
  for (const key of candidates) {
    if (Array.isArray(value?.[key])) return value[key];
  }
  return [];
}

export function useAgenticAIData() {
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
      sourceStatus[result.name] = {
        ok: result.ok,
        error: result.error,
      };
    }

    const agentsRaw = unwrapList(raw.agents, ["agents"]);
    const systemsRaw = unwrapList(raw.systems, ["systems", "items"]);
    const incidentsRaw = unwrapList(raw.incidents, ["incidents", "items"]);
    const workflowsRaw = unwrapList(raw.workflows, ["workflows", "items"]);

    const agents = normalizeAgents(agentsRaw);
    const data = {
      composition: raw.agents?.composition || [],
      agents,
      analytics: raw.analytics || {},
      systems: systemsRaw,
      incidents: incidentsRaw,
      workflows: workflowsRaw,
      connectorHealth: raw.connectorHealth || { connectors: [], summary: {} },
      agentSummary: summarizeAgents(agentsRaw),
      systemSummary: systemSummary(systemsRaw),
      incidentSummary: incidentSummary(incidentsRaw),
      generatedAt: new Date().toISOString(),
    };

    const coreAvailable = sourceStatus.agents?.ok && sourceStatus.analytics?.ok;

    setState({
      loading: false,
      refreshing: false,
      error: coreAvailable
        ? ""
        : "Core agent or AI analytics data is unavailable. The control plane will not invent substitute agent records.",
      data,
      sourceStatus,
    });
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  const agentByRef = useMemo(() => {
    const index = {};
    for (const agent of state.data?.agents || []) {
      index[agent.ref] = agent;
    }
    return index;
  }, [state.data]);

  return {
    ...state,
    agentByRef,
    reload: () => load(true),
  };
}