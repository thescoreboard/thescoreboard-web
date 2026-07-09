/**
 * TournamentRegister — full-page tournament registration flow.
 * Steps: auth → profile → select event → registration form → success
 */
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  isLoggedIn, setToken,
  login as apiLogin, register as apiSignup, googleAuth,
  getPlayerProfile, savePlayerProfile,
  getTournamentBySlug,
} from "../api/client";
import GoogleSignInButton from "../components/auth/GoogleButton";
import PageLoader from "../components/shared/PageLoader";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

const SPORT_META = {
  table_tennis: { icon: "🏓" },
  badminton:    { icon: "🏸" },
  cricket:      { icon: "🏏" },
  football:     { icon: "⚽" },
};
const sa = k => SPORT_META[k]?.icon || "🏆";

function getRegMode(ev) {
  const pt = ev?.participant_type || "individual";
  if (pt === "team") return "team";
  if (pt === "doubles_pair") return "doubles";
  return "individual";
}

async function apiPost(path, body) {
  const r = await fetch(`${API_BASE}${path}`, {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body),
  });
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || "Request failed"); }
  return r.json();
}

const registerIndividual = (tId, p) => apiPost(`/public/tournaments/${tId}/register`, p);
const registerPair       = (tId, p) => apiPost(`/public/tournaments/${tId}/register-team`, p);
const registerTeam       = (tId, p) => apiPost(`/public/tournaments/${tId}/register-team`, p);

// ── Shared style constants ────────────────────────────────────
const inputSt = {
  width:"100%", padding:"11px 12px", borderRadius:8,
  border:"1px solid var(--border)", background:"var(--input-bg, var(--elevated))",
  color:"var(--ink)", fontSize:14, boxSizing:"border-box",
};
const labelSt = {
  display:"block", fontSize:11, fontWeight:700, color:"var(--muted)",
  marginBottom:5, textTransform:"uppercase", letterSpacing:0.5,
};
const btnPrimary = {
  width:"100%", padding:"13px", borderRadius:10, border:"none",
  background:"var(--primary)", color:"#fff", fontSize:14, fontWeight:700, cursor:"pointer",
};
const errBox = {
  background:"rgba(220,38,38,.08)", border:"1px solid rgba(220,38,38,.3)",
  borderRadius:8, padding:"9px 12px", marginBottom:14,
  fontSize:12, color:"#dc2626", fontWeight:600,
};

