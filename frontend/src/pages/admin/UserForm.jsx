import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { Field, FormError, Select, TextInput } from "../../components/forms";
import { ROLE_LABELS } from "../../context/auth";

const EMPTY = { name: "", role: "faculty", email: "", roll_no: "", department_id: "", gender: "" };

/** Create (returns temp password) or edit a user. Fields follow the role's rules. */
export function UserForm({ departments, user, onSaved, onCancel }) {
  const editing = Boolean(user);
  const [form, setForm] = useState(() =>
    user
      ? {
          name: user.name,
          role: user.role,
          email: user.email ?? "",
          roll_no: user.roll_no ?? "",
          department_id: user.department_id ?? "",
          gender: user.gender ?? "",
          annotator: user.annotator ?? "",
        }
      : EMPTY,
  );
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const isStudent = form.role === "student";
  const hasGender = form.role === "faculty" || form.role === "hod";
  const needsDept = form.role !== "admin";

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    const body = {
      name: form.name.trim(),
      role: form.role,
      email: isStudent ? form.email.trim() || null : form.email.trim(),
      roll_no: isStudent ? form.roll_no.trim() : null,
      department_id: needsDept ? form.department_id || null : form.department_id || null,
      gender: hasGender ? form.gender || null : null,
      ...(editing && { annotator: isStudent ? null : form.annotator || null }),
    };
    try {
      if (editing) {
        const res = await api.patch(`/users/${user.id}`, body);
        onSaved({ user: res.data });
      } else {
        const res = await api.post("/users", body);
        onSaved(res.data);
      }
    } catch (err) {
      setError(errorMessage(err, "Couldn't save this user."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Field label="Full name">
          {(a) => <TextInput {...a} value={form.name} onChange={set("name")} autoComplete="off" />}
        </Field>
        <Field label="Role">
          {(a) => (
            <Select {...a} value={form.role} onChange={set("role")}>
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Department" hint={needsDept ? null : "Optional for IQAC admins."}>
          {(a) => (
            <Select {...a} value={form.department_id} onChange={set("department_id")}>
              <option value="">{needsDept ? "Choose a department" : "None"}</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} · {d.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {isStudent ? (
          <Field label="Roll number" hint="Students sign in with this, e.g. 2451-24-733-001.">
            {(a) => (
              <TextInput
                {...a}
                value={form.roll_no}
                onChange={set("roll_no")}
                autoCapitalize="characters"
                spellCheck={false}
              />
            )}
          </Field>
        ) : (
          <Field label="College email" hint="Staff sign in with this.">
            {(a) => (
              <TextInput
                {...a}
                type="email"
                value={form.email}
                onChange={set("email")}
                spellCheck={false}
              />
            )}
          </Field>
        )}
        {hasGender && (
          <Field
            label="Gender (optional)"
            hint="Admin-only. Used only for department-level bias checks, never shown on profiles."
          >
            {(a) => (
              <Select {...a} value={form.gender} onChange={set("gender")}>
                <option value="">Not recorded</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
                <option value="undisclosed">Prefers not to say</option>
              </Select>
            )}
          </Field>
        )}
        {editing && !isStudent && (
          <Field
            label="Labelling (evaluation)"
            hint="Annotators label comments on their own; an adjudicator settles their disagreements."
          >
            {(a) => (
              <Select {...a} value={form.annotator} onChange={set("annotator")}>
                <option value="">Not part of the evaluation</option>
                <option value="annotator">Annotator</option>
                <option value="adjudicator">Adjudicator</option>
              </Select>
            )}
          </Field>
        )}
      </div>
      <FormError>{error}</FormError>
      <div className="flex gap-2">
        <button type="submit" className="btn btn-primary" disabled={busy || !form.name.trim()}>
          {busy ? "Saving…" : editing ? "Save changes" : "Create user"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
