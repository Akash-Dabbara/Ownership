import {
  useEffect,
  useState,
} from "react";

import {
  useNavigate,
} from "react-router-dom";

import {
  getDataSourceCredentials,
  testConnectorConnection,
  browseConnectorRoot,
  browseConnectorChildren,
  validateConnectorDestination,
  createWorkspace,
} from "../api/api";

import {
  getAccessToken,
} from "../api/auth";

import TitleBanner from "../components/TitleBanner";

const DATA_SOURCE_CATALOG = [
  {
    category: "Databases",
    items: [
      { type: "POSTGRESQL", name: "PostgreSQL", icon: "🐘" },
      { type: "MYSQL", name: "MySQL", icon: "🐬" },
      { type: "MSSQL", name: "SQL Server", icon: "🗄️" },
    ],
  },
  {
    category: "Servers & Cloud",
    items: [
      { type: "SNOWFLAKE", name: "Snowflake", icon: "❄️" },
    ],
  },
  {
    category: "Blob Storages & Files",
    items: [
      { type: "LOCAL_FILE", name: "Local Files / Storage", icon: "📁" },
      { type: "AWS_S3", name: "AWS S3", icon: "📦" },
      { type: "AZURE_BLOB", name: "Cloud Blob Storage", icon: "☁️" },
      { type: "URL", name: "URL / Web Endpoint", icon: "🌐" },
    ],
  },
];

