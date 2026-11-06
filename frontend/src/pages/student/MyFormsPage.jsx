import { Link } from "react-router";
import { feedbackApi, formatDate } from "../../api/feedback";
import { FormError } from "../../components/forms";
import { PageHeader } from "../../components/PageHeader";
import { useAsync } from "../../hooks/useAsync";

const loadForms = () => feedbackApi.myForms();

function groupByCourse(forms) {
  const groups = new Map();
  for (const f of forms) {
    const key = f.course.id;
    if (!groups.has(key)) groups.set(key, { course: f.course, forms: [] });
    groups.get(key).forms.push(f);
  }
  return [...groups.values()];
}

export function MyFormsPage() {
  const forms = useAsync(loadForms);
  const list = forms.data ?? [];
  const pending = list.filter((f) => !f.submitted).length;
  const cycle = list[0]?.cycle;
  const firstPending = list.find((f) => !f.submitted)?.id;

  return (
    <div className="mx-auto flex max-w-[960px] flex-col gap-8">
      <PageHeader title="Feedback forms">
        {forms.error && forms.data == null ? null : forms.data == null ? (
          <span className="skeleton h-4 w-80 max-w-full" />
        ) : list.length === 0 ? (
          "No feedback forms are open for your courses right now."
        ) : pending === 0 ? (
          `You've answered all ${list.length} forms for ${cycle.name}. Thank you.`
        ) : (
          `${pending} of ${list.length} forms waiting for you in ${cycle.name}, open until ${formatDate(cycle.closes_at)}.`
        )}
        <span className="mt-1 block">
          Your answers are stored without your name: teachers never see who wrote them.
        </span>
      </PageHeader>

      {forms.error ? (
        <div className="flex flex-wrap items-center gap-3">
          <FormError>Couldn&apos;t load your forms.</FormError>
          <button type="button" className="btn btn-ghost h-8 px-2" onClick={forms.reload}>
            Retry
          </button>
        </div>
      ) : forms.data == null ? (
        <div className="card flex flex-col gap-4 p-[var(--card-pad)]" aria-busy="true">
          <span className="skeleton h-5 w-64" />
          <span className="skeleton h-12 w-full" />
          <span className="skeleton h-12 w-full" />
        </div>
      ) : list.length === 0 ? (
        <p className="card m-0 p-[var(--card-pad)] text-body text-muted">
          When your college opens a feedback cycle, a form for each of your teachers and courses
          appears here.
        </p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-[var(--gap)] p-0">
          {groupByCourse(list).map(({ course, forms: items }) => (
            <li key={course.id} className="card">
              <div className="border-b border-rule px-[var(--card-pad)] py-3">
                <h2 className="m-0 text-section font-medium">
                  {course.code} · {course.name}
                </h2>
                <p className="num m-0 text-small text-muted">
                  Semester {course.semester} · Section {course.section}
                </p>
              </div>
              <ul className="m-0 list-none p-0">
                {items.map((f) => (
                  <li
                    key={f.id}
                    className="flex flex-col gap-2 border-t border-rule px-[var(--card-pad)] py-3 first:border-t-0 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex flex-col">
                      <span className="font-medium">
                        {f.type === "teaching"
                          ? `Teaching: ${f.faculty?.name}`
                          : "Course and syllabus"}
                      </span>
                      <span className="text-small text-muted">
                        {f.type === "teaching"
                          ? "8 ratings and 3 short questions"
                          : "4 ratings and 1 question"}
                      </span>
                    </div>
                    {f.submitted ? (
                      <span className="pill pill-positive w-fit">Submitted</span>
                    ) : (
                      <Link
                        to={`/feedback/${f.id}`}
                        className={`btn ${f.id === firstPending ? "btn-primary" : "btn-secondary"} w-fit no-underline`}
                      >
                        Give feedback
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
