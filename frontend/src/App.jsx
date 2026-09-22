import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import WorkspaceDetails from "./pages/WorkspaceDetails";
import WorkspaceNew from "./pages/WorkspaceNew";
import DataSourceSetup from "./pages/DataSourceSetup";
import DataIngestion from "./pages/DataIngestion";
import FileGroupFiles from "./pages/FileGroupFiles";
import FilePreview from "./pages/FilePreview";
import AdminRequests from "./pages/AdminRequests";
import AdminAccounts from "./pages/AdminAccounts";
import CreateUserAccess from "./pages/CreateUserAccess";
import OwnerSetup from "./pages/OwnerSetup";
import Login from "./pages/Login";
import RoleSelect from "./pages/RoleSelect";
import Dashboard from "./pages/Dashboard";
import ChangePassword from "./pages/ChangePassword";
import { getAuthSession } from "./api/auth";
import "./App.css";

/**
 * Guards a route.
 *
 * - No session                      -> back to role select
 * - mustChangePassword is true      -> forced to /change-password
 *                                      (the /change-password route
 *                                      itself passes allowPasswordChange
 *                                      so it doesn't redirect to itself)
 * - allowedRoles given, role absent -> back to dashboard
 *
 * NOTE: this is only a UX guard. The backend enforces the same
 * rules independently (require_owner / require_admin_or_owner /
 * the must_change_password check in get_current_user).
 */
function ProtectedRoute({
  children,
  allowedRoles = null,
  allowPasswordChange = false,
}) {
  const session = getAuthSession();

  if (!session) {
    return <Navigate to="/" replace />;
  }

  if (session.mustChangePassword && !allowPasswordChange) {
    return <Navigate to="/change-password" replace />;
  }

  if (allowedRoles) {
    const role = (session.role || "").toUpperCase();

    if (!allowedRoles.includes(role)) {
      return <Navigate to="/dashboard" replace />;
    }
  }

  return children;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<RoleSelect />}
        />

        <Route
          path="/login"
          element={<Login />}
        />

        <Route
          path="/owner-setup"
          element={<OwnerSetup />}
        />

        {/* Reachable only while a forced password change is
            pending. ChangePassword.jsx itself redirects to
            /dashboard if mustChangePassword is false, so there is
            no voluntary way to reach this page. */}
        <Route
          path="/change-password"
          element={
            <ProtectedRoute allowPasswordChange>
              <ChangePassword />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin/requests"
          element={
            <ProtectedRoute allowedRoles={["OWNER"]}>
              <AdminRequests />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin/admins"
          element={
            <ProtectedRoute allowedRoles={["OWNER"]}>
              <AdminAccounts />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin/create-user"
          element={
            <ProtectedRoute allowedRoles={["OWNER", "ADMIN"]}>
              <CreateUserAccess />
            </ProtectedRoute>
          }
        />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="/datasources/new"
          element={
            <ProtectedRoute allowedRoles={["OWNER"]}>
              <DataSourceSetup />
            </ProtectedRoute>
          }
        />

        {/* Note: /workspaces/new MUST be defined BEFORE /workspaces/:workspaceId */}
        <Route
          path="/workspaces/new"
          element={
            <ProtectedRoute allowedRoles={["OWNER", "ADMIN"]}>
              <WorkspaceNew />
            </ProtectedRoute>
          }
        />

        <Route
          path="/workspaces/:workspaceId"
          element={
            <ProtectedRoute>
              <WorkspaceDetails />
            </ProtectedRoute>
          }
        />

        {/* Note: the /import and /files/.../preview routes MUST be
            defined BEFORE the bare /workspaces/:workspaceId/file-groups/:fileGroupId route */}
        <Route
          path="/workspaces/:workspaceId/file-groups/:fileGroupId/import"
          element={
            <ProtectedRoute>
              <DataIngestion />
            </ProtectedRoute>
          }
        />

        <Route
          path="/workspaces/:workspaceId/file-groups/:fileGroupId/files/:fileId/preview"
          element={
            <ProtectedRoute>
              <FilePreview />
            </ProtectedRoute>
          }
        />

        <Route
          path="/workspaces/:workspaceId/file-groups/:fileGroupId"
          element={
            <ProtectedRoute>
              <FileGroupFiles />
            </ProtectedRoute>
          }
        />

        <Route
          path="*"
          element={
            <Navigate
              to="/"
              replace
            />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;