import { Fingerprint } from "lucide-react";

export function Footer({ compact = false }) {
  return (
    <footer data-testid="app-footer" className={`border-t border-border/60 ${compact ? "px-6 py-4" : "px-6 lg:px-8 py-5"}`}>
      <div className="max-w-[1500px] mx-auto space-y-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Fingerprint className="w-3.5 h-3.5 text-primary" />
          <span className="font-head font-semibold text-foreground">Property of Obserra — Executive Protection &amp; Intelligence LLC.</span>
          <span className="font-mono">© {new Date().getFullYear()} · All rights reserved.</span>
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground/80 max-w-4xl">
          <span className="font-mono uppercase tracking-wider text-muted-foreground">Disclaimer:</span>{" "}
          Risk scores, AI evaluations, freshness indicators and recommendations are decision-support estimates derived from connected and seeded data sources and do <span className="text-foreground/90">not</span> constitute legal, financial, regulatory, or security guarantees. Automated remediation actions and connector syncs are simulated in this environment. Confidential — for authorized personnel of the licensed organization only.
        </p>
      </div>
    </footer>
  );
}
