import { ArrowLeftIcon } from "../../components/icons";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { errorMessage } from "../../api/client";
import { feedbackApi, formatDate } from "../../api/feedback";
import { FormError } from "../../components/forms";
import { PageHeader, Panel } from "../../components/PageHeader";
import { RateBar } from "../../components/RateBar";
import { CycleStatus } from "../../components/CycleStatus";

function PublishPanel({ cycle, onChanged }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    feedbackApi
      .preview(cycle.id)
      .then((p) => alive && setPreview(p))
      .catch((err) => alive && setError(errorMessage(err)));
    return () => {
      alive = false;
    };
  }, [cycle.id, cycle.status]);

  async function publish() {
    setBusy(true);
    setError(null);
    try {
      onChanged(await feedbackApi.publish(cycle.id));
    } catch (err) {
      setError(errorMessage(err, "Couldn't publish."));
    } finally {
      setBusy(false);
    }
  }

  const nothing = preview && preview.teaching_forms + preview.curriculum_forms === 0;
  return (
    <Panel title={cycle.status === "draft" ? "Publish" : "Add forms for new offerings"}>
      <div className="flex flex-col gap-4">
        {!preview && !error ? (
          <span className="skeleton h-4 w-96 max-w-full" />
        ) : preview ? (
          <p className="m-0 text-body">
            {nothing ? (
              cycle.status === "draft" ? (
                preview.offerings === 0 ? (
                  <>
                    There are no {cycle.term}-semester offerings for {cycle.academic_year} yet. Add
                    them on the <Link to="/admin/courses">Courses</Link> page, then come back.
                  </>
                ) : (
                  <>
                    None of these offerings has a teacher yet. Assign teachers on the{" "}
                    <Link to="/admin/courses">Courses</Link> page first.
                  </>
                )
              ) : (
                `All forms exist (${preview.already_created}). Publishing again would add nothing.`
              )
            ) : (
              <>
                Publishing will create <strong className="num">{preview.teaching_forms}</strong>{" "}
                teaching {preview.teaching_forms === 1 ? "form" : "forms"} and{" "}
                <strong className="num">{preview.curriculum_forms}</strong> syllabus{" "}
                {preview.curriculum_forms === 1 ? "form" : "forms"}
                {cycle.status === "draft" ? " and open the cycle to students." : "."}
              </>
            )}
          </p>
        ) : null}
        {preview?.without_teacher.length > 0 && (
          <p className="m-0 flex flex-wrap items-baseline gap-2 text-body">
            <span className="pill pill-warning">No teacher</span>
            <span>
              Skipped until a teacher is assigned: {preview.without_teacher.join(", ")}.{" "}
              <Link to="/admin/courses">Courses</Link>
            </span>
          </p>
        )}
        <FormError>{error}</FormError>
        {!nothing && preview && (
          <div>
            <button type="button" className="btn btn-primary" disabled={busy} onClick={publish}>
              {busy
                ? "Publishing…"
                : cycle.status === "draft"
                  ? "Publish and open"
                  : "Create missing forms"}
            </button>
          </div>
        )}
      </div>
    </Panel>
  );
}

export function CycleDetailPage() {
  const { cycleId } = useParams();
  const [cycle, setCycle] = useState(null);
  const [forms, setForms] = useState(null);
  const [error, setError] = useState(null);
  const [closing, setClosing] = useState(false);

  const load = useCallback(() => {
    Promise.all([feedbackApi.cycle(cycleId), feedbackApi.cycleForms(cycleId)])
      .then(([c, f]) => {
        setCycle(c);
        setForms(f);
      })
      .catch((err) => setError(errorMessage(err)));
  }, [cycleId]);

  useEffect(() => {
    load();
  }, [load]);

  async function close() {
    if (!window.confirm(`Close ${cycle.name}? Students won't be able to submit any more.`)) return;
    setClosing(true);
    try {
      setCycle(await feedbackApi.close(cycleId));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setClosing(false);
    }
  }

  if (error && !cycle) {
    return (
      <div className="mx-auto flex max-w-[1184px] flex-col gap-3">
        <Link to="/admin/cycles" className="text-body text-muted">
          <ArrowLeftIcon /> All cycles
        </Link>
        <FormError>{error}</FormError>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <div className="flex flex-col gap-3">
        <Link to="/admin/cycles" className="w-fit text-body text-muted hover:text-text">
          <ArrowLeftIcon /> All cycles
        </Link>
        <PageHeader
          title={cycle ? cycle.name : "Cycle"}
          actions={
            cycle?.status === "open" && (
              <button
                type="button"
                className="btn btn-secondary"
                disabled={closing}
                onClick={close}
              >
                {closing ? "Closing…" : "Close cycle"}
              </button>
            )
          }
        >
          {cycle ? (
            <span className="flex flex-wrap items-center gap-2">
              <CycleStatus status={cycle.status} />
              <span className="num">
                {cycle.academic_year} · {cycle.term} semesters · {formatDate(cycle.opens_at)} –{" "}
                {formatDate(cycle.closes_at)}
              </span>
            </span>
          ) : (
            <span className="skeleton h-4 w-72" />
          )}
        </PageHeader>
      </div>

      {cycle && cycle.counts && cycle.counts.eligible > 0 && (
        <div className="card flex flex-col gap-2 p-[var(--card-pad)] md:max-w-md">
          <span className="text-small text-muted">Responses across all forms</span>
          <RateBar value={cycle.counts.responses} total={cycle.counts.eligible} />
        </div>
      )}

      {cycle && cycle.status !== "closed" && (
        <PublishPanel
          cycle={cycle}
          onChanged={(c) => {
            setCycle(c);
            feedbackApi.cycleForms(cycleId).then(setForms);
          }}
        />
      )}

      <section aria-labelledby="forms-h" className="flex flex-col gap-2">
        <h2 id="forms-h" className="text-section font-medium">
          {forms ? `${forms.length} forms` : "Forms"}
        </h2>
        <div className="card overflow-hidden">
          {forms && forms.length === 0 ? (
            <p className="m-0 p-[var(--card-pad)] text-body text-muted">
              No forms yet. They are created when the cycle is published.
            </p>
          ) : (
            <table className="w-full border-collapse text-body">
              <thead className="max-md:sr-only">
                <tr className="text-left text-small text-muted">
                  <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                    Offering
                  </th>
                  <th scope="col" className="h-10 px-3 font-medium">
                    Form
                  </th>
                  <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                    Responses
                  </th>
                </tr>
              </thead>
              <tbody>
                {(forms ?? [null, null, null]).map((f, i) =>
                  f ? (
                    <tr
                      key={f.id}
                      className="border-t border-rule max-md:flex max-md:flex-col max-md:gap-1 max-md:px-4 max-md:py-3"
                    >
                      <td className="h-14 px-[var(--card-pad)] max-md:h-auto max-md:p-0">
                        <span className="font-medium">{f.course.code}</span>
                        <span className="text-muted">
                          {" "}
                          · {f.course.name} · Section {f.course.section}
                        </span>
                      </td>
                      <td className="px-3 max-md:p-0 max-md:text-small">
                        {f.type === "teaching" ? (
                          f.faculty?.name
                        ) : (
                          <span className="text-muted">Syllabus</span>
                        )}
                      </td>
                      <td className="px-[var(--card-pad)] py-2 max-md:p-0">
                        <RateBar value={f.responses} total={f.eligible} />
                      </td>
                    </tr>
                  ) : (
                    <tr key={i} className="border-t border-rule">
                      <td colSpan={3} className="h-14 px-[var(--card-pad)]">
                        <span className="skeleton h-4 w-full max-w-[520px]" />
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
