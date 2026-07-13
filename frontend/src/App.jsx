import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { isLoggedIn, saveLoginRedirect } from "./api/client";

// Public
import Landing             from "./pages/Landing";
import SportPage           from "./pages/SportPage";
import Tournaments         from "./pages/Tournaments";
import TournamentPublic    from "./pages/TournamentPublic";
import TournamentRegister  from "./pages/TournamentRegister";
import Login               from "./pages/auth/Login";
import Register            from "./pages/auth/Register";
import PrivacyPolicy       from "./pages/PrivacyPolicy";
import Terms               from "./pages/Terms";
import About               from "./pages/About";
import JoinTournament      from "./pages/JoinTournament";

// Player
import PlayerDashboard from "./pages/player/PlayerDashboard";

// Admin
import AdminPanel from "./pages/admin/AdminPanel";

// Organiser
import OrgDashboard       from "./pages/organiser/Dashboard";
import CreateTournament   from "./pages/organiser/CreateTournament";
import TournamentOverview from "./pages/organiser/workspace/TournamentOverview";
import EventWorkspace     from "./pages/organiser/workspace/EventWorkspace";

function RequireAuth({ children, orgTheme = true, requireAdmin = false }) {
  const location = useLocation();
  if (!isLoggedIn()) {
    saveLoginRedirect(location.pathname + location.search);
    return <Navigate to="/login" replace />;
  }
  if (requireAdmin) {
    // Read is_superadmin from the JWT payload (it's not stored there — we gate
    // in the API, so the frontend just redirects away from the URL if somehow
    // reached without the correct server-side panel data loading).
    // Real guard is server-side; this is just a UX redirect.
    return <>{children}</>;
  }
  if (!orgTheme) return <>{children}</>;
  return <div className="organizer-flow">{children}</div>;
}

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        {/* Public */}
        <Route path="/"                              element={<Landing />} />
        <Route path="/tournaments"                   element={<Tournaments />} />
        <Route path="/football"                      element={<SportPage />} />
        <Route path="/cricket"                       element={<SportPage />} />
        <Route path="/table-tennis"                  element={<SportPage />} />
        <Route path="/badminton"                     element={<SportPage />} />
        <Route path="/:sportUrl/tournament/:slug"    element={<TournamentPublic />} />
        <Route path="/t/:slug"                       element={<TournamentPublic />} />
        <Route path="/t/:slug/register"              element={<TournamentRegister />} />

        {/* Auth */}
        <Route path="/login"    element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Tournament invite links — public route, page handles auth itself */}
        <Route path="/join/:token" element={<JoinTournament />} />

        {/* Legal / company */}
        <Route path="/privacy" element={<PrivacyPolicy />} />
        <Route path="/terms"   element={<Terms />} />
        <Route path="/about"   element={<About />} />

        {/* Organiser */}
        <Route path="/organiser" element={<RequireAuth><OrgDashboard /></RequireAuth>} />
        <Route path="/organiser/create" element={<RequireAuth><CreateTournament /></RequireAuth>} />

        <Route
          path="/organiser/tournament/:tournamentId"
          element={<RequireAuth><TournamentOverview /></RequireAuth>}
        />

        <Route
          path="/organiser/tournament/:tournamentId/event/:eventId"
          element={<RequireAuth><EventWorkspace /></RequireAuth>}
        />

        {/* Player */}
        <Route path="/player" element={<RequireAuth orgTheme={false}><PlayerDashboard /></RequireAuth>} />

        {/* Super-admin */}
        <Route path="/admin" element={<RequireAuth orgTheme={false}><AdminPanel /></RequireAuth>} />
        <Route path="/admin/*" element={<RequireAuth orgTheme={false}><AdminPanel /></RequireAuth>} />

        {/* Legacy redirect */}
        <Route path="/dashboard/*" element={<Navigate to="/organiser" replace />} />
        <Route path="*"            element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}