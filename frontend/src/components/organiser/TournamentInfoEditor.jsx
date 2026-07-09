/**
 * TournamentInfoEditor — 4 focused sections:
 *   overview      – plain textarea
 *   prize_pool    – structured list of { category, position, amount }
 *   rules         – plain textarea
 *   contact       – structured list of { name, phone } + entry_fee + reg_deadline
 *
 * Saved as a single JSON dict to tournament.tournament_info via PATCH.
 * Supports lock/edit mode: view mode after save, edit mode on demand.
 */
import { useState } from "react";
import { updateTournament } from "../../api/client";
import DatePicker from "../shared/DatePicker";

// Fixed podium positions + sentinel for custom entry
const STANDARD_POSITIONS = ["1st Place", "2nd Place", "3rd Place"];
const CUSTOM_SENTINEL     = "__custom__";

// Returns true if a position value is NOT one of the standard ones.
// Blank ("") counts as custom too — that's the value right after picking
// "Custom…", before the organiser has typed anything into the text input.
function isCustomPosition(val) {
  return !STANDARD_POSITIONS.includes(val);
}

const empty = () => ({
  overview:   "",
  prize_pool: [],          // [{ category, position, amount }]
  rules:      "",
  contact: {
    entry_fee:    "",
    reg_deadline: "",
    persons:      [],      // [{ name, phone }]
  },
});

function parse(raw) {
  if (!raw) return empty();
  return {
    overview:   raw.overview   || "",
    prize_pool: raw.prize_pool || [],
    rules:      raw.rules      || "",
    contact: {
      entry_fee:    raw.contact?.entry_fee    || "",
      reg_deadline: raw.contact?.reg_deadline || "",
      persons:      raw.contact?.persons      || [],
    },
  };
}

function hasContent(info) {
  if (!info) return false;
  return !!(info.overview || (info.prize_pool?.length > 0) || info.rules ||
    info.contact?.entry_fee || info.contact?.reg_deadline || info.contact?.persons?.length > 0);
}

// ── Small shared styles ────────────────────────────────────────
const labelStyle = {
  display: "block", fontSize: 11, fontWeight: 700,
  textTransform: "uppercase", letterSpacing: 0.5,
  color: "var(--muted)", marginBottom: 5,
};
const inputStyle = {
  width: "100%", padding: "9px 12px", borderRadius: 8,
  border: "1.5px solid var(--border)",
  background: "var(--input-bg, var(--elevated))",
  color: "var(--ink)", fontSize: 13, boxSizing: "border-box",
  fontFamily: "inherit", outline: "none", transition: "border-color .15s",
};
const sectionHeadStyle = {
  fontSize: 11, fontWeight: 800, textTransform: "uppercase",
  letterSpacing: 1.5, color: "var(--muted)", marginBottom: 0,
};
const addBtnStyle = {
  background: "none", border: "1.5px dashed var(--border)",
  borderRadius: 8, padding: "8px 14px", cursor: "pointer",
  fontSize: 12, fontWeight: 700, color: "var(--muted)",
  width: "100%", fontFamily: "inherit", marginTop: 8,
  transition: "border-color .15s, color .15s",
};
const removeBtnStyle = {
  background: "none", border: "none", cursor: "pointer",
  color: "var(--muted)", fontSize: 18, lineHeight: 1,
  padding: "0 6px", flexShrink: 0, fontFamily: "inherit",
};

// ── Section wrapper ────────────────────────────────────────────
function Section({ title, icon, children }) {
  return (
    <div style={{
      background: "var(--surface)", border: "1.5px solid var(--border)",
      borderRadius: 12, padding: "18px 18px 14px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
        <span style={sectionHeadStyle}>{title}</span>
      </div>
      {children}
    </div>
  );
}

// ── Read-only view helpers ─────────────────────────────────────
function ReadField({ label, value }) {
  if (!value) return null;
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--muted)", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13, color: "var(--ink)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{value}</div>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div style={{ fontSize: 13, color: "var(--subtle)", fontStyle: "italic" }}>{text}</div>
  );
}

