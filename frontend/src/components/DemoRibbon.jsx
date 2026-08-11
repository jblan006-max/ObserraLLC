import { FlaskConical } from "lucide-react";
import { useDemoState } from "@/hooks/useDemoState";

// Subtle global strip shown whenever Control Intelligence demo data is active, so a
// showcase is never mistaken for live evidence during a screen-share.
export function DemoRibbon() {
  const { demoActive } = useDemoState();
  if (!demoActive) return null;
  return (
    <div
      data-testid="demo-mode-ribbon"
      className="flex items-center justify-center gap-2 px-4 py-1.5 bg-med/15 border-b border-med/30 text-med text-[11px] font-mono font-bold uppercase tracking-wider"
    >
      <FlaskConical className="w-3.5 h-3.5" />
      Demo mode active — showcase data is displayed. This is not live evidence.
    </div>
  );
}
