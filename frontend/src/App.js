import "@/App.css";
import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import Auth from "@/pages/Auth";
import AppShell from "@/pages/AppShell";
import AuthCallback from "@/pages/AuthCallback";
import { Loader2 } from "lucide-react";
import { Splash } from "@/components/Splash";
import { InstallBanner } from "@/components/InstallBanner";

// Route-level code splitting: each page (and its heavy deps like recharts)
// loads on demand instead of shipping in the initial bundle.
const Overview = lazy(() => import("@/pages/Overview"));
const RiskRegister = lazy(() => import("@/pages/RiskRegister"));
const AIGovernance = lazy(() => import("@/pages/AIGovernance"));
const Decisions = lazy(() => import("@/pages/Decisions"));
const AuditLog = lazy(() => import("@/pages/AuditLog"));
const Billing = lazy(() => import("@/pages/Billing"));
const Marketplace = lazy(() => import("@/pages/Marketplace"));
const SituationRoom = lazy(() => import("@/pages/SituationRoom"));
const AssetIntelligence = lazy(() => import("@/pages/AssetIntelligence"));
const KnowledgeGraph = lazy(() => import("@/pages/KnowledgeGraph"));
const ControlMonitoring = lazy(() => import("@/pages/ControlMonitoring"));
const Team = lazy(() => import("@/pages/Team"));
const KernelStatus = lazy(() => import("@/pages/KernelStatus"));
const Settings = lazy(() => import("@/pages/Settings"));
const AIAgents = lazy(() => import("@/pages/AIAgents"));
const Enterprise = lazy(() => import("@/pages/Enterprise"));
const AvailableConnectors = lazy(() => import("@/pages/AvailableConnectors"));
const CompliancePosture = lazy(() => import("@/pages/CompliancePosture"));
const SecurityScanner = lazy(() => import("@/pages/SecurityScanner"));
const MobileSnapshot = lazy(() => import("@/pages/MobileSnapshot"));
const VendorRisk = lazy(() => import("@/pages/VendorRisk"));
const CyberRisk = lazy(() => import("@/pages/CyberRisk"));
const Studio = lazy(() => import("@/pages/Studio"));
const SpendGovernance = lazy(() => import("@/pages/SpendGovernance"));
const Benchmark = lazy(() => import("@/pages/Benchmark"));
const Reporting = lazy(() => import("@/pages/Reporting"));
const PaymentSuccess = lazy(() => import("@/pages/PaymentSuccess"));
const QRApprove = lazy(() => import("@/pages/QRApprove"));

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
  if (window.location.hash?.includes("session_id=")) return <AuthCallback />;
  if (user) return <Navigate to="/app" replace />;
  return <Auth />;
}

function App() {
  return (
    <div className="App">
      <Splash />
      <InstallBanner />
      <AuthProvider>
        <BrowserRouter>
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
        </BrowserRouter>
        <Toaster position="top-right" richColors theme="dark" />
      </AuthProvider>
    </div>
  );
}

export default App;
