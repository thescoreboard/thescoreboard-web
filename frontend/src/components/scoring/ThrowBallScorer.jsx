/**
 * ThrowBallScorer — fullscreen Throw Ball live scorer.
 *
 * Rules: Best of 3 or 5 sets (config.sets_to_win), first to 15 wins a set,
 * no deuce. 7 players on court per team (12-player squad), 2 timeouts per
 * team per set, max 5 substitutions per team per set, no sub in serve
 * position (court_position 9).
 *
 * Score/status/set-undo/walkover flow through the same generic match props
 * every other scorer uses (onScore, onUndoSet, onWalkover, onGoLive, ...).
 * Lineup, timeouts, and substitutions are Throw-Ball-specific and are
 * fetched/posted directly by this component via the throw-ball API.
 *
 * Props
 * ─────
 *   match        – match data from API (player_1/player_2 incl. team_id, sets, status)
 *   config       – event sport_config (sets_to_win, gender_format)
 *   teamMembers  – { 1: [TeamMember...], 2: [TeamMember...] } full rosters for each side
 *   onScore, onUndoSet, onWalkover, onGoLive, onPause, onReset, onClose – same as other scorers
 *   onRefresh    – () => void, re-fetches match data (called after timeout/substitute,
 *                  since those mutate live_state outside the score-update flow)
 */
import { useState, useEffect, useCallback } from "react";
import {
  getThrowBallLineup, submitThrowBallLineup,
  recordThrowBallTimeout, substituteThrowBallPlayer,
} from "../../api/client";

const PLAYERS_ON_COURT = 7;
const MAX_TIMEOUTS = 2;
const MAX_SUBS = 5;
const SERVE_POSITION = 9;

const c = {
  bg: "#0d0d0d", surface: "#1a1a1a", border: "#2a2a2a",
  accent: "#22c55e", gold: "#FFCC00", green: "#22c55e",
  red: "#ef4444", blue: "#38bdf8", muted: "#666", ink: "#fff",
};

