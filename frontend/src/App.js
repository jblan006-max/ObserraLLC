import "@/App.css";
import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@mui/material/styles";
import theme from "@/theme";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

// Route-level code splitting — Obserra Cyber Crisis Commander dashboards.
const AccessOverview = lazyWithRetry(() => import("@/pages/AccessOverview"));
const SodCommandCenter = lazyWithRetry(() => import("@/pages/SodCommandCenter"));
const Identities = lazyWithRetry(() => import("@/pages/Identities"));
const PrivilegedAccess = lazyWithRetry(() => import("@/pages/PrivilegedAccess"));
const AccessMonitoring = lazyWithRetry(() => import("@/pages/AccessMonitoring"));
const Lifecycle = lazyWithRetry(() => import("@/pages/Lifecycle"));
const HrReconciliation = lazyWithRetry(() => import("@/pages/HrReconciliation"));
const RoleIntelligence = lazyWithRetry(() => import("@/pages/RoleIntelligence"));
const AccessRequests = lazyWithRetry(() => import("@/pages/AccessRequests"));
const Certifications = lazyWithRetry(() => import("@/pages/Certifications"));
const ConnectorHealth = lazyWithRetry(() => import("@/pages/ConnectorHealth"));
const UserActivation = lazyWithRetry(() => import("@/pages/UserActivation"));
const AccessAnalytics = lazyWithRetry(() => import("@/pages/AccessAnalytics"));
const WorkflowActivity = lazyWithRetry(() => import("@/pages/WorkflowActivity"));
const SystemHealth = lazyWithRetry(() => import("@/pages/SystemHealth"));
const AgenticAISecurity = lazyWithRetry(() => import("@/pages/AgenticAISecurity"));
const AIGroundingMonitor = lazyWithRetry(() => import("@/pages/AIGroundingMonitor"));
const ControlAssurance = lazyWithRetry(() => import("@/pages/ControlAssurance"));
const ControlIntelligence = lazyWithRetry(() => import("@/pages/ControlIntelligence"));
const CyberCrisisCommander = lazyWithRetry(() => import("@/pages/CyberCrisisCommander"));
const AIExecutiveOverview = lazyWithRetry(() => import("@/pages/AIExecutiveOverview"));
const CRAExecutiveOverview = lazyWithRetry(() => import("@/pages/CRAExecutiveOverview"));
// Reused platform pages (identical to Obserra).
const AuditLog = lazyWithRetry(() => import("@/pages/AuditLog"));
const Team = lazyWithRetry(() => import("@/pages/Team"));
const Settings = lazyWithRetry(() => import("@/pages/Settings"));
const Billing = lazyWithRetry(() => import("@/pages/Billing"));
const Marketplace = lazyWithRetry(() => import("@/pages/Marketplace"));
const PaymentSuccess = lazyWithRetry(() => import("@/pages/PaymentSuccess"));
const QRApprove = lazyWithRetry(() => import("@/pages/QRApprove"));
const ShareDigest = lazyWithRetry(() => import("@/pages/ShareDigest"));
const AuditRoom = lazyWithRetry(() => import("@/pages/AuditRoom"));
const CardShare = lazyWithRetry(() => import("@/pages/CardShare"));
const CrisisSnapshot = lazyWithRetry(() => import("@/pages/CrisisSnapshot"));
const CIAuditorPortal = lazyWithRetry(() => import("@/pages/CIAuditorPortal"));
const CRAGovernance = lazyWithRetry(() => import("@/pages/CRAGovernance"));
const CRACertificationPortal = lazyWithRetry(() => import("@/pages/CRACertificationPortal"));
const CRAVerify = lazyWithRetry(() => import("@/pages/CRAVerify"));
const CRAScorecard = lazyWithRetry(() => import("@/pages/CRAScorecard"));
const CRAExecOverviewPublic = lazyWithRetry(() => import("@/pages/CRAExecOverviewPublic"));

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
        <Route path="/audit-room/:token" element={<AuditRoom />} />
        <Route path="/card/:token" element={<CardShare />} />
        <Route path="/crisis-snapshot/:token" element={<CrisisSnapshot />} />
        <Route path="/ci-audit/:token" element={<CIAuditorPortal />} />
        <Route path="/cra-certification/:token" element={<CRACertificationPortal />} />
        <Route path="/cra-verify/:token" element={<CRAVerify />} />
        <Route path="/cra-scorecard/:token" element={<CRAScorecard />} />
        <Route path="/exec-overview/:token" element={<CRAExecOverviewPublic />} />
        <Route path="/payment/success" element={<Gate><PaymentSuccess /></Gate>} />
        <Route path="/app" element={<Gate><AppShell /></Gate>}>
          <Route index element={<CRAExecutiveOverview />} />
          <Route path="saas-overview" element={<SaaSOverview />} />
          <Route path="compliance" element={<Compliance />} />
          <Route path="sod" element={<SodCommandCenter />} />
          <Route path="identities" element={<Identities />} />
          <Route path="privileged" element={<PrivilegedAccess />} />
          <Route path="monitoring" element={<AccessMonitoring />} />
          <Route path="lifecycle" element={<Lifecycle />} />
          <Route path="hr-reconciliation" element={<HrReconciliation />} />
          <Route path="roles" element={<RoleIntelligence />} />
          <Route path="access-requests" element={<AccessRequests />} />
          <Route path="certifications" element={<Certifications />} />
          <Route path="systems" element={<ConnectorHealth />} />
          <Route path="activation" element={<UserActivation />} />
          <Route path="analytics" element={<AccessAnalytics />} />
          <Route path="workflow" element={<WorkflowActivity />} />
          <Route path="agentic-ai-security" element={<AgenticAISecurity />} />
          <Route path="control-assurance" element={<ControlAssurance />} />
          <Route path="control-intelligence" element={<ControlIntelligence />} />
          <Route path="cyber-crisis-commander" element={<CyberCrisisCommander />} />
          <Route path="cra-governance" element={<CRAGovernance />} />
        <Route path="ai-grounding" element={<AIGroundingMonitor />} />
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
  const queryClient = new QueryClient();
  return (
    <div className="App">
      <Splash />
      <InstallBanner />
      <AuthProvider>
        <ThemeProvider theme={theme}>
          <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
          </QueryClientProvider>
        </ThemeProvider>
        <Toaster position="top-right" richColors theme="dark" />
      </AuthProvider>
    </div>
  );
}

export default App;
