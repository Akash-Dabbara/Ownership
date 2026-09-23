// In production (Vercel), set VITE_API_BASE_URL to your deployed
// Render backend URL, e.g. https://dataease-backend.onrender.com
// Locally, it falls back to localhost so dev is unaffected.
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";


// ============================================================
// ERROR MESSAGE HELPER
// ============================================================

function getErrorMessage(data, fallbackMessage) {
  if (!data) {
    return fallbackMessage;
  }

  if (typeof data.detail === "string") {
    return data.detail;
  }

  if (
    data.detail &&
    typeof data.detail === "object" &&
    typeof data.detail.message === "string"
  ) {
    return data.detail.message;
  }

  if (typeof data.message === "string") {
    return data.message;
  }

  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => item.msg || item.message)
      .filter(Boolean)
      .join(", ");
  }

  return fallbackMessage;
}


// ============================================================
// SAFE RESPONSE PARSER
// ============================================================

async function parseResponse(response) {
  const contentType =
    response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();

  if (!text) {
    return null;
  }

  return {
    detail: text,
  };
}


// ============================================================
// GENERIC API REQUEST
// ============================================================

export async function apiRequest(
  endpoint,
  {
    method = "GET",
    token = null,
    body = undefined,
    timeout = 15000,
  } = {}
) {
  const controller = new AbortController();

  const timeoutId = setTimeout(
    () => controller.abort(),
    timeout
  );

  try {
    const headers = {
      Accept: "application/json",
    };

    if (body !== undefined) {
      headers["Content-Type"] =
        "application/json";
    }

    if (token) {
      headers["Authorization"] =
        `Bearer ${token}`;
    }

    const response = await fetch(
      `${API_BASE_URL}${endpoint}`,
      {
        method,
        headers,
        body:
          body !== undefined
            ? JSON.stringify(body)
            : undefined,
        signal: controller.signal,
      }
    );

    const data =
      await parseResponse(response);

    if (!response.ok) {
      throw new Error(
        getErrorMessage(
          data,
          `Request failed with status ${response.status}.`
        )
      );
    }

    return data;

  } catch (error) {

    if (error.name === "AbortError") {
      throw new Error(
        "Server request timed out. Please check if the backend is running."
      );
    }

    throw error;

  } finally {

    clearTimeout(timeoutId);

  }
}


// ============================================================
// AUTHENTICATION
// ============================================================

export async function loginUser(
  email,
  password
) {
  return apiRequest(
    "/auth/login",
    {
      method: "POST",
      body: {
        email,
        password,
      },
    }
  );
}


export async function changePassword(
  currentPassword,
  newPassword,
  token
) {
  return apiRequest(
    "/auth/change-password",
    {
      method: "POST",
      body: {
        current_password: currentPassword,
        new_password: newPassword,
      },
      token,
    }
  );
}


// ============================================================
// WORKSPACES
// ============================================================

export async function getWorkspaces(
  token
) {
  return apiRequest(
    "/workspaces",
    {
      method: "GET",
      token,
    }
  );
}


export async function getWorkspace(
  workspaceId,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}`,
    {
      method: "GET",
      token,
    }
  );
}


export async function createWorkspace(
  payload,
  token
) {
  return apiRequest(
    "/workspaces",
    {
      method: "POST",
      body: payload,
      token,
    }
  );
}


export async function updateWorkspace(
  workspaceId,
  payload,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}`,
    {
      method: "PUT",
      body: payload,
      token,
    }
  );
}


