import { useEffect, useState } from "react";
import { insightsApi, signed } from "../../api/insights";
import { useAuth } from "../../context/auth";

/**
 * A teacher's offerings in one cycle side by side, shown only when there is more than one.
 * Choosing a row opens that course below.
 */
export function AcrossCourses({ facultyId, cycleId, selectedCourseId, onPick }) {
  const { user: me } = useAuth();
  const [state, setState] = useState({ key: null, data: null });
  const key = `${facultyId}|${cycleId}`;

  useEffect(() => {
    let alive = true;
    insightsApi
      .faculty(facultyId, cycleId)
      .then((data) => alive && setState({ key, data }))
      .catch(() => alive && setState({ key, data: null }));
    return () => {
      alive = false;
    };
  }, [facultyId, cycleId, key]);

  const data = state.key === key ? state.data : null;
  if (!data || data.offerings.length < 2) return null;
  const all = data.combined;

  return (
    <section aria-labelledby="across-h" className="card overflow-hidden">
      <div className="border-b border-rule px-[var(--card-pad)] py-3">
        <h2 id="across-h" className="m-0 text-section font-medium">
          {me.id === facultyId ? "Across your courses" : "Across their courses"}
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-body">
          <thead>
            <tr className="text-left text-small text-muted">
              <th scope="col" className="h-10 pr-3 pl-[var(--card-pad)] font-medium">
                Course
              </th>
              <th scope="col" className="h-10 px-3 text-right font-medium">
                Responses
              </th>
              <th scope="col" className="h-10 px-3 text-right font-medium">
                Net sentiment
              </th>
              <th scope="col" className="h-10 px-3 text-right font-medium">
                Rating
              </th>
              <th scope="col" className="h-10 pr-[var(--card-pad)] pl-3 font-medium">
                Strength · area to improve
              </th>
            </tr>
          </thead>
          <tbody>
            {data.offerings.map((r) => {
              const current = r.course.id === selectedCourseId;
              return (
                <tr
                  key={r.form_id}
                  className={`border-t border-rule ${current ? "bg-raised" : ""}`}
                >
                  <th
                    scope="row"
                    className="py-2.5 pr-3 pl-[var(--card-pad)] text-left font-normal"
                  >
                    <button
                      type="button"
                      aria-current={current ? "true" : undefined}
                      className={`cursor-pointer text-left ${current ? "font-medium" : "underline underline-offset-3"}`}
                      onClick={() => onPick({ cycle: cycleId, course: r.course.id })}
                    >
                      {r.course.code} · Section {r.course.section}
                    </button>
                  </th>
                  <td className="num px-3 text-right">
                    {r.responses} <span className="text-small text-muted">of {r.eligible}</span>
                  </td>
                  {r.status === "available" ? (
                    <>
                      <td className="num px-3 text-right font-medium">{signed(r.net_score)}</td>
                      <td className="num px-3 text-right whitespace-nowrap">
                        {r.rating?.toFixed(1) ?? "–"}
                        <span className="text-small text-muted"> / 5</span>
                      </td>
                      <td className="pr-[var(--card-pad)] pl-3 text-small">
                        {r.top_strength?.label ?? "–"}
                        <span className="text-muted"> · </span>
                        {r.top_gap?.label ?? "–"}
                      </td>
                    </>
                  ) : (
                    <td colSpan={3} className="pr-[var(--card-pad)] pl-3 text-small text-muted">
                      {r.status === "awaiting_analysis"
                        ? "Waiting for analysis"
                        : `Shown from ${data.min_required} responses`}
                    </td>
                  )}
                </tr>
              );
            })}
            {all?.status === "available" && (
              <tr className="border-t border-border">
                <th scope="row" className="py-2.5 pr-3 pl-[var(--card-pad)] text-left font-medium">
                  All courses
                </th>
                <td className="num px-3 text-right">
                  {all.responses} <span className="text-small text-muted">of {all.eligible}</span>
                </td>
                <td className="num px-3 text-right font-medium">{signed(all.net_score)}</td>
                <td className="num px-3 text-right whitespace-nowrap">
                  {all.rating?.toFixed(1) ?? "–"}
                  <span className="text-small text-muted"> / 5</span>
                </td>
                <td className="pr-[var(--card-pad)] pl-3 text-small">
                  {all.top_strength?.label ?? "–"}
                  <span className="text-muted"> · </span>
                  {all.top_gap?.label ?? "–"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
