import { createContext, useContext } from "react";

export const AuthContext = createContext(null);

/** { status: "loading" | "signedOut" | "signedIn", user, login, logout, changePassword } */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export const ROLE_LABELS = {
  admin: "Admin",
  hod: "Head of department",
  faculty: "Faculty",
  student: "Student",
};
