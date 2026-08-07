import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import Auth from "@/pages/Auth";
import AppShell from "@/pages/AppShell";
import Overview from "@/pages/Overview";
import RiskRegister from "@/pages/RiskRegister";
import AIGovernance from "@/pages/AIGovernance";
import Decisions from "@/pages/Decisions";
import AuditLog from "@/pages/AuditLog";
import Billing from "@/pages/Billing";
import Marketplace from "@/pages/Marketplace";
import SituationRoom from "@/pages/SituationRoom";
import AssetIntelligence from "@/pages/AssetIntelligence";
import KnowledgeGraph from "@/pages/KnowledgeGraph";
import ControlMonitoring from "@/pages/ControlMonitoring";
import Reporting from "@/pages/Reporting";
import PaymentSuccess from "@/pages/PaymentSuccess";
import QRApprove from "@/pages/QRApprove";
import { Loader2 } from "lucide-react";

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

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
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
              <Route path="marketplace" element={<Marketplace />} />
              <Route path="billing" element={<Billing />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors theme="dark" />
      </AuthProvider>
    </div>
  );
}

export default App;
