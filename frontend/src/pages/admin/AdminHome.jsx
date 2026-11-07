import { Reveal } from "../../components/Reveal";
import { CountUp } from "../../components/CountUp";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { analysisApi } from "../../api/analysis";
import { errorMessage } from "../../api/client";
import { feedbackApi } from "../../api/feedback";
import { reportsApi } from "../../api/reports";
import { CycleStatus } from "../../components/CycleStatus";
import { FormError } from "../../components/forms";

const n = (v) => (v ?? 0).toLocaleString("en-IN");

/** The cycle to work on: the open one, else the most recent. */
function currentCycle(cycles) {
  return cycles.find((c) => c.status === "open") ?? cycles[0] ?? null;
}

/** Everything the home board shows, read from the screens' own APIs. */
async function loadBoard() {
  const cycles = await feedbackApi.cycles();
  const cycle = currentCycle(cycles);
  if (!cycle) return { cycle: null };
  const [analysis, queue, report] = await Promise.all([
    analysisApi.summary(cycle.id),
    analysisApi.queue({ status: "pending", limit: 1 }),
    reportsApi.status(cycle.id).catch(() => null),
  ]);
  return { cycle, analysis, moderation: queue.pending, report };
}

/** Sort the cycle's work into columns, the way a team sorts cards on a wall. */
function columns({ cycle, analysis, moderation, report }) {
  const cols = { decide: [], run: [], waiting: [], done: [] };
  const responses = cycle.counts?.responses ?? 0;
  const eligible = cycle.counts?.eligible ?? 0;
  const unanalysed = Math.max(0, (analysis?.responses ?? 0) - (analysis?.analysed ?? 0));

  if (moderation > 0)
    cols.decide.push({
      title: `${n(moderation)} comment${moderation === 1 ? "" : "s"} to moderate, across all cycles`,
      body: "Held back for abusive language or uncertainty. Hidden answers stay hidden from teachers until you decide.",
      to: "/admin/moderation",
      action: "Moderate",
    });
  else
    cols.done.push({
      title: "Moderation queue is empty",
      to: "/admin/moderation",
      action: "View decisions",
    });

  if (report && report.actions > report.approved)
    cols.decide.push({
      title: `${n(report.actions - report.approved)} Action Taken row${report.actions - report.approved === 1 ? "" : "s"} to approve`,
      body: "Department replies to the feedback, waiting for admin sign-off before the report export.",
      to: "/admin/reports",
      action: "Review",
    });

  if (unanalysed > 0)
    cols.run.push({
      title: `${n(unanalysed)} response${unanalysed === 1 ? "" : "s"} not analysed yet`,
      body: "Run the analysis to sort their comments by aspect and screen them.",
      to: "/admin/analysis",
      action: "Run analysis",
    });
  else if (responses > 0)
    cols.done.push({
      title: `All ${n(analysis.analysed)} responses analysed`,
      to: "/admin/analysis",
      action: "View analysis runs",
    });

  if (report && report.actions === 0 && responses > 0)
    cols.run.push({
      title: "No Action Taken report yet",
      body: "Draft it from the analysed feedback, then departments add what they did.",
      to: "/admin/reports",
      action: "Draft",
    });

  if (cycle.status === "open" && eligible > responses)
    cols.waiting.push({
      title: `${n(eligible - responses)} responses still due`,
      body: `${n(responses)} of ${n(eligible)} responses are in while the cycle is open.`,
      to: `/admin/cycles/${cycle.id}`,
      action: "See forms",
    });
  else if (eligible > 0)
    cols.done.push({
      title: `${n(responses)} of ${n(eligible)} students responded`,
      to: `/admin/cycles/${cycle.id}`,
      action: "View the forms",
    });

  if (report?.ready)
    cols.done.push({
      title: "Feedback report is ready to export",
      to: "/admin/reports",
      action: "Export",
    });
  return cols;
}

const COLUMNS = [
  ["decide", "Needs a decision", "Nothing is waiting on you."],
  ["run", "Ready to run", "Nothing to run."],
  ["waiting", "Waiting on people", "No one to wait for."],
  ["done", "Done", "Nothing finished yet."],
];
const TILTS = [-1.2, 0.9, -0.4, 1.3];

