import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  deactivateAdmin,
  deleteAdmin,
  deleteDataSourceCredential,
  getAdmins,
  getAllDataSourceCredentials,
  reactivateAdmin,
} from "../api/admin";
import { getAuthSession } from "../api/auth";
import TitleBanner from "../components/TitleBanner";

const SOURCE_LABELS = {
  POSTGRESQL: "PostgreSQL",
  MYSQL: "MySQL",
  MSSQL: "SQL Server",
  SNOWFLAKE: "Snowflake",
  AWS_S3: "AWS S3",
  AZURE_BLOB: "Azure Blob",
  LOCAL_FILE: "Local File",
  URL: "URL",
};

const smallButton = {
  height: "34px",
  padding: "0 14px",
  fontSize: "13px",
  fontWeight: 600,
  borderRadius: "8px",
  cursor: "pointer",
  background: "#ffffff",
};

export default function AdminAccounts() {
  const navigate = useNavigate();
  const session = getAuthSession();
  const token = session?.accessToken;

  const [admins, setAdmins] = useState([]);
  const [credentials, setCredentials] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadData() {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const [adminResponse, credentialResponse] = await Promise.all([
        getAdmins(token),
        getAllDataSourceCredentials(token),
      ]);

      setAdmins(adminResponse.admins || []);
      setCredentials(
        Array.isArray(credentialResponse) ? credentialResponse : []
      );
    } catch (error) {
      setErrorMessage(error.message || "Unable to load Admin accounts.");
    } finally {
      setIsLoading(false);
    }
  }

  const credentialsByAdmin = useMemo(() => {
    const grouped = {};

    credentials.forEach((credential) => {
      const key = credential.assigned_admin_id || "owner";
      grouped[key] = grouped[key] || [];
      grouped[key].push(credential);
    });

    return grouped;
  }, [credentials]);

  async function runAction(key, action, successText) {
    try {
      setBusyKey(key);
      setErrorMessage("");
      setSuccessMessage("");

      await action();

      setSuccessMessage(successText);
      await loadData();
    } catch (error) {
      setErrorMessage(error.message || "That action failed.");
    } finally {
      setBusyKey("");
    }
  }

  function handleToggleActive(admin) {
    const verb = admin.is_active ? "Deactivate" : "Reactivate";

    if (!window.confirm(`${verb} ${admin.email}?`)) {
      return;
    }

    runAction(
      admin.user_id,
      () =>
        admin.is_active
          ? deactivateAdmin(admin.user_id, token)
          : reactivateAdmin(admin.user_id, token),
      `${admin.email} ${admin.is_active ? "deactivated" : "reactivated"}.`
    );
  }

  function handleDeleteAdmin(admin) {
    if (
      !window.confirm(
        `Delete ${admin.email}? This cannot be undone. If the Admin has already granted access to anyone, deactivate the account instead.`
      )
    ) {
      return;
    }

    runAction(
      admin.user_id,
      () => deleteAdmin(admin.user_id, token),
      `${admin.email} deleted.`
    );
  }

  function handleRemoveCredential(credential) {
    if (
      !window.confirm(
        `Remove the data source "${credential.name}"? Workspaces that use it will lose their connection.`
      )
    ) {
      return;
    }

    runAction(
      credential.id,
      () => deleteDataSourceCredential(credential.id, token),
      `Data source "${credential.name}" removed.`
    );
  }

  function renderCredentials(list) {
    if (!list || list.length === 0) {
      return null;
    }

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {list.map((credential) => (
          <div
            key={credential.id}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "12px",
              padding: "10px 14px",
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: "10px",
              fontSize: "14px",
            }}
          >
            <span>
              <strong>{credential.name}</strong>{" "}
              <span style={{ color: "#6b7280" }}>
                {SOURCE_LABELS[credential.source_type] ||
                  credential.source_type}
                {credential.is_active ? "" : " · inactive"}
              </span>
            </span>

            <button
              type="button"
              onClick={() => handleRemoveCredential(credential)}
              disabled={busyKey === credential.id}
              style={{
                ...smallButton,
                height: "30px",
                color: "#b91c1c",
                border: "1px solid #fca5a5",
              }}
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <TitleBanner
        subtitle="Admins"
        rightContent={
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
        }
      />

      <div style={{ padding: "32px 20px", maxWidth: "900px", margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "8px",
          }}
        >
          <h2 style={{ margin: 0 }}>Admin accounts</h2>

          <button
            type="button"
            onClick={() => navigate("/admin/requests")}
            style={{
              ...smallButton,
              color: "#4f46e5",
              border: "1px solid #4f46e5",
            }}
          >
            Pending requests
          </button>
        </div>

        <p style={{ color: "#6b7280", marginTop: 0, marginBottom: "24px" }}>
          Each Admin can only use the data sources you set up for them here.
        </p>

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
          <p style={{ color: "#6b7280" }}>Loading Admin accounts...</p>
        ) : admins.length === 0 ? (
          <p style={{ color: "#6b7280" }}>
            There are no Admin accounts yet. When someone requests an Admin
            account, approve it under Pending requests.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {admins.map((admin) => (
              <div
                key={admin.user_id}
                style={{
                  background: "#ffffff",
                  border: "1px solid #e5e7eb",
                  borderRadius: "14px",
                  padding: "20px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: "16px",
                    flexWrap: "wrap",
                    marginBottom: "14px",
                  }}
                >
                  <div>
                    <div style={{ fontSize: "16px", fontWeight: 700 }}>
                      {admin.email}
                    </div>
                    <div style={{ marginTop: "6px", display: "flex", gap: "8px" }}>
                      <span
                        style={{
                          fontSize: "12px",
                          fontWeight: 700,
                          padding: "3px 10px",
                          borderRadius: "999px",
                          color: admin.is_active ? "#166534" : "#991b1b",
                          background: admin.is_active ? "#dcfce7" : "#fee2e2",
                        }}
                      >
                        {admin.is_active ? "Active" : "Inactive"}
                      </span>

                      {admin.must_change_password && (
                        <span
                          style={{
                            fontSize: "12px",
                            fontWeight: 700,
                            padding: "3px 10px",
                            borderRadius: "999px",
                            color: "#92400e",
                            background: "#fef3c7",
                          }}
                        >
                          Hasn't signed in yet
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      onClick={() =>
                        navigate(`/datasources/new?adminId=${admin.user_id}`)
                      }
                      style={{
                        ...smallButton,
                        color: "#ffffff",
                        background: "#111827",
                        border: "none",
                      }}
                    >
                      + Add data source
                    </button>

                    <button
                      type="button"
                      onClick={() => handleToggleActive(admin)}
                      disabled={busyKey === admin.user_id}
                      style={{
                        ...smallButton,
                        color: "#374151",
                        border: "1px solid #d1d5db",
                      }}
                    >
                      {admin.is_active ? "Deactivate" : "Reactivate"}
                    </button>

                    <button
                      type="button"
                      onClick={() => handleDeleteAdmin(admin)}
                      disabled={busyKey === admin.user_id}
                      style={{
                        ...smallButton,
                        color: "#b91c1c",
                        border: "1px solid #fca5a5",
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {credentialsByAdmin[admin.user_id]?.length ? (
                  renderCredentials(credentialsByAdmin[admin.user_id])
                ) : (
                  <p style={{ margin: 0, fontSize: "14px", color: "#9ca3af" }}>
                    No data source set up for this Admin yet.
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {!isLoading && credentialsByAdmin.owner?.length > 0 && (
          <div style={{ marginTop: "32px" }}>
            <h3 style={{ marginBottom: "8px" }}>Your own data sources</h3>
            <p style={{ color: "#6b7280", marginTop: 0, fontSize: "14px" }}>
              Not shared with any Admin.
            </p>
            {renderCredentials(credentialsByAdmin.owner)}
          </div>
        )}
      </div>
    </div>
  );
}