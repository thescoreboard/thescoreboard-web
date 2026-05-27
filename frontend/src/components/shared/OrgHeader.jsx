import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getMode, setMode, getStoredUser } from "../../api/client";

function getModeIcon(mode) {
  if (mode === "player") return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  );
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/>
      <line x1="9" y1="21" x2="9" y2="9"/>
    </svg>
  );
}

export default function OrgHeader({ crumbs = [], right = null, user = null, onLogout = null }) {
  const navigate = useNavigate();

  const [mode, setModeState] = useState(() => getMode());
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("theme") || "light";
  });

  // Determine whether to show the mode toggle.
  // Prefer roles from the `user` prop (freshly fetched by the page) so the
  // check stays accurate even if localStorage is slightly stale.
  const userRoles = user?.roles ?? getStoredUser()?.roles ?? [];
  const canSwitchMode = userRoles.includes("organiser");

  const toggleMode = () => {
    const next = mode === "organiser" ? "player" : "organiser";
    setModeState(next);
    setMode(next);
    navigate(next === "player" ? "/player" : "/organiser", { replace: false });
  };

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme");
    if (!savedTheme) {
      document.documentElement.setAttribute("data-theme", "light");
      localStorage.setItem("theme", "light");
    } else {
      document.documentElement.setAttribute("data-theme", savedTheme);
      setTheme(savedTheme);
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
  };

  return (
    <header className="site-header org-header" style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
      {/* ── Row 1: brand + controls ── */}
      <div className="header-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", height: 56 }}>
        {/* Brand */}
        <span
          className="header-brand"
          onClick={() => navigate("/organiser")}
          style={{ color: "var(--ink)", cursor: "pointer" }}
        >
          The<span className="accent" style={{ color: "var(--primary)" }}>Score</span>Board
        </span>

        {/* Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          {/* Username — hidden on mobile via CSS */}
          {user?.name && (
            <span className="user-name-desktop" style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600 }}>
              {user.name}
            </span>
          )}

          {right}

          {/* Superadmin: show only the admin panel link, nothing else */}
          {user?.is_superadmin ? (
            <button
              onClick={() => navigate("/admin")}
              style={{
                display:"flex", alignItems:"center", gap:6,
                padding:"6px 14px", borderRadius:6, cursor:"pointer",
                border:"1px solid rgba(124,58,237,.4)",
                background:"rgba(124,58,237,.1)",
                color:"#7c3aed",
                fontSize:11, fontWeight:700, letterSpacing:0.5, textTransform:"uppercase",
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              Admin Panel
            </button>
          ) : (
            <>
              {/* Mode toggle — only shown when the user has both player + organiser roles */}
              {canSwitchMode && (
                <button
                  onClick={toggleMode}
                  title={`Switch to ${mode === "organiser" ? "Player" : "Organiser"} mode`}
                  style={{
                    display:"flex", alignItems:"center", gap:5,
                    padding:"5px 10px", borderRadius:6, cursor:"pointer",
                    border:"1px solid var(--border)",
                    background: mode === "player" ? "rgba(22,163,74,.08)" : "var(--elevated)",
                    color: mode === "player" ? "#16a34a" : "var(--muted)",
                    fontSize:11, fontWeight:700,
                  }}
                >
                  {getModeIcon(mode === "organiser" ? "player" : "organiser")}
                  <span className="user-name-desktop">
                    {mode === "organiser" ? "Player" : "Organiser"}
                  </span>
                </button>
              )}
            </>
          )}

          <button
            onClick={toggleTheme}
            className="theme-toggle-btn"
            style={{
              background: "none", border: "1px solid var(--border)",
              borderRadius: 6, width: 32, height: 32,
              cursor: "pointer", color: "var(--ink)", flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            {theme === "light" ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
            )}
          </button>

          {onLogout && (
            <button
              className="btn btn-ghost btn-sm org-logout-btn"
              onClick={onLogout}
              style={{ color: "var(--ink)" }}
            >
              Logout
            </button>
          )}
        </div>
      </div>

      {/* ── Row 2: breadcrumbs ── */}
      {crumbs.length > 0 && (
        <div className="breadcrumb-row" style={{ background: "var(--bg)", borderBottom: "1px solid var(--border)", padding: "8px 20px" }}>
          {crumbs.map((crumb, i) => {
            const isLast = i === crumbs.length - 1;
            return (
              <span key={i} style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                {i > 0 && <span className="breadcrumb-sep" style={{ color: "var(--muted)" }}>›</span>}
                <span
                  className={`breadcrumb-item${isLast ? " current" : ""}`}
                  onClick={() => !isLast && crumb.path && navigate(crumb.path)}
                  style={{ color: isLast ? "var(--ink)" : "var(--muted)", cursor: isLast ? "default" : "pointer", fontSize: 13 }}
                >
                  {crumb.label}
                </span>
              </span>
            );
          })}
        </div>
      )}
    </header>
  );
}