export default function CreateWorkspaceStep2() {
  const navigate = useNavigate();
  const token = getAccessToken();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const [credentials, setCredentials] = useState([]);
  const [selectedSourceType, setSelectedSourceType] = useState("POSTGRESQL");
  const [selectedCredentialId, setSelectedCredentialId] = useState("");

  const [selectedDatabase, setSelectedDatabase] = useState("");
  const [selectedSchema, setSelectedSchema] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [destinationLevel, setDestinationLevel] = useState("database");
  const [selectedDestination, setSelectedDestination] = useState("");

  const [testStatus, setTestStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isBrowsing, setIsBrowsing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(() => {
    loadCredentials();
  }, []);

  async function loadCredentials() {
    try {
      setErrorMessage("");
      const response = await getDataSourceCredentials(token);
      const credentialList =
        response.credentials ||
        response.data ||
        response ||
        [];

      const credArray = Array.isArray(credentialList) ? credentialList : [];
      setCredentials(credArray);

      // Automatically map to the default source type if available
      const initialCred = credArray.find(
        (c) => (c.source_type || "").toUpperCase() === "POSTGRESQL"
      ) || credArray[0];

      if (initialCred) {
        setSelectedCredentialId(initialCred.id || initialCred.credential_id);
        setSelectedSourceType((initialCred.source_type || "POSTGRESQL").toUpperCase());
      }
    } catch (error) {
      setErrorMessage(
        error.message || "Unable to load data source credentials."
      );
    }
  }

  // Every credential registered for the currently selected source
  // type. An Admin may have more than one (e.g. two Postgres
  // databases the Owner set up for them), so this drives a picker
  // instead of silently using whichever one loaded first.
  const matchingCredentials = credentials.filter(
    (cred) =>
      (cred.source_type || "").toUpperCase() ===
      selectedSourceType.toUpperCase()
  );

  function handleSelectSourceType(sourceType) {
    setSelectedSourceType(sourceType);

    // Find the specific credential registered for this source type
    const matchingCredential = credentials.find(
      (cred) =>
        (cred.source_type || "").toUpperCase() === sourceType.toUpperCase()
    );

    if (matchingCredential) {
      setSelectedCredentialId(matchingCredential.id || matchingCredential.credential_id);
    } else {
      setSelectedCredentialId("");
    }

    setTestStatus(null);
    setSuggestions([]);
    setSelectedDatabase("");
    setSelectedSchema("");
    setSelectedDestination("");
    setDestinationLevel("database");
    setErrorMessage("");
    setSuccessMessage("");
  }

  function handleSelectCredential(credentialId) {
    setSelectedCredentialId(credentialId);
    setTestStatus(null);
    setSuggestions([]);
    setSelectedDatabase("");
    setSelectedSchema("");
    setSelectedDestination("");
    setDestinationLevel("database");
    setErrorMessage("");
    setSuccessMessage("");
  }

  const requiresConnectionTest =
    selectedSourceType !== "LOCAL_FILE" && selectedSourceType !== "URL";

  async function handleTestConnection() {
    if (!selectedCredentialId) {
      setErrorMessage(
        `No ${selectedSourceType} data source has been set up for your account. Ask the Owner to add one.`
      );
      return;
    }

    try {
      setIsLoading(true);
      setErrorMessage("");
      setSuccessMessage("");
      setTestStatus(null);

      if (requiresConnectionTest) {
        await testConnectorConnection(selectedCredentialId, token);
      }

      const response = await browseConnectorRoot(selectedCredentialId, token);
      const paths = response.paths || [];

      setSuggestions(paths);
      setSelectedDatabase("");
      setSelectedSchema("");
      setSelectedDestination("");
      setDestinationLevel("database");
      setTestStatus("success");
      setSuccessMessage(
        requiresConnectionTest
          ? `Connection successful using ${selectedSourceType} credentials. Select target database & schema below.`
          : `${selectedSourceType} source ready — no login required. Select the destination below.`
      );
    } catch (error) {
      setTestStatus("failed");
      setSuggestions([]);
      setErrorMessage(
        error.message || `Unable to load ${selectedSourceType} using its saved configuration.`
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDatabaseSelect(database) {
    if (!selectedCredentialId) return;

    try {
      setIsBrowsing(true);
      setErrorMessage("");
      setSuccessMessage("");

      setSelectedDatabase(database);
      setSelectedSchema("");
      setSelectedDestination(database);

      const response = await browseConnectorChildren(
        selectedCredentialId,
        {
          parentPath: database,
          searchText: "",
          databaseName: database,
        },
        token
      );

      setSuggestions(response.paths || []);
      setDestinationLevel("schema");
    } catch (error) {
      setSuggestions([]);
      setErrorMessage(
        error.message || "Unable to load schemas for the selected database."
      );
    } finally {
      setIsBrowsing(false);
    }
  }

  function handleSchemaSelect(schema) {
    if (!selectedDatabase) {
      setErrorMessage("Please select a database first.");
      return;
    }

    setSelectedSchema(schema);
    const fullPath = `${selectedDatabase}/${schema}`;
    setSelectedDestination(fullPath);
    setSuggestions([]);
    setSuccessMessage(`Target Schema Selected: ${fullPath} (Tables will be stored in this schema)`);
  }

  async function handleGoBackPath() {
    if (!selectedCredentialId) return;

    try {
      setIsBrowsing(true);
      setErrorMessage("");
      setSuccessMessage("");

      if (destinationLevel === "schema") {
        const response = await browseConnectorRoot(selectedCredentialId, token);
        setSuggestions(response.paths || []);
        setSelectedDatabase("");
        setSelectedSchema("");
        setSelectedDestination("");
        setDestinationLevel("database");
      }
    } catch (error) {
      setErrorMessage(
        error.message || "Unable to return to the previous destination level."
      );
    } finally {
      setIsBrowsing(false);
    }
  }

  async function handleConfirmDestination() {
    if (!selectedDestination || !selectedSchema) {
      setErrorMessage("Please select both a database and a target schema.");
      return;
    }

    if (!selectedCredentialId) return;

    try {
      setIsBrowsing(true);
      setErrorMessage("");

      const response = await validateConnectorDestination(
        selectedCredentialId,
        {
          path: selectedDestination,
          databaseName: selectedDatabase,
        },
        token
      );

      if (response.valid) {
        setSuccessMessage(`Destination confirmed: ${selectedDestination}`);
      } else {
        setErrorMessage("The selected destination schema is not valid.");
      }
    } catch (error) {
      setErrorMessage(
        error.message || "Unable to validate destination."
      );
    } finally {
      setIsBrowsing(false);
    }
  }

  async function handleFormSubmit(event) {
    event.preventDefault();
    setErrorMessage("");

    if (!name.trim()) {
      setErrorMessage("Workspace name is required.");
      return;
    }

    const finalDestinationPath = requiresConnectionTest
      ? selectedDestination
      : "local-downloads";

    if (requiresConnectionTest) {
      if (testStatus !== "success") {
        setErrorMessage("Please test the data source connection first.");
        return;
      }

      if (!selectedDestination || !selectedSchema) {
        setErrorMessage("Please select a valid destination schema path.");
        return;
      }

      if (!selectedCredentialId) {
        setErrorMessage("Please select a valid data source credential ID.");
        return;
      }
    }

    try {
      setIsLoading(true);

      const response = await createWorkspace(
        {
          name: name.trim(),
          source_type: selectedSourceType,
          destination_path: finalDestinationPath,
          description: description.trim() || null,
          data_source_credential_id: requiresConnectionTest
            ? selectedCredentialId
            : null,
        },
        token
      );

      const createdWorkspace = response.workspace || response;
      const newWorkspaceId =
        createdWorkspace.workspace_id || createdWorkspace.id;

      if (newWorkspaceId) {
        navigate(`/workspaces/${newWorkspaceId}`);
      } else {
        // Fallback in case the create response doesn't include an id —
        // avoids sending the user to a broken route.
        navigate("/dashboard");
      }
    } catch (error) {
      setErrorMessage(
        error.message || "Failed to create workspace."
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <TitleBanner
        subtitle="Create Workspace"
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
              fontWeight: "600",
              cursor: "pointer",
            }}
          >
            ← Back to Dashboard
          </button>
        }
      />

      <div
        className="workspace-form-page"
        style={{
          minHeight: "100vh",
          background: "#f8fafc",
        }}
      >

      <form onSubmit={handleFormSubmit} className="workspace-config-form" style={{ padding: "32px", maxWidth: "800px", margin: "0 auto" }}>
        {errorMessage && <div className="error-box">{errorMessage}</div>}
        {successMessage && <div className="success-box">{successMessage}</div>}

        <div className="form-field">
          <label>Workspace Name</label>
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Customer Analytics Workspace"
            required
          />
        </div>

        <div className="form-field">
          <label>Select Data Source Type</label>
          <div className="datasource-categories-container">
            {DATA_SOURCE_CATALOG.map((group) => (
              <div key={group.category} className="datasource-category-group">
                <h3 className="category-title">{group.category}</h3>
                <div className="datasource-cards-grid">
                  {group.items.map((item) => {
                    const isSelected = selectedSourceType === item.type;
                    return (
                      <div
                        key={item.type}
                        className={`datasource-card ${isSelected ? "selected" : ""}`}
                        onClick={() => handleSelectSourceType(item.type)}
                      >
                        <span className="datasource-card-icon">{item.icon}</span>
                        <div className="datasource-card-info">
                          <h4>{item.name}</h4>
                          <span className="datasource-type-badge">{item.type}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {requiresConnectionTest && (
          matchingCredentials.length === 0 ? (
            <div className="error-box">
              No {selectedSourceType} data source has been set up for your
              account. Ask the Owner to add one, then reload this page.
            </div>
          ) : matchingCredentials.length > 1 ? (
            <div className="form-field">
              <label>Data Source</label>
              <select
                value={selectedCredentialId}
                onChange={(event) => handleSelectCredential(event.target.value)}
              >
                {matchingCredentials.map((cred) => (
                  <option
                    key={cred.id || cred.credential_id}
                    value={cred.id || cred.credential_id}
                  >
                    {cred.name}
                  </option>
                ))}
              </select>
            </div>
          ) : null
        )}

        {requiresConnectionTest ? (
          <div className="test-connection-section">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={isLoading || !selectedCredentialId}
              className="secondary-action-btn"
            >
              {isLoading ? "Testing Connection..." : `Test Connection (${selectedSourceType})`}
            </button>

            {testStatus === "success" && (
              <span className="status-badge success">Connection Successful ✓</span>
            )}
            {testStatus === "failed" && (
              <span className="status-badge failed">Connection Failed ✕</span>
            )}
          </div>
        ) : (
          <div
            className="test-connection-section"
            style={{
              padding: "12px 16px",
              background: "#f0fdf4",
              border: "1px solid #bbf7d0",
              borderRadius: "8px",
              color: "#166534",
              fontWeight: 600,
              fontSize: "14px",
            }}
          >
            No Test Connection Needed.
          </div>
        )}

        {!requiresConnectionTest && (
          <div className="form-field">
            <label>Destination</label>
            <div className="current-path-display">
              <strong>Target Path: </strong>
              <span>Local Downloads Folder</span>
            </div>
          </div>
        )}

        {requiresConnectionTest && testStatus === "success" && (
          <div className="form-field destination-navigator-box">
            <label>Select Destination Schema (Where anonymized tables will be stored)</label>
            <div className="current-path-display">
              <strong>Target Path: </strong>
              <span>{selectedDestination || "Select database then schema below"}</span>
            </div>

            {destinationLevel === "schema" && (
              <button
                type="button"
                onClick={handleGoBackPath}
                disabled={isBrowsing}
                className="back-path-btn"
              >
                ← Back to Databases
              </button>
            )}

            {isBrowsing ? (
              <div className="loading-indicator">Browsing paths...</div>
            ) : (
              <div className="destination-list-grid">
                {suggestions.length === 0 ? (
                  <div className="no-suggestions">No items found at this level.</div>
                ) : (
                  suggestions.map((path, index) => (
                    <button
                      key={`${path}-${index}`}
                      type="button"
                      onClick={() => {
                        if (destinationLevel === "database") {
                          handleDatabaseSelect(path);
                        } else {
                          handleSchemaSelect(path);
                        }
                      }}
                      className={`destination-item-btn ${
                        (destinationLevel === "database" && selectedDatabase === path) ||
                        (destinationLevel === "schema" && selectedSchema === path)
                          ? "active"
                          : ""
                      }`}
                    >
                      <span className="item-icon">
                        {destinationLevel === "database" ? "🗄️" : "📂"}
                      </span>
                      <span className="item-text">{path}</span>
                    </button>
                  ))
                )}
              </div>
            )}

            {selectedSchema && (
              <button
                type="button"
                onClick={handleConfirmDestination}
                disabled={isBrowsing}
                className="confirm-path-btn"
              >
                Confirm Target Schema
              </button>
            )}
          </div>
        )}

        <div className="form-field">
          <label>Workspace Description (Optional)</label>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Enter purpose or details for this workspace"
            rows={3}
          />
        </div>

        <button
          type="submit"
          className="primary-button"
          disabled={isLoading || isBrowsing || (requiresConnectionTest && !selectedSchema)}
        >
          {isLoading ? "Creating Workspace..." : "Create Workspace"}
        </button>
      </form>
      </div>
    </>
  );
}