import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  getMe, getPlayerProfile, savePlayerProfile, clearToken,
  getMyStats, getMyTournaments, setStoredUser, setMode, deleteAccount,
} from "../../api/client";
import OrgHeader from "../../components/shared/OrgHeader";
import PageLoader from "../../components/shared/PageLoader";

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

// ── Design constants ──────────────────────────────────────────────────────────

const SPORT_LABELS = {
  table_tennis: "Table Tennis", football: "Football",
  badminton: "Badminton",       cricket:  "Cricket",
};
const SPORT_COLORS = {
  table_tennis: "#3b82f6", football: "#16a34a",
  badminton:    "#f59e0b", cricket:  "#ef4444",
};
const SPORT_ICONS = {
  table_tennis: "🏓", football: "⚽", badminton: "🏸", cricket: "🏏",
};
const STATUS_LABELS = {
  live: "Live", registration: "Open", upcoming: "Upcoming",
  fixtures: "Fixtures", completed: "Done", cancelled: "Cancelled",
};
const STATUS_COLORS = {
  live: "#ef4444", registration: "#22c55e", upcoming: "#3b82f6",
  fixtures: "#8b5cf6", completed: "#6b7280", cancelled: "#9ca3af",
};

function initials(name) {
  return (name ?? "?").split(" ").slice(0, 2).map(n => n[0]?.toUpperCase() ?? "").join("");
}

// ── Shared form styles ────────────────────────────────────────────────────────

const lbl = {
  display: "block", fontSize: 11, fontWeight: 700, color: "var(--muted)",
  marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.6,
};
const inputSt = {
  width: "100%", padding: "11px 14px", borderRadius: 8,
  border: "1.5px solid var(--border)", background: "var(--input-bg, var(--elevated))",
  color: "var(--ink)", fontSize: 14, boxSizing: "border-box",
  outline: "none", transition: "border-color 150ms",
};

// ── Section header ────────────────────────────────────────────────────────────

function SectionHead({ children, action }) {
  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:14 }}>
      <div style={{ fontFamily:"var(--font-display)", fontSize:11, fontWeight:900,
        textTransform:"uppercase", letterSpacing:2, color:"var(--muted)" }}>
        {children}
      </div>
      {action}
    </div>
  );
}

// ── Card wrapper ──────────────────────────────────────────────────────────────

function Card({ children, style = {} }) {
  return (
    <div style={{
      background: "var(--surface)", border: "1.5px solid var(--border)",
      borderRadius: 14, overflow: "hidden", boxShadow: "var(--sh-sm)",
      ...style,
    }}>
      {children}
    </div>
  );
}

// ── Profile Edit Card ─────────────────────────────────────────────────────────

