import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { testConnectorConnection } from "../api/api";
import { createDataSourceCredential, getAdmins } from "../api/admin";
import { getAuthSession } from "../api/auth";
import TitleBanner from "../components/TitleBanner";

// Each source type lists the fields the backend connector expects.
// "number" fields are sent as integers, "password" fields are sent
// exactly as typed, everything else is trimmed.
const SOURCE_TYPES = [
  {
    value: "POSTGRESQL",
    label: "PostgreSQL",
    testable: true,
    fields: [
      { key: "host", label: "Host", type: "text", initial: "localhost" },
      { key: "port", label: "Port", type: "number", initial: "5432" },
      { key: "username", label: "Username", type: "text", initial: "" },
      { key: "password", label: "Password", type: "password", initial: "" },
    ],
  },
  {
    value: "MYSQL",
    label: "MySQL",
    testable: true,
    fields: [
      { key: "host", label: "Host", type: "text", initial: "localhost" },
      { key: "port", label: "Port", type: "number", initial: "3306" },
      { key: "username", label: "Username", type: "text", initial: "" },
      { key: "password", label: "Password", type: "password", initial: "" },
    ],
  },
  {
    value: "SNOWFLAKE",
    label: "Snowflake",
    testable: true,
    fields: [
      {
        key: "account_identifier",
        label: "Account identifier",
        type: "text",
        initial: "",
        placeholder: "orgname-accountname",
      },
      { key: "username", label: "Username", type: "text", initial: "" },
      { key: "password", label: "Password", type: "password", initial: "" },
    ],
  },
  {
    value: "AWS_S3",
    label: "AWS S3",
    testable: true,
    fields: [
      { key: "access_key", label: "Access key", type: "text", initial: "" },
      { key: "secret_key", label: "Secret key", type: "password", initial: "" },
    ],
  },
  {
    value: "AZURE_BLOB",
    label: "Azure Blob Storage",
    testable: true,
    fields: [
      {
        key: "connection_string",
        label: "Connection string",
        type: "password",
        initial: "",
        placeholder: "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net",
      },
    ],
  },
];

function initialValuesFor(sourceTypeValue) {
  const source = SOURCE_TYPES.find((item) => item.value === sourceTypeValue);
  const values = {};

  (source?.fields || []).forEach((field) => {
    values[field.key] = field.initial;
  });

  return values;
}

const inputStyle = {
  width: "100%",
  height: "46px",
  padding: "0 14px",
  fontSize: "15px",
  border: "1px solid #d1d5db",
  borderRadius: "10px",
  boxSizing: "border-box",
  background: "#ffffff",
};

const labelStyle = {
  display: "block",
  marginBottom: "6px",
  fontSize: "13px",
  fontWeight: 600,
  color: "#374151",
};

