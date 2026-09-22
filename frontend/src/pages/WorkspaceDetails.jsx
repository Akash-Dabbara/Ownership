import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { 
  getFileGroups, 
  getWorkspace, 
  createFileGroup,
  updateFileGroup,
} from "../api/api";
import { getAuthSession } from "../api/auth";
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

const textareaStyle = {
  width: "100%",
  minHeight: "120px",
  padding: "14px 16px",
  fontSize: "16px",
  border: "1px solid #d1d5db",
  borderRadius: "10px",
  boxSizing: "border-box",
  fontFamily: "inherit",
  resize: "vertical",
};

function FormModal({ title, name, setName, description, setDescription, onSubmit, onCancel, submitLabel }) {
  return (
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
          maxWidth: "480px",
          background: "#ffffff",
          borderRadius: "20px",
          border: "1px solid #e5e7eb",
          boxShadow: "0 20px 48px rgba(17, 24, 39, 0.2)",
          padding: "48px 40px",
        }}
      >
        <h3 style={{ margin: "0 0 28px 0", fontSize: "22px", fontWeight: 700, color: "#111827" }}>
          {title}
        </h3>

        <form onSubmit={onSubmit}>
          <div style={{ marginBottom: "24px" }}>
            <label htmlFor="fileGroupName" style={labelStyle}>
              File Group Name
            </label>
            <input
              id="fileGroupName"
              type="text"
              placeholder="Enter file group name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              style={inputStyle}
            />
          </div>

          <div style={{ marginBottom: "28px" }}>
            <label htmlFor="fileGroupDesc" style={labelStyle}>
              Description
            </label>
            <textarea
              id="fileGroupDesc"
              placeholder="Enter description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={textareaStyle}
            />
          </div>

          <div style={{ display: "flex", gap: "12px" }}>
            <button
              type="submit"
              style={{
                flex: 1,
                height: "52px",
                fontSize: "16px",
                fontWeight: 700,
                color: "#ffffff",
                background: "#111827",
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
              }}
            >
              {submitLabel}
            </button>
            <button
              type="button"
              onClick={onCancel}
              style={{
                flex: 1,
                height: "52px",
                fontSize: "16px",
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
        </form>
      </div>
    </div>
  );
}

