import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getOwnerSetupStatus } from "../api/api";
import TitleBanner from "../components/TitleBanner";

const ROLES = [
  { value: "ADMIN", label: "Admin", icon: "🛠️" },
  { value: "USER", label: "User", icon: "👤" },
];

function RoleCard({ role, onSelect }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <button
      type="button"
      onClick={() => onSelect(role.value)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        width: "200px",
        height: "200px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "16px",
        background: "#ffffff",
        border: isHovered ? "2px solid #111827" : "2px solid #e5e7eb",
        borderRadius: "20px",
        cursor: "pointer",
        transform: isHovered ? "translateY(-6px)" : "translateY(0)",
        boxShadow: isHovered
          ? "0 16px 28px rgba(17, 24, 39, 0.16)"
          : "0 2px 6px rgba(0, 0, 0, 0.06)",
        transition: "all 0.18s ease",
      }}
    >
      <span style={{ fontSize: "48px", lineHeight: 1 }}>{role.icon}</span>
      <span style={{ fontSize: "20px", fontWeight: 700, color: "#111827" }}>
        {role.label}
      </span>
    </button>
  );
}

function RoleSelect() {
  const navigate = useNavigate();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    checkOwnerStatus();
  }, []);

  async function checkOwnerStatus() {
    try {
      const response = await getOwnerSetupStatus();
      if (!response.owner_exists) {
        navigate("/owner-setup", { replace: true });
        return;
      }
    } catch (error) {
      // If the status check itself fails (e.g. backend briefly
      // unreachable), fall through to the normal role select
      // screen rather than blocking the user indefinitely.
    } finally {
      setIsChecking(false);
    }
  }

  function handleSelectRole(roleValue) {
    navigate(`/login?role=${roleValue}`);
  }

  if (isChecking) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          background: "#f8fafc",
        }}
      >
        <TitleBanner />
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p style={{ color: "#6b7280" }}>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#f8fafc",
      }}
    >
      <TitleBanner
        rightContent={
          <button
            type="button"
            onClick={() => navigate("/login?role=OWNER")}
            style={{
              height: "36px",
              padding: "0 16px",
              background: "#ffffff",
              color: "#374151",
              border: "1px solid #d1d5db",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: "600",
              cursor: "pointer",
            }}
          >
            👑 Owner Login
          </button>
        }
      />

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "40px 20px",
          gap: "28px",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: "32px",
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          {ROLES.map((role) => (
            <RoleCard
              key={role.value}
              role={role}
              onSelect={handleSelectRole}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default RoleSelect;