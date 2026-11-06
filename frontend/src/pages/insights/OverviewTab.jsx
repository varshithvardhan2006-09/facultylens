import { CountUp } from "../../components/CountUp";
import { SortIcon } from "../../components/icons";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { pct, signed } from "../../api/insights";
import { RateBar } from "../../components/RateBar";
import { Aspects } from "../faculty/Insights";

const COLUMNS = [
  ["name", "Teacher", (r) => r.name.toLowerCase(), "left"],
  ["responses", "Responses", (r) => r.responses, "left"],
  ["net_score", "Net sentiment", (r) => r.net_score, "right"],
  ["rating", "Rating", (r) => r.rating, "right"],
  ["top_strength", "Top strength", (r) => r.top_strength?.label ?? null, "left"],
  ["top_gap", "Area to improve", (r) => r.top_gap?.label ?? null, "left"],
  ["sarcasm_rate", "Possibly sarcastic", (r) => r.sarcasm_rate, "right"],
];

function Stat({ label, children, note }) {
  return (
    <div className="flex flex-col gap-1 bg-surface p-[var(--card-pad)]">
      <span className="text-small text-muted">{label}</span>
      {children}
      {note && <span className="text-small text-muted">{note}</span>}
    </div>
  );
}

/** Teachers in one sortable table; empty values always sort last, whatever the direction. */
function TeacherTable({ rows, minimum }) {
  const [sort, setSort] = useState({ key: "name", dir: 1 });
  const sorted = useMemo(() => {
    const [, , get] = COLUMNS.find(([k]) => k === sort.key);
    return [...rows].sort((a, b) => {
      const x = get(a);
      const y = get(b);
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * sort.dir;
    });
  }, [rows, sort]);

  return (
    <section aria-labelledby="teachers-h" className="card overflow-hidden">
      <div className="border-b border-rule px-[var(--card-pad)] py-3">
        <h2 id="teachers-h" className="m-0 text-section font-medium">
          Teachers
        </h2>
        <p className="m-0 text-small text-muted">
          Each teacher&apos;s offerings combined. Courses with fewer than {minimum} responses are
          left out of their numbers.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] border-collapse text-body">
          <thead>
            <tr className="text-left text-small text-muted">
              {COLUMNS.map(([key, label, , align], i) => (
                <th
                  key={key}
                  scope="col"
                  aria-sort={
                    sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"
                  }
                  className={`h-10 font-medium ${i === 0 ? "pl-[var(--card-pad)]" : "pl-3"} ${
                    i === COLUMNS.length - 1 ? "pr-[var(--card-pad)]" : "pr-3"
                  } ${align === "right" ? "text-right" : ""}`}
                >
                  <button
                    type="button"
                    className={`inline-flex cursor-pointer items-center gap-1 hover:text-text ${
                      sort.key === key ? "text-text" : ""
                    }`}
                    onClick={() =>
                      setSort((s) =>
                        s.key === key
                          ? { key, dir: -s.dir }
                          : { key, dir: key === "name" ? 1 : -1 },
                      )
                    }
                  >
                    {label}
                    <span aria-hidden="true" className="inline-flex w-2.5">
                      {sort.key === key && <SortIcon ascending={sort.dir === 1} />}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const shown = r.status === "available";
              return (
                <tr key={r.id} className="border-t border-rule hover:bg-raised">
                  <td className="py-2.5 pr-3 pl-[var(--card-pad)]">
                    <Link
                      to={`/faculty/${r.id}`}
                      className="font-medium no-underline hover:underline"
                    >
                      {r.name}
                    </Link>
                    <span className="num block text-small text-muted">
                      {r.offerings} offering{r.offerings === 1 ? "" : "s"}
                    </span>
                  </td>
                  <td className="px-3">
                    <RateBar value={r.responses} total={r.eligible} />
                  </td>
                  {shown ? (
                    <>
                      <td className="num px-3 text-right font-medium">{signed(r.net_score)}</td>
                      <td className="num px-3 text-right whitespace-nowrap">
                        {r.rating == null ? "–" : r.rating.toFixed(1)}
                        <span className="text-small text-muted"> / 5</span>
                      </td>
                      <td className="px-3">
                        {r.top_strength ? (
                          <span className="pill pill-neutral">{r.top_strength.label}</span>
                        ) : (
                          <span className="text-faint">–</span>
                        )}
                      </td>
                      <td className="px-3">
                        {r.top_gap ? (
                          <span className="pill pill-neutral">{r.top_gap.label}</span>
                        ) : (
                          <span className="text-faint">–</span>
                        )}
                      </td>
                      <td className="num pr-[var(--card-pad)] pl-3 text-right">
                        {pct(r.sarcasm_rate)}
                      </td>
                    </>
                  ) : (
                    <td colSpan={5} className="pr-[var(--card-pad)] pl-3 text-small text-muted">
                      {r.status === "awaiting_analysis"
                        ? "Waiting for the next analysis run"
                        : `Too few responses to show (fewer than ${minimum} in every course)`}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function OverviewTab({ data }) {
  const t = data.totals;
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <div className="card grid grid-cols-1 gap-px overflow-hidden bg-rule md:grid-cols-[1.4fr_1fr_1fr]">
        <Stat label="Responses across the department">
          <RateBar value={t.responses} total={t.eligible} />
          <span className="num text-small text-muted">
            {t.teachers} teachers · {t.offerings} offerings · {t.forms_shown} with enough data
          </span>
        </Stat>
        <Stat label="Net sentiment" note="Positive minus negative share of answers, −1 to +1">
          <span className="num text-kpi font-medium">
            {t.net_score == null ? (
              signed(t.net_score)
            ) : (
              <CountUp value={t.net_score} format={signed} />
            )}
          </span>
        </Stat>
        <Stat
          label="Hidden by moderation"
          note={t.in_review ? `${t.in_review} awaiting review` : "None awaiting review"}
        >
          <span className="num text-lead font-medium">
            <CountUp value={t.hidden_comments} />
          </span>
        </Stat>
      </div>
      {data.teachers.length === 0 ? (
        <section className="card p-[var(--card-pad)]">
          <h2 className="m-0 text-section font-medium">No teaching forms in this cycle</h2>
          <p className="m-0 mt-1 text-body text-muted">
            Publish a feedback cycle with offerings in this department first.
          </p>
        </section>
      ) : (
        <TeacherTable rows={data.teachers} minimum={data.min_required} />
      )}
      {Object.keys(data.aspects).length > 0 && (
        <Aspects
          insights={{ aspects: data.aspects }}
          showAgreement={false}
          title="Teaching aspects across the department"
        />
      )}
    </div>
  );
}