export async function deleteWorkspace(
  workspaceId,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}`,
    {
      method: "DELETE",
      token,
    }
  );
}


// ============================================================
// DATA SOURCE CREDENTIALS
// ============================================================

export async function getDataSourceCredentials(
  token
) {
  return apiRequest(
    "/data-source-credentials",
    {
      method: "GET",
      token,
    }
  );
}


// ============================================================
// CONNECTOR TEST CONNECTION
// ============================================================

export async function testConnectorConnection(
  credentialId,
  token
) {
  return apiRequest(
    "/connectors/test",
    {
      method: "POST",

      body: {
        credential_id: credentialId,
      },

      token,
    }
  );
}


// ============================================================
// CONNECTOR LOOK-AHEAD
// ============================================================

export async function browseConnectorRoot(
  credentialId,
  token
) {
  return apiRequest(
    `/connectors/${credentialId}/browse/root`,
    {
      method: "GET",
      token,
    }
  );
}


export async function browseConnectorChildren(
  credentialId,
  {
    parentPath,
    searchText = null,
    databaseName = null,
  },
  token
) {
  return apiRequest(
    `/connectors/${credentialId}/browse/children`,
    {
      method: "POST",

      body: {
        parent_path: parentPath,
        search_text: searchText,
        database_name: databaseName,
      },

      token,
    }
  );
}


// ============================================================
// CONNECTOR TABLES
// ============================================================

export async function browseConnectorTables(
  credentialId,
  {
    databaseName,
    schemaName,
    searchText = null,
  },
  token
) {
  return apiRequest(
    `/connectors/${credentialId}/browse/tables`,
    {
      method: "POST",

      body: {
        database_name: databaseName,
        schema_name: schemaName,
        search_text: searchText,
      },

      token,
    }
  );
}


// ============================================================
// CONNECTOR TABLE COLUMNS
// ============================================================

export async function browseConnectorColumns(
  credentialId,
  {
    databaseName,
    schemaName,
    tableName,
  },
  token
) {
  return apiRequest(
    `/connectors/${credentialId}/browse/columns`,
    {
      method: "POST",

      body: {
        database_name: databaseName,
        schema_name: schemaName,
        table_name: tableName,
      },

      token,
    }
  );
}


// ============================================================
// VALIDATE DESTINATION
// ============================================================

export async function validateConnectorDestination(
  credentialId,
  {
    path,
    databaseName = null,
  },
  token
) {
  return apiRequest(
    `/connectors/${credentialId}/destination/validate`,
    {
      method: "POST",

      body: {
        path,
        database_name: databaseName,
      },

      token,
    }
  );
}


// ============================================================
// FILE GROUPS
// ============================================================

export async function getFileGroups(
  workspaceId,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}/file-groups`,
    {
      method: "GET",
      token,
    }
  );
}


export async function createFileGroup(
  workspaceId,
  payload,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}/file-groups`,
    {
      method: "POST",
      body: payload,
      token,
    }
  );
}


export async function updateFileGroup(
  workspaceId,
  fileGroupId,
  payload,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}/file-groups/${fileGroupId}`,
    {
      method: "PUT",
      body: payload,
      token,
    }
  );
}


// ============================================================
// GET SINGLE FILE GROUP
// ============================================================

export async function getFileGroup(
  workspaceId,
  fileGroupId,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}/file-groups/${fileGroupId}`,
    {
      method: "GET",
      token,
    }
  );
}


// ============================================================
// LIST FILES IN A FILE GROUP
// ============================================================

export async function getFileGroupFiles(
  workspaceId,
  fileGroupId,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}/file-groups/${fileGroupId}/files`,
    {
      method: "GET",
      token,
    }
  );
}


// ============================================================
// FILE GROUP DATA IMPORT
//
// Matches the real backend route:
// POST /workspaces/{workspaceId}/file-groups/{fileGroupId}/files
// Body: { data_source_credential_id, selections: [...] }
// ============================================================

export async function importFileGroupData(
  workspaceId,
  fileGroupId,
  dataSourceCredentialId,
  selections,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}/file-groups/${fileGroupId}/files`,
    {
      method: "POST",
      body: {
        data_source_credential_id: dataSourceCredentialId,
        selections,
      },
      token,
      timeout: 120000, // 2 minutes — validating large tables takes time
    }
  );
}


// ============================================================
// UPLOAD A LOCAL FILE (no credential — Local File workspaces)
// ============================================================

export async function uploadLocalFile(
  workspaceId,
  fileGroupId,
  file,
  displayName,
  token
) {
  const formData = new FormData();
  formData.append("file", file);
  if (displayName) {
    formData.append("display_name", displayName);
  }

  const headers = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(
    `${API_BASE_URL}/workspaces/${workspaceId}/file-groups/${fileGroupId}/files/upload`,
    {
      method: "POST",
      headers,
      body: formData,
    }
  );

  const data = await parseResponse(response);

  if (!response.ok) {
    throw new Error(
      getErrorMessage(data, `Upload failed with status ${response.status}.`)
    );
  }

  return data;
}


// ============================================================
// PREVIEW FILE DATA
// ============================================================

export async function previewFileData(
  workspaceId,
  fileGroupId,
  fileId,
  limit,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}/file-groups/${fileGroupId}/files/${fileId}/preview?limit=${limit}`,
    {
      method: "GET",
      token,
      timeout: 120000, // 2 minutes
    }
  );
}


