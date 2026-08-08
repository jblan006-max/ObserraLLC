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

// Recover from stale code-split chunks after a rebuild/deploy: if a dynamic
// import fails (old chunk hash no longer on the server), reload once to pull the
// fresh index.html + chunks instead of hanging on the Suspense spinner.
const lazyWithRetry = (importer) => lazy(async () => {
  try {
    const mod = await importer();
    sessionStorage.removeItem("obserra-chunk-reload");
    return mod;
  } catch (err) {
    if (!sessionStorage.getItem("obserra-chunk-reload")) {
      sessionStorage.setItem("obserra-chunk-reload", "1");
      window.location.reload();
      return new Promise(() => {}); // hold the spinner briefly while reloading
    }
    throw err;
  }
});

// Route-level code splitting: each page (and its heavy deps like recharts)
// loads on demand instead of shipping in the initial bundle.
const Overview = lazyWithRetry(() => import("@/pages/Overview"));
const RiskRegister = lazyWithRetry(() => import("@/pages/RiskRegister"));
const AIGovernance = lazyWithRetry(() => import("@/pages/AIGovernance"));
const Decisions = lazyWithRetry(() => import("@/pages/Decisions"));
const AuditLog = lazyWithRetry(() => import("@/pages/AuditLog"));
const Billing = lazyWithRetry(() => import("@/pages/Billing"));
const Marketplace = lazyWithRetry(() => import("@/pages/Marketplace"));
const SituationRoom = lazyWithRetry(() => import("@/pages/SituationRoom"));
const AssetIntelligence = lazyWithRetry(() => import("@/pages/AssetIntelligence"));
const KnowledgeGraph = lazyWithRetry(() => import("@/pages/KnowledgeGraph"));
const ControlMonitoring = lazyWithRetry(() => import("@/pages/ControlMonitoring"));
const Team = lazyWithRetry(() => import("@/pages/Team"));
const KernelStatus = lazyWithRetry(() => import("@/pages/KernelStatus"));
const Settings = lazyWithRetry(() => import("@/pages/Settings"));
const AIAgents = lazyWithRetry(() => import("@/pages/AIAgents"));
const Enterprise = lazyWithRetry(() => import("@/pages/Enterprise"));
const AvailableConnectors = lazyWithRetry(() => import("@/pages/AvailableConnectors"));
const CompliancePosture = lazyWithRetry(() => import("@/pages/CompliancePosture"));
const SecurityScanner = lazyWithRetry(() => import("@/pages/SecurityScanner"));
const MobileSnapshot = lazyWithRetry(() => import("@/pages/MobileSnapshot"));
const VendorRisk = lazyWithRetry(() => import("@/pages/VendorRisk"));
const CyberRisk = lazyWithRetry(() => import("@/pages/CyberRisk"));
const Studio = lazyWithRetry(() => import("@/pages/Studio"));
const SpendGovernance = lazyWithRetry(() => import("@/pages/SpendGovernance"));
const Benchmark = lazyWithRetry(() => import("@/pages/Benchmark"));
const Reporting = lazyWithRetry(() => import("@/pages/Reporting"));
const PaymentSuccess = lazyWithRetry(() => import("@/pages/PaymentSuccess"));
const QRApprove = lazyWithRetry(() => import("@/pages/QRApprove"));

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
  // Emergent Google OAuth returns to <origin>/app#session_id=... — process the
  // session_id FIRST, on whatever route the provider lands on, BEFORE the auth
  // Gate runs (otherwise the Gate spins forever). Read the fragment from
  // useLocation().hash (reactive) per the Emergent Auth playbook.
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/qr-approve/:token" element={<QRApprove />} />
        <Route path="/payment/success" element={<Gate><PaymentSuccess /></Gate>} />
        <Route path="/app" element={<Gate><AppShell /></Gate>}>
          <Route index element={<Overview />} />
          <Route path="situation-room" element={<SituationRoom />} />
          <Route path="risks" element={<RiskRegister />} />
          <Route path="ai-governance" element={<AIGovernance />} />
          <Route path="assets" element={<AssetIntelligence />} />
          <Route path="knowledge-graph" element={<KnowledgeGraph />} />
          <Route path="controls" element={<ControlMonitoring />} />
          <Route path="decisions" element={<Decisions />} />
          <Route path="reporting" element={<Reporting />} />
          <Route path="audit" element={<AuditLog />} />
          <Route path="kernel" element={<KernelStatus />} />
          <Route path="team" element={<Team />} />
          <Route path="settings" element={<Settings />} />
          <Route path="agents" element={<AIAgents />} />
          <Route path="vendors" element={<VendorRisk />} />
          <Route path="cyber-risk" element={<CyberRisk />} />
          <Route path="studio" element={<Studio />} />
          <Route path="spend-governance" element={<SpendGovernance />} />
          <Route path="benchmark" element={<Benchmark />} />
          <Route path="enterprise" element={<Enterprise />} />
          <Route path="connectors" element={<AvailableConnectors />} />
          <Route path="compliance" element={<CompliancePosture />} />
          <Route path="security" element={<SecurityScanner />} />
          <Route path="snapshot" element={<MobileSnapshot />} />
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
