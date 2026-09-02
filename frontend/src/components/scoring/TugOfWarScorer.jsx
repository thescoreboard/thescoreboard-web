/**
 * TugOfWarScorer — fullscreen Tug of War live scorer.
 *
 * Rules: best of 3 pulls (first to win 2). Both teams (8 pullers, weight
 * capped by match.weight_category) must complete weigh-in before pulls can
 * be recorded. Cautions accrue per team; a 3rd disqualifies them and ends
 * the match immediately. One injury substitution is allowed per team,
 * before the match starts.
 *
 * Unlike the point-tap scorers, there is no generic score endpoint here —
 * every action (weigh-in, pull, caution, injury-sub) is a dedicated
 * tug-of-war API call made directly by this component.
 *
 * Props
 * ─────
 *   match        – match data from API (player_1/player_2 incl. team_id, sets, status, weight_category)
 *   teamMembers  – { 1: [TeamMember...], 2: [TeamMember...] } full rosters for each side
 *   onWalkover, onGoLive, onPause, onReset, onClose – same as other scorers
 *   onRefresh    – () => void, re-fetches match data after any action here
 *   onSetWeightCategory – (category: string) => Promise, sets match.weight_category
 *                  (required before weigh-in can start — matches created via
 *                  auto-generated fixtures don't get one by default)
 */
import { useState, useEffect, useCallback } from "react";
import {
  getTugOfWarWeighIns, submitTugOfWarWeighIn,
  recordTugOfWarPull, recordTugOfWarCaution, tugOfWarInjurySub,
  getTugOfWarWeightCategories,
} from "../../api/client";

const CATEGORY_LABELS = {
  featherweight: "Featherweight (≤500kg)",
  lightweight: "Lightweight (≤560kg)",
  middleweight: "Middleweight (≤600kg)",
  heavyweight: "Heavyweight (≤700kg)",
  superheavyweight: "Super Heavyweight (≤800kg)",
};

const PULLERS_PER_TEAM = 8;
const MAX_CAUTIONS = 2;
const POSITIONS = ["anchor", ...Array.from({ length: 7 }, (_, i) => `puller_${i + 1}`)];

const c = {
  bg: "#0d0d0d", surface: "#1a1a1a", border: "#2a2a2a",
  accent: "#a855f7", gold: "#FFCC00", green: "#22c55e",
  red: "#ef4444", blue: "#38bdf8", muted: "#666", ink: "#fff",
};