// ============================================================
// RUN ANONYMIZATION
// ============================================================

export async function anonymizeFileData(
  workspaceId,
  fileGroupId,
  fileId,
  columnRules,
  previewLimit,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}/file-groups/${fileGroupId}/files/${fileId}/anonymize`,
    {
      method: "POST",
      body: {
        column_rules: columnRules,
        preview_limit: previewLimit,
      },
      token,
      timeout: 300000, // 5 minutes — processes the FULL dataset, not just the preview
    }
  );
}


// ============================================================
// EXPORT ANONYMIZED DATA
// ============================================================

export async function exportFileData(
  workspaceId,
  fileGroupId,
  fileId,
  columnRules,
  token
) {
  return apiRequest(
    `/workspaces/${workspaceId}/file-groups/${fileGroupId}/files/${fileId}/export`,
    {
      method: "POST",
      body: {
        column_rules: columnRules,
      },
      token,
      timeout: 300000, // 5 minutes — re-reads and re-anonymizes the full dataset
    }
  );
}


// ============================================================
// EXPORT — DOWNLOAD VARIANT
//
// Used for URL / Local File sources, where the backend returns
// the anonymized data as a CSV file stream (not JSON), which the
// browser saves directly to the user's Downloads folder.
// ============================================================

export async function exportFileDownload(
  workspaceId,
  fileGroupId,
  fileId,
  columnRules,
  token
) {
  const headers = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(
    `${API_BASE_URL}/workspaces/${workspaceId}/file-groups/${fileGroupId}/files/${fileId}/export`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({ column_rules: columnRules }),
    }
  );

  if (!response.ok) {
    const data = await parseResponse(response);
    throw new Error(
      getErrorMessage(data, `Export failed with status ${response.status}.`)
    );
  }

  const contentDisposition = response.headers.get("content-disposition") || "";
  const match = contentDisposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "anonymized_export.csv";

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(downloadUrl);

  return { filename };
}


// ============================================================
// OWNER SETUP (first-run bootstrap)
// ============================================================

export async function getOwnerSetupStatus() {
  return apiRequest("/owner-setup/status", {
    method: "GET",
  });
}

export async function submitOwnerSetupRequest(email, password) {
  return apiRequest("/owner-setup/request", {
    method: "POST",
    body: { email, password },
  });
}


// ============================================================
// USER MANAGEMENT
// ============================================================

export async function createUserWithAccess(
  email,
  password,
  workspaceId,
  fileGroupId,
  fileId,
  token
) {
  return apiRequest("/user-management/users-with-access", {
    method: "POST",
    body: {
      email,
      password,
      workspace_id: workspaceId,
      file_group_id: fileGroupId,
      file_id: fileId || null,
    },
    token,
  });
}


// ============================================================
// ADMIN SETUP (self-service — request an Admin account)
// ============================================================

export async function submitAdminSetupRequest(email, password) {
  return apiRequest("/admin-setup/request", {
    method: "POST",
    body: { email, password },
  });
}

export async function getPendingAdminRequests(token) {
  return apiRequest("/admin-setup/requests", {
    method: "GET",
    token,
  });
}

export async function approveAdminSetupRequest(requestId, token) {
  return apiRequest(`/admin-setup/requests/${requestId}/approve`, {
    method: "POST",
    token,
  });
}

export async function rejectAdminSetupRequest(requestId, token) {
  return apiRequest(`/admin-setup/requests/${requestId}/reject`, {
    method: "POST",
    body: {},
    token,
  });
}


// ============================================================
// API BASE URL
// ============================================================

export {
  API_BASE_URL,
};