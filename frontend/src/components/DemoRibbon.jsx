import { FlaskConical } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useDemoState } from "@/hooks/useDemoState";

// Subtle global strip shown whenever Cyber Crisis Commander demo data is active, so a
// showcase is never mistaken for live evidence during a screen-share. Clicking it
// jumps straight to the Defensibility "Clear demo" control.
export function DemoRibbon() {
  const { demoActive } = useDemoState();
  const navigate = useNavigate();
  if (!demoActive) return null;
  return (
    <button
      type="button"
      onClick={() => navigate("/app/control-intelligence?panel=demo")}
      data-testid="demo-mode-ribbon"
      className="w-full flex items-center justify-center gap-2 px-4 py-1.5 bg-med/15 border-b border-med/30 text-med text-[11px] font-mono font-bold uppercase tracking-wider hover:bg-med/25 transition-colors cursor-pointer"
    >
      <FlaskConical className="w-3.5 h-3.5" />
      Demo mode active — showcase data is displayed. This is not live evidence.
      <span className="underline underline-offset-2">Clear it →</span>
    </button>
  );
}
