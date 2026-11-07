import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "../context/auth";
import { LandingPage } from "../pages/LandingPage";

function SessionCheck() {
  return (
    <div className="grid min-h-dvh place-items-center bg-ground" role="status" aria-live="polite">
      <span className="text-body text-muted">Checking your session…</span>
    </div>
  );
}

/** Signed-in users only; a temporary password must be changed before anything else. */
export function RequireAuth() {
  const { status, user, signedOutOnPurpose } = useAuth();
  const location = useLocation();
  if (status === "loading") return <SessionCheck />;
  if (status === "signedOut") {
    // Visitors to the front door get the landing page; anywhere else goes to sign-in.
    if (location.pathname === "/") return <LandingPage />;
    // After signing out, the next person must not land on the previous user's page.
    const from = signedOutOnPurpose ? undefined : { from: location.pathname };
    return <Navigate to="/login" replace state={from} />;
  }
  if (user.must_change_pw) return <Navigate to="/change-password" replace />;
  return <Outlet />;
}

function NotAllowed({ children }) {
  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-2">
      <h1 className="m-0 font-marker text-marker">Not available for your account</h1>
      <p className="m-0 max-w-[60ch] text-muted">{children}</p>
    </div>
  );
}

/** Renders the child routes for the listed roles, otherwise a plain "not allowed" page. */
export function RequireRole({ roles }) {
  const { user } = useAuth();
  if (!roles.includes(user.role)) {
    return (
      <NotAllowed>
        This page is for other roles. If you think you should have access, ask your administrator.
      </NotAllowed>
    );
  }
  return <Outlet />;
}

/** The labelling tool: only accounts the admin marked as annotator or adjudicator. */
export function RequireAnnotator() {
  const { user } = useAuth();
  if (!user.annotator) {
    return (
      <NotAllowed>
        Labelling is for the evaluation team. The administrator can add you on the Users page.
      </NotAllowed>
    );
  }
  return <Outlet />;
}
