/**
 * About — the story behind TheScoreBoard.
 * Linked from the landing-page footer. Same static-page skeleton as Terms/Privacy.
 */
import { Link, useNavigate } from "react-router-dom";

const INSTAGRAM_URL  = "https://www.instagram.com/thescoreboard.in/";
const CONTACT_EMAIL  = "teams@thescoreboard.in";
// wa.me deep link opens a chat with this number directly; ?text= pre-fills
// the message so the person just has to hit send.
const WHATSAPP_URL   =
  "https://wa.me/917506134294?text=" +
  encodeURIComponent("Hi! I found TheScoreBoard and I'd like to know more.");
const WHATSAPP_LABEL = "+91 75061 34294";

const sectionLabel = {
  fontFamily: "var(--font-display)", fontSize: 11, fontWeight: 800,
  textTransform: "uppercase", letterSpacing: 2, color: "var(--primary)",
  marginBottom: 10,
};
const bodyText = { fontSize: 15, lineHeight: 1.85, color: "var(--ink)", marginBottom: 18 };

export default function About() {
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--ink)" }}>
      {/* Nav bar — nowrap + clamp so logo and link share one line on 375px */}
      <div style={{
        borderBottom: "1px solid var(--border)", padding: "14px clamp(16px, 4vw, 24px)",
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
      }}>
        <Link to="/" style={{ textDecoration: "none", whiteSpace: "nowrap" }}>
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 900, fontSize: "clamp(13px, 3.8vw, 16px)", color: "var(--ink)" }}>
            THE<span style={{ color: "var(--primary)" }}>SCORE</span>BOARD
          </span>
        </Link>
        <Link to="/tournaments" style={{
          fontSize: "clamp(11px, 3.2vw, 13px)", color: "var(--muted)",
          textDecoration: "none", whiteSpace: "nowrap", flexShrink: 0,
        }}>
          Tournaments →
        </Link>
      </div>

      {/* Content */}
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "48px 24px 80px" }}>
        <p style={sectionLabel}>Our Journey</p>
        <h1 style={{
          fontFamily: "var(--font-display)", fontSize: 34, fontWeight: 900,
          letterSpacing: -1, lineHeight: 1.15, marginBottom: 28,
        }}>
          Born at a table tennis tournament.<br />
          Built for every local court.
        </h1>

        <p style={bodyText}>
          TheScoreBoard started as an idea at a local table tennis tournament —
          paper brackets, shouted scores, and no way for anyone outside the hall
          to follow the action. We knew there had to be a better way.
        </p>
        <p style={bodyText}>
          That one tournament grew into this platform: a place where{" "}
          <strong>organisers</strong> host tournaments hassle-free,{" "}
          <strong>spectators</strong> follow live scores from anywhere, and{" "}
          <strong>players</strong> build a profile that travels with them from
          event to event.
        </p>

        {/* Mission callout */}
        <div style={{
          margin: "32px 0", padding: "22px 24px", borderLeft: "3px solid var(--primary)",
          background: "var(--elevated)", borderRadius: "0 12px 12px 0",
        }}>
          <p style={{ fontSize: 16, lineHeight: 1.75, fontWeight: 600, margin: 0 }}>
            While mainstream apps focus on professional sports, TheScoreBoard
            exists to empower <span style={{ color: "var(--primary)" }}>grassroots and local tournaments</span> —
            the club leagues, school championships, and community events where
            most of the world actually plays.
          </p>
        </div>

        {/* Founder */}
        <p style={{ ...sectionLabel, marginTop: 40 }}>Who's Behind It</p>
        <p style={bodyText}>
          TheScoreBoard was created by <strong>Rejinold Johnson</strong>, a
          developer with a passion for sports — building the tool he wished
          existed courtside.
        </p>

        {/* Contact */}
        <p style={{ ...sectionLabel, marginTop: 40 }}>Reach Out</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 44 }}>
          <a href={INSTAGRAM_URL} target="_blank" rel="noopener noreferrer" style={contactRow}>
            <span style={{ ...contactIcon, color: "#E1306C" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="0.5" fill="currentColor"/>
              </svg>
            </span>
            @thescoreboard.in
          </a>
          <a href={`mailto:${CONTACT_EMAIL}`} style={contactRow}>
            <span style={contactIcon}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 5L2 7"/>
              </svg>
            </span>
            {CONTACT_EMAIL}
          </a>
          <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer" style={contactRow}>
            <span style={{ ...contactIcon, color: "#25D366" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm5.4 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.4-.7-2.9-1.2-4.7-4.1-4.9-4.3-.1-.2-1.1-1.5-1.1-2.9s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5s.8 1.9.8 2c.1.1.1.3 0 .5-.3.6-.6.8-.5 1.1.6 1 1.3 1.8 2.2 2.4.7.5 1.2.6 1.4.5.2-.1.7-.8.9-1.1.2-.3.4-.2.6-.1l1.8.8c.2.1.4.2.4.3.1.1.1.6-.2 1.4Z"/>
              </svg>
            </span>
            WhatsApp · {WHATSAPP_LABEL}
          </a>
        </div>

        {/* CTA */}
        <div style={{
          display: "flex", gap: 12, flexWrap: "wrap",
          paddingTop: 28, borderTop: "1px solid var(--border)",
        }}>
          <button
            onClick={() => navigate("/organiser")}
            style={{
              background: "var(--primary)", color: "#fff", border: "none",
              borderRadius: 10, padding: "13px 22px", cursor: "pointer",
              fontFamily: "var(--font-display)", fontSize: 12, fontWeight: 800,
              textTransform: "uppercase", letterSpacing: 1,
            }}
          >
            Host a Tournament →
          </button>
          <button
            onClick={() => navigate("/tournaments")}
            style={{
              background: "transparent", color: "var(--ink)",
              border: "1.5px solid var(--border-mid, var(--border))",
              borderRadius: 10, padding: "13px 22px", cursor: "pointer",
              fontFamily: "var(--font-display)", fontSize: 12, fontWeight: 800,
              textTransform: "uppercase", letterSpacing: 1,
            }}
          >
            Follow Live Scores
          </button>
        </div>
      </div>
    </div>
  );
}

const contactRow = {
  display: "inline-flex", alignItems: "center", gap: 10,
  fontSize: 14, fontWeight: 700, color: "var(--ink)", textDecoration: "none",
};
const contactIcon = {
  width: 32, height: 32, borderRadius: 8, flexShrink: 0,
  display: "inline-flex", alignItems: "center", justifyContent: "center",
  background: "var(--elevated)", border: "1px solid var(--border)",
  color: "var(--primary)",
};