function Card({ card, index, done }) {
  return (
    <li
      className={`note settle note-lift ${done ? "note-praise" : "note-neutral"} flex flex-col gap-2 px-4 py-3.5`}
      style={{
        "--tilt": `${TILTS[index % TILTS.length]}deg`,
        "--tape-tilt": `${index % 2 ? 4 : -3}deg`,
        "--i": index,
        "--dy": "28px",
        "--r0": `${index % 2 ? 6 : -6}deg`,
      }}
    >
      <span className="num text-body font-bold">{card.title}</span>
      {card.body && <span className="text-small leading-5 text-muted">{card.body}</span>}
      <Link
        to={card.to}
        className="w-fit text-small font-semibold text-text underline underline-offset-3"
      >
        {card.action}
      </Link>
    </li>
  );
}

/** The admin's first screen: the current cycle, and its work sorted into columns. */
export function AdminHome() {
  const [state, setState] = useState({ data: null, error: null });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let alive = true;
    loadBoard()
      .then((data) => alive && setState({ data, error: null }))
      .catch(
        (err) =>
          alive && setState({ data: null, error: errorMessage(err, "Couldn't load the board.") }),
      );
    return () => {
      alive = false;
    };
  }, [retry]);

  const { data, error } = state;
  if (error)
    return (
      <div className="mx-auto flex max-w-[1184px] flex-wrap items-center gap-3">
        <FormError>{error}</FormError>
        <button
          type="button"
          className="btn btn-secondary h-8"
          onClick={() => setRetry((r) => r + 1)}
        >
          Try again
        </button>
      </div>
    );
  if (!data)
    return (
      <div className="mx-auto flex max-w-[1184px] flex-col gap-6" aria-busy="true">
        <span className="skeleton h-36 w-full" />
        <span className="skeleton h-72 w-full" />
      </div>
    );
  if (!data.cycle)
    return (
      <div className="mx-auto flex max-w-[1184px] flex-col gap-2">
        <h1 className="m-0 font-marker text-marker">No feedback cycle yet</h1>
        <p className="m-0 text-body text-muted">
          Create a cycle to open feedback forms for every course.{" "}
          <Link to="/admin/cycles" className="font-semibold text-text">
            Go to feedback cycles
          </Link>
        </p>
      </div>
    );

  const { cycle, analysis, moderation, report } = data;
  const cols = columns(data);
  const responses = cycle.counts?.responses ?? 0;
  const eligible = cycle.counts?.eligible ?? 0;
  const stats = [
    ["Responded", responses, eligible ? `of ${n(eligible)}` : ""],
    ["To moderate", moderation ?? 0, "comments"],
    ["Analysed", analysis?.analysed ?? 0, `of ${n(analysis?.responses)}`],
    ...(report ? [["Actions approved", report.approved, `of ${n(report.actions)}`]] : []),
  ];
  let order = 0;

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <section aria-labelledby="cycle-h" className="board flex flex-col gap-6 p-6 md:p-7">
        <div className="flex flex-wrap items-center gap-3">
          <h1 id="cycle-h" className="m-0 font-marker text-[2.25rem] leading-tight">
            {cycle.name}
          </h1>
          <CycleStatus status={cycle.status} />
        </div>
        <dl className="m-0 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-board-rule pt-5 md:grid-cols-4">
          {stats.map(([label, value, unit]) => (
            <div key={label} className="flex flex-col gap-0.5">
              <dt className="text-small text-on-board-muted">{label}</dt>
              <dd className="num m-0 text-kpi font-bold">
                <CountUp value={value} format={(v) => n(Math.round(v))} />{" "}
                <span className="text-body font-normal text-on-board-muted">{unit}</span>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <Reveal className="grid gap-x-6 gap-y-10 sm:grid-cols-2 xl:grid-cols-4">
        {COLUMNS.map(([key, title, empty]) => (
          <section key={key} aria-labelledby={`col-${key}`} className="flex flex-col gap-4">
            <h2
              id={`col-${key}`}
              className="m-0 flex items-baseline justify-between gap-2 border-b-[3px] border-text pb-1.5 font-marker text-[1.375rem]"
            >
              {title}
              <span className="num font-sans text-small font-semibold text-muted">
                {cols[key].length}
              </span>
            </h2>
            {cols[key].length === 0 ? (
              <p className="m-0 text-small text-muted">{empty}</p>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-5 p-0 pt-2">
                {cols[key].map((card) => (
                  <Card key={card.title} card={card} index={order++} done={key === "done"} />
                ))}
              </ul>
            )}
          </section>
        ))}
      </Reveal>
    </div>
  );
}