function ProfileEditCard({ profile, onSaved, isMobile }) {
  const [editing, setEditing] = useState(!profile);
  const [form, setForm] = useState({
    name: profile?.name ?? "", phone: profile?.phone ?? "",
    age: profile?.age != null ? String(profile.age) : "",
    gender: profile?.gender ?? "Male", location: profile?.location ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState("");
  const [saved,  setSaved]  = useState(false);

  const handleSave = async () => {
    if (!form.name?.trim()) return setError("Name is required.");
    setSaving(true); setError("");
    try {
      const p = await savePlayerProfile({
        name: form.name.trim(), phone: form.phone?.trim() || null,
        age: parseInt(form.age) || null, gender: form.gender,
        location: form.location?.trim() || null,
      });
      onSaved(p); setEditing(false); setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  return (
    <Card>
      {/* Card header */}
      <div style={{ padding:"14px 18px", borderBottom:"1.5px solid var(--border)",
        display:"flex", alignItems:"center", justifyContent:"space-between" }}>
        <div style={{ fontFamily:"var(--font-display)", fontSize:11, fontWeight:900,
          textTransform:"uppercase", letterSpacing:2, color:"var(--muted)" }}>
          Player Profile
        </div>
        {!editing && profile && (
          <button
            onClick={() => { setEditing(true); setForm({ name:profile.name||"", phone:profile.phone||"", age:profile.age!=null?String(profile.age):"", gender:profile.gender||"Male", location:profile.location||"" }); }}
            style={{ background:"none", border:"1.5px solid var(--border)", borderRadius:7,
              padding:"5px 14px", fontSize:12, fontWeight:700, color:"var(--muted)",
              cursor:"pointer", transition:"all 150ms" }}>
            Edit
          </button>
        )}
      </div>

      <div style={{ padding: isMobile ? 14 : 20 }}>
        {/* View mode */}
        {!editing && profile && (
          <div style={{ display:"grid", gridTemplateColumns: isMobile ? "1fr 1fr" : "1fr 1fr 1fr", gap:"16px 20px" }}>
            {[
              ["Name",     profile.name],
              ["Phone",    profile.phone],
              ["Age",      profile.age ? `${profile.age} yrs` : null],
              ["Gender",   profile.gender],
              ["Location", profile.location],
            ].map(([label, val]) => val ? (
              <div key={label}>
                <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase",
                  letterSpacing:0.6, color:"var(--muted)", marginBottom:3 }}>{label}</div>
                <div style={{ fontSize:14, fontWeight:600, color:"var(--ink)" }}>{val}</div>
              </div>
            ) : null)}
          </div>
        )}

        {/* Edit mode */}
        {editing && (
          <div>
            {!profile && (
              <div style={{ background:"var(--primary-dim)", border:"1.5px solid rgba(255,107,53,.25)",
                borderRadius:9, padding:"11px 14px", marginBottom:18,
                fontSize:13, color:"var(--muted)", lineHeight:1.5 }}>
                👋 Complete your profile to register for tournaments.
              </div>
            )}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:12 }}>
              <div>
                <label style={lbl}>Full Name *</label>
                <input className="input" style={inputSt} placeholder="Rahul Sharma" autoFocus
                  value={form.name || ""} onChange={e => setForm(f => ({...f, name:e.target.value}))} />
              </div>
              <div>
                <label style={lbl}>Phone</label>
                <input className="input" type="tel" style={inputSt} placeholder="9876543210"
                  value={form.phone || ""} onChange={e => setForm(f => ({...f, phone:e.target.value}))} />
              </div>
              <div>
                <label style={lbl}>Age</label>
                <input className="input" type="number" style={inputSt} placeholder="24" min="5" max="99"
                  value={form.age || ""} onChange={e => setForm(f => ({...f, age:e.target.value}))} />
              </div>
              <div>
                <label style={lbl}>Gender</label>
                <select className="input" style={inputSt} value={form.gender || "Male"}
                  onChange={e => setForm(f => ({...f, gender:e.target.value}))}>
                  <option>Male</option><option>Female</option><option>Other</option>
                </select>
              </div>
            </div>
            <div style={{ marginBottom:18 }}>
              <label style={lbl}>City / Location</label>
              <input className="input" style={inputSt} placeholder="e.g. Chennai"
                value={form.location || ""} onChange={e => setForm(f => ({...f, location:e.target.value}))} />
            </div>

            {error && (
              <div style={{ background:"rgba(220,38,38,.08)", border:"1.5px solid rgba(220,38,38,.25)",
                borderRadius:8, padding:"10px 14px", marginBottom:14,
                fontSize:13, color:"#dc2626", fontWeight:600 }}>
                {error}
              </div>
            )}

            <div style={{ display:"flex", gap:10 }}>
              <button onClick={handleSave} disabled={saving}
                style={{ flex:1, padding:"12px", borderRadius:9, border:"none",
                  background:"var(--primary)", color:"#fff", fontSize:13, fontWeight:700,
                  cursor:"pointer", opacity:saving?0.65:1, letterSpacing:0.3 }}>
                {saving ? "Saving…" : "Save Profile"}
              </button>
              {profile && (
                <button onClick={() => setEditing(false)}
                  style={{ padding:"12px 16px", borderRadius:9, border:"1.5px solid var(--border)",
                    background:"var(--elevated)", color:"var(--muted)", fontSize:13,
                    fontWeight:600, cursor:"pointer" }}>
                  Cancel
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {saved && (
        <div style={{ padding:"10px 18px", background:"rgba(22,163,74,.08)",
          borderTop:"1.5px solid rgba(22,163,74,.2)",
          fontSize:12, fontWeight:700, color:"#16a34a" }}>
          ✓ Profile saved successfully
        </div>
      )}
    </Card>
  );
}

// ── Main dashboard ────────────────────────────────────────────────────────────

export default function PlayerDashboard() {
  const navigate    = useNavigate();
  const windowWidth = useWindowWidth();
  const isMobile    = windowWidth < 768;
  const isTablet    = windowWidth < 1024;

  const [user,        setUser]        = useState(null);
  const [profile,     setProfile]     = useState(null);
  const [stats,       setStats]       = useState(null);
  const [tournaments, setTournaments] = useState([]);

  useEffect(() => {
    async function load() {
      try {
        const [u, p, st, tv] = await Promise.all([
          getMe(),
          getPlayerProfile().catch(() => null),
          getMyStats().catch(() => null),
          getMyTournaments().catch(() => []),
        ]);
        setUser(u); setStoredUser(u); setProfile(p);
        setStats(st ?? { tournaments_count:0, matches_played:0, wins:0, losses:0, win_pct:0, by_sport:{} });
        setTournaments(Array.isArray(tv) ? tv : []);
      } catch {
        navigate("/login", { replace: true });
      }
    }
    load();
  }, [navigate]);

  const logout = () => { clearToken(); navigate("/login", { replace: true }); };

  if (!user) return <PageLoader />;

  const displayName = user.name ?? profile?.name ?? "Player";
  const memberYear  = user.created_at ? new Date(user.created_at).getFullYear() : null;
  const sportKeys   = [...new Set(tournaments.map(t => t.sport_key).filter(Boolean))];
  const st          = stats ?? {};
  const bySport     = st.by_sport ?? {};
  const hasOrganiser = (user.roles ?? []).includes("organiser");

  const contentPad = isMobile ? "24px 16px 60px" : "32px 28px 80px";

  return (
    <div className="app" style={{ minHeight:"100vh", background:"var(--bg)" }}>
      <OrgHeader user={user} onLogout={logout} />

      {/* ── Hero banner ── */}
      <div style={{
        background:"linear-gradient(135deg, rgba(255,107,53,.08) 0%, rgba(255,204,0,.05) 100%)",
        borderBottom:"1.5px solid var(--border)",
      }}>
        <div style={{ maxWidth:900, margin:"0 auto", padding: isMobile ? "24px 16px 20px" : "36px 28px 32px" }}>
          <div style={{
            display:"flex",
            alignItems: isMobile ? "flex-start" : "center",
            gap: isMobile ? 16 : 24,
          }}>
            {/* Avatar */}
            <div style={{
              width: isMobile ? 64 : 80,
              height: isMobile ? 64 : 80,
              borderRadius:"50%", flexShrink:0,
              background:"var(--primary)",
              display:"flex", alignItems:"center", justifyContent:"center",
              boxShadow:"0 0 0 4px rgba(255,107,53,.18), var(--shadow-md)",
            }}>
              <span style={{
                fontFamily:"var(--font-display)",
                fontSize: isMobile ? 22 : 28,
                fontWeight:900, color:"#fff",
              }}>
                {initials(displayName)}
              </span>
            </div>

            {/* Name + meta */}
            <div style={{ flex:1, minWidth:0 }}>
              <div style={{
                fontFamily:"var(--font-display)",
                fontSize: isMobile ? 20 : 26,
                fontWeight:900,
                letterSpacing:-0.5, color:"var(--ink)", lineHeight:1.15, marginBottom:8,
                wordBreak:"break-word",
              }}>
                {displayName}
              </div>

              <div style={{ display:"flex", flexWrap:"wrap", gap:6, alignItems:"center" }}>
                {profile?.location && (
                  <span style={{ fontSize:13, color:"var(--muted)", display:"flex", alignItems:"center", gap:3 }}>
                    📍 {profile.location}
                  </span>
                )}
                {memberYear && (
                  <span style={{ fontSize:12, color:"var(--muted)",
                    padding:"3px 10px", background:"var(--elevated)",
                    borderRadius:20, border:"1px solid var(--border)" }}>
                    Member since {memberYear}
                  </span>
                )}
                {sportKeys.map(sk => {
                  const col = SPORT_COLORS[sk] ?? "#888";
                  return (
                    <span key={sk} style={{
                      fontSize:12, fontWeight:700,
                      background:`${col}15`, border:`1.5px solid ${col}35`,
                      color:col, borderRadius:20, padding:"3px 10px",
                      display:"flex", alignItems:"center", gap:4,
                    }}>
                      {SPORT_ICONS[sk]} {SPORT_LABELS[sk] ?? sk}
                    </span>
                  );
                })}
              </div>
            </div>

            {/* Explore button — hidden on smallest screens to avoid overflow */}
            {!isMobile && (
              <div style={{ flexShrink:0 }}>
                <button
                  onClick={() => navigate("/")}
                  style={{
                    border:"1.5px solid var(--border)", borderRadius:9,
                    padding:"9px 18px", background:"var(--surface)",
                    fontSize:13, fontWeight:700, color:"var(--muted)", cursor:"pointer",
                  }}>
                  Explore →
                </button>
              </div>
            )}
          </div>

          {/* Explore button row on mobile */}
          {isMobile && (
            <button
              onClick={() => navigate("/")}
              style={{
                marginTop:14, border:"1.5px solid var(--border)", borderRadius:9,
                padding:"9px 16px", background:"var(--surface)",
                fontSize:13, fontWeight:700, color:"var(--muted)", cursor:"pointer",
              }}>
              Explore →
            </button>
          )}
        </div>
      </div>

      {/* ── Main content ── */}
      <div style={{ maxWidth:900, margin:"0 auto", padding:contentPad }}>

        {/* ── Stats strip ── */}
        <div style={{
          display:"grid",
          gridTemplateColumns: isMobile ? "repeat(2,1fr)" : "repeat(4,1fr)",
          gap: isMobile ? 10 : 12,
          marginBottom: isMobile ? 24 : 32,
        }}>
          {[
            { label:"Tournaments", val: st.tournaments_count ?? 0, color:"var(--ink)",      icon:"🏆" },
            { label:"Matches",     val: st.matches_played ?? 0,    color:"var(--primary)",  icon:"🎮" },
            { label:"Wins",        val: st.wins ?? 0,              color:"#16a34a",          icon:"✅" },
            { label:"Win Rate",    val: `${st.win_pct ?? 0}%`,     color:"#f59e0b",          icon:"📈" },
          ].map(({ label, val, color, icon }) => (
            <div key={label} style={{
              background:"var(--surface)", border:"1.5px solid var(--border)",
              borderRadius:14, padding: isMobile ? "16px 12px" : "20px 18px",
              boxShadow:"var(--sh-sm)", textAlign:"center",
            }}>
              <div style={{ fontSize: isMobile ? 16 : 18, marginBottom:6 }}>{icon}</div>
              <div style={{
                fontFamily:"var(--font-display)",
                fontSize: isMobile ? 24 : 28,
                fontWeight:900,
                color, letterSpacing:-1, lineHeight:1, marginBottom:6,
              }}>
                {val}
              </div>
              <div style={{
                fontSize: isMobile ? 9 : 10, fontWeight:700, textTransform:"uppercase",
                letterSpacing:0.8, color:"var(--muted)",
              }}>
                {label}
              </div>
            </div>
          ))}
        </div>

        {/* ── Two-column layout — stacks on mobile/tablet ── */}
        <div style={{
          display:"grid",
          gridTemplateColumns: isTablet ? "1fr" : "1fr 340px",
          gap: isTablet ? 20 : 24,
          alignItems:"start",
        }}>

          {/* ── Left column (main) ── */}
          <div>

            {/* Sport breakdown */}
            {Object.keys(bySport).length > 0 && (
              <div style={{ marginBottom:28 }}>
                <SectionHead>By Sport</SectionHead>
                <div style={{
                  display:"grid",
                  gridTemplateColumns: isMobile
                    ? "repeat(2,1fr)"
                    : "repeat(auto-fill,minmax(180px,1fr))",
                  gap:12,
                }}>
                  {Object.entries(bySport).map(([sk, data]) => {
                    const col = SPORT_COLORS[sk] ?? "#888";
                    return (
                      <div key={sk} style={{
                        background:"var(--surface)", borderRadius:12,
                        border:"1.5px solid var(--border)",
                        borderTop:`3px solid ${col}`,
                        padding:"16px 14px 14px",
                        boxShadow:"var(--sh-sm)",
                      }}>
                        <div style={{ fontSize:22, marginBottom:6 }}>{SPORT_ICONS[sk] ?? "🏅"}</div>
                        <div style={{ fontSize:13, fontWeight:700, color:col, marginBottom:10 }}>
                          {SPORT_LABELS[sk] ?? sk}
                        </div>
                        <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
                          {[
                            ["Matches", data.matches],
                            ["Wins",    data.wins],
                            ["Win %",   `${data.win_pct}%`],
                          ].map(([l, v]) => (
                            <div key={l} style={{ display:"flex", justifyContent:"space-between",
                              fontSize:13, borderBottom:"1px solid var(--border)", paddingBottom:4 }}>
                              <span style={{ color:"var(--muted)", fontWeight:500 }}>{l}</span>
                              <span style={{ fontWeight:700, color:"var(--ink)" }}>{v}</span>
                            </div>
                          ))}
                          {data.best_finish && (
                            <div style={{ marginTop:4 }}>
                              <span style={{
                                display:"inline-block",
                                fontSize:11, fontWeight:700,
                                background:`${col}15`, border:`1.5px solid ${col}30`,
                                color:col, borderRadius:20, padding:"3px 9px",
                              }}>
                                🏅 {data.best_finish}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* My Tournaments */}
            <div style={{ marginBottom:28 }}>
              <SectionHead
                action={tournaments.length > 0 && (
                  <span style={{ fontSize:12, color:"var(--primary)", fontWeight:700, cursor:"pointer" }}
                    onClick={() => navigate("/")}>
                    Explore more →
                  </span>
                )}
              >
                My Tournaments
              </SectionHead>

              {tournaments.length === 0 ? (
                <Card>
                  <div style={{ padding: isMobile ? "36px 20px" : "44px 32px", textAlign:"center" }}>
                    <div style={{ fontSize:44, marginBottom:10 }}>🏆</div>
                    <div style={{ fontFamily:"var(--font-display)", fontSize:16, fontWeight:900,
                      color:"var(--ink)", marginBottom:6, letterSpacing:-0.5 }}>
                      No tournaments yet
                    </div>
                    <div style={{ fontSize:13, color:"var(--muted)", marginBottom:20, lineHeight:1.6 }}>
                      Register for a tournament to see your match history and achievements.
                    </div>
                    <a href="/" style={{
                      display:"inline-block",
                      background:"var(--primary)", color:"#fff",
                      borderRadius:9, padding:"11px 24px",
                      fontSize:13, fontWeight:700, textDecoration:"none",
                      letterSpacing:0.3,
                    }}>
                      Explore Tournaments
                    </a>
                  </div>
                </Card>
              ) : (
                <Card>
                  <div>
                    {tournaments.slice(0, 8).map((t, idx) => {
                      const scol  = SPORT_COLORS[t.sport_key] ?? "#888";
                      const stcol = STATUS_COLORS[t.status] ?? "#888";
                      return (
                        <a key={t.tournament_id} href={`/t/${t.slug}`}
                          style={{
                            display:"flex", alignItems:"center", gap:12,
                            padding: isMobile ? "12px 14px" : "14px 18px",
                            borderBottom: idx < tournaments.slice(0,8).length - 1
                              ? "1px solid var(--border)" : "none",
                            textDecoration:"none",
                            borderLeft:`3px solid ${scol}`,
                            transition:"background 150ms",
                          }}
                          onMouseEnter={e => e.currentTarget.style.background = "var(--elevated)"}
                          onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                        >
                          {/* Sport icon */}
                          <span style={{ fontSize: isMobile ? 18 : 22, flexShrink:0 }}>
                            {SPORT_ICONS[t.sport_key] ?? "🏅"}
                          </span>

                          {/* Info */}
                          <div style={{ flex:1, minWidth:0 }}>
                            <div style={{ fontSize: isMobile ? 13 : 14, fontWeight:700, color:"var(--ink)",
                              overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
                              marginBottom:2 }}>
                              {t.name}
                            </div>
                            <div style={{ fontSize:12, color:"var(--muted)",
                              overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                              {t.event_name}{t.city ? ` · ${t.city}` : ""}
                            </div>
                            {t.stage_reached && (
                              <span style={{
                                display:"inline-block", marginTop:4,
                                fontSize:10, fontWeight:700,
                                background:`${scol}12`, border:`1px solid ${scol}30`,
                                color:scol, borderRadius:20, padding:"2px 8px",
                              }}>
                                🏅 {t.stage_reached}
                              </span>
                            )}
                          </div>

                          {/* Status */}
                          <span style={{
                            fontSize:10, fontWeight:700, textTransform:"uppercase",
                            letterSpacing:0.6, whiteSpace:"nowrap", flexShrink:0,
                            background:`${stcol}15`, border:`1.5px solid ${stcol}30`,
                            color:stcol, borderRadius:7,
                            padding: isMobile ? "3px 8px" : "4px 10px",
                          }}>
                            {STATUS_LABELS[t.status] ?? t.status}
                          </span>
                        </a>
                      );
                    })}
                  </div>
                </Card>
              )}
            </div>

          </div>

          {/* ── Right sidebar (stacks below on tablet/mobile) ── */}
          <div>

            {/* Profile edit */}
            <div style={{ marginBottom:20 }}>
              <SectionHead>Profile</SectionHead>
              <ProfileEditCard profile={profile} onSaved={setProfile} isMobile={isMobile} />
            </div>

            {/* Account card */}
            <div style={{ marginBottom:20 }}>
              <SectionHead>Account</SectionHead>
              <Card>
                <div style={{ padding:"16px 18px" }}>
                  <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase",
                    letterSpacing:0.6, color:"var(--muted)", marginBottom:4 }}>
                    Email
                  </div>
                  <div style={{ fontSize:14, fontWeight:600, color:"var(--ink)",
                    wordBreak:"break-all" }}>
                    {user.email}
                  </div>

                  {user.plan === "pro" && (
                    <div style={{ marginTop:12 }}>
                      <span style={{
                        display:"inline-block", fontSize:11, fontWeight:700,
                        background:"rgba(245,158,11,.12)", border:"1.5px solid rgba(245,158,11,.3)",
                        color:"#d97706", borderRadius:20, padding:"3px 10px",
                        textTransform:"uppercase", letterSpacing:0.8,
                      }}>
                        ⭐ Pro Plan
                      </span>
                    </div>
                  )}
                </div>
              </Card>
            </div>

            {/* Become an organiser CTA */}
            {!hasOrganiser && (
              <div style={{ marginBottom:20 }}>
                <Card style={{ border:"1.5px solid rgba(255,107,53,.25)", background:"var(--primary-dim)" }}>
                  <div style={{ padding:"18px 18px" }}>
                    <div style={{ fontSize:14, fontWeight:700, color:"var(--ink)", marginBottom:4 }}>
                      Run your own tournament?
                    </div>
                    <div style={{ fontSize:13, color:"var(--muted)", marginBottom:14, lineHeight:1.6 }}>
                      Create and manage events for your club or school — for free.
                    </div>
                    <button
                      onClick={() => { setMode("organiser"); navigate("/organiser"); }}
                      style={{
                        width:"100%", padding:"11px", borderRadius:9, border:"none",
                        background:"var(--primary)", color:"#fff",
                        fontSize:13, fontWeight:700, cursor:"pointer", letterSpacing:0.3,
                      }}>
                      Get Started as Organiser →
                    </button>
                  </div>
                </Card>
              </div>
            )}

            {/* Sign out */}
            <button
              onClick={logout}
              style={{
                width:"100%", padding:"13px", borderRadius:11,
                border:"1.5px solid rgba(229,62,62,.3)",
                background:"var(--surface)", color:"#e53e3e",
                fontSize:13, fontWeight:700, cursor:"pointer",
                boxShadow:"var(--sh-sm)", letterSpacing:0.3,
              }}>
              Sign Out
            </button>

            {/* Legal links */}
            <div style={{ display:"flex", justifyContent:"center", gap:20, marginTop:16, flexWrap:"wrap" }}>
              <a href="/privacy" target="_blank" rel="noopener noreferrer"
                style={{ fontSize:12, color:"var(--muted)", textDecoration:"none" }}>Privacy Policy</a>
              <a href="/terms" target="_blank" rel="noopener noreferrer"
                style={{ fontSize:12, color:"var(--muted)", textDecoration:"none" }}>Terms of Service</a>
            </div>

            {/* Delete account */}
            <div style={{ marginTop:20, paddingTop:20, borderTop:"1px solid var(--border)" }}>
              <p style={{ fontSize:12, color:"var(--muted)", marginBottom:10, textAlign:"center" }}>
                Deleting your account permanently removes your personal data.
              </p>
              <button
                onClick={async () => {
                  const confirmed = window.confirm(
                    "Are you sure you want to delete your account?\n\nThis will permanently remove your personal data. Your tournament history will be anonymised. This action cannot be undone."
                  );
                  if (!confirmed) return;
                  try {
                    await deleteAccount();
                    clearToken();
                    navigate("/", { replace: true });
                  } catch (e) {
                    alert("Failed to delete account: " + (e.message || "Please try again."));
                  }
                }}
                style={{
                  width:"100%", padding:"12px", borderRadius:11,
                  border:"1.5px solid rgba(229,62,62,.2)",
                  background:"transparent", color:"#9ca3af",
                  fontSize:12, cursor:"pointer", letterSpacing:0.3,
                }}>
                Delete Account
              </button>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
