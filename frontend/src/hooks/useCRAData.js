import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const SOURCES = [
  ["dashboard", "/cra/dashboard", {}],
  ["products", "/cra/products", []],
  ["assessments", "/cra/assessments", []],
  ["providers", "/cra/providers", []],
  ["externalAssessments", "/cra/external-assessments", []],
  ["vulnerabilities", "/cra/vulnerabilities", []],
  ["regulation", "/cra/regulation", { requirements: [], categories: {} }],
  ["controls", "/cra/controls", { overall: {}, controls: [] }],
  ["nist", "/cra/nist", { overall: {}, functions: [] }],
  ["ledger", "/cra/ledger?limit=300", []],
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

export function useCRAData() {
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

    const data = {};
    const sourceStatus = {};
    for (const result of results) {
      data[result.name] = result.data;
      sourceStatus[result.name] = { ok: result.ok, error: result.error };
    }

    const coreAvailable =
      sourceStatus.dashboard?.ok &&
      sourceStatus.products?.ok &&
      sourceStatus.regulation?.ok;

    setState({
      loading: false,
      refreshing: false,
      error: coreAvailable
        ? ""
        : "One or more core EU CRA sources are unavailable. Obserra will not substitute synthetic regulatory or product data.",
      data,
      sourceStatus,
    });
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  const productIndex = useMemo(() => {
    const index = {};
    for (const product of state.data?.products || []) index[product.ref] = product;
    return index;
  }, [state.data]);

  return {
    ...state,
    productIndex,
    reload: () => load(true),
  };
}
