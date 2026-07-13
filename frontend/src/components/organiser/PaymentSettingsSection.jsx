import { useState } from "react";
import { updateTournament } from "../../api/client";
import SetupSection from "./SetupSection";
import { MediaUpload } from "../shared/MediaUpload";

const labelStyle = { fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: 2, color: "var(--muted)", fontFamily: "var(--font-display)", marginBottom: 4, display: "block" };
const inputStyle = { background: "var(--elevated)", border: "1px solid var(--border-mid)", borderRadius: 6, padding: "7px 10px", fontSize: 13, color: "var(--ink)", width: "100%", outline: "none", fontFamily: "inherit", boxSizing: "border-box" };
const fieldStyle = { marginBottom: 14 };

/**
 * Payment collection settings — one shared QR code / UPI ID / entry fee for
 * the whole tournament. Once an amount and at least one payment method are
 * set, players must upload a payment screenshot to complete registration,
 * and organisers get a review/check-in flow in the Registration tab.
 */
export default function PaymentSettingsSection({ t, defaultOpen, onSaved, flash }) {
  const [form, setForm] = useState(() => ({
    payment_amount: t.payment_amount != null ? String(t.payment_amount) : "",
    payment_upi_id: t.payment_upi_id || "",
  }));
  const [qrUrl, setQrUrl] = useState(t.payment_qr_url || null);
  const [saving, setSaving] = useState(false);

  const status = t.payment_enabled ? "complete" : "optional";

  const save = async () => {
    setSaving(true);
    try {
      await updateTournament(t.org_id, t.tournament_id, {
        payment_amount: form.payment_amount ? parseInt(form.payment_amount, 10) : null,
        payment_upi_id: form.payment_upi_id.trim() || null,
        payment_qr_url: qrUrl || null,
      });
      onSaved?.();
      flash?.("Payment settings updated!");
    } catch (e) { flash?.("Error: " + e.message); }
    finally { setSaving(false); }
  };

  return (
    <SetupSection icon="💳" title="Payment Collection" status={status} defaultOpen={defaultOpen}>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16, lineHeight: 1.6 }}>
        Set an entry fee and a way to pay it (UPI ID and/or QR code). Once both are set,
        players must upload a payment screenshot to finish registering, and you'll be able
        to review and check in each payment from the Registration tab. Leave blank to skip
        payment collection — registration works as before.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 20px" }}>
        <div style={fieldStyle}>
          <label style={labelStyle}>Entry Fee (₹)</label>
          <input type="number" min="0" style={inputStyle} placeholder="e.g. 200"
            value={form.payment_amount}
            onChange={e => setForm(f => ({ ...f, payment_amount: e.target.value }))} />
        </div>
        <div style={fieldStyle}>
          <label style={labelStyle}>UPI ID</label>
          <input style={inputStyle} placeholder="yourname@upi"
            value={form.payment_upi_id}
            onChange={e => setForm(f => ({ ...f, payment_upi_id: e.target.value }))} />
        </div>
      </div>

      <div style={{ ...fieldStyle, maxWidth: 180 }}>
        <MediaUpload
          label="QR Code"
          hint="Optional — shown to players alongside the UPI ID"
          bucket="team-banners"
          resourceType="payments/qr"
          resourceId={t.tournament_id}
          filename="qr"
          enforceAspect="1:1"
          maxWidth={800}
          previewUrl={qrUrl}
          previewStyle={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
          onUploaded={setQrUrl}
        />
      </div>

      <div style={{ marginTop: 4 }}>
        <button className="btn btn-primary btn-sm" disabled={saving} onClick={save}>
          {saving ? "Saving…" : "Save Changes"}
        </button>
      </div>
    </SetupSection>
  );
}
