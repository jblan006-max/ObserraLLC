// Prefetch a route's lazy-loaded chunk on nav hover/focus so the click renders instantly
// (no Suspense spinner). Webpack dedupes these importers with the lazy() imports in App.js,
// so a prefetched chunk is reused — not re-downloaded — when the route actually mounts.
// Keep this map in sync with the routes in App.js.
const IMPORTERS = {
  "/app": () => import("@/pages/SapOverview"),
  "/app/analytics": () => import("@/pages/SapAnalytics"),
  "/app/sod": () => import("@/pages/SodCommandCenter"),
  "/app/privileged": () => import("@/pages/PrivilegedAccess"),
  "/app/monitoring": () => import("@/pages/AccessMonitoring"),
  "/app/identities": () => import("@/pages/Identities"),
  "/app/activation": () => import("@/pages/UserActivation"),
  "/app/lifecycle": () => import("@/pages/Lifecycle"),
  "/app/hr-reconciliation": () => import("@/pages/HrReconciliation"),
  "/app/access-requests": () => import("@/pages/AccessRequests"),
  "/app/certifications": () => import("@/pages/Certifications"),
  "/app/roles": () => import("@/pages/RoleIntelligence"),
  "/app/workflow": () => import("@/pages/WorkflowActivity"),
  "/app/systems": () => import("@/pages/SapSystems"),
  "/app/audit": () => import("@/pages/AuditLog"),
  "/app/team": () => import("@/pages/Team"),
  "/app/settings": () => import("@/pages/Settings"),
  "/app/system-health": () => import("@/pages/SystemHealth"),
  "/app/billing": () => import("@/pages/Billing"),
  "/app/marketplace": () => import("@/pages/Marketplace"),
};

const done = new Set();

export function prefetchRoute(to) {
  if (!to || done.has(to)) return;
  const imp = IMPORTERS[to];
  if (!imp) return;
  done.add(to);
  imp().catch(() => done.delete(to));
}
