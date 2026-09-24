import { getAuthSession } from "../api/auth";

const ROLE_LABELS = {
  OWNER: "Owner",
  ADMIN: "Admin",
  USER: "User",
};

/**
 * Shared title banner used across every screen in the app.
 * Left: DataEase logo + optional subtitle (e.g. workspace name),
 *       plus who is currently signed in and their role, whenever
 *       there is an active session.
 * Center: optional centered action button (e.g. Create File Group).
 * Right: optional screen-specific controls (buttons, links, etc.)
 */
function TitleBanner({ subtitle, centerContent, rightContent }) {
  const session = getAuthSession();
  const roleLabel = session ? ROLE_LABELS[(session.role || "").toUpperCase()] : null;

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 1000,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        background: "#fff",
        padding: "20px 32px",
        borderBottom: "1px solid #e5e7eb",
        boxShadow: "0 2px 4px rgba(0,0,0,0.02)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div
          style={{
            width: "40px",
            height: "40px",
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "8px",
            fontWeight: "700",
            fontSize: "20px",
            flexShrink: 0,
            boxShadow: "0 2px 6px rgba(99, 102, 241, 0.4)",
          }}
        >
          D
        </div>
        <div>
          <h1 style={{ margin: 0, fontSize: "24px", color: "#111827" }}>
            DataEase
          </h1>
          {subtitle && (
            <p
              style={{
                margin: 0,
                fontSize: "13px",
                color: "#6b7280",
              }}
            >
              {subtitle}
            </p>
          )}
          {session && (
            <p
              style={{
                margin: "2px 0 0 0",
                fontSize: "12px",
                color: "#9ca3af",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <span>{session.email}</span>
              {roleLabel && (
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    letterSpacing: "0.02em",
                    textTransform: "uppercase",
                    padding: "2px 8px",
                    borderRadius: "999px",
                    color: "#4338ca",
                    background: "#eef2ff",
                  }}
                >
                  {roleLabel}
                </span>
              )}
            </p>
          )}
        </div>
      </div>

      {centerContent && (
        <div
          style={{
            position: "absolute",
            left: "50%",
            transform: "translateX(-50%)",
            display: "flex",
            alignItems: "center",
          }}
        >
          {centerContent}
        </div>
      )}

      {rightContent && (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", alignItems: "flex-end" }}>
          {rightContent}
        </div>
      )}
    </header>
  );
}

export default TitleBanner;