export default function DataSourceSetup() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const session = getAuthSession();
  const token = session?.accessToken;

  // Coming from the Admins page or from approving an Admin request,
  // the Admin is already chosen: /datasources/new?adminId=<id>
  const presetAdminId = searchParams.get("adminId") || "";

  const [admins, setAdmins] = useState([]);
  const [assignedAdminId, setAssignedAdminId] = useState(presetAdminId);

  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("POSTGRESQL");
  const [values, setValues] = useState(() => initialValuesFor("POSTGRESQL"));

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [warningMessage, setWarningMessage] = useState("");

  const sourceConfig = useMemo(
    () => SOURCE_TYPES.find((item) => item.value === sourceType),
    [sourceType]
  );

  const assignedAdmin = admins.find(
    (admin) => admin.user_id === assignedAdminId
  );

  useEffect(() => {
    loadAdmins();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadAdmins() {
    try {
      const response = await getAdmins(token);
      setAdmins(response.admins || []);
    } catch (error) {
      setErrorMessage(error.message || "Unable to load Admin accounts.");
    }
  }

  function handleSourceTypeChange(nextType) {
    setSourceType(nextType);
    setValues(initialValuesFor(nextType));
    setErrorMessage("");
    setSuccessMessage("");
    setWarningMessage("");
  }

  function handleFieldChange(key, value) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setErrorMessage("");
    setSuccessMessage("");
    setWarningMessage("");

    const config = {};

    for (const field of sourceConfig.fields) {
      const raw = values[field.key] ?? "";

      if (field.type === "number") {
        const parsed = parseInt(raw, 10);

        if (Number.isNaN(parsed)) {
          setErrorMessage(`${field.label} must be a number.`);
          return;
        }

        config[field.key] = parsed;
      } else if (field.type === "password") {
        config[field.key] = raw;
      } else {
        config[field.key] = raw.trim();
      }
    }

    try {
      setIsSubmitting(true);

      const created = await createDataSourceCredential(
        {
          name: name.trim(),
          source_type: sourceType,
          config,
          assigned_admin_id: assignedAdminId || null,
        },
        token
      );

      const ownerLabel = assignedAdmin
        ? `for ${assignedAdmin.email}`
        : "for the Owner only";

      // Don't keep secrets in the form after they've been saved.
      setName("");
      setValues(initialValuesFor(sourceType));

      if (sourceConfig.testable) {
        try {
          await testConnectorConnection(created.id, token);
          setSuccessMessage(
            `Data source saved ${ownerLabel}. The connection test passed.`
          );
        } catch (testError) {
          setSuccessMessage(`Data source saved ${ownerLabel}.`);
          setWarningMessage(
            `The connection test failed: ${
              testError.message || "unable to connect"
            }. Check the details and add the data source again if needed.`
          );
        }
      } else {
        setSuccessMessage(`Data source saved ${ownerLabel}.`);
      }
    } catch (error) {
      setErrorMessage(error.message || "Failed to save the data source.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const backTarget = presetAdminId ? "/admin/admins" : "/dashboard";

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <TitleBanner
        subtitle="Data Source Setup"
        rightContent={
          <button
            type="button"
            onClick={() => navigate(backTarget)}
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
            ← Back
          </button>
        }
      />

      <div style={{ padding: "32px 20px", maxWidth: "620px", margin: "0 auto" }}>
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            borderRadius: "16px",
            padding: "32px",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Add a data source</h2>
          <p style={{ color: "#6b7280", fontSize: "14px", marginTop: 0 }}>
            The details are encrypted before they are stored. The Admin you
            choose will be able to use this data source when creating
            workspaces, but never sees its password or keys.
          </p>

          {errorMessage && (
            <div className="error-box" style={{ marginBottom: "16px" }}>
              {errorMessage}
            </div>
          )}

          {successMessage && (
            <div className="success-box" style={{ marginBottom: "16px" }}>
              {successMessage}{" "}
              <Link to="/admin/admins" style={{ color: "#4f46e5", fontWeight: 600 }}>
                View Admins
              </Link>
            </div>
          )}

          {warningMessage && (
            <div
              style={{
                marginBottom: "16px",
                padding: "12px 16px",
                borderRadius: "8px",
                background: "#fffbeb",
                border: "1px solid #fde68a",
                color: "#92400e",
                fontSize: "14px",
              }}
            >
              {warningMessage}
            </div>
          )}

          <form
            onSubmit={handleSubmit}
            style={{ display: "flex", flexDirection: "column", gap: "18px" }}
          >
            <div>
              <label htmlFor="assignedAdmin" style={labelStyle}>
                Set up for
              </label>
              <select
                id="assignedAdmin"
                value={assignedAdminId}
                onChange={(event) => setAssignedAdminId(event.target.value)}
                style={inputStyle}
              >
                <option value="">Me (Owner only, not shared with any Admin)</option>
                {admins.map((admin) => (
                  <option key={admin.user_id} value={admin.user_id}>
                    {admin.email}
                    {admin.is_active ? "" : " (inactive)"}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="credentialName" style={labelStyle}>
                Name
              </label>
              <input
                id="credentialName"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Sales warehouse"
                required
                style={inputStyle}
              />
            </div>

            <div>
              <label htmlFor="sourceType" style={labelStyle}>
                Source type
              </label>
              <select
                id="sourceType"
                value={sourceType}
                onChange={(event) => handleSourceTypeChange(event.target.value)}
                style={inputStyle}
              >
                {SOURCE_TYPES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>

            {sourceConfig.fields.map((field) => (
              <div key={field.key}>
                <label htmlFor={`field-${field.key}`} style={labelStyle}>
                  {field.label}
                </label>
                <input
                  id={`field-${field.key}`}
                  type={field.type === "number" ? "text" : field.type}
                  inputMode={field.type === "number" ? "numeric" : undefined}
                  value={values[field.key] ?? ""}
                  onChange={(event) =>
                    handleFieldChange(field.key, event.target.value)
                  }
                  placeholder={field.placeholder}
                  autoComplete={
                    field.type === "password" ? "new-password" : "off"
                  }
                  required
                  style={inputStyle}
                />
              </div>
            ))}

            <p style={{ margin: 0, fontSize: "13px", color: "#6b7280" }}>
              You don't choose a database or schema here. After saving, the
              Admin browses every database and schema this login can see when
              they create a workspace.
            </p>

            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                height: "50px",
                fontSize: "15px",
                fontWeight: 700,
                color: "#ffffff",
                background: isSubmitting ? "#9ca3af" : "#111827",
                border: "none",
                borderRadius: "10px",
                cursor: isSubmitting ? "not-allowed" : "pointer",
              }}
            >
              {isSubmitting ? "Saving..." : "Save data source"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}