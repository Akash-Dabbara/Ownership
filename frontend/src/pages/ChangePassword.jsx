import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { changePassword } from "../api/api";
import {
  getAuthSession,
  updateAuthSession,
  clearAuthSession,
} from "../api/auth";
import TitleBanner from "../components/TitleBanner";

const inputStyle = {
  width: "100%",
  height: "52px",
  padding: "0 16px",
  fontSize: "16px",
  border: "1px solid #d1d5db",
  borderRadius: "10px",
  boxSizing: "border-box",
};

const labelStyle = {
  display: "block",
  marginBottom: "8px",
  fontSize: "14px",
  fontWeight: 600,
  color: "#374151",
};

function ChangePassword() {
  const navigate = useNavigate();
  const session = getAuthSession();

  // This page exists only for the forced first-login password
  // change. There is no voluntary "Change Password" entry point
  // anywhere else in the app, so if someone reaches this URL
  // without needing to change their password, send them away.
  if (!session?.mustChangePassword) {
    return <Navigate to="/dashboard" replace />;
  }

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isSuccess, setIsSuccess] = useState(false);

  function handleLogout() {
    clearAuthSession();
    navigate("/", { replace: true });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage("");

    if (!currentPassword) {
      setErrorMessage("Enter your current password.");
      return;
    }

    if (newPassword.length < 8) {
      setErrorMessage("New password must be at least 8 characters.");
      return;
    }

    if (newPassword === currentPassword) {
      setErrorMessage(
        "New password must be different from your current password.",
      );
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMessage("New passwords do not match.");
      return;
    }

    try {
      setIsLoading(true);

      await changePassword(
        currentPassword,
        newPassword,
        session?.accessToken,
      );

      // Clear the "must change" flag locally so the dashboard
      // route lets the user through without logging in again.
      updateAuthSession({ mustChangePassword: false });

      setIsSuccess(true);

      setTimeout(() => {
        navigate("/dashboard", { replace: true });
      }, 1200);
    } catch (error) {
      setErrorMessage(error.message || "Unable to change password.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#f8fafc",
      }}
    >
      <TitleBanner
        subtitle="Change password"
        rightContent={
          <button
            type="button"
            onClick={handleLogout}
            style={{
              height: "40px",
              padding: "0 16px",
              border: "1px solid #d1d5db",
              borderRadius: "8px",
              background: "#ffffff",
              color: "#374151",
              fontSize: "14px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Logout
          </button>
        }
      />

      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "40px 20px",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "480px",
            background: "#ffffff",
            borderRadius: "20px",
            border: "1px solid #e5e7eb",
            boxShadow: "0 12px 32px rgba(17, 24, 39, 0.08)",
            padding: "48px 40px",
          }}
        >
          {isSuccess ? (
            <>
              <div
                style={{
                  fontSize: "40px",
                  marginBottom: "12px",
                  textAlign: "center",
                }}
              >
                ✅
              </div>
              <h3 style={{ textAlign: "center", margin: "0 0 8px 0" }}>
                Password changed
              </h3>
              <p style={{ textAlign: "center", color: "#6b7280", margin: 0 }}>
                Taking you to your dashboard...
              </p>
            </>
          ) : (
            <form onSubmit={handleSubmit}>
              <h2 style={{ margin: "0 0 8px 0", color: "#111827" }}>
                Set a new password
              </h2>

              <p
                style={{
                  margin: "0 0 28px 0",
                  fontSize: "14px",
                  color: "#6b7280",
                }}
              >
                Before you continue, replace the password you signed in with.
              </p>

              <div style={{ marginBottom: "20px" }}>
                <label htmlFor="currentPassword" style={labelStyle}>
                  Current password
                </label>
                <input
                  id="currentPassword"
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  autoComplete="current-password"
                  disabled={isLoading}
                  style={inputStyle}
                />
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label htmlFor="newPassword" style={labelStyle}>
                  New password
                </label>
                <input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                  disabled={isLoading}
                  style={inputStyle}
                />
              </div>

              <div style={{ marginBottom: "24px" }}>
                <label htmlFor="confirmNewPassword" style={labelStyle}>
                  Confirm new password
                </label>
                <input
                  id="confirmNewPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                  disabled={isLoading}
                  style={inputStyle}
                />
              </div>

              {errorMessage && (
                <div className="login-error" style={{ marginBottom: "20px" }}>
                  {errorMessage}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                style={{
                  width: "100%",
                  height: "52px",
                  fontSize: "16px",
                  fontWeight: 700,
                  color: "#ffffff",
                  background: "#111827",
                  border: "none",
                  borderRadius: "10px",
                  cursor: isLoading ? "not-allowed" : "pointer",
                  opacity: isLoading ? 0.6 : 1,
                }}
              >
                {isLoading ? "Saving..." : "Save new password"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

export default ChangePassword;