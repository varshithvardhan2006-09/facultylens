import { useCallback, useEffect, useMemo, useState } from "react";
import { api, refreshSession, setAccessToken, setAuthHandlers } from "../api/client";
import { AuthContext } from "./auth";

/** Restores the session from the refresh cookie on load; keeps the access token in memory. */
export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: "loading", user: null });

  const accept = useCallback((data) => {
    setAccessToken(data.access_token);
    setState({ status: "signedIn", user: data.user });
    return data.user;
  }, []);

  const signOutLocally = useCallback(() => {
    setAccessToken(null);
    setState({ status: "signedOut", user: null });
  }, []);

  useEffect(() => {
    let alive = true;
    refreshSession()
      .then((data) => {
        if (!alive) return;
        if (data) accept(data);
        else signOutLocally();
      })
      .catch(() => alive && signOutLocally()); // API unreachable: the sign-in page explains it
    setAuthHandlers({
      onSessionLost: signOutLocally,
      onPasswordChangeRequired: () =>
        setState((s) => (s.user ? { ...s, user: { ...s.user, must_change_pw: true } } : s)),
    });
    return () => {
      alive = false;
    };
  }, [accept, signOutLocally]);

  const login = useCallback(
    async (username, password) => {
      const res = await api.post("/auth/login", { username, password }, { _skipAuthRetry: true });
      return accept(res.data);
    },
    [accept],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout", null, { _skipAuthRetry: true });
    } catch {
      // Signing out here still has to work when the server can't be reached.
    } finally {
      signOutLocally();
    }
  }, [signOutLocally]);

  const changePassword = useCallback(
    async (currentPassword, newPassword) => {
      const res = await api.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      return accept(res.data);
    },
    [accept],
  );

  const value = useMemo(
    () => ({ ...state, login, logout, changePassword }),
    [state, login, logout, changePassword],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
