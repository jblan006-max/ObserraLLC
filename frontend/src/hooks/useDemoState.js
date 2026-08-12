import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

// Polls the org-wide Cyber Crisis Commander demo flag so the global DEMO ribbon and
// the CI dashboards can light up together when a showcase journey is seeded.
export function useDemoState(pollMs = 45000) {
  const [active, setActive] = useState(false);

  const refresh = useCallback(() => {
    api
      .get("/control-intelligence/demo/state")
      .then((r) => setActive(Boolean(r.data.active)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const onChange = () => refresh();
    window.addEventListener("ci-demo-changed", onChange);
    const id = pollMs ? setInterval(refresh, pollMs) : null;
    return () => {
      window.removeEventListener("ci-demo-changed", onChange);
      if (id) clearInterval(id);
    };
  }, [refresh, pollMs]);

  return { demoActive: active, refreshDemo: refresh };
}
