import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import {
  controlSummary,
  frameworkSummary,
  normalizeControls,
} from "@/lib/controlIntelligenceModels";

const SOURCES = [
  ["controls", "/controls", []],
  ["compliance", "/controls/compliance", { frameworks: [], gaps: [] }],
  ["crosswalk", "/controls/crosswalk", { frameworks: [], rows: [] }],
  ["connectorHealth", "/connectors/health", { connectors: [], summary: {} }],
  ["effHistory", "/control-intelligence/effectiveness-history?days=30", { history: [] }],
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

export function useControlIntelligenceData(demo = false) {
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

    const sources = SOURCES.map(([name, path, fallback]) =>
      name === "controls" && demo
        ? [name, "/controls?demo=true", fallback]
        : [name, path, fallback]
    );

    const results = await Promise.all(
      sources.map(([name, path, fallback]) => fetchSource(name, path, fallback))
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

    const controls = normalizeControls(
      Array.isArray(raw.controls) ? raw.controls : raw.controls?.controls || []
    );

    const data = {
      controls,
      compliance: raw.compliance || {},
      crosswalk: raw.crosswalk || {},
      connectorHealth: raw.connectorHealth || { connectors: [], summary: {} },
      summary: controlSummary(controls),
      frameworks: frameworkSummary(raw.compliance || {}),
      gaps: Array.isArray(raw.compliance?.gaps) ? raw.compliance.gaps : [],
      effHistory: Array.isArray(raw.effHistory?.history) ? raw.effHistory.history : [],
      generatedAt: new Date().toISOString(),
    };

    setState({
      loading: false,
      refreshing: false,
      error:
        sourceStatus.controls?.ok && sourceStatus.compliance?.ok
          ? ""
          : "One or more core control intelligence sources are unavailable. No substitute controls or compliance values are generated.",
      data,
      sourceStatus,
    });
  }, [demo]);

  useEffect(() => {
    load(false);
  }, [load]);

  const byId = useMemo(() => {
    const index = {};
    for (const control of state.data?.controls || []) {
      index[control.control_id] = control;
    }
    return index;
  }, [state.data]);

  return {
    ...state,
    byId,
    reload: () => load(true),
  };
}
