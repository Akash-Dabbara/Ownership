import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  approveAdminSetupRequest,
  getPendingAdminRequests,
  rejectAdminSetupRequest,
} from "../api/api";
import { getAuthSession } from "../api/auth";
import TitleBanner from "../components/TitleBanner";

export default function AdminRequests() {
  const navigate = useNavigate();
  const session = getAuthSession();
  const token = session?.accessToken;

  const [requests, setRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [processingId, setProcessingId] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  // Set right after an approval so the Owner can immediately
  // set up that Admin's data source.
  const [approvedAdmin, setApprovedAdmin] = useState(null);

  useEffect(() => {
    loadRequests();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadRequests() {
    try {
      setIsLoading(true);
      const response = await getPendingAdminRequests(token);
      setRequests(response.requests || []);
    } catch (error) {
      setErrorMessage(error.message || "Failed to load Admin requests.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleApprove(request) {
    try {
      setProcessingId(request.request_id);
      setErrorMessage("");
      setSuccessMessage("");

      const response = await approveAdminSetupRequest(
        request.request_id,
        token
      );

      setApprovedAdmin({
        userId: response.user_id,
        email: response.email || request.email,
      });

      await loadRequests();
    } catch (error) {
      setErrorMessage(error.message || "Failed to approve the request.");
    } finally {
      setProcessingId("");
    }
  }

  async function handleReject(request) {
    if (!window.confirm(`Reject the request from ${request.email}?`)) {
      return;
    }

    try {
      setProcessingId(request.request_id);
      setErrorMessage("");
      setSuccessMessage("");

      await rejectAdminSetupRequest(request.request_id, token);

      setSuccessMessage(`Request from ${request.email} rejected.`);
      await loadRequests();
    } catch (error) {
      setErrorMessage(error.message || "Failed to reject the request.");
    } finally {
      setProcessingId("");
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <TitleBanner
        subtitle="Admin account requests"
        rightContent={
          <>
            <button
              type="button"
              onClick={() => navigate("/admin/admins")}
              style={{
                height: "40px",
                padding: "0 16px",
                border: "1px solid #4f46e5",
                borderRadius: "8px",
                background: "#ffffff",
                color: "#4f46e5",
                fontSize: "14px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Admins
            </button>

            <button
              type="button"
              onClick={() => navigate("/dashboard")}
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
              Home
            </button>
          </>
        }
      />

      <div style={{ padding: "32px 20px", maxWidth: "800px", margin: "0 auto" }}>
        <h2 style={{ marginTop: 0 }}>Pending Admin requests</h2>

        {errorMessage && (
          <div className="error-box" style={{ marginBottom: "16px" }}>
            {errorMessage}
          </div>
        )}

        {successMessage && (
          <div className="success-box" style={{ marginBottom: "16px" }}>
            {successMessage}
          </div>
        )}

        {isLoading ? (
          <p style={{ color: "#6b7280" }}>Loading requests...</p>
        ) : requests.length === 0 ? (
          <p style={{ color: "#6b7280" }}>No pending Admin requests.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {requests.map((request) => (
              <div
                key={request.request_id}
                style={{
                  background: "#ffffff",
                  border: "1px solid #e5e7eb",
                  borderRadius: "12px",
                  padding: "16px 20px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "12px",
                  flexWrap: "wrap",
                }}
              >
                <div>
                  <div style={{ fontSize: "15px", fontWeight: 600 }}>
                    {request.email}
                  </div>

                  {request.created_at && (
                    <div style={{ fontSize: "12px", color: "#9ca3af" }}>
                      Requested {new Date(request.created_at).toLocaleString()}
                    </div>
                  )}
                </div>

                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    type="button"
                    onClick={() => handleApprove(request)}
                    disabled={processingId === request.request_id}
                    style={{
                      height: "36px",
                      padding: "0 16px",
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#ffffff",
                      background: "#111827",
                      border: "none",
                      borderRadius: "8px",
                      cursor: "pointer",
                    }}
                  >
                    Approve
                  </button>

                  <button
                    type="button"
                    onClick={() => handleReject(request)}
                    disabled={processingId === request.request_id}
                    style={{
                      height: "36px",
                      padding: "0 16px",
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#b91c1c",
                      background: "#ffffff",
                      border: "1px solid #fca5a5",
                      borderRadius: "8px",
                      cursor: "pointer",
                    }}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {approvedAdmin && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(17, 24, 39, 0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 2000,
            padding: "20px",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "440px",
              background: "#ffffff",
              borderRadius: "20px",
              padding: "36px",
              textAlign: "center",
              boxShadow: "0 20px 48px rgba(17, 24, 39, 0.2)",
            }}
          >
            <div style={{ fontSize: "40px", marginBottom: "12px" }}>✅</div>
            <h3 style={{ margin: "0 0 8px 0" }}>Admin approved</h3>
            <p style={{ color: "#6b7280", margin: "0 0 24px 0" }}>
              <strong>{approvedAdmin.email}</strong> can now sign in with the
              password they chose. They have no data source yet, so they can't
              create a workspace until you set one up for them.
            </p>

            <button
              type="button"
              onClick={() =>
                navigate(`/datasources/new?adminId=${approvedAdmin.userId}`)
              }
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
                marginBottom: "12px",
              }}
            >
              Set up their data source now
            </button>

            <button
              type="button"
              onClick={() => setApprovedAdmin(null)}
              style={{
                width: "100%",
                height: "44px",
                fontSize: "14px",
                fontWeight: 600,
                color: "#374151",
                background: "#ffffff",
                border: "1px solid #d1d5db",
                borderRadius: "10px",
                cursor: "pointer",
              }}
            >
              Later
            </button>
          </div>
        </div>
      )}
    </div>
  );
}