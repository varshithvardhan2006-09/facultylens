import { PageHeader } from "../components/PageHeader";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { feedbackApi } from "../api/feedback";
import { RateBar } from "../components/RateBar";
import { FormError } from "../components/forms";
import { useAuth } from "../context/auth";
import { useAsync } from "../hooks/useAsync";

const COPY = {
  hod: {
    title: "Department courses",
    lead: "Every course offering in your department, with how many students have answered the open feedback cycle.",
    empty: "No course offerings in your department yet. The IQAC coordinator creates them.",
  },
  faculty: {
    title: "My courses",
    lead: "The course offerings you teach and how many students have answered so far. Ratings appear once enough students respond; comments appear after they are checked for abuse and personal details.",
    empty: "No courses assigned to you yet. Your IQAC coordinator assigns teachers to offerings.",
  },
  student: {
    title: "My courses",
    lead: "The course offerings you are enrolled in. Feedback forms are under Feedback forms.",
    empty: "You aren't enrolled in any course yet. Ask your department office if this looks wrong.",
  },
};

/** Progress of the open cycle for each offering: faculty see their own forms, a HoD the department. */
function useCycleProgress(user) {
  const [state, setState] = useState({ cycle: null, byCourse: {} });
  useEffect(() => {
    if (user.role === "student") return undefined;
    let alive = true;
    (async () => {
      const cycles = await feedbackApi.cycles();
      const cycle = cycles.find((c) => c.status === "open");
      if (!cycle) return;
      const byCourse = {};
      if (user.role === "hod") {
        for (const f of await feedbackApi.cycleForms(cycle.id)) {
          if (f.type === "teaching" && !byCourse[f.course.id]) {
            byCourse[f.course.id] = { responses: f.responses, eligible: f.eligible };
          }
        }
      }
      for (const s of await feedbackApi.facultyFeedback(user.id, { cycle: cycle.id })) {
        byCourse[s.course.id] = {
          responses: s.responses,
          eligible: s.eligible,
          min: s.min_required,
          visible: s.visible,
        };
      }
      if (alive) setState({ cycle, byCourse });
    })().catch(() => {});
    return () => {
      alive = false;
    };
  }, [user.id, user.role]);
  return state;
}

async function loadCourses() {
  return (await api.get("/courses")).data;
}

export function MyCoursesPage() {
  const { user } = useAuth();
  const copy = COPY[user.role];
  const courses = useAsync(loadCourses);
  const retry = useCallback(() => courses.reload(), [courses]);
  const progress = useCycleProgress(user);
  const showCycle = Boolean(progress.cycle);

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader title={copy.title}>{copy.lead}</PageHeader>

      <section aria-label="Course offerings" className="card overflow-hidden">
        {courses.error ? (
          <div className="flex flex-wrap items-center gap-3 p-[var(--card-pad)]">
            <FormError>Couldn&apos;t load your courses.</FormError>
            <button type="button" className="btn btn-ghost h-8 px-2" onClick={retry}>
              Retry
            </button>
          </div>
        ) : courses.data && courses.data.length === 0 ? (
          <p className="m-0 p-[var(--card-pad)] text-body text-muted">{copy.empty}</p>
        ) : (
          <table className="w-full border-collapse text-body">
            <thead className="max-md:sr-only">
              <tr className="text-left text-small text-muted">
                <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                  Course
                </th>
                <th scope="col" className="h-10 px-3 font-medium">
                  Year · semester · section
                </th>
                <th scope="col" className="h-10 px-3 font-medium">
                  Taught by
                </th>
                {showCycle ? (
                  <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                    {progress.cycle.name}
                  </th>
                ) : (
                  user.role !== "student" && (
                    <th scope="col" className="h-10 px-[var(--card-pad)] text-right font-medium">
                      Students
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {(courses.data ?? Array.from({ length: 3 }, () => null)).map((c, i) =>
                c ? (
                  <tr
                    key={c.id}
                    className="border-t border-rule max-md:flex max-md:flex-col max-md:gap-0.5 max-md:px-4 max-md:py-3"
                  >
                    <td className="h-[var(--row-height)] px-[var(--card-pad)] max-md:h-auto max-md:p-0">
                      <span className="font-medium">{c.code}</span>
                      <span className="text-muted"> · {c.name}</span>
                    </td>
                    <td className="num px-3 max-md:p-0 max-md:text-small max-md:text-muted">
                      {c.academic_year} · Sem {c.semester} · {c.section}
                    </td>
                    <td className="px-3 max-md:p-0 max-md:text-small max-md:text-muted">
                      {c.faculty.length ? (
                        c.faculty.map((f) => f.name).join(", ")
                      ) : (
                        <span className="text-faint">Not assigned</span>
                      )}
                    </td>
                    {showCycle ? (
                      <td className="px-[var(--card-pad)] py-2 max-md:p-0 max-md:pt-1">
                        {progress.byCourse[c.id] ? (
                          <div className="flex flex-col gap-1">
                            <RateBar
                              value={progress.byCourse[c.id].responses}
                              total={progress.byCourse[c.id].eligible}
                            />
                            {progress.byCourse[c.id].visible === false && (
                              <span className="text-small text-muted">
                                Ratings visible from {progress.byCourse[c.id].min} responses
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-small text-faint">No form in this cycle</span>
                        )}
                      </td>
                    ) : (
                      user.role !== "student" && (
                        <td className="num px-[var(--card-pad)] text-right max-md:p-0 max-md:text-left max-md:text-small max-md:text-muted">
                          {c.student_count}
                          <span className="md:hidden"> students</span>
                        </td>
                      )
                    )}
                  </tr>
                ) : (
                  <tr key={i} className="border-t border-rule">
                    <td colSpan={4} className="h-[var(--row-height)] px-[var(--card-pad)]">
                      <span className="skeleton h-4 w-full max-w-[520px]" />
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
