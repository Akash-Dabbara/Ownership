import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  deleteWorkspace,
  getWorkspaces,
  updateWorkspace,
} from "../api/api";

import {
  getAccessToken,
  getAuthSession,
} from "../api/auth";


export default function Workspaces() {
  const session = getAuthSession();
  const token = getAccessToken();
  const navigate = useNavigate();


  // ============================================================
  // STATE
  // ============================================================

  const [workspaces, setWorkspaces] = useState([]);

  const [searchQuery, setSearchQuery] =
    useState("");

  const [isLoading, setIsLoading] =
    useState(true);

  const [isSubmitting, setIsSubmitting] =
    useState(false);

  const [errorMessage, setErrorMessage] =
    useState("");

  const [successMessage, setSuccessMessage] =
    useState("");


  // ============================================================
  // EDIT STATE
  // ============================================================

  const [
    editingWorkspaceId,
    setEditingWorkspaceId,
  ] = useState(null);

  const [editingName, setEditingName] =
    useState("");

  const [
    editingDescription,
    setEditingDescription,
  ] = useState("");


  // ============================================================
  // NORMALIZE WORKSPACE
  // ============================================================

  function normalizeWorkspace(workspace) {
    if (!workspace) {
      return null;
    }

    return {
      ...workspace,

      workspace_id:
        workspace.workspace_id ||
        workspace.id ||
        null,
    };
  }


  // ============================================================
  // LOAD WORKSPACES
  // ============================================================

  async function loadWorkspaces() {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const response =
        await getWorkspaces(token);

      const rawWorkspaces =
        response?.workspaces || [];

      const normalizedWorkspaces =
        rawWorkspaces
          .map(normalizeWorkspace)
          .filter(
            (workspace) =>
              workspace &&
              workspace.workspace_id,
          );

      setWorkspaces(
        normalizedWorkspaces,
      );

    } catch (error) {
      setErrorMessage(
        error.message ||
          "Unable to load workspaces.",
      );

    } finally {
      setIsLoading(false);
    }
  }


  useEffect(() => {
    loadWorkspaces();
  }, []);


  // ============================================================
  // START EDIT
  // ============================================================

  function handleStartEdit(workspace) {
    const workspaceId =
      workspace.workspace_id;

    if (!workspaceId) {
      setErrorMessage(
        "Invalid workspace ID provided for editing.",
      );

      return;
    }

    setEditingWorkspaceId(
      workspaceId,
    );

    setEditingName(
      workspace.name || "",
    );

    setEditingDescription(
      workspace.description || "",
    );

    setErrorMessage("");
    setSuccessMessage("");
  }


  // ============================================================
  // CANCEL EDIT
  // ============================================================

  function handleCancelEdit() {
    setEditingWorkspaceId(null);
    setEditingName("");
    setEditingDescription("");
  }


  // ============================================================
  // UPDATE WORKSPACE
  // ============================================================

  async function handleUpdateWorkspace(
    event,
    workspaceId,
  ) {
    event.preventDefault();

    setErrorMessage("");
    setSuccessMessage("");


    if (!workspaceId) {
      setErrorMessage(
        "Invalid workspace ID provided for update.",
      );

      return;
    }


    const normalizedName =
      editingName.trim();


    if (!normalizedName) {
      setErrorMessage(
        "Workspace name cannot be empty.",
      );

      return;
    }


    try {
      setIsSubmitting(true);


      const response =
        await updateWorkspace(
          workspaceId,
          {
            name: normalizedName,
            description:
              editingDescription.trim() ||
              null,
          },
          token,
        );


      const updatedWorkspace =
        response?.workspace
          ? normalizeWorkspace(
              response.workspace,
            )
          : null;


      if (
        updatedWorkspace &&
        updatedWorkspace.workspace_id
      ) {
        setWorkspaces(
          (currentWorkspaces) =>
            currentWorkspaces.map(
              (workspace) =>
                workspace.workspace_id ===
                updatedWorkspace.workspace_id
                  ? updatedWorkspace
                  : workspace,
            ),
        );

      } else {
        setWorkspaces(
          (currentWorkspaces) =>
            currentWorkspaces.map(
              (workspace) =>
                workspace.workspace_id ===
                workspaceId
                  ? {
                      ...workspace,
                      name: normalizedName,
                      description:
                        editingDescription.trim() ||
                        null,
                    }
                  : workspace,
            ),
        );
      }


      setSuccessMessage(
        response?.message ||
          "Workspace updated successfully.",
      );

      handleCancelEdit();

    } catch (error) {
      setErrorMessage(
        error.message ||
          "Unable to update workspace.",
      );

    } finally {
      setIsSubmitting(false);
    }
  }


  // ============================================================
  // DELETE WORKSPACE
  // ============================================================

  async function handleDeleteWorkspace(
    workspace,
  ) {
    const workspaceId =
      workspace?.workspace_id;


    if (!workspaceId) {
      setErrorMessage(
        "Invalid workspace ID provided for deletion.",
      );

      return;
    }


    const confirmed =
      window.confirm(
        `Are you sure you want to delete "${workspace.name}"?`,
      );


    if (!confirmed) {
      return;
    }


    try {
      setIsSubmitting(true);

      setErrorMessage("");
      setSuccessMessage("");


      const response =
        await deleteWorkspace(
          workspaceId,
          token,
        );


      // Remove immediately from UI after successful deletion.
      setWorkspaces(
        (currentWorkspaces) =>
          currentWorkspaces.filter(
            (currentWorkspace) =>
              currentWorkspace.workspace_id !==
              workspaceId,
          ),
      );


      // Close edit mode if the deleted workspace
      // happened to be the currently edited workspace.
      if (
        editingWorkspaceId ===
        workspaceId
      ) {
        handleCancelEdit();
      }


      setSuccessMessage(
        response?.message ||
          "Workspace deleted successfully.",
      );

    } catch (error) {
      setErrorMessage(
        error.message ||
          "Unable to delete workspace.",
      );

    } finally {
      setIsSubmitting(false);
    }
  }


  // ============================================================
  // ROLE / OWNERSHIP CHECKS
  // ============================================================

  const canManageWorkspaces =
    session?.role === "OWNER" ||
    session?.role === "ADMIN";

  // Owner can edit/delete any workspace. An Admin can only
  // edit/delete a workspace they themselves created — this
  // matches the same rule now enforced on the backend, so the
  // buttons here just reflect what the server will actually allow.
  function canEditWorkspace(workspace) {
    if (session?.role === "OWNER") {
      return true;
    }

    if (session?.role === "ADMIN") {
      return workspace.created_by === session?.userId;
    }

    return false;
  }


  // ============================================================
  // FILTER WORKSPACES
  // ============================================================

  const normalizedSearchQuery =
    searchQuery
      .trim()
      .toLowerCase();


  const filteredWorkspaces =
    workspaces.filter(
      (workspace) =>
        (workspace.name || "")
          .toLowerCase()
          .includes(
            normalizedSearchQuery,
          ),
    );


  // ============================================================
  // UI
  // ============================================================

  return (
    <div className="workspace-page">

      {/* ========================================================
          ERROR MESSAGE
      ======================================================== */}

      {errorMessage && (
        <div
          className="workspace-error"
          style={{
            padding: "12px",
            background: "#fef2f2",
            color: "#b91c1c",
            borderRadius: "8px",
            marginBottom: "16px",
          }}
        >
          {errorMessage}
        </div>
      )}


      {/* ========================================================
          SUCCESS MESSAGE
      ======================================================== */}

      {successMessage && (
        <div
          className="workspace-success"
          style={{
            padding: "12px",
            background: "#f0fdf4",
            color: "#15803d",
            borderRadius: "8px",
            marginBottom: "16px",
          }}
        >
          {successMessage}
        </div>
      )}


      {/* ========================================================
          HEADER
      ======================================================== */}

      <div
        style={{
          display: "flex",
          justifyContent:
            "space-between",
          alignItems: "center",
          marginBottom: "24px",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >

        <h2
          style={{
            margin: 0,
            fontSize: "22px",
            color: "#111827",
          }}
        >
          MY WORKSPACES
        </h2>


        <input
          type="text"
          placeholder="🔍 Search workspaces by name..."
          value={searchQuery}
          onChange={(event) =>
            setSearchQuery(
              event.target.value,
            )
          }
          style={{
            padding: "10px 16px",
            width: "300px",
            border:
              "1px solid #d1d5db",
            borderRadius: "8px",
            outline: "none",
            background: "#fff",
          }}
        />

      </div>


      {/* ========================================================
          WORKSPACE LIST
      ======================================================== */}

      <div className="workspace-list">

        {isLoading ? (

          <div
            className="workspace-empty"
            style={{
              textAlign: "center",
              padding: "40px",
              color: "#6b7280",
            }}
          >
            Loading workspaces...
          </div>

        ) : filteredWorkspaces.length === 0 ? (

          <div
            className="workspace-empty"
            style={{
              textAlign: "center",
              padding: "40px",
              background: "#fff",
              borderRadius: "12px",
              border:
                "1px solid #e5e7eb",
              color: "#6b7280",
            }}
          >

            <h2>
              No Workspaces Yet
            </h2>

            <p>
              Create your first workspace
              to get started.
            </p>

          </div>

        ) : (

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fill, minmax(280px, 1fr))",
              gap: "20px",
            }}
          >

            {filteredWorkspaces.map(
              (workspace) => {

                const workspaceId =
                  workspace.workspace_id;

                const isEditing =
                  editingWorkspaceId ===
                  workspaceId;

                const canEditThisWorkspace =
                  canEditWorkspace(workspace);


                return (

                  <div
                    key={workspaceId}
                    className="workspace-card"
                    onClick={() => {
                      if (!isEditing) {
                        navigate(
                          `/workspaces/${workspaceId}`,
                        );
                      }
                    }}
                    style={{
                      background: "#fff",
                      padding: "24px",
                      borderRadius: "12px",
                      border:
                        "1px solid #e5e7eb",
                      cursor:
                        isEditing
                          ? "default"
                          : "pointer",
                      display: "flex",
                      flexDirection:
                        "column",
                      justifyContent:
                        "space-between",
                      minHeight: "160px",
                      boxShadow:
                        "0 1px 3px rgba(0,0,0,0.05)",
                    }}
                  >

                    {/* EDIT MODE */}

                    {isEditing ? (

                      <form
                        onSubmit={(event) =>
                          handleUpdateWorkspace(
                            event,
                            workspaceId,
                          )
                        }
                      >

                        <div
                          className="form-field"
                          style={{
                            marginBottom:
                              "12px",
                          }}
                        >

                          <label
                            style={{
                              display:
                                "block",
                              marginBottom:
                                "4px",
                              fontSize:
                                "14px",
                              fontWeight:
                                "600",
                            }}
                          >
                            Workspace Name
                          </label>

                          <input
                            type="text"
                            value={
                              editingName
                            }
                            onChange={(
                              event,
                            ) =>
                              setEditingName(
                                event.target
                                  .value,
                              )
                            }
                            disabled={
                              isSubmitting
                            }
                            style={{
                              width: "100%",
                              padding: "8px",
                              border:
                                "1px solid #d1d5db",
                              borderRadius:
                                "6px",
                            }}
                          />

                        </div>


                        <div
                          className="form-field"
                          style={{
                            marginBottom:
                              "12px",
                          }}
                        >

                          <label
                            style={{
                              display:
                                "block",
                              marginBottom:
                                "4px",
                              fontSize:
                                "14px",
                              fontWeight:
                                "600",
                            }}
                          >
                            Description
                          </label>

                          <textarea
                            rows="2"
                            value={
                              editingDescription
                            }
                            onChange={(
                              event,
                            ) =>
                              setEditingDescription(
                                event.target
                                  .value,
                              )
                            }
                            disabled={
                              isSubmitting
                            }
                            style={{
                              width: "100%",
                              padding: "8px",
                              border:
                                "1px solid #d1d5db",
                              borderRadius:
                                "6px",
                            }}
                          />

                        </div>


                        <div
                          className="workspace-actions"
                          style={{
                            display: "flex",
                            gap: "8px",
                          }}
                        >

                          <button
                            type="submit"
                            disabled={
                              isSubmitting
                            }
                            style={{
                              padding:
                                "6px 12px",
                              background:
                                "#111827",
                              color: "#fff",
                              border: "none",
                              borderRadius:
                                "6px",
                              fontSize:
                                "13px",
                              cursor:
                                "pointer",
                            }}
                          >
                            {isSubmitting
                              ? "Saving..."
                              : "Save"}
                          </button>


                          <button
                            type="button"
                            onClick={
                              handleCancelEdit
                            }
                            disabled={
                              isSubmitting
                            }
                            style={{
                              padding:
                                "6px 12px",
                              background:
                                "#f3f4f6",
                              color:
                                "#374151",
                              border:
                                "1px solid #d1d5db",
                              borderRadius:
                                "6px",
                              fontSize:
                                "13px",
                              cursor:
                                "pointer",
                            }}
                          >
                            Cancel
                          </button>

                        </div>

                      </form>

                    ) : (

                      <>

                        {/* WORKSPACE INFORMATION */}

                        <div
                          className="workspace-card-content"
                        >

                          <h2
                            style={{
                              margin:
                                "0 0 8px 0",
                              fontSize:
                                "18px",
                              color:
                                "#111827",
                            }}
                          >
                            {workspace.name}
                          </h2>


                          {workspace.description && (

                            <p
                              style={{
                                margin: 0,
                                color:
                                  "#6b7280",
                                fontSize:
                                  "14px",
                                lineHeight:
                                  "1.4",
                              }}
                            >
                              {
                                workspace.description
                              }
                            </p>

                          )}


                          <div
                            className="workspace-meta"
                            style={{
                              marginTop:
                                "12px",
                              fontSize:
                                "12px",
                              color:
                                "#9ca3af",
                              display: "flex",
                              flexDirection: "column",
                              gap: "2px",
                            }}
                          >

                            <span>
                              Created by:{" "}
                              {workspace.created_by_email || "Unknown"}
                            </span>

                            <span>

                              Created:{" "}

                              {workspace.created_at
                                ? new Date(
                                    workspace.created_at,
                                  ).toLocaleString()
                                : "N/A"}

                            </span>

                          </div>

                        </div>


                        {/* WORKSPACE ACTIONS */}

                        {canManageWorkspaces && (

                          <div
                            className="workspace-actions"
                            onClick={(event) =>
                              event.stopPropagation()
                            }
                            style={{
                              display: "flex",
                              justifyContent:
                                "space-between",
                              alignItems:
                                "center",
                              marginTop:
                                "20px",
                              paddingTop:
                                "12px",
                              borderTop:
                                "1px solid #f3f4f6",
                            }}
                          >

                            <span
                              onClick={() =>
                                navigate(
                                  `/workspaces/${workspaceId}`,
                                )
                              }
                              style={{
                                fontSize:
                                  "13px",
                                fontWeight:
                                  "600",
                                color:
                                  "#2563eb",
                                cursor:
                                  "pointer",
                              }}
                            >
                              Open Workspace →
                            </span>


                            {canEditThisWorkspace && (
                              <div
                                style={{
                                  display:
                                    "flex",
                                  gap:
                                    "10px",
                                }}
                              >

                                <button
                                  type="button"
                                  onClick={() =>
                                    handleStartEdit(
                                      workspace,
                                    )
                                  }
                                  disabled={
                                    isSubmitting
                                  }
                                  style={{
                                    background:
                                      "none",
                                    border:
                                      "none",
                                    color:
                                      "#4b5563",
                                    fontSize:
                                      "13px",
                                    fontWeight:
                                      "600",
                                    cursor:
                                      "pointer",
                                  }}
                                >
                                  Edit
                                </button>


                                <button
                                  type="button"
                                  onClick={() =>
                                    handleDeleteWorkspace(
                                      workspace,
                                    )
                                  }
                                  disabled={
                                    isSubmitting
                                  }
                                  style={{
                                    background:
                                      "none",
                                    border:
                                      "none",
                                    color:
                                      "#dc2626",
                                    fontSize:
                                      "13px",
                                    fontWeight:
                                      "600",
                                    cursor:
                                      "pointer",
                                  }}
                                >
                                  Delete
                                </button>

                              </div>
                            )}

                          </div>

                        )}

                      </>

                    )}

                  </div>

                );
              },
            )}

          </div>

        )}

      </div>

    </div>
  );
}