export default function TugOfWarScorer({
  match, teamMembers = {}, onWalkover, onGoLive, onPause, onReset, onClose, onRefresh,
  onSetWeightCategory,
}) {
  const [weighins, setWeighins]       = useState({ 1: null, 2: null });
  const [enabledCategories, setEnabledCategories] = useState([]);
  const [pickedCategory, setPickedCategory]       = useState("");
  const [editingTeam, setEditingTeam] = useState(null);
  const [draft, setDraft]             = useState([]);
  const [duration, setDuration]       = useState(60);
  const [cautionReason, setCautionReason] = useState("");
  const [injurySubFor, setInjurySubFor]   = useState(null); // position | null
  const [err, setErr]                 = useState("");
  const [showWalkover, setShowWalkover] = useState(false);

  const p1 = match.player_1 || {};
  const p2 = match.player_2 || {};
  const isDone    = match.status === "done";
  const isPreLive = match.status === "scheduled";
  const p1Name = p1?.name || "Team 1";
  const p2Name = p2?.name || "Team 2";

  const sets = (match.sets || []).slice().sort((a, b) => a.set_number - b.set_number);
  const completedPulls = sets.filter(s => s.is_complete);
  const pullsWon = { 1: p1.score || 0, 2: p2.score || 0 };
  const matchWinner = isDone ? (p1?.is_winner ? 1 : p2?.is_winner ? 2 : null) : null;
  const nextPullNum = Math.min(completedPulls.length + 1, 3);

  const refresh = useCallback(() => {
    if (!match.match_id) return;
    getTugOfWarWeighIns(match.match_id).then(d => {
      const byPos = { 1: null, 2: null };
      (d.weigh_ins || []).forEach(w => { byPos[w.position] = w; });
      setWeighins(byPos);
    }).catch(() => {});
  }, [match.match_id]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (match.weight_category || !match.event_id) return;
    getTugOfWarWeightCategories(match.event_id).then(d => {
      const cats = d.weight_categories || [];
      setEnabledCategories(cats);
      setPickedCategory(cats[0] || "");
    }).catch(() => {});
  }, [match.weight_category, match.event_id]);

  const confirmWeightCategory = async () => {
    if (!pickedCategory) return;
    setErr("");
    try {
      await onSetWeightCategory(pickedCategory);
    } catch (e) { setErr(e.message); }
  };

  const bothVerified = weighins[1] && weighins[2];
  const anyDisqualified = weighins[1]?.is_disqualified || weighins[2]?.is_disqualified;

  const openWeighInEditor = (position) => {
    const members = (teamMembers[position] || []).slice(0, PULLERS_PER_TEAM);
    setDraft(members.map((m, i) => ({ team_member_id: m.tm_id, name: m.name, weight_kg: "", position: POSITIONS[i] })));
    setEditingTeam(position);
  };

  const saveWeighIn = async () => {
    setErr("");
    try {
      await submitTugOfWarWeighIn(match.match_id, editingTeam, draft.map(d => ({
        team_member_id: d.team_member_id, weight_kg: Number(d.weight_kg), position: d.position,
      })));
      setEditingTeam(null);
      refresh();
    } catch (e) { setErr(e.message); }
  };

  const recordPull = async (winningPosition) => {
    setErr("");
    try {
      await recordTugOfWarPull(match.match_id, winningPosition, Number(duration) || 0);
      onRefresh && onRefresh();
    } catch (e) { setErr(e.message); }
  };

  const giveCaution = async (position) => {
    setErr("");
    try {
      await recordTugOfWarCaution(match.match_id, position, cautionReason || undefined);
      setCautionReason("");
      onRefresh && onRefresh();
      refresh();
    } catch (e) { setErr(e.message); }
  };

  const openInjurySub = (position) => setInjurySubFor(position);
  const confirmInjurySub = async (injuredId, replacementId, replacementWeight) => {
    setErr("");
    try {
      await tugOfWarInjurySub(match.match_id, injurySubFor, injuredId, replacementId, Number(replacementWeight));
      setInjurySubFor(null);
      refresh();
    } catch (e) { setErr(e.message); }
  };

  const totalWeight = draft.reduce((sum, d) => sum + (Number(d.weight_kg) || 0), 0);
  const positionsUsed = new Set(draft.map(d => d.position));
  const validPositions = POSITIONS.every(p => positionsUsed.has(p)) && draft.length === PULLERS_PER_TEAM;

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 9999, background: c.bg, display: "flex", flexDirection: "column", overflow: "auto", fontFamily: "'Space Grotesk',sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 16px", background: c.surface, borderBottom: `2px solid ${isPreLive ? "#f59e0b" : c.accent}`, gap: "8px 12px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ background: isPreLive ? "#f59e0b" : c.accent, color: c.bg, fontFamily: "'Unbounded',sans-serif", fontSize: 10, fontWeight: 800, letterSpacing: 2, textTransform: "uppercase", padding: "3px 10px", borderRadius: 4 }}>
            {isDone ? "Final" : isPreLive ? "Ready" : `Pull ${nextPullNum}`}
          </span>
          <span style={{ fontSize: 12, color: c.muted, fontWeight: 600 }}>
            Pulls: <strong style={{ color: c.accent }}>{pullsWon[1]}</strong> — <strong style={{ color: c.accent }}>{pullsWon[2]}</strong>
          </span>
          <span style={{ fontSize: 11, color: c.muted, textTransform: "uppercase" }}>{match.weight_category}</span>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {!isDone && !isPreLive && onWalkover && <TopBtn onClick={() => setShowWalkover(true)}>Walkover</TopBtn>}
          {!isDone && !isPreLive && onPause && <TopBtn onClick={onPause}>Pause</TopBtn>}
          {!isDone && !isPreLive && onReset && <TopBtn onClick={onReset}>Reset</TopBtn>}
          <TopBtn onClick={onClose}>✕ Close</TopBtn>
        </div>
      </div>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "16px 20px 24px", gap: 16, maxWidth: 640, margin: "0 auto", width: "100%" }}>
        {err && <div style={{ fontSize: 12, color: c.red }}>{err}</div>}

        {!match.weight_category ? (
          <div style={{ background: c.surface, border: `1px solid ${c.border}`, borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 12, color: c.muted, marginBottom: 10 }}>
              This match has no weight category yet — pick one before weigh-in can start.
            </div>
            <select value={pickedCategory} onChange={e => setPickedCategory(e.target.value)} style={{ ...selectStyle, marginBottom: 10 }}>
              {enabledCategories.map(cat => <option key={cat} value={cat}>{CATEGORY_LABELS[cat] || cat}</option>)}
            </select>
            <button onClick={confirmWeightCategory} disabled={!pickedCategory} style={btnStyle(c.accent, !pickedCategory)}>Confirm Weight Category</button>
          </div>
        ) : (
        <>
        {/* Weigh-in status */}
        <div style={{ display: "flex", gap: 10 }}>
          {[1, 2].map(pos => (
            <div key={pos} style={{ flex: 1, background: c.surface, border: `1px solid ${c.border}`, borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: 11, color: c.muted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{pos === 1 ? p1Name : p2Name}</div>
              {weighins[pos] ? (
                <>
                  <div style={{ fontSize: 12, color: c.green, marginBottom: 4 }}>✓ Weighed in — {weighins[pos].total_weight_kg}kg</div>
                  <div style={{ fontSize: 11, color: c.muted, marginBottom: 8 }}>
                    Cautions: {weighins[pos].caution_count}/{MAX_CAUTIONS}
                    {weighins[pos].is_disqualified && <span style={{ color: c.red }}> — DISQUALIFIED</span>}
                  </div>
                  {isPreLive && weighins[pos].substitution_count < 1 && (
                    <button onClick={() => openInjurySub(pos)} style={outlineBtnStyle}>Injury Substitute</button>
                  )}
                </>
              ) : (
                <>
                  <div style={{ fontSize: 12, color: c.red, marginBottom: 8 }}>Not weighed in</div>
                  <button onClick={() => openWeighInEditor(pos)} style={btnStyle(c.blue)}>Weigh In</button>
                </>
              )}
            </div>
          ))}
        </div>

        {isPreLive && !bothVerified && (
          <div style={{ textAlign: "center", fontSize: 12, color: c.muted }}>
            Both teams must complete weigh-in before the match can go live.
          </div>
        )}
        {isPreLive && bothVerified && (
          <button onClick={onGoLive} style={{ ...btnStyle(c.accent), padding: "20px 0", fontSize: 15, fontWeight: 900, textTransform: "uppercase", fontFamily: "'Unbounded',sans-serif" }}>
            ▶ Go Live
          </button>
        )}

        {!isPreLive && (
          <>
            {completedPulls.length > 0 && (
              <div style={{ display: "flex", justifyContent: "center", gap: 6, flexWrap: "wrap" }}>
                {completedPulls.map(s => (
                  <span key={s.set_number} style={{ fontSize: 11, padding: "3px 10px", borderRadius: 4, fontWeight: 800, background: s.winner_position === 1 ? `${c.green}18` : `${c.red}18`, color: s.winner_position === 1 ? c.green : c.red, border: `1px solid ${s.winner_position === 1 ? c.green : c.red}44` }}>
                    Pull {s.set_number}: {s.winner_position === 1 ? p1Name : p2Name}
                  </span>
                ))}
              </div>
            )}

            {matchWinner && (
              <div style={{ textAlign: "center", fontSize: 16, fontWeight: 900, textTransform: "uppercase", letterSpacing: 2, color: c.gold }}>
                {matchWinner === 1 ? p1Name : p2Name} Wins!
                {match.live_state?.match_points && (
                  <div style={{ fontSize: 11, color: c.muted, marginTop: 4, textTransform: "none", letterSpacing: 0 }}>
                    Points — {p1Name}: {match.live_state.match_points["1"] ?? 0}, {p2Name}: {match.live_state.match_points["2"] ?? 0}
                  </div>
                )}
              </div>
            )}

            {!isDone && !anyDisqualified && (
              <>
                <div>
                  <div style={{ fontSize: 11, color: c.muted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>Record Pull {nextPullNum}</div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
                    <span style={{ fontSize: 12, color: c.muted }}>Duration (s):</span>
                    <input type="number" min={0} value={duration} onChange={e => setDuration(e.target.value)}
                      style={{ width: 70, padding: "6px 8px", background: c.bg, border: `1px solid ${c.border}`, borderRadius: 6, color: c.ink, fontSize: 12 }} />
                  </div>
                  <div style={{ display: "flex", gap: 12 }}>
                    <button onClick={() => recordPull(1)} style={btnStyle(c.accent)}>{p1Name} Wins Pull</button>
                    <button onClick={() => recordPull(2)} style={btnStyle(c.accent)}>{p2Name} Wins Pull</button>
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: 11, color: c.muted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>Cautions</div>
                  <input placeholder="Reason (optional) — loss of grip, sitting, etc." value={cautionReason} onChange={e => setCautionReason(e.target.value)}
                    style={{ width: "100%", padding: "8px 10px", background: c.bg, border: `1px solid ${c.border}`, borderRadius: 6, color: c.ink, fontSize: 12, marginBottom: 8 }} />
                  <div style={{ display: "flex", gap: 12 }}>
                    {[1, 2].map(pos => (
                      <button key={pos} disabled={weighins[pos]?.is_disqualified} onClick={() => giveCaution(pos)} style={outlineBtnStyle}>
                        Caution {pos === 1 ? p1Name : p2Name} ({weighins[pos]?.caution_count ?? 0}/{MAX_CAUTIONS})
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </>
        )}
        </>
        )}
      </div>

      {showWalkover && (
        <Modal onClose={() => setShowWalkover(false)}>
          <ModalTitle>Record Walkover</ModalTitle>
          <ModalBody>The match will be marked as done. The winner advances in the bracket.</ModalBody>
          {[{ pos: 1, name: p1Name }, { pos: 2, name: p2Name }].map(({ pos, name }) => (
            <BigButton key={pos} color={c.blue} onClick={() => { setShowWalkover(false); onWalkover(pos); }}>{name} wins by walkover</BigButton>
          ))}
          <CancelButton onClick={() => setShowWalkover(false)} />
        </Modal>
      )}

      {editingTeam && (
        <Modal onClose={() => setEditingTeam(null)} wide>
          <ModalTitle>{editingTeam === 1 ? p1Name : p2Name} — Weigh In</ModalTitle>
          <ModalBody>Exactly {PULLERS_PER_TEAM} pullers, one per position (anchor + puller_1..7). Total weight must not exceed the {match.weight_category} limit.</ModalBody>
          <div style={{ maxHeight: 320, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }}>
            {draft.map((d, i) => (
              <div key={d.team_member_id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", background: c.bg, borderRadius: 8 }}>
                <span style={{ flex: 1, fontSize: 12, color: c.ink }}>{d.name}</span>
                <select value={d.position} onChange={e => { const next = [...draft]; next[i] = { ...next[i], position: e.target.value }; setDraft(next); }}
                  style={{ background: c.surface, border: `1px solid ${c.border}`, borderRadius: 6, color: c.ink, fontSize: 11, padding: "4px 6px" }}>
                  {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <input type="number" min={1} placeholder="kg" value={d.weight_kg}
                  onChange={e => { const next = [...draft]; next[i] = { ...next[i], weight_kg: e.target.value }; setDraft(next); }}
                  style={{ width: 60, padding: "4px 6px", background: c.surface, border: `1px solid ${c.border}`, borderRadius: 6, color: c.ink, fontSize: 12 }} />
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: c.muted, marginTop: 8 }}>Total: {totalWeight.toFixed(1)}kg</div>
          {err && <div style={{ fontSize: 12, color: c.red, marginTop: 6 }}>{err}</div>}
          <BigButton color={c.green} onClick={saveWeighIn} disabled={!validPositions}>Confirm Weigh In</BigButton>
          <CancelButton onClick={() => setEditingTeam(null)} />
        </Modal>
      )}

      {injurySubFor && (
        <InjurySubModal
          position={injurySubFor}
          weighin={weighins[injurySubFor]}
          candidates={(teamMembers[injurySubFor] || []).filter(m => !(weighins[injurySubFor]?.pullers || []).some(p => p.team_member_id === m.tm_id))}
          onConfirm={confirmInjurySub}
          onClose={() => setInjurySubFor(null)}
        />
      )}
    </div>
  );
}

function InjurySubModal({ position, weighin, candidates, onConfirm, onClose }) {
  const [injuredId, setInjuredId] = useState(weighin?.pullers?.[0]?.team_member_id || "");
  const [replacementId, setReplacementId] = useState(candidates?.[0]?.tm_id || "");
  const [weight, setWeight] = useState("");
  return (
    <Modal onClose={onClose} wide>
      <ModalTitle>Injury Substitute</ModalTitle>
      <ModalBody>Only one substitution is allowed per team, before the match starts.</ModalBody>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <label style={{ fontSize: 11, color: c.muted }}>Injured puller</label>
        <select value={injuredId} onChange={e => setInjuredId(e.target.value)} style={selectStyle}>
          {(weighin?.pullers || []).map(p => <option key={p.team_member_id} value={p.team_member_id}>{p.name} ({p.position})</option>)}
        </select>
        <label style={{ fontSize: 11, color: c.muted }}>Replacement</label>
        <select value={replacementId} onChange={e => setReplacementId(e.target.value)} style={selectStyle}>
          {candidates.map(m => <option key={m.tm_id} value={m.tm_id}>{m.name}</option>)}
        </select>
        <label style={{ fontSize: 11, color: c.muted }}>Replacement weight (kg)</label>
        <input type="number" value={weight} onChange={e => setWeight(e.target.value)} style={{ ...selectStyle, padding: "8px 10px" }} />
      </div>
      <BigButton color={c.green} onClick={() => onConfirm(Number(injuredId), Number(replacementId), weight)}>Confirm Substitution</BigButton>
      <CancelButton onClick={onClose} />
    </Modal>
  );
}

const selectStyle = { width: "100%", padding: "8px 10px", background: c.bg, border: `1px solid ${c.border}`, borderRadius: 6, color: c.ink, fontSize: 12 };

function TopBtn({ onClick, children }) {
  return <button onClick={onClick} style={{ background: "transparent", color: c.muted, border: `1px solid ${c.border}`, borderRadius: 6, padding: "5px 12px", cursor: "pointer", fontSize: 12, fontWeight: 700, fontFamily: "inherit" }}>{children}</button>;
}
function btnStyle(color, disabled) {
  return { flex: 1, padding: "12px 0", borderRadius: 8, background: disabled ? c.surface : color, color: disabled ? c.muted : c.bg, border: "none", fontWeight: 800, fontSize: 13, fontFamily: "inherit", cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1, width: "100%" };
}
const outlineBtnStyle = { flex: 1, padding: "9px 0", background: "transparent", color: c.muted, border: `1px solid ${c.border}`, borderRadius: 8, fontSize: 12, fontWeight: 700, fontFamily: "inherit", cursor: "pointer" };

function Modal({ children, onClose, wide }) {
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 10000, background: "rgba(0,0,0,0.85)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div onClick={e => e.stopPropagation()} style={{ background: c.surface, border: `1px solid ${c.border}`, borderRadius: 14, padding: "24px 22px", width: "100%", maxWidth: wide ? 420 : 340 }}>
        {children}
      </div>
    </div>
  );
}
function ModalTitle({ children }) { return <div style={{ fontFamily: "'Unbounded',sans-serif", fontSize: 13, fontWeight: 900, textTransform: "uppercase", letterSpacing: 1, color: c.ink, marginBottom: 6 }}>{children}</div>; }
function ModalBody({ children }) { return <div style={{ fontSize: 12, color: c.muted, marginBottom: 16, lineHeight: 1.5 }}>{children}</div>; }
function BigButton({ children, onClick, color, disabled }) {
  return <button onClick={onClick} disabled={disabled} style={{ width: "100%", padding: "12px 16px", borderRadius: 10, background: disabled ? c.bg : `${color}18`, border: `2px solid ${disabled ? c.border : color}`, color: disabled ? c.muted : c.ink, fontSize: 12, fontWeight: 800, cursor: disabled ? "not-allowed" : "pointer", marginBottom: 8, fontFamily: "inherit", marginTop: 12 }}>{children}</button>;
}
function CancelButton({ onClick }) {
  return <button onClick={onClick} style={{ width: "100%", padding: "10px 0", background: "transparent", color: c.muted, border: `1px solid ${c.border}`, borderRadius: 8, fontSize: 12, fontWeight: 700, fontFamily: "inherit", cursor: "pointer", marginTop: 4 }}>Cancel</button>;
}
