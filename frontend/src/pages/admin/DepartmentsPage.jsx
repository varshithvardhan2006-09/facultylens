import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { Field, FormError, TextInput } from "../../components/forms";
import { PageHeader, Panel } from "../../components/PageHeader";
import { useDepartments } from "../../hooks/useDepartments";

function RenameRow({ department, onDone }) {
  const [name, setName] = useState(department.name);
  const [error, setError] = useState(null);
  async function save(event) {
    event.preventDefault();
    try {
      await api.patch(`/departments/${department.id}`, { name: name.trim() });
      onDone(true);
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <form onSubmit={save} className="flex flex-wrap items-center gap-2">
      <div className="w-full max-w-sm">
        <TextInput
          aria-label={`New name for ${department.code}`}
          value={name}
          onChange={(e) => setName(e.target.value)}
          // eslint-disable-next-line jsx-a11y/no-autofocus -- focus moves into the row being edited
          autoFocus
        />
      </div>
      <button type="submit" className="btn btn-primary h-8" disabled={name.trim().length < 2}>
        Save
      </button>
      <button type="button" className="btn btn-ghost h-8" onClick={() => onDone(false)}>
        Cancel
      </button>
      <FormError>{error}</FormError>
    </form>
  );
}

export function DepartmentsPage() {
  const departments = useDepartments();
  const [form, setForm] = useState({ name: "", code: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);

  async function add(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/departments", { name: form.name.trim(), code: form.code.trim() });
      setForm({ name: "", code: "" });
      departments.reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't add the department."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader title="Departments">
        Every user except admins belongs to one department. The short code is used in bulk uploads
        and reports.
      </PageHeader>

      <Panel title="Add a department">
        <form onSubmit={add} className="flex flex-col gap-4" noValidate>
          <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto] md:items-end">
            <Field label="Name">
              {(a) => (
                <TextInput
                  {...a}
                  placeholder="Computer Science and Engineering"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              )}
            </Field>
            <Field label="Code">
              {(a) => (
                <TextInput
                  {...a}
                  placeholder="CSE"
                  autoCapitalize="characters"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
                />
              )}
            </Field>
            <button
              type="submit"
              className="btn btn-primary h-10"
              disabled={busy || form.name.trim().length < 2 || form.code.trim().length < 2}
            >
              {busy ? "Adding…" : "Add department"}
            </button>
          </div>
          <FormError>{error}</FormError>
        </form>
      </Panel>

      <section aria-labelledby="dept-list-h" className="flex flex-col gap-2">
        <h2 id="dept-list-h" className="text-section font-medium">
          {departments.data ? `${departments.list.length} departments` : "Departments"}
        </h2>
        <div className="card overflow-hidden">
          {departments.error ? (
            <div className="flex flex-wrap items-center gap-3 p-[var(--card-pad)]">
              <FormError>Couldn&apos;t load departments.</FormError>
              <button type="button" className="btn btn-ghost h-8 px-2" onClick={departments.reload}>
                Retry
              </button>
            </div>
          ) : departments.data && departments.list.length === 0 ? (
            <p className="m-0 p-[var(--card-pad)] text-body text-muted">
              No departments yet. Add the first one above; users and courses need one.
            </p>
          ) : (
            <ul className="m-0 list-none p-0">
              {(departments.data ? departments.list : [null, null, null]).map((d, i) => (
                <li
                  key={d?.id ?? i}
                  className="flex min-h-[var(--row-height)] flex-wrap items-center gap-x-4 gap-y-2 border-rule px-[var(--card-pad)] py-2 [&+&]:border-t"
                >
                  {!d ? (
                    <span className="skeleton h-4 w-72" />
                  ) : editing === d.id ? (
                    <>
                      <span className="w-16 font-medium">{d.code}</span>
                      <RenameRow
                        department={d}
                        onDone={(saved) => {
                          setEditing(null);
                          if (saved) departments.reload();
                        }}
                      />
                    </>
                  ) : (
                    <>
                      <span className="w-16 font-medium">{d.code}</span>
                      <span className="flex-1">{d.name}</span>
                      <button
                        type="button"
                        className="btn btn-ghost h-8 px-2 text-small"
                        onClick={() => setEditing(d.id)}
                      >
                        Rename
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
