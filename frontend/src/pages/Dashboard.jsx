import { useNavigate } from "react-router-dom";
import Workspaces from "./Workspaces";
import { clearAuthSession, getAuthSession } from "../api/auth";
import TitleBanner from "../components/TitleBanner";

function Dashboard() {
  const navigate = useNavigate();
  const session = getAuthSession();

  function handleLogout() {
    clearAuthSession();
    navigate("/", {
      replace: true,
    });
  }

  const userRole = session?.role?.toUpperCase();
  const isOwner = userRole === "OWNER";
  const canManageWorkspaces = userRole === "OWNER" || userRole === "ADMIN";

  return (
    <div className="dashboard-page" style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <TitleBanner
        rightContent={
          <>
            {/* Button to register/setup data source credentials —
                Owner only, per DataEase's access policy. */}
            {isOwner && (
              <button
                type="button"
                onClick={() => navigate("/datasources/new")}
                style={{
                  height: "40px",
                  padding: "0 16px",
                  background: "#ffffff",
                  color: "#2563eb",
                  border: "1px solid #2563eb",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: "600",
                  cursor: "pointer",
                }}
              >
                + Data Source Setup
              </button>
            )}

            {isOwner && (
              <button
                type="button"
                onClick={() => navigate("/admin/admins")}
                style={{
                  height: "40px",
                  padding: "0 16px",
                  background: "#ffffff",
                  color: "#4f46e5",
                  border: "1px solid #4f46e5",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: "600",
                  cursor: "pointer",
                }}
              >
                Admins
              </button>
            )}

            {canManageWorkspaces && (
              <button
                type="button"
                onClick={() => navigate("/workspaces/new")}
                style={{
                  height: "40px",
                  padding: "0 20px",
                  background: "#111827",
                  color: "#fff",
                  border: "none",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: "600",
                  cursor: "pointer",
                }}
              >
                Create Workspace
              </button>
            )}

            {isOwner && (
              <button
                type="button"
                onClick={() => navigate("/admin/requests")}
                style={{
                  height: "40px",
                  padding: "0 16px",
                  background: "#ffffff",
                  color: "#4f46e5",
                  border: "1px solid #4f46e5",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: "600",
                  cursor: "pointer",
                }}
              >
                Requests
              </button>
            )}

            {canManageWorkspaces && (
              <button
                type="button"
                onClick={() => navigate("/admin/create-user")}
                style={{
                  height: "40px",
                  padding: "0 16px",
                  background: "#ffffff",
                  color: "#4f46e5",
                  border: "1px solid #4f46e5",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: "600",
                  cursor: "pointer",
                }}
              >
                + Create User
              </button>
            )}

            <button
              type="button"
              className="logout-button"
              onClick={handleLogout}
              style={{
                height: "40px",
                padding: "0 16px",
                border: "1px solid #d1d5db",
                borderRadius: "8px",
                background: "#ffffff",
                color: "#374151",
                fontSize: "14px",
                fontWeight: "600",
                cursor: "pointer",
              }}
            >
              Logout
            </button>
          </>
        }
      />

      <main style={{ padding: "32px", maxWidth: "1200px", margin: "0 auto" }}>
        <Workspaces />
      </main>
    </div>
  );
}

export default Dashboard;