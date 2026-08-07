import { useSearchParams } from "react-router-dom";

// Keeps a small filter value (search text, status, etc.) in the URL query string
// so a filtered list can be shared or bookmarked. Signature mirrors useState.
export function useUrlState(key, def = "") {
  const [sp, setSp] = useSearchParams();
  const val = sp.get(key) ?? def;
  const set = (v) => {
    const next = typeof v === "function" ? v(val) : v;
    setSp((prev) => {
      const n = new URLSearchParams(prev);
      if (next && next !== def) n.set(key, next);
      else n.delete(key);
      return n;
    }, { replace: true });
  };
  return [val, set];
}