export default function WorkspaceDetails() {
  const navigate = useNavigate();
  const { workspaceId } = useParams();
  const session = getAuthSession();

  const [workspace, setWorkspace] = useState(null);
  const [fileGroups, setFileGroups] = useState([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingFileGroup, setEditingFileGroup] = useState(null);
  const [groupName, setGroupName] = useState("");
  const [groupDesc, setGroupDesc] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [hoveredCardId, setHoveredCardId] = useState(null);

  const isAdminOrOwner = session?.role === "OWNER" || session?.role === "ADMIN";

  useEffect(() => {
    loadData();
  }, [workspaceId]);

  async function loadData() {
    try {
      setIsLoading(true);
      const [wsRes, fgRes] = await Promise.all([
        getWorkspace(workspaceId, session.accessToken),
        getFileGroups(workspaceId, session.accessToken),
      ]);
      setWorkspace(wsRes.workspace || wsRes);
      setFileGroups(fgRes.file_groups || []);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load workspace content.");
    } finally {
      setIsLoading(false);
    }
  }

  function openCreateModal() {
    setGroupName("");
    setGroupDesc("");
    setShowCreateModal(true);
  }

  function openEditModal(fileGroup) {
    setEditingFileGroup(fileGroup);
    setGroupName(fileGroup.name);
    setGroupDesc(fileGroup.description || "");
  }

  async function handleCreateGroup(e) {
    e.preventDefault();
    if (!groupName.trim()) return;

    try {
      const response = await createFileGroup(
        workspaceId,
        {
          name: groupName.trim(),
          description: groupDesc.trim() || null,
        },
        session.accessToken
      );

      setShowCreateModal(false);

      const createdFileGroup = response.file_group || response;
      const newFileGroupId =
        createdFileGroup.file_group_id || createdFileGroup.id;

      if (newFileGroupId) {
        navigate(
          `/workspaces/${workspaceId}/file-groups/${newFileGroupId}/import`
        );
      } else {
        loadData();
      }
    } catch (err) {
      setErrorMessage(err.message || "Failed to create file group.");
    }
  }

  async function handleUpdateGroup(e) {
    e.preventDefault();
    if (!groupName.trim() || !editingFileGroup) return;

    try {
      await updateFileGroup(
        workspaceId,
        editingFileGroup.file_group_id,
        {
          name: groupName.trim(),
          description: groupDesc.trim() || null,
        },
        session.accessToken
      );

      setEditingFileGroup(null);
      loadData();
    } catch (err) {
      setErrorMessage(err.message || "Failed to update file group.");
    }
  }

  function handleOpenFileGroup(fileGroup) {
    navigate(`/workspaces/${workspaceId}/file-groups/${fileGroup.file_group_id}`);
  }

  function handleImportShortcut(e, fileGroup) {
    e.stopPropagation();
    navigate(`/workspaces/${workspaceId}/file-groups/${fileGroup.file_group_id}/import`);
  }

  function handleEditShortcut(e, fileGroup) {
    e.stopPropagation();
    openEditModal(fileGroup);
  }

  if (isLoading) return <div className="loading-state">Loading workspace details...</div>;
  if (errorMessage) return <div className="error-state">{errorMessage}</div>;

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <TitleBanner
        subtitle={
          workspace ? (
            <>
              {workspace.name}
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
          isAdminOrOwner && (
            <button
              type="button"
              onClick={openCreateModal}
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
              + Create File Group
            </button>
          )
        }
        rightContent={
          <>
            <button
              type="button"
              onClick={() => navigate("/workspaces/new")}
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

      {showCreateModal && (
        <FormModal
          title="Create File Group"
          name={groupName}
          setName={setGroupName}
          description={groupDesc}
          setDescription={setGroupDesc}
          onSubmit={handleCreateGroup}
          onCancel={() => setShowCreateModal(false)}
          submitLabel="Save File Group"
        />
      )}

      {editingFileGroup && (
        <FormModal
          title="Edit File Group"
          name={groupName}
          setName={setGroupName}
          description={groupDesc}
          setDescription={setGroupDesc}
          onSubmit={handleUpdateGroup}
          onCancel={() => setEditingFileGroup(null)}
          submitLabel="Save Changes"
        />
      )}

      <div style={{ padding: "32px", maxWidth: "1200px", margin: "0 auto" }}>
        {fileGroups.length === 0 ? (
          <p>No file groups available in this workspace.</p>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
              gap: "20px",
            }}
          >
            {fileGroups.map((fg) => {
              const isHovered = hoveredCardId === fg.file_group_id;
              return (
                <div
                  key={fg.file_group_id}
                  onClick={() => handleOpenFileGroup(fg)}
                  onMouseEnter={() => setHoveredCardId(fg.file_group_id)}
                  onMouseLeave={() => setHoveredCardId(null)}
                  style={{
                    background: "#ffffff",
                    border: isHovered ? "2px solid #111827" : "1px solid #e5e7eb",
                    borderRadius: "16px",
                    padding: "24px",
                    cursor: "pointer",
                    transform: isHovered ? "translateY(-4px)" : "translateY(0)",
                    boxShadow: isHovered
                      ? "0 12px 24px rgba(17, 24, 39, 0.12)"
                      : "0 1px 3px rgba(0, 0, 0, 0.06)",
                    transition: "all 0.15s ease",
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                    <h4 style={{ margin: 0, fontSize: "18px", color: "#111827" }}>{fg.name}</h4>
                    <span style={{ fontSize: "24px" }}>📁</span>
                  </div>

                  <p style={{ margin: 0, color: "#6b7280", fontSize: "14px", flex: 1 }}>
                    {fg.description || "No description provided."}
                  </p>

                  {isAdminOrOwner && (
                    <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                      <button
                        type="button"
                        onClick={(e) => handleImportShortcut(e, fg)}
                        style={{
                          flex: 1,
                          height: "36px",
                          fontSize: "13px",
                          fontWeight: 600,
                          color: "#2563eb",
                          background: "#ffffff",
                          border: "1px solid #2563eb",
                          borderRadius: "8px",
                          cursor: "pointer",
                        }}
                      >
                        + Import Data
                      </button>
                      <button
                        type="button"
                        onClick={(e) => handleEditShortcut(e, fg)}
                        style={{
                          flex: 1,
                          height: "36px",
                          fontSize: "13px",
                          fontWeight: 600,
                          color: "#374151",
                          background: "#ffffff",
                          border: "1px solid #d1d5db",
                          borderRadius: "8px",
                          cursor: "pointer",
                        }}
                      >
                        ✎ Edit
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}