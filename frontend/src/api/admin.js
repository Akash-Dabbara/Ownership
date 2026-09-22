import { apiRequest } from "./api";


// ============================================================
// ADMIN ACCOUNTS (Owner only)
// ============================================================

export function getAdmins(token) {
  return apiRequest("/admin-management/admins", {
    method: "GET",
    token,
  });
}

export function deactivateAdmin(adminId, token) {
  return apiRequest(`/admin-management/admins/${adminId}/deactivate`, {
    method: "POST",
    token,
  });
}

export function reactivateAdmin(adminId, token) {
  return apiRequest(`/admin-management/admins/${adminId}/reactivate`, {
    method: "POST",
    token,
  });
}

export function deleteAdmin(adminId, token) {
  return apiRequest(`/admin-management/admins/${adminId}`, {
    method: "DELETE",
    token,
  });
}


// ============================================================
// DATA SOURCE CREDENTIALS (Owner only)
// ============================================================

// Includes inactive ones. The Owner sees every credential,
// each with its assigned_admin_id (null = Owner-only).
export function getAllDataSourceCredentials(token) {
  return apiRequest("/data-source-credentials?include_inactive=true", {
    method: "GET",
    token,
  });
}

export function createDataSourceCredential(payload, token) {
  return apiRequest("/data-source-credentials", {
    method: "POST",
    body: payload,
    token,
  });
}

export function deleteDataSourceCredential(credentialId, token) {
  return apiRequest(`/data-source-credentials/${credentialId}`, {
    method: "DELETE",
    token,
  });
}