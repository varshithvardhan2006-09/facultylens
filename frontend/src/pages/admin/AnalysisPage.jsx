import { ArrowRightIcon } from "../../components/icons";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { analysisApi, formatSeconds } from "../../api/analysis";
import { errorMessage } from "../../api/client";
import { feedbackApi, formatDate } from "../../api/feedback";
import { Field, FormError, Select } from "../../components/forms";
import { PageHeader } from "../../components/PageHeader";
import { RateBar } from "../../components/RateBar";
import { useAsync } from "../../hooks/useAsync";

const loadCycles = () => feedbackApi.cycles();
const ACTIVE = ["queued", "running"];

const JOB_STATUS = {
  queued: ["pill-neutral", "Queued"],
  running: ["pill-neutral", "Running"],
  done: ["pill-positive", "Done"],
  failed: ["pill-negative", "Failed"],
  interrupted: ["pill-warning", "Interrupted"],
};

function JobStatus({ status }) {
  const [cls, text] = JOB_STATUS[status] ?? JOB_STATUS.queued;
  return <span className={`pill ${cls}`}>{text}</span>;
}

const n = (v) => (v ?? 0).toLocaleString("en-IN");

/** One card split by 1px dividers: the cycle's coverage for the current model version. */
function Coverage({ summary }) {
  const cells = [
    ["Responses", summary?.responses],
    ["Analysed", summary?.analysed],
    ["Waiting for analysis", summary?.pending],
  ];
  return (
    <div className="card grid grid-cols-3 gap-px overflow-hidden bg-rule">
      {cells.map(([label, value]) => (
        <div
          key={label}
          className="flex flex-col justify-between gap-1 bg-surface p-3 sm:p-[var(--card-pad)]"
        >
          <span className="text-small text-muted">{label}</span>
          {summary ? (
            <span className="num text-lead font-medium">{n(value)}</span>
          ) : (
            <span className="skeleton h-[26px] w-20" />
          )}
        </div>
      ))}
    </div>
  );
}

/** Live progress for the job that is running now (polled every 2 s by the page). */
function Progress({ job, now }) {
  const started = job.started_at ? new Date(job.started_at).getTime() : null;
  const elapsed = started ? Math.max(0, (now - started) / 1000) : null;
  const rate = elapsed && job.done ? (1000 * elapsed) / job.done : null;
  const unit = job.kind === "summaries" ? "course" : "response";
  return (
    <section
      aria-label="Analysis in progress"
      className="card flex flex-col gap-4 p-[var(--card-pad)]"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-section font-medium" aria-live="polite">
          {job.status === "queued"
            ? "Waiting for the analysis worker"
            : job.kind === "summaries"
              ? "Writing summaries"
              : job.total == null
                ? "Finding responses to analyse"
                : job.done === 0
                  ? "Starting: the first batch loads the models"
                  : "Analysing responses"}
        </h2>
        <JobStatus status={job.status} />
      </div>
      {job.total ? (
        <RateBar value={job.done} total={job.total} label={`${unit}s`} />
      ) : (
        <div className="h-1.5 w-full rounded-full bg-active" />
      )}
      <dl className="m-0 flex flex-wrap gap-x-8 gap-y-1 text-small">
        <div className="flex gap-1.5">
          <dt className="text-muted">Elapsed</dt>
          <dd className="num m-0">{formatSeconds(elapsed)}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-muted">Per {unit} so far</dt>
          <dd className="num m-0">{rate ? `${Math.round(rate)} ms` : "–"}</dd>
        </div>
      </dl>
      <p className="m-0 text-small text-muted">
        You can leave this page; the run continues on the server.
      </p>
    </section>
  );
}

