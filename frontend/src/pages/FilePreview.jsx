import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getWorkspace, getFileGroup, previewFileData, anonymizeFileData, exportFileData, exportFileDownload } from "../api/api";
import { getAuthSession } from "../api/auth";
import TitleBanner from "../components/TitleBanner";

const ROW_COUNT_OPTIONS = [100, 150, 200, 500, 1000];

const ALGORITHM_OPTIONS = [
  { value: "", label: "No anonymization" },
  { value: "FIRST_NAME", label: "First Name" },
  { value: "LAST_NAME", label: "Last Name" },
  { value: "FULL_NAME", label: "Full Name" },
  { value: "EMAIL", label: "Email" },
  { value: "PHONE_NUMBER", label: "Phone Number" },
  { value: "DATE", label: "Date" },
  { value: "NUMBER", label: "Number" },
  { value: "ALPHANUMERIC", label: "Alphanumeric" },
  { value: "BUCKET_BASED", label: "Bucket Based" },
];

// Algorithms whose output is alphabetic text, where a casing
// choice actually makes sense.
const TEXT_ALGORITHMS = new Set([
  "FIRST_NAME",
  "LAST_NAME",
  "FULL_NAME",
  "EMAIL",
  "ALPHANUMERIC",
]);

const CASING_OPTIONS = [
  { value: "ORIGINAL", label: "Original" },
  { value: "UPPERCASE", label: "UPPERCASE" },
  { value: "lowercase", label: "lowercase" },
  { value: "Title Case", label: "Title Case" },
];

// Height of the TitleBanner (padding 20px top/bottom + ~40px content).
const BANNER_HEIGHT = "90px";

