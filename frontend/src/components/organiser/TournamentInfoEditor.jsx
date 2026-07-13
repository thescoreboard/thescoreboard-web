/**
 * Independent Setup Progress sections, each reading/writing its own
 * slice of tournament.tournament_info:
 *   PrizePoolSection — prize_pool: [{ category, position, amount }]
 *   RulesSection     — rules: plain text
 *
 * (Registration & Contact fields live in Basic Info's `extras` — see
 * TournamentBasicInfoSection — not as their own section here.)
 *
 * Each section saves independently but PATCHes the *whole* tournament_info
 * object (spread from `fullInfo`) since the column is a single JSON blob —
 * saving one section must not clobber the others.
 */
import { useState } from "react";
import { updateTournament } from "../../api/client";
import SetupSection from "./SetupSection";
import { isSectionComplete } from "../../utils/tournamentCompleteness";

const STANDARD_POSITIONS = ["1st Place", "2nd Place", "3rd Place"];
const CUSTOM_SENTINEL     = "__custom__";
function isCustomPosition(val) { return !STANDARD_POSITIONS.includes(val); }

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
const primaryColor = "var(--primary, #FF6B35)";
const focusStyle = (e) => { e.target.style.borderColor = primaryColor; };
const blurStyle  = (e) => { e.target.style.borderColor = "var(--border)"; };

async function saveInfo(orgId, tournamentId, fullInfo, patch) {
  await updateTournament(orgId, tournamentId, { tournament_info: { ...fullInfo, ...patch } });
}

// ── Prize Pool ──────────────────────────────────────────────────
export function PrizePoolSection({ orgId, tournamentId, fullInfo, checklist, defaultOpen, onSaved, flash }) {
  const [prizes, setPrizes] = useState(() => fullInfo.prize_pool || []);
  const [saving, setSaving] = useState(false);
  const status = isSectionComplete(checklist, "prize") ? "complete" : "not_started";

  const addPrize    = () => setPrizes(p => [...p, { category: "", position: "1st Place", amount: "" }]);
  const updatePrize = (i, field, val) => setPrizes(p => p.map((x, idx) => idx === i ? { ...x, [field]: val } : x));
  const removePrize  = (i) => setPrizes(p => p.filter((_, idx) => idx !== i));

  const save = async () => {
    setSaving(true);
    try {
      await saveInfo(orgId, tournamentId, fullInfo, { prize_pool: prizes });
      onSaved?.();
      flash?.("Prize pool updated!");
    } catch (e) { flash?.("Error: " + e.message); }
    finally { setSaving(false); }
  };

  return (
    <SetupSection icon="🏆" title="Prize Pool" status={status} defaultOpen={defaultOpen}>
      {prizes.length === 0 && (
        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 10 }}>No prizes added yet.</div>
      )}
      {prizes.map((prize, i) => {
        const custom = isCustomPosition(prize.position);
        return (
          <div key={i} style={{ background: "var(--elevated)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 14px", marginBottom: 10, position: "relative" }}>
            <button onClick={() => removePrize(i)} title="Remove"
              style={{ position: "absolute", top: 8, right: 8, background: "none", border: "none", cursor: "pointer", color: "var(--muted)", fontSize: 18, lineHeight: 1, padding: "2px 6px", fontFamily: "inherit" }}>×</button>
            <div style={{ marginBottom: 8 }}>
              <label style={labelStyle}>Position</label>
              <select style={{ ...inputStyle, cursor: "pointer", paddingRight: 32 }}
                value={custom ? CUSTOM_SENTINEL : prize.position}
                onChange={e => updatePrize(i, "position", e.target.value === CUSTOM_SENTINEL ? "" : e.target.value)}
                onFocus={focusStyle} onBlur={blurStyle}>
                {STANDARD_POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                <option value={CUSTOM_SENTINEL}>Custom…</option>
              </select>
              {custom && (
                <input style={{ ...inputStyle, marginTop: 6 }} placeholder="e.g. Best Player, Fair Play Award…"
                  value={prize.position} onChange={e => updatePrize(i, "position", e.target.value)}
                  onFocus={focusStyle} onBlur={blurStyle} autoFocus />
              )}
            </div>
            <div style={{ marginBottom: 8 }}>
              <label style={labelStyle}>Category <span style={{ fontSize: 9, fontWeight: 400, textTransform: "none", color: "var(--subtle)" }}>(optional)</span></label>
              <input style={inputStyle} placeholder="e.g. Champions, U-18, Mixed…"
                value={prize.category} onChange={e => updatePrize(i, "category", e.target.value)}
                onFocus={focusStyle} onBlur={blurStyle} />
            </div>
            <div>
              <label style={labelStyle}>Amount / Prize</label>
              <input style={inputStyle} placeholder="e.g. ₹20,000 or Trophy"
                value={prize.amount} onChange={e => updatePrize(i, "amount", e.target.value)}
                onFocus={focusStyle} onBlur={blurStyle} />
            </div>
          </div>
        );
      })}
      <button onClick={addPrize} style={addBtnStyle}
        onMouseEnter={e => { e.target.style.borderColor = primaryColor; e.target.style.color = primaryColor; }}
        onMouseLeave={e => { e.target.style.borderColor = "var(--border)"; e.target.style.color = "var(--muted)"; }}>
        + Add Prize
      </button>
      <div style={{ marginTop: 14 }}>
        <button className="btn btn-primary btn-sm" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save Changes"}</button>
      </div>
    </SetupSection>
  );
}

// ── Rules & Regulations ────────────────────────────────────────
export function RulesSection({ orgId, tournamentId, fullInfo, checklist, defaultOpen, onSaved, flash }) {
  const [rules, setRules]   = useState(() => fullInfo.rules || "");
  const [saving, setSaving] = useState(false);
  const status = isSectionComplete(checklist, "rules") ? "complete" : "not_started";

  const save = async () => {
    setSaving(true);
    try {
      await saveInfo(orgId, tournamentId, fullInfo, { rules });
      onSaved?.();
      flash?.("Rules updated!");
    } catch (e) { flash?.("Error: " + e.message); }
    finally { setSaving(false); }
  };

  return (
    <SetupSection icon="📋" title="Rules & Regulations" status={status} defaultOpen={defaultOpen}>
      <textarea
        value={rules}
        onChange={e => setRules(e.target.value)}
        onFocus={focusStyle} onBlur={blurStyle}
        placeholder={`List your key rules — eligibility, conduct, match regulations, admin guidelines…\n\nExample:\n• Each team may register only one entry\n• Players must carry valid ID at all times\n• Walkovers awarded if team is absent 10 mins after match time\n• Committee decisions are final`}
        rows={7}
        style={{ ...inputStyle, resize: "vertical", lineHeight: 1.65 }}
      />
      <div style={{ marginTop: 14 }}>
        <button className="btn btn-primary btn-sm" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save Changes"}</button>
      </div>
    </SetupSection>
  );
}

