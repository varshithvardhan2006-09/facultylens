import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, errorMessage } from "../../api/client";
import { Field, FormError, Select, TextInput } from "../../components/forms";
import { PageHeader, Panel } from "../../components/PageHeader";
import { useDepartments } from "../../hooks/useDepartments";
import { currentAcademicYear } from "../../lib/academicYear";

function NewOffering({ departments, onCancel }) {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    code: "",
    name: "",
    department_id: "",
    academic_year: currentAcademicYear(),
    semester: "1",
    section: "A",
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const ready = form.code.trim() && form.name.trim().length >= 2 && form.department_id;

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post("/courses", { ...form, semester: Number(form.semester) });
      navigate(`/admin/courses/${res.data.id}`);
    } catch (err) {
      setError(errorMessage(err, "Couldn't create the offering."));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1fr_2fr_1.5fr]">
        <Field label="Course code">
          {(a) => <TextInput {...a} placeholder="CS501" value={form.code} onChange={set("code")} />}
        </Field>
        <Field label="Course name">
          {(a) => (
            <TextInput
              {...a}
              placeholder="Compiler Design"
              value={form.name}
              onChange={set("name")}
            />
          )}
        </Field>
        <Field label="Department">
          {(a) => (
            <Select {...a} value={form.department_id} onChange={set("department_id")}>
              <option value="">Choose a department</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} · {d.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Academic year" hint="Format 2026-27">
          {(a) => <TextInput {...a} value={form.academic_year} onChange={set("academic_year")} />}
        </Field>
        <Field label="Semester">
          {(a) => (
            <Select {...a} value={form.semester} onChange={set("semester")}>
              {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
                <option key={s} value={s}>
                  Semester {s}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Section" hint="Each section is its own offering with its own students.">
          {(a) => (
            <TextInput
              {...a}
              value={form.section}
              maxLength={4}
              onChange={(e) => setForm({ ...form, section: e.target.value.toUpperCase() })}
            />
          )}
        </Field>
      </div>
      <FormError>{error}</FormError>
      <div className="flex gap-2">
        <button type="submit" className="btn btn-primary" disabled={busy || !ready}>
          {busy ? "Creating…" : "Create offering"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export function CoursesPage() {
  const departments = useDepartments();
  const [adding, setAdding] = useState(false);
  const [filters, setFilters] = useState({ department_id: "", academic_year: "", semester: "" });
  const [courses, setCourses] = useState(null);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0);

  const [seenYears, setSeenYears] = useState([]);

  useEffect(() => {
    let alive = true;
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
    api
      .get("/courses", { params })
      .then((res) => {
        if (!alive) return;
        setCourses(res.data);
        setError(null);
        // Remember every year seen, so filtering doesn't remove the other years from the list.
        setSeenYears((y) => [...new Set([...y, ...res.data.map((c) => c.academic_year)])]);
      })
      .catch((err) => alive && setError(errorMessage(err)));
    return () => {
      alive = false;
    };
  }, [filters, version]);

  const years = [...new Set([currentAcademicYear(), ...seenYears])].sort().reverse();
  const setFilter = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }));
  const filtered = Object.values(filters).some(Boolean);

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader
        title="Courses"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            aria-expanded={adding}
            onClick={() => setAdding(!adding)}
          >
            Add offering
          </button>
        }
      >
        A course offering is one course in one section of one semester. Feedback forms are later
        created per offering and teacher.
      </PageHeader>

      {adding && (
        <Panel title="New course offering">
          <NewOffering departments={departments.list} onCancel={() => setAdding(false)} />
        </Panel>
      )}

      <section aria-labelledby="courses-h" className="flex flex-col gap-3">
        <h2 id="courses-h" className="sr-only">
          Course offerings
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
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
          <Select
            aria-label="Academic year"
            value={filters.academic_year}
            onChange={setFilter("academic_year")}
          >
            <option value="">All years</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </Select>
          <Select aria-label="Semester" value={filters.semester} onChange={setFilter("semester")}>
            <option value="">All semesters</option>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
              <option key={s} value={s}>
                Semester {s}
              </option>
            ))}
          </Select>
        </div>

        <div className="card overflow-hidden">
          {error ? (
            <div className="flex flex-wrap items-center gap-3 p-[var(--card-pad)]">
              <FormError>{error}</FormError>
              <button
                type="button"
                className="btn btn-ghost h-8 px-2"
                onClick={() => setVersion((v) => v + 1)}
              >
                Retry
              </button>
            </div>
          ) : courses && courses.length === 0 ? (
            <p className="m-0 p-[var(--card-pad)] text-body text-muted">
              {filtered
                ? "No offerings match these filters."
                : "No course offerings yet. Add one, then assign its teacher and students."}
            </p>
          ) : (
            <table className="w-full border-collapse text-body">
              <thead className="max-md:sr-only">
                <tr className="text-left text-small text-muted">
                  <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                    Course
                  </th>
                  <th scope="col" className="h-10 px-3 font-medium">
                    Department
                  </th>
                  <th scope="col" className="h-10 px-3 font-medium">
                    Year · semester · section
                  </th>
                  <th scope="col" className="h-10 px-3 font-medium">
                    Taught by
                  </th>
                  <th scope="col" className="h-10 px-[var(--card-pad)] text-right font-medium">
                    Students
                  </th>
                </tr>
              </thead>
              <tbody>
                {(courses ?? [null, null, null, null]).map((c, i) =>
                  c ? (
                    <tr
                      key={c.id}
                      className="border-t border-rule hover:bg-raised max-md:flex max-md:flex-col max-md:gap-0.5 max-md:px-4 max-md:py-3"
                    >
                      <td className="h-[var(--row-height)] px-[var(--card-pad)] max-md:h-auto max-md:p-0">
                        <Link
                          to={`/admin/courses/${c.id}`}
                          className="font-medium no-underline hover:underline"
                        >
                          {c.code} · {c.name}
                        </Link>
                      </td>
                      <td className="px-3 max-md:p-0 max-md:text-small max-md:text-muted">
                        {departments.byId[c.department_id]?.code ?? "–"}
                      </td>
                      <td className="num px-3 max-md:p-0 max-md:text-small max-md:text-muted">
                        {c.academic_year} · Sem {c.semester} · {c.section}
                      </td>
                      <td className="px-3 max-md:p-0 max-md:text-small">
                        {c.faculty.length ? (
                          c.faculty.map((f) => f.name).join(", ")
                        ) : (
                          <span className="pill pill-warning">No teacher yet</span>
                        )}
                      </td>
                      <td className="num px-[var(--card-pad)] text-right max-md:p-0 max-md:text-left max-md:text-small max-md:text-muted">
                        {c.student_count}
                        <span className="md:hidden"> students</span>
                      </td>
                    </tr>
                  ) : (
                    <tr key={i} className="border-t border-rule">
                      <td colSpan={5} className="h-[var(--row-height)] px-[var(--card-pad)]">
                        <span className="skeleton h-4 w-full max-w-[640px]" />
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