export default function FilePreview() {
  const navigate = useNavigate();
  const { workspaceId, fileGroupId, fileId } = useParams();
  const session = getAuthSession();

  const [workspace, setWorkspace] = useState(null);
  const [fileGroup, setFileGroup] = useState(null);
  const [fileInfo, setFileInfo] = useState(null);
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  const [rowLimit, setRowLimit] = useState(100);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  // Column configuration (Rule Registry)
  const [activeConfigColumn, setActiveConfigColumn] = useState(null);
  const [columnConfigs, setColumnConfigs] = useState({});
  // Draft values while a column's popover is open
  const [draftAlgorithm, setDraftAlgorithm] = useState("");
  const [draftCasing, setDraftCasing] = useState("ORIGINAL");
  const [draftConsistency, setDraftConsistency] = useState(false);

  // Anonymization run state
  const [isAnonymizing, setIsAnonymizing] = useState(false);
  const [anonymizedColumns, setAnonymizedColumns] = useState(null);
  const [anonymizedRows, setAnonymizedRows] = useState(null);
  const [showAnonymized, setShowAnonymized] = useState(false);
  const [anonymizeError, setAnonymizeError] = useState("");

  // Export state
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [showExportSuccess, setShowExportSuccess] = useState(false);
  const [exportResult, setExportResult] = useState(null);

  useEffect(() => {
    loadContext();
  }, [workspaceId, fileGroupId]);

  useEffect(() => {
    loadPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowLimit, fileId]);

  async function loadContext() {
    try {
      const [wsRes, fgRes] = await Promise.all([
        getWorkspace(workspaceId, session.accessToken),
        getFileGroup(workspaceId, fileGroupId, session.accessToken),
      ]);
      setWorkspace(wsRes.workspace || wsRes);
      setFileGroup(fgRes.file_group || fgRes);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load context.");
    }
  }

  async function loadPreview() {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const response = await previewFileData(
        workspaceId,
        fileGroupId,
        fileId,
        rowLimit,
        session.accessToken
      );

      setFileInfo(response.file);
      setColumns(response.columns || []);
      setRows(response.rows || []);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load data preview.");
      setColumns([]);
      setRows([]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleOpenColumnConfig(column) {
    const existing = columnConfigs[column];
    setDraftAlgorithm(existing?.algorithm || "");
    setDraftCasing(existing?.casing || "ORIGINAL");
    setDraftConsistency(existing?.consistency || false);
    setActiveConfigColumn(column);
  }

  function handleSaveColumnConfig() {
    if (!draftAlgorithm) {
      // Treat "No anonymization" as removing any existing config
      // for this column.
      setColumnConfigs((current) => {
        const updated = { ...current };
        delete updated[activeConfigColumn];
        return updated;
      });
    } else {
      setColumnConfigs((current) => ({
        ...current,
        [activeConfigColumn]: {
          algorithm: draftAlgorithm,
          casing: TEXT_ALGORITHMS.has(draftAlgorithm) ? draftCasing : "ORIGINAL",
          consistency: draftConsistency,
        },
      }));
    }
    setActiveConfigColumn(null);
    // Config changed — any previous anonymization result is now stale.
    setAnonymizedColumns(null);
    setAnonymizedRows(null);
    setShowAnonymized(false);
  }

  function handleResetConfig() {
    setColumnConfigs({});
    setActiveConfigColumn(null);
    setAnonymizedColumns(null);
    setAnonymizedRows(null);
    setShowAnonymized(false);
  }

  async function handleRunAnonymization() {
    setAnonymizeError("");
    setIsAnonymizing(true);

    try {
      // Convert columnConfigs {col: {algorithm, casing, consistency}}
      // into the backend's expected column_rules shape.
      const columnRules = {};
      Object.entries(columnConfigs).forEach(([col, config]) => {
        columnRules[col] = {
          algorithm: config.algorithm,
          casing: config.casing || "ORIGINAL",
          consistency: Boolean(config.consistency),
        };
      });

      const response = await anonymizeFileData(
        workspaceId,
        fileGroupId,
        fileId,
        columnRules,
        rowLimit,
        session.accessToken
      );

      setAnonymizedColumns(response.columns || []);
      setAnonymizedRows(response.rows || []);
      setShowAnonymized(true);
    } catch (err) {
      setAnonymizeError(err.message || "Anonymization failed.");
    } finally {
      setIsAnonymizing(false);
    }
  }

  function buildColumnRulesPayload() {
    const columnRules = {};
    Object.entries(columnConfigs).forEach(([col, config]) => {
      columnRules[col] = {
        algorithm: config.algorithm,
        casing: config.casing || "ORIGINAL",
        consistency: Boolean(config.consistency),
      };
    });
    return columnRules;
  }

  async function handleExportData() {
    setExportError("");
    setIsExporting(true);

    const sourceType = (workspace?.source_type || "").toUpperCase();
    const isNoCredentialSource = sourceType === "LOCAL_FILE" || sourceType === "URL";

    try {
      if (isNoCredentialSource) {
        // Backend returns a CSV file stream — the browser saves
        // it directly to the user's Downloads folder.
        const result = await exportFileDownload(
          workspaceId,
          fileGroupId,
          fileId,
          buildColumnRulesPayload(),
          session.accessToken
        );
        setExportResult({
          location: `Downloads/${result.filename}`,
          rowsWritten: null,
        });
      } else {
        const result = await exportFileData(
          workspaceId,
          fileGroupId,
          fileId,
          buildColumnRulesPayload(),
          session.accessToken
        );
        setExportResult({
          location: result.export_location,
          rowsWritten: result.rows_written,
        });
      }

      setShowExportSuccess(true);
    } catch (err) {
      setExportError(err.message || "Export failed.");
    } finally {
      setIsExporting(false);
    }
  }

  const configuredColumns = Object.keys(columnConfigs);
  const hasConfig = configuredColumns.length > 0;

  const displayedColumns = showAnonymized && anonymizedColumns ? anonymizedColumns : columns;
  const displayedRows = showAnonymized && anonymizedRows ? anonymizedRows : rows;

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden", background: "#f8fafc" }}>
      <TitleBanner
        subtitle={
          workspace && fileGroup && fileInfo ? (
            <>
              {workspace.name} / {fileGroup.name} / {fileInfo.display_name}
              <br />
              <span style={{ fontSize: "11px", color: "#9ca3af" }}>
                Destination: {workspace.destination_path}
              </span>
            </>
          ) : (
            ""
          )
        }
        centerContent={
          hasConfig && (
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <button
                type="button"
                onClick={handleRunAnonymization}
                disabled={isAnonymizing}
                style={{
                  height: "40px",
                  padding: "0 20px",
                  background: isAnonymizing ? "#9ca3af" : "#111827",
                  color: "#fff",
                  border: "none",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: "600",
                  cursor: isAnonymizing ? "not-allowed" : "pointer",
                }}
              >
                {isAnonymizing ? "Anonymizing..." : "Run Anonymization"}
              </button>

              {anonymizedRows !== null && (
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                    userSelect: "none",
                  }}
                >
                  Preview
                  <span
                    onClick={() => setShowAnonymized((current) => !current)}
                    style={{
                      position: "relative",
                      display: "inline-block",
                      width: "44px",
                      height: "24px",
                      borderRadius: "999px",
                      background: showAnonymized ? "#111827" : "#d1d5db",
                      transition: "background 0.15s ease",
                      cursor: "pointer",
                    }}
                  >
                    <span
                      style={{
                        position: "absolute",
                        top: "3px",
                        left: showAnonymized ? "23px" : "3px",
                        width: "18px",
                        height: "18px",
                        borderRadius: "50%",
                        background: "#ffffff",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                        transition: "left 0.15s ease",
                      }}
                    />
                  </span>
                </label>
              )}
            </div>
          )
        }
        rightContent={
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", alignItems: "flex-end" }}>
            <div style={{ display: "flex", gap: "12px" }}>
              <button
                type="button"
                onClick={() => navigate(`/workspaces/${workspaceId}/file-groups/${fileGroupId}`)}
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
            </div>

            <select
              value={rowLimit}
              onChange={(e) => setRowLimit(Number(e.target.value))}
              style={{
                height: "36px",
                padding: "0 12px",
                borderRadius: "8px",
                border: "1px solid #d1d5db",
                fontSize: "14px",
              }}
            >
              {ROW_COUNT_OPTIONS.map((count) => (
                <option key={count} value={count}>
                  Preview {count} rows
                </option>
              ))}
            </select>
          </div>
        }
      />

      {/* Fixed-height row below the banner. This row itself never
          scrolls — its two children each scroll independently. */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {hasConfig && (
          <div
            style={{
              width: "280px",
              flexShrink: 0,
              background: "#ffffff",
              borderRight: "1px solid #e5e7eb",
              padding: "24px",
              overflowY: "auto",
              height: "100%",
              boxSizing: "border-box",
            }}
          >
            <h3 style={{ marginTop: 0, fontSize: "16px" }}>Rule Registry</h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {configuredColumns.map((col) => {
                const config = columnConfigs[col];
                const algoLabel =
                  ALGORITHM_OPTIONS.find((a) => a.value === config.algorithm)?.label ||
                  config.algorithm;

                return (
                  <div
                    key={col}
                    style={{
                      padding: "12px",
                      border: "1px solid #e5e7eb",
                      borderRadius: "10px",
                      fontSize: "13px",
                    }}
                  >
                    <div style={{ fontWeight: 700, marginBottom: "4px" }}>🛡️ {col}</div>
                    <div style={{ color: "#6b7280" }}>Algorithm: {algoLabel}</div>
                    {TEXT_ALGORITHMS.has(config.algorithm) && (
                      <div style={{ color: "#6b7280" }}>Casing: {config.casing}</div>
                    )}
                    <div style={{ color: "#6b7280" }}>
                      Consistency: {config.consistency ? "On" : "Off"}
                    </div>
                  </div>
                );
              })}
            </div>

            <button
              type="button"
              onClick={handleResetConfig}
              style={{
                marginTop: "24px",
                width: "100%",
                height: "40px",
                fontSize: "14px",
                fontWeight: 600,
                color: "#b91c1c",
                background: "#ffffff",
                border: "1px solid #fca5a5",
                borderRadius: "8px",
                cursor: "pointer",
              }}
            >
              Reset Config
            </button>

            {anonymizedRows !== null && (
              <button
                type="button"
                onClick={handleExportData}
                disabled={isExporting}
                style={{
                  marginTop: "12px",
                  width: "100%",
                  height: "44px",
                  fontSize: "14px",
                  fontWeight: 700,
                  color: "#ffffff",
                  background: isExporting ? "#9ca3af" : "#111827",
                  border: "none",
                  borderRadius: "8px",
                  cursor: isExporting ? "not-allowed" : "pointer",
                }}
              >
                {isExporting ? "Exporting..." : "Export Data"}
              </button>
            )}

            {exportError && (
              <div className="error-box" style={{ marginTop: "12px" }}>
                {exportError}
              </div>
            )}
          </div>
        )}

        <div
          style={{
            flex: 1,
            minWidth: 0,
            height: "100%",
            overflowY: "auto",
            padding: "16px 32px 32px",
            boxSizing: "border-box",
          }}
        >
          {errorMessage && <div className="error-box">{errorMessage}</div>}
          {anonymizeError && <div className="error-box">{anonymizeError}</div>}

          {isLoading ? (
            <div className="loading-state">Loading preview...</div>
          ) : displayedColumns.length === 0 ? (
            <p>No data available to preview.</p>
          ) : (
            <div
              style={{
                overflowX: "auto",
                background: "#fff",
                borderRadius: "12px",
                border: "1px solid #e5e7eb",
                position: "relative",
              }}
            >
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13.5px" }}>
                <thead>
                  <tr>
                    {displayedColumns.map((col) => {
                      const isConfigured = Boolean(columnConfigs[col]);
                      return (
                        <th
                          key={col}
                          onClick={() => handleOpenColumnConfig(col)}
                          style={{
                            textAlign: "left",
                            padding: "9px 14px",
                            borderBottom: "2px solid #e5e7eb",
                            background: "#f9fafb",
                            color: "#111827",
                            whiteSpace: "nowrap",
                            cursor: "pointer",
                            userSelect: "none",
                            position: "relative",
                          }}
                        >
                          {col}
                          {isConfigured && (
                            <span style={{ marginLeft: "8px" }} title="Anonymization configured">
                              🛡️
                            </span>
                          )}{" "}
                          <span style={{ fontSize: "11px", opacity: 0.7 }}>▾</span>

                          {activeConfigColumn === col && (
                            <div
                              onClick={(e) => e.stopPropagation()}
                              style={{
                                position: "absolute",
                                top: "100%",
                                left: 0,
                                marginTop: "4px",
                                background: "#ffffff",
                                color: "#111827",
                                border: "1px solid #d1d5db",
                                borderRadius: "10px",
                                boxShadow: "0 12px 24px rgba(17,24,39,0.15)",
                                padding: "16px",
                                width: "240px",
                                zIndex: 50,
                                fontWeight: 400,
                                whiteSpace: "normal",
                              }}
                            >
                              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
                                Algorithm
                              </label>
                              <select
                                value={draftAlgorithm}
                                onChange={(e) => setDraftAlgorithm(e.target.value)}
                                style={{ width: "100%", height: "36px", marginBottom: "12px", borderRadius: "6px", border: "1px solid #d1d5db" }}
                              >
                                {ALGORITHM_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                  </option>
                                ))}
                              </select>

                              {TEXT_ALGORITHMS.has(draftAlgorithm) && (
                                <>
                                  <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
                                    Casing
                                  </label>
                                  <select
                                    value={draftCasing}
                                    onChange={(e) => setDraftCasing(e.target.value)}
                                    style={{ width: "100%", height: "36px", marginBottom: "12px", borderRadius: "6px", border: "1px solid #d1d5db" }}
                                  >
                                    {CASING_OPTIONS.map((opt) => (
                                      <option key={opt.value} value={opt.value}>
                                        {opt.label}
                                      </option>
                                    ))}
                                  </select>
                                </>
                              )}

                              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", marginBottom: "14px" }}>
                                <input
                                  type="checkbox"
                                  checked={draftConsistency}
                                  onChange={(e) => setDraftConsistency(e.target.checked)}
                                />
                                Consistency
                              </label>

                              <div style={{ display: "flex", gap: "8px" }}>
                                <button
                                  type="button"
                                  onClick={handleSaveColumnConfig}
                                  style={{
                                    flex: 1,
                                    height: "32px",
                                    fontSize: "13px",
                                    fontWeight: 600,
                                    color: "#fff",
                                    background: "#111827",
                                    border: "none",
                                    borderRadius: "6px",
                                    cursor: "pointer",
                                  }}
                                >
                                  Apply
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setActiveConfigColumn(null)}
                                  style={{
                                    flex: 1,
                                    height: "32px",
                                    fontSize: "13px",
                                    fontWeight: 600,
                                    color: "#374151",
                                    background: "#fff",
                                    border: "1px solid #d1d5db",
                                    borderRadius: "6px",
                                    cursor: "pointer",
                                  }}
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          )}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {displayedRows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td
                          key={cellIndex}
                          style={{
                            padding: "7px 14px",
                            borderBottom: "1px solid #f1f5f9",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {cell === null || cell === undefined ? "" : String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showExportSuccess && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(17, 24, 39, 0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 3000,
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "420px",
              background: "#ffffff",
              borderRadius: "20px",
              padding: "40px",
              textAlign: "center",
              boxShadow: "0 20px 48px rgba(17, 24, 39, 0.2)",
            }}
          >
            <div style={{ fontSize: "40px", marginBottom: "12px" }}>✅</div>
            <h3 style={{ margin: "0 0 8px 0" }}>Export Successful</h3>
            <p style={{ color: "#6b7280", marginBottom: "8px" }}>
              The anonymized data has been exported successfully.
            </p>
            {exportResult?.location && (
              <p style={{ color: "#374151", fontSize: "13px", marginBottom: "4px", wordBreak: "break-all" }}>
                <strong>Location:</strong> {exportResult.location}
              </p>
            )}
            {exportResult?.rowsWritten !== null && exportResult?.rowsWritten !== undefined && (
              <p style={{ color: "#374151", fontSize: "13px", marginBottom: "8px" }}>
                <strong>Rows written:</strong> {exportResult.rowsWritten}
              </p>
            )}
            {exportResult?.rowsWritten === 0 && (
              <p style={{ color: "#b91c1c", fontSize: "13px", marginBottom: "24px", fontWeight: 600 }}>
                ⚠️ 0 rows were written — the destination file/table exists
                but is empty. This means the source data read back as
                empty during export.
              </p>
            )}
            <div style={{ display: "flex", gap: "12px" }}>
              <button
                type="button"
                onClick={() => setShowExportSuccess(false)}
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
                Stay Here
              </button>
              <button
                type="button"
                onClick={() => navigate("/dashboard")}
                style={{
                  flex: 1,
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
                Go to Main Screen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}