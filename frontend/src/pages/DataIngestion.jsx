import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  getWorkspace,
  browseConnectorRoot,
  browseConnectorChildren,
  browseConnectorTables,
  importFileGroupData,
  uploadLocalFile,
} from "../api/api";
import { getAuthSession } from "../api/auth";
import TitleBanner from "../components/TitleBanner";

// Source types that are browsed as database -> schema -> table.
const DATABASE_SOURCE_TYPES = ["POSTGRESQL", "MYSQL", "MSSQL", "SNOWFLAKE"];

// Source types with no login/credential at all.
const NO_CREDENTIAL_SOURCE_TYPES = ["LOCAL_FILE", "URL"];

// Shared styling for the accordion's pick-one buttons at every
// level (database, schema, table).
function pickerButtonStyle(isSelected) {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "10px 16px",
    borderRadius: "8px",
    border: isSelected ? "2px solid #111827" : "1px solid #d1d5db",
    background: isSelected ? "#111827" : "#fff",
    color: isSelected ? "#fff" : "#111827",
    cursor: "pointer",
    fontSize: "14px",
  };
}

export default function DataIngestion() {
  const navigate = useNavigate();
  const { workspaceId, fileGroupId } = useParams();
  const session = getAuthSession();

  const [workspace, setWorkspace] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [isImporting, setIsImporting] = useState(false);

  // Database-type source browsing state. Each level holds the
  // full list fetched for it, plus which single item (if any) is
  // currently selected at that level. Once something is selected,
  // the UI only renders that one item (the accordion "collapses"
  // around it) and expands the next level underneath it. Selecting
  // the same item again clears it and brings the full list back.
  const [databases, setDatabases] = useState([]);
  const [selectedDatabase, setSelectedDatabase] = useState("");
  const [schemas, setSchemas] = useState([]);
  const [selectedSchema, setSelectedSchema] = useState("");
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState("");

  // File/URL-type source browsing state (folder-style paths, for S3 etc.)
  const [pathLevels, setPathLevels] = useState([]); // array of { label, options, selected }

  // Local File upload / URL paste state (no credential)
  const [selectedLocalFile, setSelectedLocalFile] = useState(null);
  const [urlInput, setUrlInput] = useState("");

  // Rename-before-import confirmation. Every import path (local
  // file upload, URL, and database/path selection) routes through
  // this same prompt before actually importing, so the user always
  // gets a chance to rename the file/table or keep its original
  // name. "type" records which of the three import paths to run
  // once the user confirms.
  const [pendingImportType, setPendingImportType] = useState(null);
  const [importDisplayName, setImportDisplayName] = useState("");

  useEffect(() => {
    loadWorkspace();
  }, [workspaceId]);

  async function loadWorkspace() {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const response = await getWorkspace(workspaceId, session.accessToken);
      const ws = response.workspace || response;
      setWorkspace(ws);

      const sourceType = (ws.source_type || "").toUpperCase();

      if (NO_CREDENTIAL_SOURCE_TYPES.includes(sourceType)) {
        // No credential, no browsing needed — the UI below just
        // shows a file picker or a URL field.
        return;
      }

      const credentialId = ws.data_source_credential_id;
      if (!credentialId) {
        setErrorMessage("This workspace has no data source credential configured.");
        return;
      }

      const rootResponse = await browseConnectorRoot(credentialId, session.accessToken);
      const rootPaths = rootResponse.paths || [];

      if (DATABASE_SOURCE_TYPES.includes((ws.source_type || "").toUpperCase())) {
        setDatabases(rootPaths);
      } else {
        setPathLevels([{ label: "Select a path", options: rootPaths, selected: "" }]);
      }
    } catch (error) {
      setErrorMessage(error.message || "Unable to load workspace data source.");
    } finally {
      setIsLoading(false);
    }
  }

  const isDatabaseSource = DATABASE_SOURCE_TYPES.includes(
    (workspace?.source_type || "").toUpperCase()
  );

  const isNoCredentialSource = NO_CREDENTIAL_SOURCE_TYPES.includes(
    (workspace?.source_type || "").toUpperCase()
  );

  // --------------------------------------------------------
  // RENAME-BEFORE-IMPORT PROMPT
  //
  // Every import path opens this same confirmation first instead
  // of importing immediately. It's pre-filled with the item's
  // original name — the user can leave it as-is to import under
  // the original name, or edit it to rename on the way in.
  // --------------------------------------------------------

  function openImportPrompt(type, defaultName) {
    setPendingImportType(type);
    setImportDisplayName(defaultName || "");
  }

  function closeImportPrompt() {
    setPendingImportType(null);
    setImportDisplayName("");
  }

  function confirmImportPrompt() {
    const finalName = importDisplayName.trim();
    const type = pendingImportType;

    closeImportPrompt();

    if (type === "local") {
      performLocalFileImport(finalName);
    } else if (type === "url") {
      performUrlImport(finalName);
    } else if (type === "selection") {
      performSelectionImport(finalName);
    }
  }

  // --------------------------------------------------------
  // LOCAL FILE UPLOAD / URL PASTE (no credential)
  // --------------------------------------------------------

  function handleLocalFileImportClick() {
    if (!selectedLocalFile) return;
    openImportPrompt("local", selectedLocalFile.name);
  }

  async function performLocalFileImport(displayName) {
    setErrorMessage("");
    setIsImporting(true);

    try {
      const response = await uploadLocalFile(
        workspaceId,
        fileGroupId,
        selectedLocalFile,
        displayName || selectedLocalFile.name,
        session.accessToken
      );

      const importedFiles = response.files || [];
      const firstFile = importedFiles[0];

      if (firstFile) {
        navigate(
          `/workspaces/${workspaceId}/file-groups/${fileGroupId}/files/${firstFile.file_id}/preview`
        );
      } else {
        navigate(`/workspaces/${workspaceId}/file-groups/${fileGroupId}`);
      }
    } catch (error) {
      setErrorMessage(error.message || "Failed to upload file.");
    } finally {
      setIsImporting(false);
    }
  }

  function handleUrlImportClick() {
    if (!urlInput.trim()) return;

    const guessedName =
      urlInput
        .trim()
        .split("/")
        .filter(Boolean)
        .pop() || "imported_data";

    openImportPrompt("url", guessedName);
  }

  async function performUrlImport(displayName) {
    setErrorMessage("");
    setIsImporting(true);

    try {
      const response = await importFileGroupData(
        workspaceId,
        fileGroupId,
        null,
        [
          {
            source_path: urlInput.trim(),
            display_name: displayName || undefined,
          },
        ],
        session.accessToken
      );

      const importedFiles = response.files || [];
      const firstFile = importedFiles[0];

      if (firstFile) {
        navigate(
          `/workspaces/${workspaceId}/file-groups/${fileGroupId}/files/${firstFile.file_id}/preview`
        );
      } else {
        navigate(`/workspaces/${workspaceId}/file-groups/${fileGroupId}`);
      }
    } catch (error) {
      setErrorMessage(error.message || "Failed to import from URL.");
    } finally {
      setIsImporting(false);
    }
  }

  // --------------------------------------------------------
  // DATABASE -> SCHEMA -> TABLE DRILL-DOWN
  //
  // Each handler toggles: clicking the already-selected item at
  // that level clears it (and everything below it) and brings the
  // full list at that level back. Clicking a different item
  // selects it, clears anything chosen below it, and fetches the
  // next level.
  // --------------------------------------------------------

  async function handleSelectDatabase(database) {
    if (selectedDatabase === database) {
      // Deselect — collapse back to showing every database again.
      setSelectedDatabase("");
      setSelectedSchema("");
      setSelectedTable("");
      setSchemas([]);
      setTables([]);
      return;
    }

    try {
      setErrorMessage("");
      setSelectedDatabase(database);
      setSelectedSchema("");
      setSelectedTable("");
      setTables([]);

      const response = await browseConnectorChildren(
        workspace.data_source_credential_id,
        { parentPath: database, databaseName: database },
        session.accessToken
      );
      setSchemas(response.paths || []);
    } catch (error) {
      setErrorMessage(error.message || "Unable to load schemas.");
    }
  }

  async function handleSelectSchema(schema) {
    if (selectedSchema === schema) {
      // Deselect — collapse back to showing every schema in this
      // database again.
      setSelectedSchema("");
      setSelectedTable("");
      setTables([]);
      return;
    }

    try {
      setErrorMessage("");
      setSelectedSchema(schema);
      setSelectedTable("");

      const response = await browseConnectorTables(
        workspace.data_source_credential_id,
        { databaseName: selectedDatabase, schemaName: schema },
        session.accessToken
      );
      setTables(response.tables || response.paths || []);
    } catch (error) {
      setErrorMessage(error.message || "Unable to load tables.");
    }
  }

  function handleSelectTable(table) {
    // Toggling the same table deselects it; picking another table
    // just swaps the selection — a single table is selected at a
    // time, ready for the Import Data button.
    setSelectedTable((current) => (current === table ? "" : table));
  }

  // --------------------------------------------------------
  // FOLDER-STYLE PATH FLOW (Local File / URL / S3 / Blob)
  // --------------------------------------------------------

  async function handleSelectPathLevel(levelIndex, value) {
    try {
      setErrorMessage("");

      const updatedLevels = pathLevels.slice(0, levelIndex + 1);
      updatedLevels[levelIndex] = {
        ...updatedLevels[levelIndex],
        selected: value,
      };

      const currentPath = updatedLevels
        .map((level) => level.selected)
        .filter(Boolean)
        .join("/");

      const response = await browseConnectorChildren(
        workspace.data_source_credential_id,
        { parentPath: currentPath },
        session.accessToken
      );

      const childPaths = response.paths || [];

      if (childPaths.length > 0) {
        updatedLevels.push({
          label: "Select a path",
          options: childPaths,
          selected: "",
        });
      }

      setPathLevels(updatedLevels);
    } catch (error) {
      setErrorMessage(error.message || "Unable to browse path.");
    }
  }

  function getSelectedFilePath() {
    return pathLevels
      .map((level) => level.selected)
      .filter(Boolean)
      .join("/");
  }

  // --------------------------------------------------------
  // IMPORT
  // --------------------------------------------------------

  function handleImportClick() {
    if (!canImport) return;

    const defaultName = isDatabaseSource
      ? selectedTable
      : getSelectedFilePath().split("/").filter(Boolean).pop() ||
        "imported_data";

    openImportPrompt("selection", defaultName);
  }

  async function performSelectionImport(displayName) {
    setErrorMessage("");
    setIsImporting(true);

    try {
      const selections = isDatabaseSource
        ? [
            {
              database_name: selectedDatabase,
              schema_name: selectedSchema,
              table_name: selectedTable,
              display_name: displayName || undefined,
            },
          ]
        : [
            {
              source_path: getSelectedFilePath(),
              display_name: displayName || undefined,
            },
          ];

      const response = await importFileGroupData(
        workspaceId,
        fileGroupId,
        workspace.data_source_credential_id,
        selections,
        session.accessToken
      );

      const importedFiles = response.files || [];
      const firstFile = importedFiles[0];

      if (firstFile) {
        navigate(
          `/workspaces/${workspaceId}/file-groups/${fileGroupId}/files/${firstFile.file_id}/preview`
        );
      } else {
        // Fallback: if the response didn't include the created
        // files for some reason, go to the list instead of a
        // broken route.
        navigate(`/workspaces/${workspaceId}/file-groups/${fileGroupId}`);
      }
    } catch (error) {
      setErrorMessage(error.message || "Failed to import data.");
    } finally {
      setIsImporting(false);
    }
  }

  const canImport = isDatabaseSource
    ? Boolean(selectedTable)
    : Boolean(getSelectedFilePath());

  if (isLoading) {
    return <div className="loading-state">Loading data source...</div>;
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <TitleBanner
        subtitle={workspace?.name}
        rightContent={
          <>
            <button
              type="button"
              onClick={() => navigate(`/workspaces/${workspaceId}`)}
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
              ← Back
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
                fontWeight: "600",
                cursor: "pointer",
              }}
            >
              Home
            </button>
          </>
        }
      />

      <div style={{ padding: "32px", maxWidth: "900px", margin: "0 auto" }}>
        <h2 style={{ marginTop: 0 }}>Select Data to Import</h2>

        {errorMessage && <div className="error-box">{errorMessage}</div>}

        {isNoCredentialSource ? (
          (workspace?.source_type || "").toUpperCase() === "LOCAL_FILE" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "480px" }}>
              <label style={{ fontWeight: 600, fontSize: "14px" }}>
                Choose a file from your computer
              </label>
              <input
                type="file"
                onChange={(e) => setSelectedLocalFile(e.target.files?.[0] || null)}
                style={{
                  padding: "12px",
                  border: "1px solid #d1d5db",
                  borderRadius: "8px",
                }}
              />
              <button
                type="button"
                onClick={handleLocalFileImportClick}
                disabled={!selectedLocalFile || isImporting}
                style={{
                  height: "48px",
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#ffffff",
                  background: !selectedLocalFile || isImporting ? "#9ca3af" : "#111827",
                  border: "none",
                  borderRadius: "10px",
                  cursor: !selectedLocalFile || isImporting ? "not-allowed" : "pointer",
                }}
              >
                {isImporting ? "Uploading..." : "Import Data"}
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "480px" }}>
              <label style={{ fontWeight: 600, fontSize: "14px" }}>
                Paste a publicly accessible link to the data
              </label>
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://example.com/data.csv"
                style={{
                  height: "48px",
                  padding: "0 16px",
                  border: "1px solid #d1d5db",
                  borderRadius: "8px",
                  fontSize: "15px",
                }}
              />
              <button
                type="button"
                onClick={handleUrlImportClick}
                disabled={!urlInput.trim() || isImporting}
                style={{
                  height: "48px",
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#ffffff",
                  background: !urlInput.trim() || isImporting ? "#9ca3af" : "#111827",
                  border: "none",
                  borderRadius: "10px",
                  cursor: !urlInput.trim() || isImporting ? "not-allowed" : "pointer",
                }}
              >
                {isImporting ? "Importing..." : "Import Data"}
              </button>
            </div>
          )
        ) : isDatabaseSource ? (
          <div>
            {/* Breadcrumb: shows the path chosen so far. Each
                segment is clickable — clicking it is the same as
                deselecting that level, which clears it (and
                whatever was chosen below it) and brings its list
                back. Nothing is shown here until a database has
                been picked. */}
            {selectedDatabase && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginBottom: "20px",
                  fontSize: "20px",
                  fontWeight: 700,
                  color: "#111827",
                }}
              >
                <span
                  onClick={() => handleSelectDatabase(selectedDatabase)}
                  style={{ cursor: "pointer" }}
                  title="Click to change database"
                >
                  🗄️ {selectedDatabase}
                </span>

                {selectedSchema && (
                  <>
                    <span style={{ color: "#9ca3af", fontWeight: 400 }}>/</span>
                    <span
                      onClick={() => handleSelectSchema(selectedSchema)}
                      style={{ cursor: "pointer" }}
                      title="Click to change schema"
                    >
                      📂 {selectedSchema}
                    </span>
                  </>
                )}
              </div>
            )}

            {/* Exactly one of these three lists is visible at a
                time: every database until one is picked, then
                every schema inside it until one of those is
                picked, then every table inside that schema. */}
            {!selectedDatabase ? (
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                {databases.map((db) => (
                  <button
                    key={db}
                    type="button"
                    onClick={() => handleSelectDatabase(db)}
                    style={pickerButtonStyle(false)}
                  >
                    🗄️ {db}
                  </button>
                ))}
              </div>
            ) : !selectedSchema ? (
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                {schemas.map((schema) => (
                  <button
                    key={schema}
                    type="button"
                    onClick={() => handleSelectSchema(schema)}
                    style={pickerButtonStyle(false)}
                  >
                    📂 {schema}
                  </button>
                ))}
              </div>
            ) : (
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                {tables.map((table) => {
                  const isSelected = selectedTable === table;
                  return (
                    <button
                      key={table}
                      type="button"
                      onClick={() => handleSelectTable(table)}
                      style={pickerButtonStyle(isSelected)}
                      title={isSelected ? "Click to deselect" : undefined}
                    >
                      📄 {table}
                      {isSelected && <span style={{ opacity: 0.8 }}>✕</span>}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            {pathLevels.map((level, index) => (
              <div key={index}>
                <h4>Select Path {index > 0 ? `(inside ${pathLevels[index - 1].selected})` : ""}</h4>
                <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                  {level.options.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => handleSelectPathLevel(index, option)}
                      style={{
                        padding: "10px 16px",
                        borderRadius: "8px",
                        border: level.selected === option ? "2px solid #111827" : "1px solid #d1d5db",
                        background: level.selected === option ? "#111827" : "#fff",
                        color: level.selected === option ? "#fff" : "#111827",
                        cursor: "pointer",
                      }}
                    >
                      📁 {option}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {!isNoCredentialSource && (
          <button
            type="button"
            onClick={handleImportClick}
            disabled={!canImport || isImporting}
            style={{
              marginTop: "32px",
              height: "52px",
              padding: "0 32px",
              fontSize: "16px",
              fontWeight: 700,
              color: "#ffffff",
              background: !canImport || isImporting ? "#9ca3af" : "#111827",
              border: "none",
              borderRadius: "10px",
              cursor: !canImport || isImporting ? "not-allowed" : "pointer",
            }}
          >
            {isImporting ? "Importing..." : "Import Data"}
          </button>
        )}
      </div>

      {pendingImportType && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(17, 24, 39, 0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 3000,
            padding: "20px",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "420px",
              background: "#ffffff",
              borderRadius: "20px",
              padding: "36px",
              boxShadow: "0 20px 48px rgba(17, 24, 39, 0.2)",
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: "8px" }}>
              Name this {pendingImportType === "selection" && isDatabaseSource ? "table" : "file"}
            </h3>
            <p style={{ color: "#6b7280", fontSize: "14px", marginBottom: "20px" }}>
              Keep the original name, or enter a different one to use inside
              DataEase.
            </p>

            <input
              type="text"
              value={importDisplayName}
              onChange={(e) => setImportDisplayName(e.target.value)}
              autoFocus
              style={{
                width: "100%",
                height: "48px",
                padding: "0 16px",
                border: "1px solid #d1d5db",
                borderRadius: "10px",
                fontSize: "15px",
                marginBottom: "24px",
                boxSizing: "border-box",
              }}
            />

            <div style={{ display: "flex", gap: "12px" }}>
              <button
                type="button"
                onClick={confirmImportPrompt}
                disabled={!importDisplayName.trim()}
                style={{
                  flex: 1,
                  height: "48px",
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#ffffff",
                  background: importDisplayName.trim() ? "#111827" : "#9ca3af",
                  border: "none",
                  borderRadius: "10px",
                  cursor: importDisplayName.trim() ? "pointer" : "not-allowed",
                }}
              >
                Import
              </button>
              <button
                type="button"
                onClick={closeImportPrompt}
                style={{
                  flex: 1,
                  height: "48px",
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#374151",
                  background: "#ffffff",
                  border: "1px solid #d1d5db",
                  borderRadius: "10px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}