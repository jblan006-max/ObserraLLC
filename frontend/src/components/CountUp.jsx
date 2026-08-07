import { useEffect, useRef, useState } from "react";

export function CountUp({ value = 0, duration = 900, decimals = 0, prefix = "", suffix = "", className = "" }) {
  const [v, setV] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    let raf; const startT = performance.now(); const start = from.current;
    const tick = (t) => {
      const p = Math.min(1, (t - startT) / duration);
      setV(start + (value - start) * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick); else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  return <span className={className}>{prefix}{v.toFixed(decimals)}{suffix}</span>;
}
