import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import { PageLoader } from "./components/ui";
import Landing from "./pages/Landing";
import Login, { Forgot, Reset, VerifyEmail } from "./pages/Login";
import Register from "./pages/Register";
import { Dashboard, ProfilePage, MedicalPage, AnalysisPage, Settings } from "./pages/patient/Pages";
import { Overview, Patients, PatientDetail, Audit, Explorer } from "./pages/admin/Pages";

function Guard({ role }) {
  const { user, loading } = useAuth(); const loc = useLocation();
  if (loading) return <PageLoader label="Loading your account…" />;
  if (!user) return <Navigate to={role === "admin" ? "/admin/login" : "/login"} state={{ from: loc.pathname }} replace />;
  if (user.role !== role) return <Navigate to={user.role === "admin" ? "/admin" : "/app"} replace />;
  return <Layout role={role} />;
}

export default function App() {
  const { loading } = useAuth();
  if (loading) return <PageLoader label="Starting Sanjeevani AI…" />;
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/admin/login" element={<Login admin />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot" element={<Forgot />} />
      <Route path="/reset-password" element={<Reset />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/app" element={<Guard role="patient" />}>
        <Route index element={<Dashboard />} /><Route path="profile" element={<ProfilePage />} /><Route path="medical" element={<MedicalPage />} />
        <Route path="analysis" element={<AnalysisPage />} /><Route path="settings" element={<Settings />} />
      </Route>
      <Route path="/admin" element={<Guard role="admin" />}>
        <Route index element={<Overview />} /><Route path="patients" element={<Patients />} /><Route path="patients/:id" element={<PatientDetail />} />
        <Route path="data" element={<Explorer />} /><Route path="audit" element={<Audit />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