/** What the last finished run of this cycle flagged, with the way into the queue. */
function Findings({ job }) {
  const c = job.counts ?? {};
  const flagged = (c.hidden ?? 0) + (c.review ?? 0);
  const rows = [
    ["Hidden until an admin reviews them", c.hidden],
    ["Shown, but sent for review", c.review],
    ["Personal details redacted", c.pii],
    ["Possibly sarcastic, weighted half", c.sarcastic],
  ];
  return (
    <section aria-labelledby="findings-h" className="card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-[var(--card-pad)] py-3">
        <h2 id="findings-h" className="m-0 text-section font-medium">
          Last run: {n(job.total)} responses in {formatSeconds(job.seconds)}
        </h2>
        <span className="num text-small text-muted">{formatDate(job.finished_at, true)}</span>
      </div>
      <ul className="m-0 list-none p-0">
        {rows.map(([label, value]) => (
          <li
            key={label}
            className="flex h-11 items-center justify-between gap-4 border-t border-rule px-[var(--card-pad)] text-body first:border-t-0"
          >
            <span>{label}</span>
            <span className="num font-medium">{n(value)}</span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-[var(--card-pad)] py-3 text-small text-muted">
        <span>Counts are text answers; one response can have up to three.</span>
        {flagged > 0 && (
          <Link to="/admin/moderation" className="text-body font-medium text-text">
            Review flagged answers <ArrowRightIcon />
          </Link>
        )}
      </div>
    </section>
  );
}

function JobsTable({ jobs, cycleNames }) {
  return (
    <section aria-labelledby="jobs-h" className="flex flex-col gap-2">
      <h2 id="jobs-h" className="text-section font-medium">
        Recent runs
      </h2>
      <div className="card overflow-hidden">
        {jobs && jobs.length === 0 ? (
          <p className="m-0 p-[var(--card-pad)] text-body text-muted">
            No runs yet. New submissions are analysed as they arrive; run a cycle to catch up on
            anything older.
          </p>
        ) : (
          <table className="w-full border-collapse text-body">
            <thead className="max-md:sr-only">
              <tr className="text-left text-small text-muted">
                <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                  Started
                </th>
                <th scope="col" className="h-10 px-3 font-medium">
                  Run
                </th>
                <th scope="col" className="h-10 px-3 font-medium">
                  Status
                </th>
                <th
                  scope="col"
                  className="h-10 px-[var(--card-pad)] text-right font-medium lg:px-3"
                >
                  Responses
                </th>
                <th scope="col" className="h-10 px-3 text-right font-medium max-lg:hidden">
                  Time
                </th>
                <th
                  scope="col"
                  className="h-10 px-[var(--card-pad)] text-right font-medium max-lg:hidden"
                >
                  Per response
                </th>
              </tr>
            </thead>
            <tbody>
              {(jobs ?? [null, null, null]).map((j, i) =>
                j ? (
                  <tr
                    key={j.id}
                    className="border-t border-rule max-md:flex max-md:flex-wrap max-md:items-center max-md:gap-x-3 max-md:gap-y-1 max-md:px-4 max-md:py-3"
                  >
                    <td className="num h-12 px-[var(--card-pad)] text-muted max-md:h-auto max-md:w-full max-md:p-0 max-md:text-small">
                      {formatDate(j.created_at, true)}
                    </td>
                    <td className="px-3 max-md:p-0">
                      {j.kind === "cycle" ? (
                        (cycleNames[j.cycle_id] ?? "Cycle")
                      ) : j.kind === "summaries" ? (
                        `Summaries · ${cycleNames[j.cycle_id] ?? "Cycle"}`
                      ) : (
                        <span className="text-muted">New submissions</span>
                      )}
                      {j.status === "failed" && j.error && (
                        <span className="block text-small text-negative">{j.error}</span>
                      )}
                    </td>
                    <td className="px-3 max-md:p-0">
                      <JobStatus status={j.status} />
                    </td>
                    <td className="num px-[var(--card-pad)] text-right max-md:p-0 max-md:text-small lg:px-3">
                      {j.total == null
                        ? "–"
                        : `${n(j.done)} of ${n(j.total)}${j.kind === "summaries" ? " courses" : ""}`}
                    </td>
                    <td className="num px-3 text-right max-lg:hidden">
                      {formatSeconds(j.seconds)}
                    </td>
                    <td className="num px-[var(--card-pad)] text-right max-lg:hidden">
                      {j.per_response_ms == null ? "–" : `${Math.round(j.per_response_ms)} ms`}
                    </td>
                  </tr>
                ) : (
                  <tr key={i} className="border-t border-rule">
                    <td colSpan={6} className="h-12 px-[var(--card-pad)]">
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
  );
}

export function AnalysisPage() {
  const cycles = useAsync(loadCycles);
  const [picked, setPicked] = useState(null);
  const [summary, setSummary] = useState(null);
  const [jobs, setJobs] = useState(null);
  const [active, setActive] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  const list = useMemo(
    () => (cycles.data ?? []).filter((c) => c.status !== "draft"),
    [cycles.data],
  );
  const cycleId = picked ?? (list.find((c) => c.status === "open") ?? list[0])?.id ?? null;
  const cycleNames = useMemo(
    () => Object.fromEntries((cycles.data ?? []).map((c) => [c.id, c.name])),
    [cycles.data],
  );

  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    // Load whenever the chosen cycle changes or a run finishes.
    if (!cycleId) return undefined;
    let alive = true;
    Promise.all([analysisApi.summary(cycleId), analysisApi.jobs(20)])
      .then(([s, j]) => {
        if (!alive) return;
        setSummary(s);
        setJobs(j);
        setActive(s.active_job);
        setError(null);
      })
      .catch((err) => alive && setError(errorMessage(err, "Couldn't load the analysis summary.")));
    return () => {
      alive = false;
    };
  }, [cycleId, version]);

  const activeId = active && ACTIVE.includes(active.status) ? active.id : null;
  useEffect(() => {
    if (!activeId) return undefined;
    const poll = setInterval(async () => {
      try {
        const job = await analysisApi.status(activeId);
        setActive(job);
        if (!ACTIVE.includes(job.status)) refresh();
      } catch {
        // A missed poll is retried on the next tick.
      }
    }, 2000);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [activeId, refresh]);

  async function run(kind = "analysis") {
    setStarting(true);
    setError(null);
    try {
      const job =
        kind === "summaries"
          ? await analysisApi.summaries(cycleId)
          : await analysisApi.run(cycleId);
      setActive(job);
      setNow(Date.now());
      setJobs(await analysisApi.jobs(20));
    } catch (err) {
      setError(errorMessage(err, "Couldn't start the analysis."));
    } finally {
      setStarting(false);
    }
  }

  const lastDone = (jobs ?? []).find(
    (j) => j.kind === "cycle" && j.cycle_id === cycleId && j.status === "done" && j.total > 0,
  );
  const running = Boolean(activeId);
  const nothingToDo = summary && summary.pending === 0;

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader
        title="Analysis"
        actions={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!cycleId || running || starting || !summary?.analysed}
              title="Rewrite every course summary in this cycle, e.g. after adding a Groq key"
              onClick={() => run("summaries")}
            >
              Regenerate summaries
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!cycleId || running || starting || nothingToDo || !summary}
              onClick={() => run()}
            >
              {running ? "Running…" : starting ? "Starting…" : "Analyse waiting responses"}
            </button>
          </>
        }
      >
        Every text answer is redacted, checked for abuse, and scored for sentiment, teaching
        aspects, emotion and sarcasm on this computer&apos;s CPU. Results are kept, so a response is
        never scored twice by the same models.
      </PageHeader>

      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <Field label="Cycle" className="md:w-80">
          {(a) =>
            cycles.data ? (
              <Select
                {...a}
                value={cycleId ?? ""}
                disabled={list.length === 0}
                onChange={(e) => {
                  setPicked(e.target.value);
                  setSummary(null);
                  setActive(null);
                }}
              >
                {list.length === 0 && <option value="">No published cycles</option>}
                {list.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.status === "closed" ? " (closed)" : ""}
                  </option>
                ))}
              </Select>
            ) : (
              <span className="skeleton h-10 w-full" />
            )
          }
        </Field>
        {summary && (
          <p className="m-0 text-small text-muted">
            Models <span className="font-mono">{summary.model_version}</span>
          </p>
        )}
      </div>

      {cycles.error && <FormError>Couldn&apos;t load cycles.</FormError>}
      {cycles.data && list.length === 0 && (
        <p className="m-0 text-body text-muted">
          Publish a feedback cycle first; its responses appear here once students submit.
        </p>
      )}
      <FormError>{error}</FormError>

      {cycleId && (
        <>
          <Coverage
            summary={
              // A summaries job counts courses, so it doesn't change these response counts.
              running && summary && active?.kind !== "summaries"
                ? {
                    ...summary,
                    analysed: summary.analysed + (active.done ?? 0),
                    pending: Math.max(0, summary.pending - (active.done ?? 0)),
                  }
                : summary
            }
          />
          {nothingToDo && !running && summary.responses > 0 && (
            <p className="-mt-5 m-0 text-small text-muted">
              Everything in this cycle is analysed. New submissions are analysed as they arrive.
            </p>
          )}
          {running && <Progress job={active} now={now} />}
          {!running && lastDone && <Findings job={lastDone} />}
        </>
      )}

      <JobsTable
        jobs={cycleId ? jobs?.map((j) => (active && j.id === active.id ? active : j)) : []}
        cycleNames={cycleNames}
      />
    </div>
  );
}
