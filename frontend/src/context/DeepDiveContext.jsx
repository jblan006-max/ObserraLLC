import { createContext, useContext, useState, useCallback } from "react";
import { RiskDetailModal } from "@/components/RiskDetailModal";

// Global deep-dive modal — ONE RiskDetailModal mounted app-wide. Any card anywhere
// calls openDeepDive(item) to open the standardized deep-dive (live rating/score, AI
// brief + grounded recommendations, and an honest action hub). Items may carry an
// async onAction(kind) that performs a REAL provider call; busy/result are managed here.
const DeepDiveContext = createContext(null);

export function DeepDiveProvider({ children }) {
  const [item, setItem] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const openDeepDive = useCallback((it) => { setResult(null); setBusy(false); setItem(it || null); }, []);
  const close = useCallback(() => { setItem(null); setBusy(false); setResult(null); }, []);

  const handleAction = useCallback(async (kind) => {
    if (!item?.onAction) return;
    setBusy(true);
    try {
      const res = await item.onAction(kind);
      if (res) setResult({ taskId: item.taskId, ...res });
    } catch (e) {
      setResult({
        taskId: item.taskId, verified: false, status: "Not applied",
        message: e?.response?.data?.detail || e?.message || "The live provider call failed — recorded to the Defensibility Ledger.",
      });
    }
    setBusy(false);
  }, [item]);

  return (
    <DeepDiveContext.Provider value={{ openDeepDive, close }}>
      {children}
      <RiskDetailModal
        item={item}
        accent={item?.accent || "255 85% 66%"}
        busy={busy}
        result={result}
        onClose={close}
        onAction={item?.onAction ? handleAction : undefined}
      />
    </DeepDiveContext.Provider>
  );
}

export const useDeepDive = () => useContext(DeepDiveContext) || { openDeepDive: () => {}, close: () => {} };
