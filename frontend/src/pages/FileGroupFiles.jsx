import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  getWorkspace,
  getFileGroup,
  getFileGroupFiles,
} from "../api/api";
import { getAuthSession } from "../api/auth";
import TitleBanner from "../components/TitleBanner";

export default function FileGroupFiles() {
  const navigate = useNavigate();
  const { workspaceId, fileGroupId } = useParams();
  const session = getAuthSession();

  const [workspace, setWorkspace] = useState(null);
  const [fileGroup, setFileGroup] = useState(null);
  const [files, setFiles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const isAdminOrOwner = session?.role === "OWNER" || session?.role === "ADMIN";

  useEffect(() => {
    loadData();
  }, [workspaceId, fileGroupId]);

  async function loadData() {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const [wsRes, fgRes, filesRes] = await Promise.all([
        getWorkspace(workspaceId, session.accessToken),
        getFileGroup(workspaceId, fileGroupId, session.accessToken),
        getFileGroupFiles(workspaceId, fileGroupId, session.accessToken),
      ]);

      setWorkspace(wsRes.workspace || wsRes);
      setFileGroup(fgRes.file_group || fgRes);
      setFiles(filesRes.files || []);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load this file group.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleOpenFile(file) {
    navigate(
      `/workspaces/${workspaceId}/file-groups/${fileGroupId}/files/${file.file_id}/preview`
    );
  }

  if (isLoading) return <div className="loading-state">Loading file group...</div>;
  if (errorMessage) return <div className="error-state">{errorMessage}</div>;

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <TitleBanner
        subtitle={`${workspace?.name || ""} / ${fileGroup?.name || ""}`}
        centerContent={
          isAdminOrOwner && (
            <button
              type="button"
              onClick={() =>
                navigate(`/workspaces/${workspaceId}/file-groups/${fileGroupId}/import`)
              }
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
              + Import Data
            </button>
          )
        }
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

      <div style={{ padding: "32px", maxWidth: "1000px", margin: "0 auto" }}>
        <h2 style={{ marginTop: 0 }}>Imported Data</h2>

        {files.length === 0 ? (
          <p>
            No data has been imported into this file group yet.
            {isAdminOrOwner && ' Click "+ Import Data" above to bring in a table or file.'}
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {files.map((file) => (
              <div
                key={file.file_id}
                onClick={() => handleOpenFile(file)}
                style={{
                  padding: "20px",
                  background: "#ffffff",
                  border: "1px solid #e5e7eb",
                  borderRadius: "12px",
                  cursor: "pointer",
                }}
              >
                <h4 style={{ margin: "0 0 6px 0" }}>{file.display_name}</h4>
                <p style={{ margin: 0, color: "#6b7280", fontSize: "14px" }}>
                  {file.table_name
                    ? `${file.database_name} / ${file.schema_name} / ${file.table_name}`
                    : file.source_path}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}