export default function ThrowBallScorer({
  match, config, teamMembers = {}, onScore, onUndoSet, onWalkover,
  onGoLive, onPause, onReset, onClose, onRefresh,
}) {
  const [lineup, setLineup]           = useState({ 1: [], 2: [] });
  const [editingTeam, setEditingTeam] = useState(null); // 1 | 2 | null
  const [draft, setDraft]             = useState([]);
  const [subFor, setSubFor]           = useState(null); // { position, outId } | null
  const [err, setErr]                 = useState("");
  const [showWalkover, setShowWalkover] = useState(false);

  const p1 = match.player_1 || {};
  const p2 = match.player_2 || {};
  const sets = (match.sets || []).slice().sort((a, b) => a.set_number - b.set_number);
  const currentSet = sets.find(s => !s.is_complete) || sets[sets.length - 1];
  const isDone    = match.status === "done";
  const isPreLive = match.status === "scheduled";

  const s1 = currentSet?.score_p1 ?? 0;
  const s2 = currentSet?.score_p2 ?? 0;
  const pts = config.points_per_set || 15;

  const setWinner = s1 >= pts && s1 > s2 ? 1 : (s2 >= pts && s2 > s1 ? 2 : null);
  const setsWon1 = sets.filter(s => s.is_complete && s.winner_position === 1).length;
  const setsWon2 = sets.filter(s => s.is_complete && s.winner_position === 2).length;
  const matchWinner = isDone ? (p1?.is_winner ? 1 : p2?.is_winner ? 2 : null) : null;

  const p1Name = p1?.name || "Team 1";
  const p2Name = p2?.name || "Team 2";

  const refreshLineup = useCallback(() => {
    if (!match.match_id) return;
    getThrowBallLineup(match.match_id).then(d => {
      const rows = d.lineup || [];
      setLineup({ 1: rows.filter(r => r.position === 1), 2: rows.filter(r => r.position === 2) });
    }).catch(() => {});
  }, [match.match_id]);

  useEffect(() => { refreshLineup(); }, [refreshLineup]);

  const timeoutsUsed = (match.live_state?.throw_ball?.timeouts || {})[String(currentSet?.set_number)] || { "1": 0, "2": 0 };
  const subsUsed     = (match.live_state?.throw_ball?.substitutions || {})[String(currentSet?.set_number)] || { "1": 0, "2": 0 };

  const team1Ready = lineup[1].filter(r => r.on_court).length === PLAYERS_ON_COURT;
  const team2Ready = lineup[2].filter(r => r.on_court).length === PLAYERS_ON_COURT;
  const bothReady  = team1Ready && team2Ready;

  const addPoint = (team) => {
    if (isDone || setWinner || isPreLive) return;
    const ns1 = team === 1 ? s1 + 1 : s1;
    const ns2 = team === 2 ? s2 + 1 : s2;
    onScore(ns1, ns2, team); // serving team just scored
  };
  const undoPoint = (team) => {
    if (team === 1 && s1 === 0) return;
    if (team === 2 && s2 === 0) return;
    onScore(team === 1 ? s1 - 1 : s1, team === 2 ? s2 - 1 : s2, match.current_server);
  };

  const callTimeout = async (position) => {
    setErr("");
    try {
      await recordThrowBallTimeout(match.match_id, position);
      onRefresh && onRefresh();
    } catch (e) { setErr(e.message); }
  };

  const openSubPicker = (position, outId) => setSubFor({ position, outId });

  const confirmSub = async (inId) => {
    if (!subFor) return;
    setErr("");
    try {
      await substituteThrowBallPlayer(match.match_id, subFor.position, subFor.outId, inId);
      setSubFor(null);
      refreshLineup();
      onRefresh && onRefresh();
    } catch (e) { setErr(e.message); }
  };

  const openLineupEditor = (position) => {
    const existing = lineup[position];
    const members = teamMembers[position] || [];
    if (existing.length) {
      setDraft(existing.map(r => ({ team_member_id: r.team_member_id, on_court: r.on_court, court_position: r.court_position, name: r.name })));
    } else {
      setDraft(members.map((m, i) => ({
        team_member_id: m.tm_id, name: m.name,
        on_court: i < PLAYERS_ON_COURT, court_position: i < PLAYERS_ON_COURT ? i + 1 : null,
      })));
    }
    setEditingTeam(position);
  };

  const saveLineup = async () => {
    setErr("");
    try {
      await submitThrowBallLineup(match.match_id, editingTeam, draft.map(d => ({
        team_member_id: d.team_member_id, on_court: d.on_court, court_position: d.on_court ? Number(d.court_position) : null,
      })));
      setEditingTeam(null);
      refreshLineup();
    } catch (e) { setErr(e.message); }
  };

  const walkoverModal = showWalkover && (
    <Modal onClose={() => setShowWalkover(false)}>
      <ModalTitle>Record Walkover</ModalTitle>
      <ModalBody>The match will be marked as done. The winner advances in the bracket.</ModalBody>
      {[{ pos: 1, name: p1Name }, { pos: 2, name: p2Name }].map(({ pos, name }) => (
        <BigButton key={pos} color={c.blue} onClick={() => { setShowWalkover(false); onWalkover(pos); }}>
          {name} wins by walkover
        </BigButton>
      ))}
      <CancelButton onClick={() => setShowWalkover(false)} />
    </Modal>
  );

  const lineupModal = editingTeam && (
    <Modal onClose={() => setEditingTeam(null)} wide>
      <ModalTitle>{editingTeam === 1 ? p1Name : p2Name} — Set Lineup</ModalTitle>
      <ModalBody>Exactly {PLAYERS_ON_COURT} players must be on court, each with a unique court position (1-9). Position 9 is the serve position.</ModalBody>
      <div style={{ maxHeight: 340, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }}>
        {draft.map((d, i) => (
          <div key={d.team_member_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 8px", background: c.bg, borderRadius: 8 }}>
            <input type="checkbox" checked={d.on_court} onChange={e => {
              const next = [...draft];
              next[i] = { ...next[i], on_court: e.target.checked, court_position: e.target.checked ? next[i].court_position || "" : null };
              setDraft(next);
            }} />
            <span style={{ flex: 1, fontSize: 13, color: c.ink }}>{d.name}</span>
            {d.on_court && (
              <input type="number" min={1} max={9} value={d.court_position || ""} placeholder="Pos"
                onChange={e => { const next = [...draft]; next[i] = { ...next[i], court_position: e.target.value }; setDraft(next); }}
                style={{ width: 50, padding: "4px 6px", background: c.surface, border: `1px solid ${c.border}`, borderRadius: 6, color: c.ink, fontSize: 12 }}
              />
            )}
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: draft.filter(d => d.on_court).length === PLAYERS_ON_COURT ? c.green : c.red, marginTop: 8 }}>
        On court: {draft.filter(d => d.on_court).length} / {PLAYERS_ON_COURT}
      </div>
      {err && <div style={{ fontSize: 12, color: c.red, marginTop: 6 }}>{err}</div>}
      <BigButton color={c.green} onClick={saveLineup} disabled={draft.filter(d => d.on_court).length !== PLAYERS_ON_COURT}>
        Save Lineup
      </BigButton>
      <CancelButton onClick={() => setEditingTeam(null)} />
    </Modal>
  );

  const subModal = subFor && (
    <Modal onClose={() => setSubFor(null)}>
      <ModalTitle>Substitute Player</ModalTitle>
      <ModalBody>Choose a bench player to bring on.</ModalBody>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {lineup[subFor.position].filter(r => !r.on_court).map(r => (
          <BigButton key={r.team_member_id} color={c.blue} onClick={() => confirmSub(r.team_member_id)}>
            {r.name}
          </BigButton>
        ))}
        {lineup[subFor.position].filter(r => !r.on_court).length === 0 && (
          <div style={{ fontSize: 12, color: c.muted }}>No bench players available.</div>
        )}
      </div>
      <CancelButton onClick={() => setSubFor(null)} />
    </Modal>
  );

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 9999, background: c.bg, display: "flex", flexDirection: "column", overflow: "auto", fontFamily: "'Space Grotesk',sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 16px", background: c.surface, borderBottom: `2px solid ${isPreLive ? "#f59e0b" : c.accent}`, gap: "8px 12px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ background: isPreLive ? "#f59e0b" : c.accent, color: c.bg, fontFamily: "'Unbounded',sans-serif", fontSize: 10, fontWeight: 800, letterSpacing: 2, textTransform: "uppercase", padding: "3px 10px", borderRadius: 4 }}>
            {isDone ? "Final" : isPreLive ? "Ready" : `Set ${currentSet?.set_number || 1}`}
          </span>
          <span style={{ fontSize: 12, color: c.muted, fontWeight: 600 }}>
            Sets: <strong style={{ color: c.accent }}>{setsWon1}</strong> — <strong style={{ color: c.accent }}>{setsWon2}</strong>
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {!isDone && !isPreLive && onWalkover && (
            <TopBtn onClick={() => setShowWalkover(true)}>Walkover</TopBtn>
          )}
          {!isDone && !isPreLive && onPause && <TopBtn onClick={onPause}>Pause</TopBtn>}
          {!isDone && !isPreLive && onReset && <TopBtn onClick={onReset}>Reset</TopBtn>}
          <TopBtn onClick={onClose}>✕ Close</TopBtn>
        </div>
      </div>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "16px 20px 24px", gap: 16, maxWidth: 640, margin: "0 auto", width: "100%" }}>
        {err && <div style={{ fontSize: 12, color: c.red }}>{err}</div>}

        {/* Lineup status / editor entry points */}
        <div style={{ display: "flex", gap: 10 }}>
          {[1, 2].map(pos => (
            <div key={pos} style={{ flex: 1, background: c.surface, border: `1px solid ${c.border}`, borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: 11, color: c.muted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{pos === 1 ? p1Name : p2Name}</div>
              <div style={{ fontSize: 12, color: (pos === 1 ? team1Ready : team2Ready) ? c.green : c.red, marginBottom: 8 }}>
                {lineup[pos].filter(r => r.on_court).length} / {PLAYERS_ON_COURT} on court
              </div>
              <button onClick={() => openLineupEditor(pos)} style={btnStyle(c.blue)}>
                {lineup[pos].length ? "Edit Lineup" : "Set Lineup"}
              </button>
            </div>
          ))}
        </div>

        {isPreLive && !bothReady && (
          <div style={{ textAlign: "center", fontSize: 12, color: c.muted }}>
            Both teams need exactly {PLAYERS_ON_COURT} players on court before the match can go live.
          </div>
        )}
        {isPreLive && bothReady && (
          <button onClick={onGoLive} style={{ ...btnStyle(c.accent), padding: "20px 0", fontSize: 15, fontWeight: 900, textTransform: "uppercase", fontFamily: "'Unbounded',sans-serif" }}>
            ▶ Go Live
          </button>
        )}

        {!isPreLive && (
          <>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 16 }}>
              {[{ name: p1Name, score: s1, pos: 1 }, { name: p2Name, score: s2, pos: 2 }].map(side => (
                <div key={side.pos} onClick={!isDone && !setWinner ? () => addPoint(side.pos) : undefined}
                  style={{ flex: 1, textAlign: "center", cursor: !isDone && !setWinner ? "pointer" : "default", userSelect: "none" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: "uppercase", color: c.muted, marginBottom: 8 }}>{side.name}</div>
                  <div style={{ fontFamily: "'Unbounded',sans-serif", fontSize: 80, fontWeight: 900, color: matchWinner === side.pos ? c.gold : setWinner === side.pos ? c.green : c.ink }}>
                    {side.score}
                  </div>
                </div>
              ))}
            </div>

            {setWinner && !matchWinner && (
              <div style={{ textAlign: "center", fontSize: 13, fontWeight: 800, textTransform: "uppercase", letterSpacing: 2, color: c.green }}>
                Set {currentSet?.set_number} → {setWinner === 1 ? p1Name : p2Name}
              </div>
            )}
            {matchWinner && (
              <div style={{ textAlign: "center", fontSize: 16, fontWeight: 900, textTransform: "uppercase", letterSpacing: 2, color: c.gold }}>
                {matchWinner === 1 ? p1Name : p2Name} Wins!
              </div>
            )}

            {!isDone && (
              <div style={{ display: "flex", gap: 12 }}>
                {[1, 2].map(pos => (
                  <div key={pos} style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
                    <button onClick={() => addPoint(pos)} disabled={!!setWinner} style={btnStyle(c.accent, setWinner)}>+ Point</button>
                    <button onClick={() => undoPoint(pos)} disabled={(pos === 1 ? s1 : s2) === 0} style={outlineBtnStyle}>↩ Undo</button>
                  </div>
                ))}
              </div>
            )}

            {/* Timeouts */}
            {!isDone && (
              <div style={{ display: "flex", gap: 12 }}>
                {[1, 2].map(pos => {
                  const used = timeoutsUsed[String(pos)] || 0;
                  return (
                    <button key={pos} disabled={used >= MAX_TIMEOUTS} onClick={() => callTimeout(pos)}
                      style={outlineBtnStyle}>
                      Timeout {pos === 1 ? p1Name : p2Name} ({MAX_TIMEOUTS - used} left)
                    </button>
                  );
                })}
              </div>
            )}

            {/* Substitutions */}
            {!isDone && (
              <div>
                <div style={{ fontSize: 11, color: c.muted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>Substitutions</div>
                {[1, 2].map(pos => (
                  <div key={pos} style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 11, color: c.muted, marginBottom: 4 }}>
                      {pos === 1 ? p1Name : p2Name} — {MAX_SUBS - (subsUsed[String(pos)] || 0)} left this set
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {lineup[pos].filter(r => r.on_court).map(r => (
                        <button key={r.team_member_id} disabled={(subsUsed[String(pos)] || 0) >= MAX_SUBS}
                          onClick={() => openSubPicker(pos, r.team_member_id)}
                          style={{ ...outlineBtnStyle, padding: "6px 10px", fontSize: 11 }}>
                          {r.name}{r.court_position === SERVE_POSITION ? " (serve)" : ""} ↔
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {!isDone && sets.length > 0 && (
              <button onClick={onUndoSet} style={{ ...outlineBtnStyle, marginTop: 4 }}>↩ Undo Last Set</button>
            )}
          </>
        )}
      </div>

      {walkoverModal}
      {lineupModal}
      {subModal}
    </div>
  );
}

function TopBtn({ onClick, children }) {
  return <button onClick={onClick} style={{ background: "transparent", color: c.muted, border: `1px solid ${c.border}`, borderRadius: 6, padding: "5px 12px", cursor: "pointer", fontSize: 12, fontWeight: 700, fontFamily: "inherit" }}>{children}</button>;
}
function btnStyle(color, disabled) {
  return { width: "100%", padding: "12px 0", borderRadius: 8, background: disabled ? c.surface : color, color: disabled ? c.muted : c.bg, border: "none", fontWeight: 800, fontSize: 13, fontFamily: "inherit", cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1 };
}
const outlineBtnStyle = { width: "100%", padding: "9px 0", background: "transparent", color: c.muted, border: `1px solid ${c.border}`, borderRadius: 8, fontSize: 12, fontWeight: 700, fontFamily: "inherit", cursor: "pointer" };

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
function BigButton({ children, onClick, color }) {
  return <button onClick={onClick} style={{ width: "100%", padding: "12px 16px", borderRadius: 10, background: `${color}18`, border: `2px solid ${color}`, color: c.ink, fontSize: 12, fontWeight: 800, cursor: "pointer", marginBottom: 8, fontFamily: "inherit" }}>{children}</button>;
}
function CancelButton({ onClick }) {
  return <button onClick={onClick} style={{ width: "100%", padding: "10px 0", background: "transparent", color: c.muted, border: `1px solid ${c.border}`, borderRadius: 8, fontSize: 12, fontWeight: 700, fontFamily: "inherit", cursor: "pointer", marginTop: 4 }}>Cancel</button>;
}
