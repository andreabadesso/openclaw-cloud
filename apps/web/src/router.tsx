import { Routes, Route, Navigate } from "react-router-dom";
import { RootLayout } from "./layouts/RootLayout";
import { LocaleLayout } from "./layouts/LocaleLayout";
import { DashboardLayout } from "./layouts/DashboardLayout";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import AuthCallbackPage from "./pages/AuthCallbackPage";
import SetupPage from "./pages/SetupPage";
import OnboardingPage from "./pages/OnboardingPage";
import DashboardPage from "./pages/DashboardPage";
import ConnectionsPage from "./pages/ConnectionsPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import SettingsPage from "./pages/SettingsPage";
import AdminPage from "./pages/AdminPage";
import ConnectProviderPage from "./pages/ConnectProviderPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<RootLayout />}>
        {/* Redirect bare / to default locale */}
        <Route index element={<Navigate to="/pt" replace />} />

        {/* Auth callback without locale prefix (used by API redirects) */}
        <Route path="auth/callback" element={<AuthCallbackPage />} />

        <Route path=":locale" element={<LocaleLayout />}>
          <Route index element={<HomePage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="auth/callback" element={<AuthCallbackPage />} />
          <Route path="setup" element={<SetupPage />} />
          <Route path="onboarding" element={<OnboardingPage />} />
          <Route path="admin" element={<AdminPage />} />
          <Route path="connect/:provider" element={<ConnectProviderPage />} />

          <Route path="dashboard" element={<DashboardLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="connections" element={<ConnectionsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}
