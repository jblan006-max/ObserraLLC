import React, { useEffect, useRef, useState, cloneElement } from "react";

// React 19 + Recharts ResponsiveContainer throws a "markRef" ref error.
// ChartBox measures its own width (ResizeObserver) and passes explicit
// width/height to the chart, bypassing ResponsiveContainer entirely.
// The error boundary guarantees a chart failure never white-screens the page.
class ChartErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { err: false };
  }
  static getDerivedStateFromError() {
    return { err: true };
  }
  render() {
    return this.state.err
      ? <div className="text-[11px] text-muted-foreground p-2">Chart unavailable.</div>
      : this.props.children;
  }
}

export function ChartBox({ height = 200, children }) {
  const ref = useRef(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setW(Math.max(0, Math.floor(el.clientWidth)));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={ref} style={{ width: "100%", height }}>
      <ChartErrorBoundary>{w > 0 ? cloneElement(children, { width: w, height }) : null}</ChartErrorBoundary>
    </div>
  );
}
