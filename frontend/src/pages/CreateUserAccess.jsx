import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createUserWithAccess,
  getWorkspaces,
  getFileGroups,
  getFileGroupFiles,
} from "../api/api";
import { getAuthSession } from "../api/auth";
import TitleBanner from "../components/TitleBanner";

const labelStyle = {
  display: "block",
  fontSize: "13px",
  fontWeight: 600,
  marginBottom: "6px",
  color: "#374151",
};

const selectStyle = {
  width: "100%",
  height: "48px",
  borderRadius: "8px",
  border: "1px solid #d1d5db",
  padding: "0 12px",
  fontSize: "14px",
  boxSizing: "border-box",
};

export default function CreateUserAccess() {
  const navigate = useNavigate();
  const session = getAuthSession();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [workspaces, setWorkspaces] = useState([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [fileGroups, setFileGroups] = useState([]);
  const [selectedFileGroupId, setSelectedFileGroupId] = useState("");
  const [files, setFiles] = useState([]);
  const [selectedFileId, setSelectedFileId] = useState("");

  const [hasLoadedWorkspaces, setHasLoadedWorkspaces] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  async function ensureWorkspacesLoaded() {
    if (hasLoadedWorkspaces) return;
    try {
      const response = await getWorkspaces(session.accessToken);
      setWorkspaces(response.workspaces || []);
      setHasLoadedWorkspaces(true);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load workspaces.");
    }
  }

  async function handleWorkspaceSelect(workspaceId) {
    setSelectedWorkspaceId(workspaceId);
    setSelectedFileGroupId("");
    setSelectedFileId("");
    setFiles([]);
    setErrorMessage("");

    if (!workspaceId) {
      setFileGroups([]);
      return;
    }

    try {
      const response = await getFileGroups(workspaceId, session.accessToken);
      setFileGroups(response.file_groups || []);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load file groups.");
    }
  }

  async function handleFileGroupSelect(fileGroupId) {
    setSelectedFileGroupId(fileGroupId);
    setSelectedFileId("");
    setErrorMessage("");

    if (!fileGroupId) {
      setFiles([]);
      return;
    }

    try {
      const response = await getFileGroupFiles(
        selectedWorkspaceId,
        fileGroupId,
        session.accessToken
      );
      setFiles(response.files || []);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load files.");
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    if (!email.trim() || !password || !selectedWorkspaceId || !selectedFileGroupId) {
      setErrorMessage("Please fill in the email, password, and select a workspace and file group.");
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
      setIsCreating(true);
      const response = await createUserWithAccess(
        email.trim(),
        password,
        selectedWorkspaceId,
        selectedFileGroupId,
        selectedFileId || null,
        session.accessToken
      );
      setSuccessMessage(
        response.email_sent
          ? `User ${response.email} created and access granted. Credentials were emailed.`
          : `User ${response.email} created and access granted, but the email could not be sent. Give them the email and password directly.`
      );
      setEmail("");
      setPassword("");
      setConfirmPassword("");
      setSelectedWorkspaceId("");
      setSelectedFileGroupId("");
      setSelectedFileId("");
      setFileGroups([]);
      setFiles([]);
    } catch (err) {
      setErrorMessage(err.message || "Failed to create user.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <TitleBanner
        subtitle="Create User"
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
            Home
          </button>
        }
      />

      <div style={{ padding: "32px", maxWidth: "560px", margin: "0 auto" }}>
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            borderRadius: "16px",
            padding: "32px",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Create User & Grant Access</h2>
          <p style={{ color: "#6b7280", fontSize: "14px", marginBottom: "24px" }}>
            Creates a new User account with the credentials you set here, and
            grants them access to the workspace/file group (or one specific
            file) you choose — all in one step. The user can log in with
            exactly the email and password you provide below.
          </p>

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: "18px" }}>
              <label style={labelStyle}>User's Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                style={selectStyle}
                required
              />
            </div>

            <div style={{ marginBottom: "18px" }}>
              <label style={labelStyle}>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                style={selectStyle}
                required
              />
            </div>

            <div style={{ marginBottom: "18px" }}>
              <label style={labelStyle}>Confirm Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                style={selectStyle}
                required
              />
            </div>

            <div style={{ marginBottom: "18px" }}>
              <label style={labelStyle}>Workspace</label>
              <select
                value={selectedWorkspaceId}
                onFocus={ensureWorkspacesLoaded}
                onChange={(e) => handleWorkspaceSelect(e.target.value)}
                style={selectStyle}
              >
                <option value="">Select a workspace</option>
                {workspaces.map((ws) => (
                  <option key={ws.workspace_id} value={ws.workspace_id}>
                    {ws.name}
                  </option>
                ))}
              </select>
            </div>

            {selectedWorkspaceId && (
              <div style={{ marginBottom: "18px" }}>
                <label style={labelStyle}>File Group</label>
                <select
                  value={selectedFileGroupId}
                  onChange={(e) => handleFileGroupSelect(e.target.value)}
                  style={selectStyle}
                >
                  <option value="">Select a file group</option>
                  {fileGroups.map((fg) => (
                    <option key={fg.file_group_id} value={fg.file_group_id}>
                      {fg.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {selectedFileGroupId && (
              <div style={{ marginBottom: "24px" }}>
                <label style={labelStyle}>
                  File (optional — leave blank for whole File Group)
                </label>
                <select
                  value={selectedFileId}
                  onChange={(e) => setSelectedFileId(e.target.value)}
                  style={selectStyle}
                >
                  <option value="">Whole File Group</option>
                  {files.map((f) => (
                    <option key={f.file_id} value={f.file_id}>
                      {f.display_name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {errorMessage && <div className="error-box" style={{ marginBottom: "16px" }}>{errorMessage}</div>}
            {successMessage && <div className="success-box" style={{ marginBottom: "16px" }}>{successMessage}</div>}

            <button
              type="submit"
              disabled={isCreating}
              style={{
                width: "100%",
                height: "50px",
                fontSize: "15px",
                fontWeight: 700,
                color: "#ffffff",
                background: isCreating ? "#9ca3af" : "#111827",
                border: "none",
                borderRadius: "10px",
                cursor: isCreating ? "not-allowed" : "pointer",
              }}
            >
              {isCreating ? "Creating..." : "Create User & Grant Access"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}