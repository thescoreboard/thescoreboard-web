import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getMode, setMode, getStoredUser } from "../../api/client";

// ── Responsive hook ───────────────────────────────────────────────────────────
function useWindowWidth() {
  const [width, setWidth] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth : 1024
  );
  useEffect(() => {
    const handler = () => setWidth(window.innerWidth);
    window.addEventListener("resize", handler, { passive: true });
    return () => window.removeEventListener("resize", handler);
  }, []);
  return width;
}

// ── OrgHeader ─────────────────────────────────────────────────────────────────
export default function OrgHeader({ crumbs = [], right = null, user = null, onLogout = null, hideModePill = false }) {
  const navigate    = useNavigate();
  const windowWidth = useWindowWidth();
  const isMobile    = windowWidth < 640;

  const [mode, setModeState] = useState(() => getMode());
  const [theme, setTheme]    = useState(() => localStorage.getItem("theme") || "light");

  const userRoles    = user?.roles ?? getStoredUser()?.roles ?? [];
  const canSwitchMode = userRoles.includes("organiser");

  const switchMode = (key) => {
    setModeState(key);
    setMode(key);
    navigate(key === "player" ? "/player" : "/organiser");
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
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  };

  // ── Segmented mode pill ──────────────────────────────────────────────────────
  const PLAYER_ICON = (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
    </svg>
  );
  const ORGANISER_ICON = (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2"/><path d="M8 2v4M16 2v4M3 10h18"/>
    </svg>
  );
  const ModePill = ({ fullWidth = false }) => (
    <div style={{
      display: "flex", alignItems: "center",
      background: "var(--elevated)",
      border: "1.5px solid var(--border)",
      borderRadius: 8, padding: 3, gap: 2,
      flexShrink: 0,
      width: fullWidth ? "100%" : "auto",
    }}>
      {[
        { key: "player",    label: "Player",    icon: PLAYER_ICON },
        { key: "organiser", label: "Organiser", icon: ORGANISER_ICON },
      ].map(({ key, label, icon }) => {
        const isActive = mode === key;
        return (
          <button
            key={key}
            onClick={() => { if (!isActive) switchMode(key); }}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              gap: 5, border: "none", borderRadius: 6,
              padding: fullWidth ? "7px 0" : "6px 12px",
              flex: fullWidth ? 1 : undefined,
              background: isActive ? "var(--surface)" : "transparent",
              color: isActive ? "var(--ink)" : "var(--muted)",
              fontSize: 11, fontWeight: 700, textTransform: "uppercase",
              letterSpacing: 0.8, cursor: isActive ? "default" : "pointer",
              transition: "all 150ms", whiteSpace: "nowrap",
              boxShadow: isActive ? "0 1px 4px rgba(0,0,0,0.1)" : "none",
            }}
          >
            {icon}
            <span>{label}</span>
          </button>
        );
      })}
    </div>
  );

  // ── Theme toggle button ──────────────────────────────────────────────────────
  const ThemeBtn = () => (
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
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      )}
    </button>
  );

  return (
    <header
      className="site-header org-header"
      style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}
    >
      {/* ── MOBILE layout: two rows ── */}
      {isMobile ? (
        <>
          {/* Row 1 — brand + icons */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0 16px", height: 52,
          }}>
            {/* Brand */}
            <span
              className="header-brand"
              onClick={() => navigate(mode === "organiser" ? "/organiser" : "/player")}
              style={{ color: "var(--ink)", cursor: "pointer" }}
            >
              The<span className="accent" style={{ color: "var(--primary)" }}>Score</span>Board
            </span>

            {/* Right: user actions */}
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {right}
              {user?.is_superadmin && (
                <button
                  onClick={() => navigate("/admin")}
                  style={{
                    padding: "5px 10px", borderRadius: 6, cursor: "pointer",
                    border: "1px solid rgba(124,58,237,.4)",
                    background: "rgba(124,58,237,.1)", color: "#7c3aed",
                    fontSize: 10, fontWeight: 700, letterSpacing: 0.5, textTransform: "uppercase",
                  }}
                >
                  Admin
                </button>
              )}
              <ThemeBtn />
              {onLogout && (
                <button
                  onClick={onLogout}
                  style={{
                    background: "none", border: "1px solid var(--border)",
                    borderRadius: 6, padding: "5px 11px",
                    fontSize: 12, fontWeight: 700, color: "var(--ink)",
                    cursor: "pointer",
                  }}
                >
                  Logout
                </button>
              )}
            </div>
          </div>

          {/* Row 2 — mode toggle (only when user has organiser role and not hidden) */}
          {canSwitchMode && !user?.is_superadmin && !hideModePill && (
            <div style={{
              padding: "8px 16px 10px",
              borderTop: "1px solid var(--border)",
            }}>
              <ModePill fullWidth />
            </div>
          )}
        </>
      ) : (
        /* ── DESKTOP layout: single row ── */
        <div
          className="header-row"
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0 24px", height: 56,
          }}
        >
          {/* Brand */}
          <span
            className="header-brand"
            onClick={() => navigate(mode === "organiser" ? "/organiser" : "/player")}
            style={{ color: "var(--ink)", cursor: "pointer" }}
          >
            The<span className="accent" style={{ color: "var(--primary)" }}>Score</span>Board
          </span>

          {/* Controls */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            {/* Username */}
            {user?.name && (
              <span style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600 }}>
                {user.name}
              </span>
            )}

            {right}

            {user?.is_superadmin ? (
              <button
                onClick={() => navigate("/admin")}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "6px 14px", borderRadius: 6, cursor: "pointer",
                  border: "1px solid rgba(124,58,237,.4)",
                  background: "rgba(124,58,237,.1)", color: "#7c3aed",
                  fontSize: 11, fontWeight: 700, letterSpacing: 0.5, textTransform: "uppercase",
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
                Admin Panel
              </button>
            ) : (
              canSwitchMode && !hideModePill && <ModePill />
            )}

            <ThemeBtn />

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
      )}

      {/* ── Breadcrumbs (always below, both layouts) ── */}
      {crumbs.length > 0 && (
        <div
          className="breadcrumb-row"
          style={{
            background: "var(--bg)", borderBottom: "1px solid var(--border)",
            padding: "8px 20px",
          }}
        >
          {crumbs.map((crumb, i) => {
            const isLast = i === crumbs.length - 1;
            return (
              <span key={i} style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                {i > 0 && <span className="breadcrumb-sep" style={{ color: "var(--muted)" }}>›</span>}
                <span
                  className={`breadcrumb-item${isLast ? " current" : ""}`}
                  onClick={() => !isLast && crumb.path && navigate(crumb.path)}
                  style={{
                    color: isLast ? "var(--ink)" : "var(--muted)",
                    cursor: isLast ? "default" : "pointer",
                    fontSize: 13,
                  }}
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
