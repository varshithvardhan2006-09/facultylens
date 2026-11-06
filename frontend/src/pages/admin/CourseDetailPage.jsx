import { ArrowLeftIcon } from "../../components/icons";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api, errorMessage } from "../../api/client";
import { Field, FormError, TextArea } from "../../components/forms";
import { PageHeader, Panel } from "../../components/PageHeader";
import { useDepartments } from "../../hooks/useDepartments";

function parseRollNumbers(text) {
  return [
    ...new Set(
      text
        .split(/[\s,;]+/)
        .map((r) => r.trim().toUpperCase())
        .filter(Boolean),
    ),
  ];
}

function Teachers({ course, onSaved }) {
  const [candidates, setCandidates] = useState(null);
  const [selected, setSelected] = useState(() => new Set(course.faculty.map((f) => f.id)));
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    const params = { department_id: course.department_id, page_size: 100 };
    Promise.all([
      api.get("/users", { params: { ...params, role: "faculty" } }),
      api.get("/users", { params: { ...params, role: "hod" } }),
    ])
      .then(([f, h]) => alive && setCandidates([...h.data.items, ...f.data.items]))
      .catch((err) => alive && setError(errorMessage(err)));
    return () => {
      alive = false;
    };
  }, [course.department_id]);

  const changed =
    selected.size !== course.faculty.length || course.faculty.some((f) => !selected.has(f.id));

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post(`/courses/${course.id}/enrol`, { faculty_ids: [...selected] });
      onSaved(res.data.course);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Taught by"
      actions={
        <button
          type="button"
          className="btn btn-primary h-8"
          disabled={!changed || busy}
          onClick={save}
        >
          {busy ? "Saving…" : "Save teachers"}
        </button>
      }
    >
      {candidates === null && !error ? (
        <span className="skeleton h-4 w-64" />
      ) : candidates?.length === 0 ? (
        <p className="m-0 text-body text-muted">
          No faculty in this department yet. Add them on the <Link to="/admin/users">Users</Link>{" "}
          page.
        </p>
      ) : (
        <fieldset className="m-0 border-0 p-0">
          <legend className="mb-3 text-small text-muted">
            Faculty and HoD of this department. Usually one teacher per section.
          </legend>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {(candidates ?? []).map((p) => (
              <label
                key={p.id}
                className="flex min-h-10 cursor-pointer items-center gap-2.5 rounded-control px-2 hover:bg-raised"
              >
                <input
                  type="checkbox"
                  className="size-4 accent-[var(--primary)]"
                  checked={selected.has(p.id)}
                  onChange={(e) => {
                    const next = new Set(selected);
                    if (e.target.checked) next.add(p.id);
                    else next.delete(p.id);
                    setSelected(next);
                  }}
                />
                <span>
                  {p.name}
                  {p.role === "hod" && <span className="text-small text-muted"> · HoD</span>}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <div className="mt-3">
        <FormError>{error}</FormError>
      </div>
    </Panel>
  );
}

function Students({ course, onChange }) {
  const [text, setText] = useState("");
  const [unknown, setUnknown] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const rolls = parseRollNumbers(text);

  async function call(body) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post(`/courses/${course.id}/enrol`, body);
      setUnknown(res.data.unknown_roll_numbers);
      onChange(res.data.course);
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title={`Students (${course.student_count})`}>
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-3">
          <Field
            label="Add students by roll number"
            hint="Paste roll numbers separated by spaces, commas or new lines."
          >
            {(a) => (
              <TextArea
                {...a}
                className="min-h-20 font-mono"
                spellCheck={false}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            )}
          </Field>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || rolls.length === 0}
              onClick={async () => {
                if (await call({ add_roll_numbers: rolls })) setText("");
              }}
            >
              {rolls.length ? `Enrol ${rolls.length}` : "Enrol"}
            </button>
            <FormError>{error}</FormError>
          </div>
          {unknown.length > 0 && (
            <p className="m-0 flex flex-wrap items-baseline gap-2 text-body" role="status">
              <span className="pill pill-warning">Not found</span>
              <span>
                {unknown.length} roll {unknown.length === 1 ? "number isn't" : "numbers aren't"} an
                active student: <span className="font-mono text-[13px]">{unknown.join(", ")}</span>
              </span>
            </p>
          )}
        </div>

        {course.students.length === 0 ? (
          <p className="m-0 text-body text-muted">No students enrolled yet.</p>
        ) : (
          <div className="max-h-[480px] overflow-auto rounded-control border border-border">
            <table className="w-full border-collapse text-body">
              <thead className="sticky top-0 bg-surface">
                <tr className="text-left text-small text-muted">
                  <th scope="col" className="h-9 px-3 font-medium">
                    Roll number
                  </th>
                  <th scope="col" className="h-9 px-3 font-medium">
                    Name
                  </th>
                  <th scope="col" className="h-9 px-3 text-right font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {course.students.map((s) => (
                  <tr key={s.id} className="border-t border-rule">
                    <td className="h-10 px-3 font-mono text-[13px]">{s.roll_no}</td>
                    <td className="px-3">{s.name}</td>
                    <td className="px-3 text-right">
                      <button
                        type="button"
                        className="btn btn-ghost h-8 px-2 text-small"
                        disabled={busy}
                        onClick={() => call({ remove_roll_numbers: [s.roll_no] })}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}

export function CourseDetailPage() {
  const { courseId } = useParams();
  const departments = useDepartments();
  const [course, setCourse] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    api
      .get(`/courses/${courseId}`)
      .then((res) => (setCourse(res.data), setError(null)))
      .catch((err) => setError(errorMessage(err)));
  }, [courseId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="mx-auto flex max-w-[1184px] flex-col gap-4">
        <Link to="/admin/courses" className="text-body text-muted">
          <ArrowLeftIcon /> All courses
        </Link>
        <FormError>{error}</FormError>
      </div>
    );
  }

  const dept = course ? departments.byId[course.department_id] : null;
  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <div className="flex flex-col gap-3">
        <Link to="/admin/courses" className="w-fit text-body text-muted hover:text-text">
          <ArrowLeftIcon /> All courses
        </Link>
        <PageHeader title={course ? `${course.code} · ${course.name}` : "Course"}>
          {course ? (
            <span className="num">
              {dept ? `${dept.code} · ` : ""}
              {course.academic_year} · Semester {course.semester} · Section {course.section}
            </span>
          ) : (
            <span className="skeleton h-4 w-64" />
          )}
        </PageHeader>
      </div>
      {course && (
        <div className="grid gap-[var(--gap)] lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
          <Teachers
            key={course.faculty.map((f) => f.id).join()}
            course={course}
            onSaved={setCourse}
          />
          <Students course={course} onChange={setCourse} />
        </div>
      )}
    </div>
  );
}