// ── Step indicator ────────────────────────────────────────────
function StepBar({ step, needsAuth, isSingleEvent }) {
  const base  = isSingleEvent
    ? ["profile", "form"]
    : ["profile", "select", "form"];
  const order = needsAuth ? ["auth", ...base] : base;
  const idx   = order.indexOf(step);
  return (
    <div style={{ display:"flex", alignItems:"center", gap:0, marginBottom:28 }}>
      {order.slice(0, -1).map((s, i) => {
        const done    = i < idx;
        const current = i === idx;
        return (
          <div key={s} style={{ display:"flex", alignItems:"center", flex: i < order.length - 2 ? 1 : 0 }}>
            <div style={{
              width:26, height:26, borderRadius:"50%", flexShrink:0,
              display:"flex", alignItems:"center", justifyContent:"center",
              background: done ? "#16a34a" : current ? "var(--primary)" : "var(--elevated)",
              border:`2px solid ${done ? "#16a34a" : current ? "var(--primary)" : "var(--border)"}`,
              fontSize:10, fontWeight:900,
              color: (done || current) ? "#fff" : "var(--muted)",
            }}>
              {done ? "✓" : i + 1}
            </div>
            {i < order.length - 2 && (
              <div style={{ flex:1, height:2, background: done ? "#16a34a" : "var(--border)", margin:"0 4px" }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Tournament top-bar ────────────────────────────────────────
function TournamentBar({ tournament, slug, navigate }) {
  if (!tournament) return (
    <div style={{ background:"var(--surface)", borderBottom:"1px solid var(--border)", padding:"14px 20px", height:60 }} />
  );
  const hasLogo = !!tournament.logo_url;
  const initials = tournament.name.split(" ").slice(0,2).map(w => w[0] || "").join("").toUpperCase() || "T";
  return (
    <div style={{ background:"var(--surface)", borderBottom:"1px solid var(--border)", padding:"10px 20px", display:"flex", alignItems:"center", gap:12, position:"sticky", top:0, zIndex:50 }}>
      <button onClick={() => navigate(`/t/${slug}`)} style={{ background:"none", border:"1px solid var(--border)", borderRadius:6, cursor:"pointer", color:"var(--muted)", fontSize:16, lineHeight:1, padding:"4px 10px", flexShrink:0 }}>←</button>
      <div style={{ width:34, height:34, borderRadius:8, background:"var(--elevated)", border:"1px solid var(--border)", overflow:"hidden", flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center" }}>
        {hasLogo
          ? <img src={tournament.logo_url} alt="" style={{ width:"100%", height:"100%", objectFit:"cover" }} />
          : <span style={{ fontFamily:"var(--font-display)", fontSize:11, fontWeight:900, color:"var(--primary)" }}>{initials}</span>
        }
      </div>
      <div style={{ minWidth:0 }}>
        <div style={{ fontFamily:"var(--font-display)", fontSize:13, fontWeight:900, textTransform:"uppercase", letterSpacing:"-0.5px", color:"var(--ink)", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
          {tournament.name}
        </div>
        <div style={{ fontSize:10, color:"var(--muted)", marginTop:1 }}>Registration</div>
      </div>
    </div>
  );
}

// ── Step: Auth ────────────────────────────────────────────────
function AuthStep({ onDone }) {
  const [mode,    setMode]    = useState("login");
  const [form,    setForm]    = useState({ name:"", email:"", password:"" });
  const [error,   setError]   = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!form.email || !form.password) return setError("Email and password are required.");
    if (mode === "signup" && !form.name.trim()) return setError("Name is required.");
    setLoading(true); setError("");
    try {
      const d = await (mode === "signup" ? apiSignup(form) : apiLogin(form));
      setToken(d.access_token);
      onDone();
    } catch(e) { setError(e.message || "Authentication failed."); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <div style={{ textAlign:"center", marginBottom:24 }}>
        <div style={{ fontFamily:"var(--font-display)", fontSize:20, fontWeight:900, textTransform:"uppercase", letterSpacing:-0.5, color:"var(--ink)", marginBottom:6 }}>
          Sign In to Register
        </div>
        <div style={{ fontSize:13, color:"var(--muted)" }}>You need an account to register for this tournament</div>
      </div>

      {/* Toggle */}
      <div style={{ display:"flex", background:"var(--elevated)", borderRadius:10, padding:3, marginBottom:20, border:"1px solid var(--border)" }}>
        {["login","signup"].map(m => (
          <button key={m} onClick={() => { setMode(m); setError(""); }} style={{
            flex:1, padding:"8px 0", borderRadius:8, border:"none", cursor:"pointer",
            background: mode === m ? "var(--surface)" : "transparent",
            color: mode === m ? "var(--ink)" : "var(--muted)",
            fontWeight: mode === m ? 700 : 500, fontSize:13,
            boxShadow: mode === m ? "0 1px 4px rgba(0,0,0,.08)" : "none", transition:"all .15s",
          }}>
            {m === "login" ? "Sign In" : "Create Account"}
          </button>
        ))}
      </div>

      <GoogleSignInButton onSuccess={onDone} onError={msg => setError(msg)} />

      <div style={{ display:"flex", alignItems:"center", gap:10, margin:"16px 0" }}>
        <div style={{ flex:1, height:1, background:"var(--border)" }} />
        <span style={{ fontSize:11, color:"var(--muted)", fontWeight:600 }}>OR</span>
        <div style={{ flex:1, height:1, background:"var(--border)" }} />
      </div>

      {mode === "signup" && (
        <div style={{ marginBottom:14 }}>
          <label style={labelSt}>Your Name</label>
          <input className="input" style={inputSt} placeholder="Rahul Sharma" autoFocus
            value={form.name} onChange={e => setForm(f => ({...f, name:e.target.value}))} />
        </div>
      )}

      <div style={{ marginBottom:14 }}>
        <label style={labelSt}>Email</label>
        <input className="input" type="email" style={inputSt} placeholder="you@email.com"
          value={form.email} onChange={e => setForm(f => ({...f, email:e.target.value}))}
          onKeyDown={e => e.key === "Enter" && submit()} />
      </div>

      <div style={{ marginBottom:20 }}>
        <label style={labelSt}>Password</label>
        <input className="input" type="password" style={inputSt} placeholder="••••••••"
          value={form.password} onChange={e => setForm(f => ({...f, password:e.target.value}))}
          onKeyDown={e => e.key === "Enter" && submit()} />
      </div>

      {error && <div style={errBox}>{error}</div>}

      <button onClick={submit} disabled={loading} style={{ ...btnPrimary, opacity:loading ? 0.65 : 1 }}>
        {loading ? "Please wait…" : mode === "login" ? "Sign In →" : "Create Account →"}
      </button>
    </div>
  );
}

// ── Step: Player Profile ──────────────────────────────────────
function ProfileStep({ existingProfile, onDone }) {
  const [form, setForm] = useState({
    name:     existingProfile?.name     || "",
    phone:    existingProfile?.phone    || "",
    age:      existingProfile?.age      != null ? String(existingProfile.age) : "",
    gender:   existingProfile?.gender   || "Male",
    location: existingProfile?.location || "",
  });
  const [error,   setError]   = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!form.name.trim()) return setError("Name is required.");
    setLoading(true); setError("");
    try {
      const saved = await savePlayerProfile({
        name:     form.name.trim(),
        phone:    form.phone.trim()    || null,
        age:      parseInt(form.age)   || null,
        gender:   form.gender,
        location: form.location.trim() || null,
      });
      onDone(saved);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <div>
      <div style={{ marginBottom:20 }}>
        <div style={{ fontFamily:"var(--font-display)", fontSize:18, fontWeight:900, textTransform:"uppercase", letterSpacing:-0.5, color:"var(--ink)", marginBottom:6 }}>
          Your Player Profile
        </div>
        <div style={{ fontSize:13, color:"var(--muted)", lineHeight:1.5 }}>
          Your details will be used when registering for events. You can update them anytime.
        </div>
      </div>

      <div style={{ marginBottom:14 }}>
        <label style={labelSt}>Full Name *</label>
        <input className="input" style={inputSt} autoFocus placeholder="Rahul Sharma"
          value={form.name} onChange={e => setForm(f => ({...f, name:e.target.value}))} />
      </div>

      <div style={{ marginBottom:14 }}>
        <label style={labelSt}>Phone</label>
        <input className="input" type="tel" style={inputSt} placeholder="9876543210"
          value={form.phone} onChange={e => setForm(f => ({...f, phone:e.target.value}))} />
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:14 }}>
        <div>
          <label style={labelSt}>Age</label>
          <input className="input" type="number" style={inputSt} placeholder="24" min="5" max="99"
            value={form.age} onChange={e => setForm(f => ({...f, age:e.target.value}))} />
        </div>
        <div>
          <label style={labelSt}>Gender</label>
          <select className="input" style={inputSt} value={form.gender} onChange={e => setForm(f => ({...f, gender:e.target.value}))}>
            <option>Male</option><option>Female</option><option>Other</option>
          </select>
        </div>
      </div>

      <div style={{ marginBottom:20 }}>
        <label style={labelSt}>City / Location</label>
        <input className="input" style={inputSt} placeholder="e.g. Chennai"
          value={form.location} onChange={e => setForm(f => ({...f, location:e.target.value}))} />
      </div>

      {error && <div style={errBox}>{error}</div>}

      <button onClick={submit} disabled={loading} style={{ ...btnPrimary, opacity:loading ? 0.65 : 1 }}>
        {loading ? "Saving…" : "Save & Continue →"}
      </button>
    </div>
  );
}

// ── Step: Event Select ────────────────────────────────────────
function SelectStep({ events, profile, onSelect }) {
  const open = events.filter(ev => ev.is_configured !== false);
  const modeLabel = { team:"Team Sport", doubles:"Doubles Pair", individual:"Individual" };

  if (open.length === 0) {
    return (
      <div style={{ textAlign:"center", padding:"40px 0" }}>
        <div style={{ fontSize:36, marginBottom:14 }}>🔒</div>
        <div style={{ fontFamily:"var(--font-display)", fontSize:16, fontWeight:900, textTransform:"uppercase", color:"var(--ink)", marginBottom:8 }}>
          Registration Closed
        </div>
        <p style={{ fontSize:13, color:"var(--muted)" }}>No events are open for registration right now.</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom:20 }}>
        <div style={{ fontFamily:"var(--font-display)", fontSize:18, fontWeight:900, textTransform:"uppercase", letterSpacing:-0.5, color:"var(--ink)", marginBottom:6 }}>
          Pick an Event
        </div>
        {profile?.name && (
          <div style={{ fontSize:13, color:"var(--muted)" }}>
            Hi <strong style={{ color:"var(--ink)" }}>{profile.name}</strong>! Choose which event to register for.
          </div>
        )}
      </div>

      {open.map(ev => {
        const mode = getRegMode(ev);
        return (
          <div key={ev.event_id} onClick={() => onSelect(ev)} style={{
            display:"flex", alignItems:"center", gap:14, padding:"14px 16px",
            borderRadius:14, marginBottom:8, background:"var(--surface)",
            border:"1.5px solid var(--border)", borderLeft:"4px solid var(--accent)",
            cursor:"pointer", boxShadow:"var(--sh-sm, 0 1px 4px rgba(0,0,0,.06))",
            transition:"box-shadow .15s",
          }}
            onMouseEnter={e => e.currentTarget.style.boxShadow="0 4px 16px rgba(0,0,0,.12)"}
            onMouseLeave={e => e.currentTarget.style.boxShadow="var(--sh-sm, 0 1px 4px rgba(0,0,0,.06))"}
          >
            <div style={{ width:44, height:44, borderRadius:12, background:"var(--accent-dim)", border:"1px solid var(--accent-border, var(--border))", display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0, fontFamily:"var(--font-display)", fontSize:12, fontWeight:900, color:"var(--accent, var(--primary))" }}>
              {sa(ev.sport_key)}
            </div>
            <div style={{ flex:1, minWidth:0 }}>
              <div style={{ fontFamily:"var(--font-display)", fontSize:13, fontWeight:900, textTransform:"uppercase", letterSpacing:"-0.5px", color:"var(--ink)", marginBottom:6, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                {ev.name}
              </div>
              <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
                <span style={{ fontFamily:"var(--font-display)", fontSize:8, fontWeight:900, textTransform:"uppercase", letterSpacing:1, background:"var(--accent-dim)", color:"var(--accent, var(--primary))", border:"1px solid var(--accent-border, var(--border))", padding:"2px 8px", borderRadius:20 }}>
                  {modeLabel[mode] || "Individual"}
                </span>
                {ev.format && (
                  <span style={{ fontFamily:"var(--font-display)", fontSize:8, fontWeight:900, textTransform:"uppercase", letterSpacing:1, background:"var(--elevated)", color:"var(--muted)", border:"1px solid var(--border)", padding:"2px 8px", borderRadius:20 }}>
                    {ev.format.replace(/_/g, " ")}
                  </span>
                )}
              </div>
            </div>
            <div style={{ color:"var(--accent, var(--primary))", fontSize:20, flexShrink:0 }}>›</div>
          </div>
        );
      })}
    </div>
  );
}

// ── Step: Individual form ─────────────────────────────────────
function IndividualFormStep({ event, tournament, profile, onSuccess, onBack }) {
  const [form, setForm] = useState({
    name:   profile?.name   || "",
    phone:  profile?.phone  || "",
    age:    profile?.age    != null ? String(profile.age) : "",
    gender: profile?.gender || "Male",
  });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  const submit = async () => {
    if (!form.name.trim())  return setError("Name is required.");
    if (!form.phone.trim()) return setError("Phone number is required.");
    setLoading(true); setError("");
    try {
      await registerIndividual(tournament.tournament_id, {
        name: form.name.trim(), phone: form.phone.trim(),
        age: parseInt(form.age) || null, gender: form.gender,
        event_ids: [event.event_id],
      });
      onSuccess(form.name.trim());
    } catch(e) { setError(e.message); } finally { setLoading(false); }
  };

  return (
    <div>
      <FormHeader event={event} subtitle="Individual Registration" onBack={onBack} />
      {profile?.name && (
        <div style={{ background:"rgba(var(--accent-rgb, 255,107,53),.06)", border:"1px solid var(--accent-border, var(--border))", borderRadius:8, padding:"10px 13px", marginBottom:16, fontSize:12, color:"var(--muted)" }}>
          Pre-filled from your profile — edit if needed.
        </div>
      )}
      <div style={{ marginBottom:14 }}>
        <label style={labelSt}>Name *</label>
        <input className="input" style={inputSt} autoFocus value={form.name} onChange={e => setForm(f => ({...f, name:e.target.value}))} />
      </div>
      <div style={{ marginBottom:14 }}>
        <label style={labelSt}>Phone *</label>
        <input className="input" type="tel" style={inputSt} value={form.phone} onChange={e => setForm(f => ({...f, phone:e.target.value}))} />
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:20 }}>
        <div>
          <label style={labelSt}>Age</label>
          <input className="input" type="number" style={inputSt} value={form.age} min="5" max="99" onChange={e => setForm(f => ({...f, age:e.target.value}))} />
        </div>
        <div>
          <label style={labelSt}>Gender</label>
          <select className="input" style={inputSt} value={form.gender} onChange={e => setForm(f => ({...f, gender:e.target.value}))}>
            <option>Male</option><option>Female</option><option>Other</option>
          </select>
        </div>
      </div>
      {error && <div style={errBox}>{error}</div>}
      <button onClick={submit} disabled={loading} style={{ ...btnPrimary, opacity:loading ? 0.65 : 1 }}>
        {loading ? "Registering…" : "Confirm Registration →"}
      </button>
    </div>
  );
}

// ── Step: Doubles form ────────────────────────────────────────
function DoublesFormStep({ event, tournament, profile, onSuccess, onBack }) {
  const isMixed = event.sport_config?.mixed;
  const [form, setForm] = useState({ p1: profile?.name || "", p2:"", phone: profile?.phone || "" });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  const submit = async () => {
    if (!form.p1.trim()) return setError(`${isMixed ? "Male player" : "Player 1"} name is required.`);
    if (!form.p2.trim()) return setError(`${isMixed ? "Female player" : "Player 2"} name is required.`);
    if (form.p1.trim().toLowerCase() === form.p2.trim().toLowerCase())
      return setError("Both players must be different people.");
    setLoading(true); setError("");
    try {
      await registerPair(tournament.tournament_id, {
        name: `${form.p1.trim()} & ${form.p2.trim()}`,
        contact_phone: form.phone.trim() || "",
        sport_key: event.sport_key, event_id: event.event_id,
        members: [
          { name: form.p1.trim(), role: isMixed ? "male"   : "player1" },
          { name: form.p2.trim(), role: isMixed ? "female" : "player2" },
        ],
      });
      onSuccess(`${form.p1.trim()} & ${form.p2.trim()}`);
    } catch(e) { setError(e.message); } finally { setLoading(false); }
  };

  return (
    <div>
      <FormHeader event={event} subtitle={isMixed ? "Mixed Doubles" : "Doubles Registration"} onBack={onBack} />
      <div style={{ background:"var(--elevated)", border:"1px solid var(--border)", borderRadius:8, padding:"10px 14px", marginBottom:16, fontSize:12, color:"var(--muted)", lineHeight:1.5 }}>
        Enter both partners. The organiser will seed the draw.
      </div>
      <div style={{ border:"2px solid var(--border)", borderLeft:"4px solid var(--primary)", borderRadius:8, padding:"14px 16px", marginBottom:10, background:"var(--surface)" }}>
        <div style={{ fontFamily:"var(--font-display)", fontSize:9, fontWeight:800, textTransform:"uppercase", letterSpacing:2, color:"var(--primary)", marginBottom:10 }}>
          {isMixed ? "Male Player *" : "Player 1 *"}
        </div>
        <input className="input" style={inputSt} autoFocus placeholder="Full name" value={form.p1} onChange={e => setForm(f => ({...f, p1:e.target.value}))} />
      </div>
      <div style={{ border:"2px solid var(--border)", borderLeft:"4px solid #92700A", borderRadius:8, padding:"14px 16px", marginBottom:14, background:"var(--surface)" }}>
        <div style={{ fontFamily:"var(--font-display)", fontSize:9, fontWeight:800, textTransform:"uppercase", letterSpacing:2, color:"#92700A", marginBottom:10 }}>
          {isMixed ? "Female Player *" : "Player 2 *"}
        </div>
        <input className="input" style={inputSt} placeholder="Full name" value={form.p2} onChange={e => setForm(f => ({...f, p2:e.target.value}))} />
      </div>
      <div style={{ marginBottom:20 }}>
        <label style={labelSt}>Contact Phone (optional)</label>
        <input className="input" type="tel" style={inputSt} placeholder="9876543210" value={form.phone} onChange={e => setForm(f => ({...f, phone:e.target.value}))} />
      </div>
      {error && <div style={errBox}>{error}</div>}
      <button onClick={submit} disabled={loading} style={{ ...btnPrimary, opacity:loading ? 0.65 : 1 }}>
        {loading ? "Registering…" : "Register Pair →"}
      </button>
    </div>
  );
}

// ── Step: Team form ───────────────────────────────────────────
function TeamFormStep({ event, tournament, onSuccess, onBack }) {
  const cfg        = event.sport_config || {};
  const teamSize   = cfg.team_size   || 11;
  const subs       = cfg.substitutes || 0;
  const totalSlots = teamSize + subs;

  const emptyMember = (role) => ({ name:"", role, jersey:"", age:"" });
  const [teamName, setTeamName] = useState("");
  const [phone,    setPhone]    = useState("");
  const [members,  setMembers]  = useState(() => [
    emptyMember("captain"),
    emptyMember("vice_captain"),
    ...Array.from({ length: Math.max(0, Math.min(totalSlots - 2, 9)) }, () => emptyMember("player")),
  ]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  const updateMember = (i, field, val) =>
    setMembers(prev => prev.map((m, idx) => idx === i ? {...m, [field]:val} : m));

  const submit = async () => {
    if (!teamName.trim()) return setError("Team name is required.");
    const captain = members.find(m => m.role === "captain" && m.name.trim());
    if (!captain) return setError("Captain name is required.");
    const valid = members.filter(m => m.name.trim()).map(m => ({
      name: m.name.trim(), role: m.role,
      jersey_number: m.jersey ? parseInt(m.jersey) || null : null,
      age: m.age ? parseInt(m.age) || null : null,
    }));
    setLoading(true); setError("");
    try {
      await registerTeam(tournament.tournament_id, {
        name: teamName.trim(), contact_phone: phone.trim(),
        sport_key: event.sport_key, event_ids: [event.event_id], members: valid,
      });
      onSuccess(teamName.trim());
    } catch(e) { setError(e.message); } finally { setLoading(false); }
  };

  const roleLabel = r => r === "vice_captain" ? "Vice Captain" : r.charAt(0).toUpperCase() + r.slice(1);

  return (
    <div>
      <FormHeader event={event} subtitle="Team Registration" onBack={onBack} />
      <div style={{ marginBottom:14 }}>
        <label style={labelSt}>Team Name *</label>
        <input className="input" style={inputSt} autoFocus placeholder="e.g. FC Rangers" value={teamName} onChange={e => setTeamName(e.target.value)} />
      </div>
      <div style={{ marginBottom:16 }}>
        <label style={labelSt}>Captain's Contact Phone</label>
        <input className="input" type="tel" style={inputSt} placeholder="9876543210" value={phone} onChange={e => setPhone(e.target.value)} />
      </div>
      <div style={{ background:"var(--elevated)", border:"1px solid var(--border)", borderRadius:8, padding:"8px 14px", marginBottom:14, fontSize:12, color:"var(--muted)" }}>
        {teamSize} on field{subs > 0 ? ` + ${subs} subs` : ""} · Fill in your squad below
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 54px 48px 100px 28px", gap:5, marginBottom:4 }}>
        {["Player Name","Jersey","Age","Role",""].map(h => (
          <span key={h} style={{ fontSize:9, fontWeight:800, textTransform:"uppercase", letterSpacing:1, color:"var(--muted)" }}>{h}</span>
        ))}
      </div>
      {members.map((m, i) => (
        <div key={i} style={{ display:"grid", gridTemplateColumns:"1fr 54px 48px 100px 28px", gap:5, marginBottom:5, alignItems:"center" }}>
          <input className="input" style={{ ...inputSt, padding:"8px 10px" }}
            placeholder={i === 0 ? "Captain *" : i === 1 ? "Vice Captain" : `Player ${i+1}`}
            value={m.name} onChange={e => updateMember(i, "name", e.target.value)} />
          <input className="input" type="number" placeholder="#" style={{ ...inputSt, padding:"8px 6px", textAlign:"center" }}
            value={m.jersey} onChange={e => updateMember(i, "jersey", e.target.value)} />
          <input className="input" type="number" placeholder="Age" min="5" max="60" style={{ ...inputSt, padding:"8px 6px", textAlign:"center" }}
            value={m.age} onChange={e => updateMember(i, "age", e.target.value)} />
          <select className="input" style={{ ...inputSt, padding:"8px 6px" }} value={m.role} onChange={e => updateMember(i, "role", e.target.value)}>
            {["captain","vice_captain","player"].map(r => <option key={r} value={r}>{roleLabel(r)}</option>)}
          </select>
          <button onClick={() => setMembers(p => p.filter((_,idx) => idx !== i))} disabled={members.length <= 1}
            style={{ background:"none", border:"none", color:"var(--muted)", cursor:"pointer", fontSize:18, padding:0, opacity: members.length <= 1 ? 0.3 : 1 }}>×</button>
        </div>
      ))}
      {members.length < totalSlots + 3 && (
        <button onClick={() => setMembers(p => [...p, emptyMember("player")])} style={{ width:"100%", padding:"7px 0", background:"none", border:"1.5px dashed var(--border)", borderRadius:6, color:"var(--muted)", fontFamily:"var(--font-display)", fontSize:10, fontWeight:700, letterSpacing:1, textTransform:"uppercase", cursor:"pointer", marginBottom:14, marginTop:4 }}>
          + Add Player
        </button>
      )}
      <p style={{ fontSize:11, color:"var(--muted)", marginBottom:14 }}>
        {members.filter(m => m.name.trim()).length} of {totalSlots} slots filled
      </p>
      {error && <div style={errBox}>{error}</div>}
      <button onClick={submit} disabled={loading} style={{ ...btnPrimary, opacity:loading ? 0.65 : 1 }}>
        {loading ? "Registering…" : "Register Team →"}
      </button>
    </div>
  );
}

// ── Form header (back + event name) ──────────────────────────
function FormHeader({ event, subtitle, onBack }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:20, paddingBottom:16, borderBottom:"1px solid var(--border)" }}>
      <button onClick={onBack} style={{ background:"none", border:"none", cursor:"pointer", color:"var(--muted)", fontSize:22, padding:"0 2px", lineHeight:1 }}>←</button>
      <div style={{ width:32, height:32, borderRadius:6, background:"var(--primary-dim, rgba(255,107,53,.1))", display:"flex", alignItems:"center", justifyContent:"center", fontFamily:"var(--font-display)", fontSize:11, fontWeight:900, color:"var(--primary)", flexShrink:0 }}>
        {sa(event.sport_key)}
      </div>
      <div>
        <div style={{ fontFamily:"var(--font-display)", fontSize:13, fontWeight:900, textTransform:"uppercase", letterSpacing:-0.5, color:"var(--ink)" }}>{event.name}</div>
        <div style={{ fontSize:11, color:"var(--muted)", marginTop:1 }}>{subtitle}</div>
      </div>
    </div>
  );
}

// ── Step: Registration form dispatcher ────────────────────────
function FormStep({ event, tournament, profile, onSuccess, onBack }) {
  const mode = getRegMode(event);
  if (mode === "team")    return <TeamFormStep    event={event} tournament={tournament} onSuccess={onSuccess} onBack={onBack} />;
  if (mode === "doubles") return <DoublesFormStep event={event} tournament={tournament} profile={profile} onSuccess={onSuccess} onBack={onBack} />;
  return <IndividualFormStep event={event} tournament={tournament} profile={profile} onSuccess={onSuccess} onBack={onBack} />;
}

// ── Step: Success ─────────────────────────────────────────────
function SuccessStep({ name, event, slug, navigate }) {
  return (
    <div style={{ textAlign:"center", padding:"36px 0" }}>
      <div style={{ width:72, height:72, borderRadius:"50%", background:"rgba(34,197,94,.12)", border:"2px solid rgba(34,197,94,.3)", margin:"0 auto 20px", display:"flex", alignItems:"center", justifyContent:"center", fontSize:32 }}>✓</div>
      <div style={{ fontFamily:"var(--font-display)", fontSize:24, fontWeight:900, textTransform:"uppercase", letterSpacing:-1, color:"#16a34a", marginBottom:10 }}>
        You're In!
      </div>
      <p style={{ fontSize:14, color:"var(--muted)", lineHeight:1.7, marginBottom:28 }}>
        <strong style={{ color:"var(--ink)" }}>{name}</strong> has been registered for{" "}
        <strong style={{ color:"var(--ink)" }}>{event?.name}</strong>.
      </p>
      <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
        <button onClick={() => navigate(`/t/${slug}`)} style={btnPrimary}>
          View Tournament →
        </button>
        <button onClick={() => navigate("/player")} style={{ ...btnPrimary, background:"none", color:"var(--muted)", border:"1px solid var(--border)" }}>
          My Registrations
        </button>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────
export default function TournamentRegister() {
  const { slug } = useParams();
  const navigate = useNavigate();

  const [tournament,  setTournament]  = useState(null);
  const [events,      setEvents]      = useState([]);
  const [loadError,   setLoadError]   = useState(null);
  const [step,        setStep]        = useState(null);
  const [profile,     setProfile]     = useState(null);
  const [selEvent,    setSelEvent]    = useState(null);
  const [regName,     setRegName]     = useState("");

  // Derived: open events & single-event shortcut flag
  const openEvents    = events.filter(ev => ev.is_configured !== false);
  const isSingleEvent = openEvents.length === 1;

  // After profile is confirmed, skip "select" if there's only one event
  const advanceToFormOrSelect = (evArr) => {
    const open = (evArr || []).filter(ev => ev.is_configured !== false);
    if (open.length === 1) {
      setSelEvent(open[0]);
      setStep("form");
    } else {
      setStep("select");
    }
  };

  useEffect(() => {
    async function load() {
      try {
        const d = await getTournamentBySlug(slug);
        setTournament(d.tournament);
        setEvents(d.events || []);

        if (!d.tournament.registration_open) {
          setLoadError("Registration is not currently open for this tournament.");
          return;
        }

        if (isLoggedIn()) {
          const prof = await getPlayerProfile().catch(() => null);
          setProfile(prof);
          // Use d.events directly — state not yet flushed at this point
          if (prof) advanceToFormOrSelect(d.events || []);
          else setStep("profile");
        } else {
          setStep("auth");
        }
      } catch(e) {
        setLoadError(e.message || "Tournament not found.");
      }
    }
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const afterAuth = async () => {
    try {
      const prof = await getPlayerProfile().catch(() => null);
      setProfile(prof);
      if (prof) advanceToFormOrSelect(events);
      else setStep("profile");
    } catch {
      setStep("profile");
    }
  };

  // ── Loading ──
  if (!step && !loadError) return <PageLoader />;

  // ── Error ──
  if (loadError) return (
    <>
      <TournamentBar tournament={tournament} slug={slug} navigate={navigate} />
      <div style={{ maxWidth:400, margin:"60px auto", padding:"0 24px", textAlign:"center" }}>
        <div style={{ fontSize:40, marginBottom:16 }}>😕</div>
        <p style={{ fontSize:14, color:"var(--muted)", marginBottom:24 }}>{loadError}</p>
        <button onClick={() => navigate(`/t/${slug}`)} style={{ ...btnPrimary, maxWidth:220, margin:"0 auto" }}>
          Back to Tournament
        </button>
      </div>
    </>
  );

  const showBar = step !== "success";

  return (
    <div className="app" style={{ minHeight:"100vh", background:"var(--bg)" }}>
      <TournamentBar tournament={tournament} slug={slug} navigate={navigate} />

      <div style={{ maxWidth:480, margin:"0 auto", padding:"28px 20px 48px" }}>
        {showBar && <StepBar step={step} needsAuth={!isLoggedIn()} isSingleEvent={isSingleEvent} />}

        {step === "auth"    && <AuthStep onDone={afterAuth} />}
        {step === "profile" && (
          <ProfileStep
            existingProfile={profile}
            onDone={p => { setProfile(p); advanceToFormOrSelect(events); }}
          />
        )}
        {step === "select"  && <SelectStep events={events} profile={profile} onSelect={ev => { setSelEvent(ev); setStep("form"); }} />}
        {step === "form"    && selEvent && (
          <FormStep
            event={selEvent}
            tournament={tournament}
            profile={profile}
            onSuccess={n => { setRegName(n); setStep("success"); }}
            onBack={() => {
              setSelEvent(null);
              // Single-event: no select step to go back to — go to profile instead
              setStep(isSingleEvent ? "profile" : "select");
            }}
          />
        )}
        {step === "success" && <SuccessStep name={regName} event={selEvent} slug={slug} navigate={navigate} />}
      </div>
    </div>
  );
}
