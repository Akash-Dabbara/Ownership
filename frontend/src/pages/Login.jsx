import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";

import { loginUser, submitAdminSetupRequest } from "../api/api";
import { saveAuthSession, clearAuthSession } from "../api/auth";
import TitleBanner from "../components/TitleBanner";

const ROLE_LABELS = {
  OWNER: "Owner",
  ADMIN: "Admin",
  USER: "User",
};

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

function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const selectedRole = (searchParams.get("role") || "").toUpperCase();
  const selectedRoleLabel = ROLE_LABELS[selectedRole];
  const isAdminRole = selectedRole === "ADMIN";
  const isUserRole = selectedRole === "USER";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Toggles between "Sign in" and "Create Admin Account" — only
  // ever relevant for the Admin role. Owner is bootstrapped once
  // via Owner Setup; Users are created by Admin/Owner, not self-serve.
  const [isCreatingAccount, setIsCreatingAccount] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [requestSubmitted, setRequestSubmitted] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    setErrorMessage("");

    if (!selectedRoleLabel) {
      setErrorMessage(
        "Please select a role before signing in.",
      );
      return;
    }

    const normalizedEmail = email.trim();

    if (!normalizedEmail) {
      setErrorMessage(
        "Please enter your email address.",
      );
      return;
    }

    if (!password) {
      setErrorMessage(
        "Please enter your password.",
      );
      return;
    }

    // ------------------------------------------------------
    // CREATE ADMIN ACCOUNT MODE
    // ------------------------------------------------------
    if (isCreatingAccount) {
      if (password.length < 8) {
        setErrorMessage("Password must be at least 8 characters.");
        return;
      }

      if (password !== confirmPassword) {
        setErrorMessage("Passwords do not match.");
        return;
      }

      try {
        setIsLoading(true);
        await submitAdminSetupRequest(normalizedEmail, password);
        setRequestSubmitted(true);
      } catch (error) {
        setErrorMessage(error.message || "Failed to submit request.");
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // ------------------------------------------------------
    // NORMAL SIGN IN
    // ------------------------------------------------------
    try {
      setIsLoading(true);

      const response = await loginUser(
        normalizedEmail,
        password,
      );

      if ((response.role || "").toUpperCase() !== selectedRole) {
        clearAuthSession();
        setErrorMessage(
          `These credentials don't belong to a ${selectedRoleLabel} account.`,
        );
        return;
      }

      const session = saveAuthSession(response);

      console.log(
        "Login successful:",
        session,
      );

      navigate(
        session.mustChangePassword ? "/change-password" : "/dashboard",
        { replace: true },
      );

    } catch (error) {
      setErrorMessage(
        error.message ||
          "Unable to sign in.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  function toggleCreateAccountMode() {
    setIsCreatingAccount((current) => !current);
    setErrorMessage("");
    setRequestSubmitted(false);
    setPassword("");
    setConfirmPassword("");
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
        subtitle={
          selectedRoleLabel
            ? isCreatingAccount
              ? `Create ${selectedRoleLabel} Account`
              : `Sign in as ${selectedRoleLabel}`
            : "Sign in to continue"
        }
        rightContent={
          <Link
            to="/"
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: "#374151",
              textDecoration: "none",
            }}
          >
            ← Choose a different role
          </Link>
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
          {!selectedRoleLabel && (
            <div className="login-error" style={{ marginBottom: "20px" }}>
              No role selected. Please go back and choose a role.
            </div>
          )}

          {requestSubmitted ? (
            <>
              <div style={{ fontSize: "40px", marginBottom: "12px", textAlign: "center" }}>✅</div>
              <h3 style={{ textAlign: "center", margin: "0 0 8px 0" }}>Request Submitted</h3>
              <p style={{ textAlign: "center", color: "#6b7280", marginBottom: "24px" }}>
                The Owner has been notified and will review your request.
                You'll be able to sign in once it's approved.
              </p>
              <Link
                to="/"
                style={{
                  display: "block",
                  textAlign: "center",
                  height: "48px",
                  lineHeight: "48px",
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#ffffff",
                  background: "#111827",
                  borderRadius: "10px",
                  textDecoration: "none",
                }}
              >
                Back to Role Select
              </Link>
            </>
          ) : (
            <form onSubmit={handleSubmit}>

              <div style={{ marginBottom: "24px" }}>
                <label htmlFor="email" style={labelStyle}>
                  Email
                </label>

                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) =>
                    setEmail(
                      event.target.value,
                    )
                  }
                  placeholder="Enter your email"
                  autoComplete="email"
                  disabled={isLoading}
                  style={inputStyle}
                />
              </div>

              <div style={{ marginBottom: isCreatingAccount ? "24px" : "24px" }}>
                <label htmlFor="password" style={labelStyle}>
                  Password
                </label>

                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) =>
                    setPassword(
                      event.target.value,
                    )
                  }
                  placeholder={
                    isCreatingAccount
                      ? "At least 8 characters"
                      : "Enter your password"
                  }
                  autoComplete={
                    isCreatingAccount ? "new-password" : "current-password"
                  }
                  disabled={isLoading}
                  style={inputStyle}
                />
              </div>

              {isCreatingAccount && (
                <div style={{ marginBottom: "24px" }}>
                  <label htmlFor="confirmPassword" style={labelStyle}>
                    Confirm Password
                  </label>

                  <input
                    id="confirmPassword"
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    placeholder="Re-enter password"
                    autoComplete="new-password"
                    disabled={isLoading}
                    style={inputStyle}
                  />
                </div>
              )}

              {errorMessage && (
                <div
                  className="login-error"
                  style={{ marginBottom: "20px" }}
                >
                  {errorMessage}
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading || !selectedRoleLabel}
                style={{
                  width: "100%",
                  height: "52px",
                  fontSize: "16px",
                  fontWeight: 700,
                  color: "#ffffff",
                  background: "#111827",
                  border: "none",
                  borderRadius: "10px",
                  cursor:
                    isLoading || !selectedRoleLabel
                      ? "not-allowed"
                      : "pointer",
                  opacity: isLoading || !selectedRoleLabel ? 0.6 : 1,
                  marginBottom: (isAdminRole || isUserRole) ? "16px" : 0,
                }}
              >
                {isLoading
                  ? (isCreatingAccount ? "Submitting..." : "Signing in...")
                  : (isCreatingAccount ? "Submit Request" : "Sign in")}
              </button>

              {isAdminRole && (
                <button
                  type="button"
                  onClick={toggleCreateAccountMode}
                  disabled={isLoading}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "center",
                    fontSize: "14px",
                    fontWeight: 600,
                    color: "#4f46e5",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 0,
                  }}
                >
                  {isCreatingAccount
                    ? "← Already have an account? Sign in"
                    : "Don't have an account? Create one"}
                </button>
              )}

              {isUserRole && (
                <p
                  style={{
                    textAlign: "center",
                    fontSize: "14px",
                    color: "#6b7280",
                    margin: 0,
                  }}
                >
                  Accounts for this role are created by your Admin.
                </p>
              )}

            </form>
          )}
        </div>
      </div>
    </div>
  );
}


export default Login;