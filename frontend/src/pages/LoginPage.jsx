import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { errorMessage } from "../api/client";
import { Field, FormError, TextInput } from "../components/forms";
import { StandaloneLayout } from "../components/StandaloneLayout";
import { useAuth } from "../context/auth";

const FACTS = [
  {
    title: "Student feedback is anonymous",
    body: "Teachers never see your name with a comment; a one-way code only checks that each student submits once.",
  },
  {
    title: "Comments are screened before anyone reads them",
    body: "Abusive language is held back for an admin, and a filter removes names, phone and roll numbers.",
  },
  {
    title: "Small classes stay private",
    body: "Comments appear only once enough students respond, so no single answer stands out.",
  },
  {
    title: "Faculty approve their own profile",
    body: "Profiles are written from each teacher's records and stay hidden until they approve them.",
  },
];

export function LoginPage() {
  const { status, user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  if (status === "signedIn") {
    const home = location.state?.from || "/";
    return <Navigate to={user.must_change_pw ? "/change-password" : home} replace />;
  }

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const signedIn = await login(form.username.trim(), form.password);
      const from = location.state?.from;
      navigate(signedIn.must_change_pw ? "/change-password" : from || "/", { replace: true });
    } catch (err) {
      setError(errorMessage(err, "Couldn't sign in. Try again."));
      setForm((f) => ({ ...f, password: "" }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <StandaloneLayout notes={FACTS}>
      <h1 className="m-0 font-marker text-marker">Sign in</h1>
      <p className="mt-2 mb-8 text-body text-muted">
        Staff use their college email. Students use their roll number.
      </p>
      <form className="flex flex-col gap-5" onSubmit={submit} noValidate>
        <Field label="Email or roll number">
          {(a11y) => (
            <TextInput
              {...a11y}
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
          )}
        </Field>
        <Field label="Password">
          {(a11y) => (
            <TextInput
              {...a11y}
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          )}
        </Field>
        <FormError>{error}</FormError>
        <button
          type="submit"
          className="btn btn-primary h-10 w-full"
          disabled={busy || !form.username.trim() || !form.password}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="m-0 text-small text-muted">
          Forgot your password? Ask your administrator to reset it.
        </p>
      </form>
    </StandaloneLayout>
  );
}
