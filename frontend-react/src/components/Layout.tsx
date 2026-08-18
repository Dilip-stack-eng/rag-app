import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { AthenaLogo } from "./AthenaLogo";
import { t } from "../i18n/translations";

interface NavItem {
  to: string;
  label: string;
  superAdminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/home", label: t("tab_home") },
  { to: "/query-trace", label: t("tab_query_trace") },
  { to: "/knowledge-base", label: "Knowledge base", superAdminOnly: true },
  { to: "/training-log", label: "Training log", superAdminOnly: true },
  { to: "/quarantine", label: "Quarantine", superAdminOnly: true },
  { to: "/prompts", label: "Prompts", superAdminOnly: true },
  { to: "/security", label: "Security", superAdminOnly: true },
  { to: "/users", label: "Users", superAdminOnly: true },
  { to: "/control-panel", label: "Control panel", superAdminOnly: true },
];

export function Layout() {
  const { username, isSuperAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const roleLabel = isSuperAdmin ? "SuperAdmin" : username || t("role_local");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <AthenaLogo size={24} />
          ATHENA
        </div>

        <NavLink to="/home" className="btn-secondary btn-block" style={{ marginBottom: "0.8rem", textAlign: "left" }}>
          {t("new_chat")}
        </NavLink>

        <nav className="nav-list">
          {NAV_ITEMS.filter((item) => !item.superAdminOnly || isSuperAdmin).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          🔒&nbsp; {roleLabel} &middot; Gemini + Chroma
          <button className="btn-secondary btn-block" style={{ marginTop: "0.7rem" }} onClick={handleLogout}>
            {t("log_out")}
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
