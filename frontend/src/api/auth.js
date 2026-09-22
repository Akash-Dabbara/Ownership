const AUTH_STORAGE_KEY = "dataease_auth";


export function saveAuthSession(loginResponse) {
  if (!loginResponse) {
    throw new Error(
      "Invalid authentication response.",
    );
  }

  if (!loginResponse.access_token) {
    throw new Error(
      "Authentication response does not contain an access token.",
    );
  }

  const session = {
    accessToken: loginResponse.access_token,
    tokenType:
      loginResponse.token_type || "bearer",
    userId: loginResponse.user_id,
    email: loginResponse.email,
    role: loginResponse.role,
    mustChangePassword:
      Boolean(loginResponse.must_change_password),
  };

  localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify(session),
  );

  return session;
}


export function getAuthSession() {
  const storedSession =
    localStorage.getItem(AUTH_STORAGE_KEY);

  if (!storedSession) {
    return null;
  }

  try {
    const session =
      JSON.parse(storedSession);

    if (
      !session ||
      typeof session !== "object" ||
      !session.accessToken
    ) {
      localStorage.removeItem(
        AUTH_STORAGE_KEY,
      );

      return null;
    }

    return session;
  } catch {
    localStorage.removeItem(
      AUTH_STORAGE_KEY,
    );

    return null;
  }
}


// NEW: merge a partial update into the stored session.
// Used after a successful password change to clear the
// mustChangePassword flag without forcing a re-login.
export function updateAuthSession(changes) {
  const session = getAuthSession();

  if (!session) {
    return null;
  }

  const updatedSession = {
    ...session,
    ...changes,
  };

  localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify(updatedSession),
  );

  return updatedSession;
}


export function getAccessToken() {
  const session = getAuthSession();

  return session?.accessToken || null;
}


export function clearAuthSession() {
  localStorage.removeItem(
    AUTH_STORAGE_KEY,
  );
}


export function isAuthenticated() {
  return Boolean(getAccessToken());
}