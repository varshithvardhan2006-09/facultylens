import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { errorMessage } from "../api/client";
import { Field, FormError, TextInput } from "../components/forms";
import { StandaloneLayout } from "../components/StandaloneLayout";
import { useAuth } from "../context/auth";

const MIN_LENGTH = 10;

export function ChangePasswordPage() {
  const { status, user, changePassword, logout } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  if (status === "loading") return null;
  if (status === "signedOut") return <Navigate to="/login" replace />;
  const forced = user.must_change_pw;

  const tooShort = form.next.length > 0 && form.next.length < MIN_LENGTH;
  const sameAsOld = form.next.length > 0 && form.next === form.current;
  const mismatch = form.confirm.length > 0 && form.confirm !== form.next;
  const ready =
    form.current && form.next.length >= MIN_LENGTH && !sameAsOld && form.confirm === form.next;

  async function submit(event) {
    event.preventDefault();
    setTouched(true);
    if (!ready) return;
    setError(null);
    setBusy(true);
    try {
      await changePassword(form.current, form.next);
      navigate("/", { replace: true });
    } catch (err) {
      setError(errorMessage(err, "Couldn't change the password. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <StandaloneLayout>
      <h1 className="m-0 font-marker text-marker">
        {forced ? "Choose your own password" : "Change password"}
      </h1>
      <p className="mt-2 mb-8 text-body text-muted">
        {forced
          ? `Signed in as ${user.name}. Replace the temporary password before you continue.`
          : `Signed in as ${user.name}.`}
      </p>
      <form className="flex flex-col gap-5" onSubmit={submit} noValidate>
        <Field label={forced ? "Temporary password" : "Current password"}>
          {(a11y) => (
            <TextInput
              {...a11y}
              type="password"
              autoComplete="current-password"
              value={form.current}
              onChange={(e) => setForm({ ...form, current: e.target.value })}
            />
          )}
        </Field>
        <Field
          label="New password"
          hint={`At least ${MIN_LENGTH} characters. A short phrase is easier to remember.`}
          error={
            (touched || form.next.length >= MIN_LENGTH) && tooShort
              ? `Use at least ${MIN_LENGTH} characters.`
              : sameAsOld
                ? "Choose a password different from the current one."
                : null
          }
        >
          {(a11y) => (
            <TextInput
              {...a11y}
              type="password"
              autoComplete="new-password"
              value={form.next}
              onChange={(e) => setForm({ ...form, next: e.target.value })}
            />
          )}
        </Field>
        <Field
          label="Repeat new password"
          error={mismatch ? "The two new passwords don't match." : null}
        >
          {(a11y) => (
            <TextInput
              {...a11y}
              type="password"
              autoComplete="new-password"
              value={form.confirm}
              onChange={(e) => setForm({ ...form, confirm: e.target.value })}
            />
          )}
        </Field>
        <FormError>{error}</FormError>
        <button type="submit" className="btn btn-primary h-10 w-full" disabled={busy || !ready}>
          {busy ? "Saving…" : "Save password"}
        </button>
        {forced ? (
          <button type="button" className="btn btn-ghost h-10 w-full" onClick={logout}>
            Sign out
          </button>
        ) : (
          <Link to="/" className="text-center text-body text-muted underline">
            Cancel
          </Link>
        )}
      </form>
    </StandaloneLayout>
  );
}
