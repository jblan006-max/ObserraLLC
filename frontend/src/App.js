import "@/App.css";
import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import Auth from "@/pages/Auth";
import AppShell from "@/pages/AppShell";
import AuthCallback from "@/pages/AuthCallback";
import { Loader2 } from "lucide-react";
import { Splash } from "@/components/Splash";
import { InstallBanner } from "@/components/InstallBanner";

// Recover from stale code-split chunks after a rebuild/deploy.
const lazyWithRetry = (importer) => lazy(async () => {
  try {
    const mod = await importer();
    sessionStorage.removeItem("obserra-chunk-reload");
    return mod;
  } catch (err) {
    if (!sessionStorage.getItem("obserra-chunk-reload")) {
      sessionStorage.setItem("obserra-chunk-reload", "1");
      window.location.reload();
      return new Promise(() => {});
    }
    throw err;
  }
});

// Route-level code splitting — Obserra SAP UAC dashboards.
const SapOverview = lazyWithRetry(() => import("@/pages/SapOverview"));
const SodCommandCenter = lazyWithRetry(() => import("@/pages/SodCommandCenter"));
const Identities = lazyWithRetry(() => import("@/pages/Identities"));
const PrivilegedAccess = lazyWithRetry(() => import("@/pages/PrivilegedAccess"));
const AccessMonitoring = lazyWithRetry(() => import("@/pages/AccessMonitoring"));
const Lifecycle = lazyWithRetry(() => import("@/pages/Lifecycle"));
const HrReconciliation = lazyWithRetry(() => import("@/pages/HrReconciliation"));
const RoleIntelligence = lazyWithRetry(() => import("@/pages/RoleIntelligence"));
const AccessRequests = lazyWithRetry(() => import("@/pages/AccessRequests"));
const Certifications = lazyWithRetry(() => import("@/pages/Certifications"));
const SapSystems = lazyWithRetry(() => import("@/pages/SapSystems"));
const UserActivation = lazyWithRetry(() => import("@/pages/UserActivation"));
const SapAnalytics = lazyWithRetry(() => import("@/pages/SapAnalytics"));
const WorkflowActivity = lazyWithRetry(() => import("@/pages/WorkflowActivity"));
const SystemHealth = lazyWithRetry(() => import("@/pages/SystemHealth"));
const AgenticAISecurity = lazyWithRetry(() => import("@/pages/AgenticAISecurity"));
const AIExecutiveOverview = lazyWithRetry(() => import("@/pages/AIExecutiveOverview"));
// Reused platform pages (identical to Obserra).
const AuditLog = lazyWithRetry(() => import("@/pages/AuditLog"));
const Team = lazyWithRetry(() => import("@/pages/Team"));
const Settings = lazyWithRetry(() => import("@/pages/Settings"));
const Billing = lazyWithRetry(() => import("@/pages/Billing"));
const Marketplace = lazyWithRetry(() => import("@/pages/Marketplace"));
const PaymentSuccess = lazyWithRetry(() => import("@/pages/PaymentSuccess"));
const QRApprove = lazyWithRetry(() => import("@/pages/QRApprove"));
const ShareDigest = lazyWithRetry(() => import("@/pages/ShareDigest"));

function PageLoader() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center" data-testid="route-loader">
      <Loader2 className="w-6 h-6 animate-spin text-primary" />
    </div>
  );
}

function Gate({ children }) {
  const { user } = useAuth();
  if (user === null) return <div className="min-h-screen flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  if (!user) return <Navigate to="/" replace />;
  return children;
}

function Landing() {
  const { user } = useAuth();
  if (user) return <Navigate to="/app" replace />;
  return <Auth />;
}

function AppRoutes() {
  const location = useLocation();
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/qr-approve/:token" element={<QRApprove />} />
        <Route path="/share/digest/:token" element={<ShareDigest />} />
        <Route path="/payment/success" element={<Gate><PaymentSuccess /></Gate>} />
        <Route path="/app" element={<Gate><AppShell /></Gate>}>
          <Route index element={<AIExecutiveOverview />} />
          <Route path="sod" element={<SodCommandCenter />} />
          <Route path="identities" element={<Identities />} />
          <Route path="privileged" element={<PrivilegedAccess />} />
          <Route path="monitoring" element={<AccessMonitoring />} />
          <Route path="lifecycle" element={<Lifecycle />} />
          <Route path="hr-reconciliation" element={<HrReconciliation />} />
          <Route path="roles" element={<RoleIntelligence />} />
          <Route path="access-requests" element={<AccessRequests />} />
          <Route path="certifications" element={<Certifications />} />
          <Route path="systems" element={<SapSystems />} />
          <Route path="activation" element={<UserActivation />} />
          <Route path="analytics" element={<SapAnalytics />} />
          <Route path="workflow" element={<WorkflowActivity />} />
          <Route path="agentic-ai-security" element={<AgenticAISecurity />} />
          <Route path="system-health" element={<SystemHealth />} />
          <Route path="audit" element={<AuditLog />} />
          <Route path="team" element={<Team />} />
          <Route path="settings" element={<Settings />} />
          <Route path="marketplace" element={<Marketplace />} />
          <Route path="billing" element={<Billing />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

function App() {
  return (
    <div className="App">
      <Splash />
      <InstallBanner />
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
        <Toaster position="top-right" richColors theme="dark" />
      </AuthProvider>
    </div>
  );
}

export default App;
