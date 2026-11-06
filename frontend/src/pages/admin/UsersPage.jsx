import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, errorMessage } from "../../api/client";
import { CredentialsNotice } from "../../components/CredentialsNotice";
import { FormError, Select, TextInput } from "../../components/forms";
import { PageHeader, Panel } from "../../components/PageHeader";
import { ROLE_LABELS, useAuth } from "../../context/auth";
import { useDepartments } from "../../hooks/useDepartments";
import { BulkAdd } from "./BulkAdd";
import { UserForm } from "./UserForm";

const PAGE_SIZE = 50;

function StatusPill({ user }) {
  if (!user.is_active) return <span className="pill pill-neutral">Deactivated</span>;
  if (user.must_change_pw) return <span className="pill pill-warning">Temporary password</span>;
  return <span className="pill pill-positive">Active</span>;
}

export function UsersPage() {
  const { user: me } = useAuth();
  const departments = useDepartments();
  const [filters, setFilters] = useState({ q: "", role: "", department_id: "", inactive: false });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [panel, setPanel] = useState(null); // "add" | "bulk" | {edit: user}
  const [credentials, setCredentials] = useState(null);
  const [rowError, setRowError] = useState(null);
  const [version, setVersion] = useState(0);

  const reload = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    let alive = true;
    const params = { page, page_size: PAGE_SIZE };
    if (filters.q.trim()) params.q = filters.q.trim();
    if (filters.role) params.role = filters.role;
    if (filters.department_id) params.department_id = filters.department_id;
    if (filters.inactive) params.include_inactive = true;
    const timer = setTimeout(
      () => {
        api
          .get("/users", { params })
          .then((res) => alive && (setData(res.data), setLoadError(null)))
          .catch((err) => alive && setLoadError(errorMessage(err)));
      },
      filters.q ? 250 : 0,
    );
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [filters, page, version]);

  const setFilter = (key) => (e) => {
    const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };

  async function resetPassword(u) {
    setRowError(null);
    try {
      const res = await api.post(`/users/${u.id}/reset-password`);
      setCredentials([
        { name: u.name, role: u.role, email: u.email, roll_no: u.roll_no, ...res.data },
      ]);
      reload();
    } catch (err) {
      setRowError(errorMessage(err));
    }
  }

  async function deactivate(u) {
    if (!window.confirm(`Deactivate ${u.name}? They won't be able to sign in. Records stay.`)) {
      return;
    }
    setRowError(null);
    try {
      await api.delete(`/users/${u.id}`);
      reload();
    } catch (err) {
      setRowError(errorMessage(err));
    }
  }

  async function reactivate(u) {
    setRowError(null);
    try {
      await api.patch(`/users/${u.id}`, { is_active: true });
      reload();
    } catch (err) {
      setRowError(errorMessage(err));
    }
  }

  const total = data?.total ?? 0;
  const first = total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const last = Math.min(page * PAGE_SIZE, total);
  const filtered = Boolean(filters.q || filters.role || filters.department_id);

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader
        title="Users"
        actions={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              aria-expanded={panel === "bulk"}
              onClick={() => setPanel(panel === "bulk" ? null : "bulk")}
            >
              Bulk add
            </button>
            <button
              type="button"
              className="btn btn-primary"
              aria-expanded={panel === "add"}
              onClick={() => setPanel(panel === "add" ? null : "add")}
            >
              Add user
            </button>
          </>
        }
      >
        Staff sign in with their email, students with their roll number. New accounts get a
        temporary password that must be changed at first sign-in.
      </PageHeader>

      {credentials && (
        <CredentialsNotice credentials={credentials} onDone={() => setCredentials(null)} />
      )}

      {panel === "add" && (
        <Panel title="Add a user">
          <UserForm
            departments={departments.list}
            onCancel={() => setPanel(null)}
            onSaved={({ user, temp_password }) => {
              setPanel(null);
              setCredentials([{ ...user, temp_password }]);
              reload();
            }}
          />
        </Panel>
      )}
      {panel === "bulk" && (
        <Panel title="Bulk add from CSV">
          <BulkAdd
            onCancel={() => setPanel(null)}
            onCreated={(creds) => {
              setPanel(null);
              setCredentials(creds);
              reload();
            }}
          />
        </Panel>
      )}
      {panel?.edit && (
        <Panel title={`Edit ${panel.edit.name}`}>
          <UserForm
            departments={departments.list}
            user={panel.edit}
            onCancel={() => setPanel(null)}
            onSaved={() => {
              setPanel(null);
              reload();
            }}
          />
        </Panel>
      )}

      <section aria-labelledby="people-h" className="flex flex-col gap-3">
        <h2 id="people-h" className="sr-only">
          People
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,2fr)_1fr_1fr_auto]">
          <TextInput
            type="search"
            aria-label="Search by name, email or roll number"
            placeholder="Search name, email or roll number"
            value={filters.q}
            onChange={setFilter("q")}
          />
          <Select aria-label="Role" value={filters.role} onChange={setFilter("role")}>
            <option value="">All roles</option>
            {Object.entries(ROLE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Department"
            value={filters.department_id}
            onChange={setFilter("department_id")}
          >
            <option value="">All departments</option>
            {departments.list.map((d) => (
              <option key={d.id} value={d.id}>
                {d.code} · {d.name}
              </option>
            ))}
          </Select>
          <label className="flex h-10 cursor-pointer items-center gap-2 text-body text-muted">
            <input
              type="checkbox"
              className="size-4 accent-[var(--primary)]"
              checked={filters.inactive}
              onChange={setFilter("inactive")}
            />
            Show deactivated
          </label>
        </div>
        <FormError>{rowError}</FormError>

        <div className="card overflow-hidden">
          {loadError ? (
            <div className="flex flex-wrap items-center gap-3 p-[var(--card-pad)]">
              <FormError>{loadError}</FormError>
              <button type="button" className="btn btn-ghost h-8 px-2" onClick={reload}>
                Retry
              </button>
            </div>
          ) : data && data.items.length === 0 ? (
            <p className="m-0 p-[var(--card-pad)] text-body text-muted">
              {filtered
                ? "No users match these filters."
                : "No users yet. Add the first staff member or upload a CSV of students."}
            </p>
          ) : (
            <table className="w-full border-collapse text-body">
              <thead className="max-md:sr-only">
                <tr className="text-left text-small text-muted">
                  <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                    Name
                  </th>
                  <th scope="col" className="h-10 px-3 font-medium">
                    Role
                  </th>
                  <th scope="col" className="h-10 px-3 font-medium">
                    Department
                  </th>
                  <th scope="col" className="h-10 px-3 font-medium">
                    Status
                  </th>
                  <th scope="col" className="h-10 px-[var(--card-pad)] text-right font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? Array.from({ length: 6 }, () => null)).map((u, i) =>
                  u ? (
                    <tr
                      key={u.id}
                      className="border-t border-rule max-md:grid max-md:grid-cols-[1fr_auto] max-md:gap-x-3 max-md:gap-y-1 max-md:px-4 max-md:py-3"
                    >
                      <td className="h-[52px] px-[var(--card-pad)] max-md:h-auto max-md:p-0">
                        <div className="font-medium">{u.name}</div>
                        <div className="text-small text-muted">{u.email ?? u.roll_no}</div>
                      </td>
                      <td className="px-3 max-md:hidden">{ROLE_LABELS[u.role]}</td>
                      <td className="px-3 max-md:col-span-2 max-md:row-start-2 max-md:p-0 max-md:text-small max-md:text-muted">
                        <span className="md:hidden">{ROLE_LABELS[u.role]} · </span>
                        {departments.byId[u.department_id]?.code ?? (
                          <span className="text-faint">–</span>
                        )}
                      </td>
                      <td className="px-3 max-md:col-start-2 max-md:row-start-1 max-md:p-0">
                        <StatusPill user={u} />
                      </td>
                      <td className="px-[var(--card-pad)] text-right max-md:col-span-2 max-md:p-0 max-md:text-left">
                        <div className="flex justify-end gap-1 max-md:justify-start max-md:-ml-2">
                          {(u.role === "faculty" || u.role === "hod") && (
                            <Link
                              to={`/admin/faculty/${u.id}/profile`}
                              className="btn btn-ghost h-8 px-2 text-small no-underline"
                            >
                              Profile
                            </Link>
                          )}
                          <button
                            type="button"
                            className="btn btn-ghost h-8 px-2 text-small"
                            onClick={() => setPanel({ edit: u })}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost h-8 px-2 text-small"
                            onClick={() => resetPassword(u)}
                          >
                            Reset password
                          </button>
                          {u.id !== me.id &&
                            (u.is_active ? (
                              <button
                                type="button"
                                className="btn btn-ghost h-8 px-2 text-small text-negative"
                                onClick={() => deactivate(u)}
                              >
                                Deactivate
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-ghost h-8 px-2 text-small"
                                onClick={() => reactivate(u)}
                              >
                                Reactivate
                              </button>
                            ))}
                        </div>
                      </td>
                    </tr>
                  ) : (
                    <tr key={i} className="border-t border-rule">
                      <td colSpan={5} className="h-[52px] px-[var(--card-pad)]">
                        <span className="skeleton h-4 w-full max-w-[640px]" />
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          )}
        </div>
        {data && total > 0 && (
          <div className="flex items-center justify-between gap-3 text-small text-muted">
            <span className="num">
              {first}–{last} of {total.toLocaleString("en-IN")}
            </span>
            {total > PAGE_SIZE && (
              <div className="flex gap-1">
                <button
                  type="button"
                  className="btn btn-ghost h-8 px-2"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-ghost h-8 px-2"
                  disabled={last >= total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
