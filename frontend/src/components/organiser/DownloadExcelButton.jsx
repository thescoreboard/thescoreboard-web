import { useState } from "react";
import { exportTournamentExcel } from "../../api/client";

/**
 * Downloads the tournament's Excel export. Visible wherever the caller
 * already has workspace access (backend enforces staff-or-above regardless).
 */
export function DownloadExcelButton({ tournamentId, flash }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const { blob, filename } = await exportTournamentExcel(tournamentId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      flash?.("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button className="btn btn-outline btn-sm" onClick={handleClick} disabled={loading}>
      {loading ? "Preparing…" : "Download Excel"}
    </button>
  );
}
