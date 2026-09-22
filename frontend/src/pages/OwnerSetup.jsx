import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { submitOwnerSetupRequest } from "../api/api";
import TitleBanner from "../components/TitleBanner";

const labelStyle = {
  display: "block",
  marginBottom: "8px",
  fontSize: "14px",
  fontWeight: 600,
  color: "#374151",
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

export default function OwnerSetup() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isDone, setIsDone] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErrorMessage("");

    if (!email.trim() || !password) {
      setErrorMessage("Please fill in both fields.");
      return;
    }

    if (password.length < 8) {
      setErrorMessage("Password must be at least 8 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    try {
      setIsSubmitting(true);
      await submitOwnerSetupRequest(email.trim(), password);
      setIsDone(true);
    } catch (error) {
      setErrorMessage(error.message || "Failed to create Owner account.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "#f8fafc" }}>
      <TitleBanner subtitle="First-Time Setup" />

      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 20px" }}>
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
          {isDone ? (
            <>
              <div style={{ fontSize: "40px", marginBottom: "12px", textAlign: "center" }}>✅</div>
              <h2 style={{ textAlign: "center", margin: "0 0 8px 0" }}>Owner Account Created</h2>
              <p style={{ textAlign: "center", color: "#6b7280", marginBottom: "24px" }}>
                You can now sign in as Owner with the credentials you just set.
              </p>
              <button
                type="button"
                onClick={() => navigate("/", { replace: true })}
                style={{
                  width: "100%",
                  height: "48px",
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#ffffff",
                  background: "#111827",
                  border: "none",
                  borderRadius: "10px",
                  cursor: "pointer",
                }}
              >
                Continue to Sign In
              </button>
            </>
          ) : (
            <>
              <h2 style={{ margin: "0 0 4px 0" }}>Welcome to DataEase</h2>
              <p style={{ color: "#6b7280", marginBottom: "28px", fontSize: "14px" }}>
                No Owner account exists yet on this installation. Set one up
                now — this only needs to be done once.
              </p>

              <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: "24px" }}>
                  <label style={labelStyle}>Owner Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    style={inputStyle}
                    disabled={isSubmitting}
                  />
                </div>

                <div style={{ marginBottom: "24px" }}>
                  <label style={labelStyle}>Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    style={inputStyle}
                    disabled={isSubmitting}
                  />
                </div>

                <div style={{ marginBottom: "24px" }}>
                  <label style={labelStyle}>Confirm Password</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter password"
                    style={inputStyle}
                    disabled={isSubmitting}
                  />
                </div>

                {errorMessage && (
                  <div className="error-box" style={{ marginBottom: "20px" }}>
                    {errorMessage}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{
                    width: "100%",
                    height: "52px",
                    fontSize: "16px",
                    fontWeight: 700,
                    color: "#ffffff",
                    background: isSubmitting ? "#9ca3af" : "#111827",
                    border: "none",
                    borderRadius: "10px",
                    cursor: isSubmitting ? "not-allowed" : "pointer",
                  }}
                >
                  {isSubmitting ? "Creating Account..." : "Create Owner Account"}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}