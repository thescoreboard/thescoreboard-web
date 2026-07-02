export const SPORT_LABELS = {
  table_tennis: "Table Tennis",
  badminton:    "Badminton",
  cricket:      "Cricket",
  football:     "Football",
};

export const SPORT_ICONS = {
  table_tennis: "🏓",
  badminton:    "🏸",
  cricket:      "🏏",
  football:     "⚽",
};

// Sport accent colors for top-strip
const SPORT_COLOR = {
  table_tennis: "#FF6B35",
  badminton:    "#38bdf8",
  cricket:      "#D97706",
  football:     "#22c55e",
};

const STATUS_META = {
  live:      { label: "LIVE",      bg: "var(--primary)",  text: "#fff" },
  upcoming:  { label: "UPCOMING",  bg: "var(--gold-dim)", text: "#92700A" },
  completed: { label: "DONE",      bg: "var(--green-dim)",text: "#15803d" },
  draft:     { label: "DRAFT",     bg: "var(--elevated)", text: "var(--muted)" },
};

function formatDate(iso) {
  if (!iso) return null;
  const [y, m, d] = iso.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${months[parseInt(m,10)-1]} ${parseInt(d,10)}, ${y}`;
}

export default function TournamentCard({ tournament: t, onClick }) {
  const sm       = STATUS_META[t.status] || STATUS_META.upcoming;
  const sports   = t.sports || [];

  // Accent: if single sport use its color, else primary
  const accentColor = sports.length === 1 ? (SPORT_COLOR[sports[0]] || "var(--primary)") : "var(--primary)";

  return (
    <div
      onClick={onClick}
      style={{
        background:    "var(--surface)",
        border:        "2px solid var(--border)",
        borderTop:     `3px solid ${accentColor}`,
        borderRadius:  "var(--radius-lg)",
        cursor:        "pointer",
        transition:    "all 200ms ease",
        position:      "relative",
        overflow:      "hidden",
        display:       "flex",
        flexDirection: "column",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor  = "var(--primary)";
        e.currentTarget.style.transform    = "translateY(-3px)";
        e.currentTarget.style.boxShadow    = "0 8px 28px rgba(255,107,53,0.14)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor  = "var(--border)";
        e.currentTarget.style.transform    = "none";
        e.currentTarget.style.boxShadow    = "none";
      }}
    >

      <div style={{ padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 10, position: "relative" }}>
        {/* Top row: sport chips + status */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", flex: 1 }}>
            {sports.slice(0, 3).map(s => (
              <span key={s} style={{
                fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5,
                padding: "2px 8px", borderRadius: 4,
                background: "var(--elevated)", color: "var(--muted)",
                border: "1px solid var(--border)",
                whiteSpace: "nowrap",
              }}>
                {SPORT_LABELS[s] || s}
              </span>
            ))}
          </div>
          <span style={{
            fontSize: 10, fontWeight: 800, letterSpacing: 1.5,
            textTransform: "uppercase", fontFamily: "var(--font-display)",
            padding: "3px 9px", borderRadius: 4,
            background: sm.bg, color: sm.text,
            display: "inline-flex", alignItems: "center", gap: 5,
            flexShrink: 0,
          }}>
            {sm.label}
          </span>
        </div>

        {/* Name */}
        <div>
          <h3 style={{
            fontFamily: "var(--font-display)", fontSize: 15, fontWeight: 900,
            textTransform: "uppercase", letterSpacing: -0.5, color: "var(--ink)",
            lineHeight: 1.25, margin: 0,
            overflow: "hidden", display: "-webkit-box",
            WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
          }}>{t.name}</h3>
          {t.org_name && (
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 3, fontWeight: 500 }}>
              by {t.org_name}
            </div>
          )}
        </div>

        {/* Meta: location + date */}
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {(t.city || t.venue) && (
            <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "var(--muted)" }}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
                <circle cx="12" cy="9" r="2.5"/>
              </svg>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {[t.venue, t.city, t.state].filter(Boolean).join(", ")}
              </span>
            </div>
          )}
          {t.start_date && (
            <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "var(--muted)" }}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
                <rect x="3" y="4" width="18" height="18" rx="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
              {formatDate(t.start_date)}
            </div>
          )}
        </div>

        {/* Stats row */}
        <div style={{
          display: "flex", gap: 16, paddingTop: 10,
          borderTop: "1px solid var(--border)", marginTop: "auto",
        }}>
          {[
            { label: "Players",  value: t.total_players  || 0 },
            { label: "Matches",  value: t.total_matches  || 0 },
            { label: "Done",     value: t.completed_matches || 0, color: "var(--green)" },
          ].filter(Boolean).map(({ label, value, color }) => (
            <div key={label} style={{ textAlign: "center", flex: 1 }}>
              <div style={{
                fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 900,
                color: color || "var(--ink)", lineHeight: 1,
              }}>{value}</div>
              <div style={{
                fontSize: 9, fontWeight: 700, textTransform: "uppercase",
                letterSpacing: 0.5, color: "var(--muted)", marginTop: 2,
              }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