export default function TournamentInfoEditor({ orgId, tournamentId, initialInfo, onSaved }) {
  const [info,      setInfo]      = useState(() => parse(initialInfo));
  const [isEditing, setIsEditing] = useState(() => !hasContent(initialInfo));
  const [saving,    setSaving]    = useState(false);
  const [saved,     setSaved]     = useState(false);
  const [error,     setError]     = useState("");
  const [editSnap,  setEditSnap]  = useState(null); // snapshot to revert on cancel

  const set = (key, val) => { setInfo(p => ({ ...p, [key]: val })); setSaved(false); };
  const setContact = (key, val) =>
    setInfo(p => ({ ...p, contact: { ...p.contact, [key]: val } }));

  // ── Prize pool helpers ───────────────────────────────────────
  const addPrize = () =>
    set("prize_pool", [...info.prize_pool, { category: "", position: "1st Place", amount: "" }]);
  const updatePrize = (i, field, val) =>
    set("prize_pool", info.prize_pool.map((p, idx) => idx === i ? { ...p, [field]: val } : p));
  const removePrize = (i) =>
    set("prize_pool", info.prize_pool.filter((_, idx) => idx !== i));

  // ── Contact person helpers ───────────────────────────────────
  const addPerson = () =>
    setInfo(p => ({ ...p, contact: { ...p.contact, persons: [...p.contact.persons, { name: "", phone: "" }] } }));
  const updatePerson = (i, field, val) =>
    setInfo(p => ({
      ...p,
      contact: {
        ...p.contact,
        persons: p.contact.persons.map((c, idx) => idx === i ? { ...c, [field]: val } : c),
      },
    }));
  const removePerson = (i) =>
    setInfo(p => ({
      ...p,
      contact: { ...p.contact, persons: p.contact.persons.filter((_, idx) => idx !== i) },
    }));

  // ── Edit / Cancel ────────────────────────────────────────────
  const startEdit = () => {
    setEditSnap(JSON.parse(JSON.stringify(info))); // snapshot
    setIsEditing(true);
    setSaved(false);
    setError("");
  };
  const cancelEdit = () => {
    if (editSnap) setInfo(editSnap);
    setEditSnap(null);
    setIsEditing(false);
    setError("");
  };

  // ── Save ─────────────────────────────────────────────────────
  const handleSave = async () => {
    setSaving(true); setError(""); setSaved(false);
    try {
      await updateTournament(orgId, tournamentId, { tournament_info: info });
      setSaved(true);
      setIsEditing(false);
      setEditSnap(null);
      onSaved?.(info);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e.message || "Failed to save.");
    } finally {
      setSaving(false);
    }
  };

  const focusStyle  = (e) => { e.target.style.borderColor = "var(--primary, #FF6B35)"; };
  const blurStyle   = (e) => { e.target.style.borderColor = "var(--border)"; };
  const primaryColor = "var(--primary, #FF6B35)";

  // ── READ-ONLY VIEW ────────────────────────────────────────────
  if (!isEditing) {
    return (
      <div>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
          <div style={sectionHeadStyle}>Info &amp; Rules</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {saved && (
              <span style={{ fontSize: 12, color: "var(--primary)", fontWeight: 700 }}>✓ Saved</span>
            )}
            <button onClick={startEdit}
              style={{
                padding: "7px 18px", borderRadius: 8,
                border: "1.5px solid var(--border)",
                background: "var(--surface)", color: "var(--ink)",
                fontWeight: 700, fontSize: 12, cursor: "pointer",
                fontFamily: "inherit", display: "flex", alignItems: "center", gap: 6,
              }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
              Edit
            </button>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

          {/* Overview — read */}
          <Section title="Tournament Overview" icon="📋">
            {info.overview
              ? <div style={{ fontSize: 13, color: "var(--ink)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{info.overview}</div>
              : <EmptyState text="No overview added." />
            }
          </Section>

          {/* Prize Pool — read */}
          <Section title="Prize Pool" icon="🏆">
            {info.prize_pool.length === 0 ? (
              <EmptyState text="No prizes added." />
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      {["Category", "Position", "Amount / Prize"].map(h => (
                        <th key={h} style={{ textAlign: "left", paddingBottom: 8, fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {info.prize_pool.map((prize, i) => (
                      <tr key={i}>
                        <td style={{ padding: "7px 12px 7px 0", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>{prize.category || "—"}</td>
                        <td style={{ padding: "7px 12px 7px 0", fontWeight: 700, color: "var(--ink)", borderBottom: "1px solid var(--border)" }}>{prize.position}</td>
                        <td style={{ padding: "7px 0 7px 0", color: "var(--primary)", fontWeight: 700, borderBottom: "1px solid var(--border)" }}>{prize.amount || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          {/* Rules — read */}
          <Section title="Rules & Regulations" icon="📏">
            {info.rules
              ? <div style={{ fontSize: 13, color: "var(--ink)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{info.rules}</div>
              : <EmptyState text="No rules added." />
            }
          </Section>

          {/* Contact — read */}
          <Section title="Registration & Contact" icon="📞">
            {!info.contact.entry_fee && !info.contact.reg_deadline && info.contact.persons.length === 0 ? (
              <EmptyState text="No contact info added." />
            ) : (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: info.contact.persons.length ? 14 : 0 }}>
                  <ReadField label="Entry Fee" value={info.contact.entry_fee} />
                  <ReadField label="Registration Deadline" value={info.contact.reg_deadline} />
                </div>
                {info.contact.persons.length > 0 && (
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--muted)", marginBottom: 8 }}>Contact Persons</div>
                    {info.contact.persons.map((p, i) => (
                      <div key={i} style={{ display: "flex", gap: 16, fontSize: 13, color: "var(--ink)", marginBottom: 4 }}>
                        <span style={{ fontWeight: 600 }}>{p.name || "—"}</span>
                        <span style={{ color: "var(--muted)" }}>{p.phone || ""}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </Section>

        </div>
      </div>
    );
  }

  // ── EDIT VIEW ────────────────────────────────────────────────
  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div style={sectionHeadStyle}>Info &amp; Rules</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {editSnap && (
            <button onClick={cancelEdit}
              style={{
                padding: "7px 14px", borderRadius: 8,
                border: "1.5px solid var(--border)", background: "none",
                color: "var(--muted)", fontWeight: 700, fontSize: 12,
                cursor: "pointer", fontFamily: "inherit",
              }}>
              Cancel
            </button>
          )}
          <button onClick={handleSave} disabled={saving}
            style={{
              padding: "9px 22px", borderRadius: 8, border: "none",
              background: saving ? "var(--elevated)" : primaryColor,
              color: saving ? "var(--muted)" : "#fff",
              fontWeight: 700, fontSize: 13,
              cursor: saving ? "not-allowed" : "pointer", fontFamily: "inherit",
            }}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: "10px 14px", borderRadius: 8, background: "#fee2e2",
          border: "1px solid #fca5a5", color: "#dc2626", fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

        {/* ── Overview ── */}
        <Section title="Tournament Overview" icon="📋">
          <textarea
            value={info.overview}
            onChange={e => set("overview", e.target.value)}
            onFocus={focusStyle} onBlur={blurStyle}
            placeholder="Describe the tournament — its purpose, theme, number of teams, what makes it special…"
            rows={4}
            style={{ ...inputStyle, resize: "vertical", lineHeight: 1.65 }}
          />
        </Section>

        {/* ── Prize Pool ── */}
        <Section title="Prize Pool" icon="🏆">
          {info.prize_pool.length === 0 && (
            <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 10 }}>
              No prizes added yet.
            </div>
          )}

          {info.prize_pool.map((prize, i) => {
            const custom = isCustomPosition(prize.position);
            return (
              <div key={i} style={{
                background: "var(--elevated)", border: "1px solid var(--border)",
                borderRadius: 10, padding: "12px 14px", marginBottom: 10,
                position: "relative",
              }}>
                {/* Remove button */}
                <button onClick={() => removePrize(i)}
                  title="Remove"
                  style={{
                    position: "absolute", top: 8, right: 8,
                    background: "none", border: "none", cursor: "pointer",
                    color: "var(--muted)", fontSize: 18, lineHeight: 1,
                    padding: "2px 6px", fontFamily: "inherit",
                  }}>×</button>

                {/* Position row */}
                <div style={{ marginBottom: 8 }}>
                  <label style={labelStyle}>Position</label>
                  <select
                    style={{ ...inputStyle, cursor: "pointer", paddingRight: 32 }}
                    value={custom ? CUSTOM_SENTINEL : prize.position}
                    onChange={e => {
                      if (e.target.value === CUSTOM_SENTINEL) {
                        updatePrize(i, "position", "");   // blank → user types
                      } else {
                        updatePrize(i, "position", e.target.value);
                      }
                    }}
                    onFocus={focusStyle} onBlur={blurStyle}
                  >
                    {STANDARD_POSITIONS.map(p => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                    <option value={CUSTOM_SENTINEL}>Custom…</option>
                  </select>
                  {/* Custom text input appears below the select */}
                  {custom && (
                    <input
                      style={{ ...inputStyle, marginTop: 6 }}
                      placeholder="e.g. Best Player, Fair Play Award…"
                      value={prize.position}
                      onChange={e => updatePrize(i, "position", e.target.value)}
                      onFocus={focusStyle} onBlur={blurStyle}
                      autoFocus
                    />
                  )}
                </div>

                {/* Category row */}
                <div style={{ marginBottom: 8 }}>
                  <label style={labelStyle}>Category <span style={{ fontSize: 9, fontWeight: 400, textTransform: "none", color: "var(--subtle)" }}>(optional)</span></label>
                  <input style={inputStyle} placeholder="e.g. Champions, U-18, Mixed…"
                    value={prize.category}
                    onChange={e => updatePrize(i, "category", e.target.value)}
                    onFocus={focusStyle} onBlur={blurStyle}
                  />
                </div>

                {/* Amount row */}
                <div>
                  <label style={labelStyle}>Amount / Prize</label>
                  <input style={inputStyle} placeholder="e.g. ₹20,000 or Trophy"
                    value={prize.amount}
                    onChange={e => updatePrize(i, "amount", e.target.value)}
                    onFocus={focusStyle} onBlur={blurStyle}
                  />
                </div>
              </div>
            );
          })}

          <button onClick={addPrize}
            style={addBtnStyle}
            onMouseEnter={e => { e.target.style.borderColor = primaryColor; e.target.style.color = primaryColor; }}
            onMouseLeave={e => { e.target.style.borderColor = "var(--border)"; e.target.style.color = "var(--muted)"; }}
          >
            + Add Prize
          </button>
        </Section>

        {/* ── Rules ── */}
        <Section title="Rules & Regulations" icon="📏">
          <textarea
            value={info.rules}
            onChange={e => set("rules", e.target.value)}
            onFocus={focusStyle} onBlur={blurStyle}
            placeholder={`List your key rules — eligibility, conduct, match regulations, admin guidelines…\n\nExample:\n• Each team may register only one entry\n• Players must carry valid ID at all times\n• Walkovers awarded if team is absent 10 mins after match time\n• Red card = immediate disqualification\n• Committee decisions are final`}
            rows={7}
            style={{ ...inputStyle, resize: "vertical", lineHeight: 1.65 }}
          />
        </Section>

        {/* ── Registration & Contact ── */}
        <Section title="Registration & Contact" icon="📞">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
            <div>
              <label style={labelStyle}>Entry Fee</label>
              <input style={inputStyle} placeholder="e.g. ₹3,000 per team"
                value={info.contact.entry_fee}
                onChange={e => setContact("entry_fee", e.target.value)}
                onFocus={focusStyle} onBlur={blurStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Registration Deadline</label>
              <DatePicker
                value={info.contact.reg_deadline}
                onChange={val => setContact("reg_deadline", val)}
                placeholder="Pick a date"
              />
            </div>
          </div>

          {info.contact.persons.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <label style={labelStyle}>Contact Persons</label>
              {info.contact.persons.map((person, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8, marginBottom: 8 }}>
                  <input style={inputStyle} placeholder="Name"
                    value={person.name}
                    onChange={e => updatePerson(i, "name", e.target.value)}
                    onFocus={focusStyle} onBlur={blurStyle}
                  />
                  <input style={inputStyle} placeholder="Phone / WhatsApp"
                    value={person.phone}
                    onChange={e => updatePerson(i, "phone", e.target.value)}
                    onFocus={focusStyle} onBlur={blurStyle}
                  />
                  <button onClick={() => removePerson(i)} style={removeBtnStyle} title="Remove">×</button>
                </div>
              ))}
            </div>
          )}
          <button onClick={addPerson}
            style={addBtnStyle}
            onMouseEnter={e => { e.target.style.borderColor = primaryColor; e.target.style.color = primaryColor; }}
            onMouseLeave={e => { e.target.style.borderColor = "var(--border)"; e.target.style.color = "var(--muted)"; }}
          >
            + Add Contact Person
          </button>
        </Section>

      </div>

      {/* Bottom save */}
      <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end", gap: 8 }}>
        {editSnap && (
          <button onClick={cancelEdit}
            style={{
              padding: "7px 14px", borderRadius: 8,
              border: "1.5px solid var(--border)", background: "none",
              color: "var(--muted)", fontWeight: 700, fontSize: 12,
              cursor: "pointer", fontFamily: "inherit",
            }}>
            Cancel
          </button>
        )}
        <button onClick={handleSave} disabled={saving}
          style={{
            padding: "9px 22px", borderRadius: 8, border: "none",
            background: saving ? "var(--elevated)" : primaryColor,
            color: saving ? "var(--muted)" : "#fff",
            fontWeight: 700, fontSize: 13,
            cursor: saving ? "not-allowed" : "pointer", fontFamily: "inherit",
          }}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
