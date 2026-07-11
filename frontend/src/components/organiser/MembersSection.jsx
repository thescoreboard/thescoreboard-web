/**
 * MembersSection — manage who can help run this tournament (admins only).
 *
 * Shows: current members (org owners locked; invited members can be
 * promoted/demoted/removed), live invite links (revocable), and a
 * generate-invite-link form (role + copy-to-clipboard).
 */
import { useState, useEffect, useCallback } from "react";
import {
  getTournamentMembers, createInvite, revokeInvite,
  updateMemberRole, removeMember,
} from "../../api/client";

const labelStyle = { fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: 2, color: "var(--muted)", fontFamily: "var(--font-display)", marginBottom: 4, display: "block" };

function RoleBadge({ role, source }) {
  if (source === "org") return <span className="pill pill-gold">Owner</span>;
  return role === "admin"
    ? <span className="pill pill-orange">Admin</span>
    : <span className="pill pill-green">Staff</span>;
}

export default function MembersSection({ tournamentId, currentUserId, flash }) {
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [inviteRole, setInviteRole] = useState("staff");
  const [creating, setCreating] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  const load = useCallback(async () => {
    try { setData(await getTournamentMembers(tournamentId)); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [tournamentId]);

  useEffect(() => { load(); }, [load]);

  const handleCreateInvite = async () => {
    setCreating(true);
    try {
      const invite = await createInvite(tournamentId, { role: inviteRole });
      await load();
      copyLink(invite.token, invite.invite_id);
      flash?.("Invite link created & copied!");
    } catch (e) { flash?.("Error: " + e.message); }
    finally { setCreating(false); }
  };

  const copyLink = (token, inviteId) => {
    navigator.clipboard.writeText(`${window.location.origin}/join/${token}`);
    setCopiedId(inviteId);
    setTimeout(() => setCopiedId(null), 2500);
  };

  const handleRevoke = async (inviteId) => {
    try { await revokeInvite(tournamentId, inviteId); load(); flash?.("Invite link revoked."); }
    catch (e) { flash?.("Error: " + e.message); }
  };

  const handleRoleChange = async (userId, role) => {
    try { await updateMemberRole(tournamentId, userId, role); load(); flash?.("Role updated."); }
    catch (e) { flash?.("Error: " + e.message); }
  };

  const handleRemove = async (userId, name) => {
    if (!window.confirm(`Remove ${name || "this member"} from the tournament?`)) return;
    try { await removeMember(tournamentId, userId); load(); flash?.("Member removed."); }
    catch (e) { flash?.("Error: " + e.message); }
  };

  const fmtExpiry = (iso) => {
    if (!iso) return "never expires";
    const d = new Date(iso);
    return `expires ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
  };

  if (loading) return <div style={{ fontSize: 13, color: "var(--muted)" }}>Loading team…</div>;
  if (!data) return <div style={{ fontSize: 13, color: "var(--muted)" }}>Could not load team members.</div>;

  return (
    <div>
      {/* ── Members list ── */}
      <div style={{ marginBottom: 20 }}>
        {data.members.map(m => (
          <div key={m.user_id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "10px 0", borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>
                {m.name || m.email}
                {m.user_id === currentUserId && <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 400 }}> (you)</span>}
              </div>
              {m.name && <div style={{ fontSize: 11, color: "var(--muted)" }}>{m.email}</div>}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
              <RoleBadge role={m.role} source={m.source} />
              {m.source === "invite" && (
                <>
                  <button className="btn btn-outline btn-sm"
                    onClick={() => handleRoleChange(m.user_id, m.role === "admin" ? "staff" : "admin")}>
                    {m.role === "admin" ? "Make Staff" : "Make Admin"}
                  </button>
                  <button className="btn btn-outline btn-sm" style={{ color: "var(--red, #dc2626)" }}
                    onClick={() => handleRemove(m.user_id, m.name)}>
                    Remove
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* ── Active invite links ── */}
      {data.invites.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <label style={labelStyle}>Active Invite Links</label>
          {data.invites.map(inv => (
            <div key={inv.invite_id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "8px 12px", background: "var(--elevated)", border: "1px solid var(--border)", borderRadius: 8, marginBottom: 8, flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                <RoleBadge role={inv.role} source="invite" />
                <span style={{ fontSize: 11, color: "var(--muted)" }}>
                  {fmtExpiry(inv.expires_at)} · used {inv.use_count}×
                </span>
              </div>
              <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                <button className="btn btn-outline btn-sm" onClick={() => copyLink(inv.token, inv.invite_id)}>
                  {copiedId === inv.invite_id ? "✓ Copied" : "Copy Link"}
                </button>
                <button className="btn btn-outline btn-sm" style={{ color: "var(--red, #dc2626)" }}
                  onClick={() => handleRevoke(inv.invite_id)}>
                  Revoke
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Generate new invite ── */}
      <div style={{ background: "var(--elevated)", border: "1.5px dashed var(--border)", borderRadius: 10, padding: "14px 16px" }}>
        <label style={labelStyle}>Invite Someone</label>
        <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>
          Generate a link and share it on WhatsApp — they log in (or sign up) and join instantly. Links expire after 7 days.
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select
            value={inviteRole}
            onChange={e => setInviteRole(e.target.value)}
            style={{ background: "var(--surface)", border: "1px solid var(--border-mid)", borderRadius: 6, padding: "7px 10px", fontSize: 13, color: "var(--ink)", fontFamily: "inherit", outline: "none" }}
          >
            <option value="staff">Staff — players, fixtures & scoring</option>
            <option value="admin">Admin — full control incl. members</option>
          </select>
          <button className="btn btn-primary btn-sm" disabled={creating} onClick={handleCreateInvite}>
            {creating ? "Creating…" : "Generate Invite Link"}
          </button>
        </div>
      </div>
    </div>
  );
}
