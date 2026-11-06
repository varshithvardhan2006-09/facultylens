import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { api, errorMessage } from "../../api/client";
import { insightsApi } from "../../api/insights";
import { FormError, Select } from "../../components/forms";
import { Tabs } from "../../components/Tabs";
import { PageHeader } from "../../components/PageHeader";
import { useAuth } from "../../context/auth";
import { useAsync } from "../../hooks/useAsync";
import { useDepartments } from "../../hooks/useDepartments";
import { BiasTab } from "./BiasTab";
import { ActionsTab } from "./ActionsTab";
import { OverviewTab } from "./OverviewTab";

const loadCourses = () => api.get("/courses").then((r) => r.data);

const TABS = [
  ["overview", "Overview"],
  ["bias", "Bias & sarcasm"],
  ["actions", "Action taken"],
];

/**
 * Department insights (SPEC §11.5, §11.7). A HoD sees their own department; the IQAC admin
 * picks one. The selection lives in the URL so a view can be shared and reloaded.
 */
export function InsightsPage() {
  const { user } = useAuth();
  const departments = useDepartments();
  const [params, setParams] = useSearchParams();
  const courses = useAsync(loadCourses);
  const requested = params.get("tab");
  // "Action taken" is the HoD's place to approve their rows; the admin uses the NAAC report page.
  const tabs = user.role === "hod" ? TABS : TABS.slice(0, 2);
  const tab = tabs.some(([k]) => k === requested) ? requested : "overview";
  const cycle = params.get("cycle") ?? "";
  const department =
    user.role === "hod"
      ? user.department_id
      : (params.get("department") ??
        (courses.loading
          ? undefined
          : // Open on a department with something to show, not simply the first by name.
            (
              departments.list.find((d) => courses.data?.some((c) => c.department_id === d.id)) ??
              departments.list[0]
            )?.id));
  const [state, setState] = useState({
    key: null,
    overview: null,
    bias: null,
    sarcasm: null,
    error: null,
  });
  const [reload, setReload] = useState(0);
  const key = `${department}|${cycle}|${tab}|${reload}`;

  useEffect(() => {
    // Load the overview always (it carries the cycle list) and the panel on its tab.
    if (!department) return undefined;
    let alive = true;
    Promise.all([
      insightsApi.department(department, cycle),
      tab === "bias" ? insightsApi.bias(department, cycle) : null,
      tab === "bias" ? insightsApi.sarcasm(department, cycle) : null,
    ])
      .then(
        ([overview, bias, sarcasm]) =>
          alive && setState({ key, overview, bias, sarcasm, error: null }),
      )
      .catch(
        (err) =>
          alive &&
          setState((s) => ({ ...s, key, error: errorMessage(err, "Couldn't load the insights.") })),
      );
    return () => {
      alive = false;
    };
  }, [department, cycle, tab, key]);

  const set = (changes) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next, { replace: true });
  };
  const loaded = state.key === key && !state.error;
  const data = state.overview;

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-6">
      <PageHeader
        title={data && user.role === "hod" ? data.department.name : "Department insights"}
      >
        How students rated and described each teacher in a cycle, and a check for patterns in the
        feedback itself. Every number comes from moderated, anonymous responses.
      </PageHeader>

      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row">
          {user.role === "admin" && (
            <label className="flex flex-col gap-1.5 sm:w-96">
              <span className="text-small text-muted">Department</span>
              <Select
                value={department ?? ""}
                onChange={(e) => set({ department: e.target.value, cycle: "" })}
                disabled={departments.list.length === 0}
              >
                {departments.list.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </Select>
            </label>
          )}
          {data?.cycles?.length > 1 && (
            <label className="flex flex-col gap-1.5 sm:w-64">
              <span className="text-small text-muted">Cycle</span>
              <Select value={data.cycle?.id ?? ""} onChange={(e) => set({ cycle: e.target.value })}>
                {data.cycles.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.status === "open" ? " (open)" : ""}
                  </option>
                ))}
              </Select>
            </label>
          )}
          {data?.cycles?.length === 1 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-small text-muted">Cycle</span>
              <span className="text-body font-medium">
                {data.cycle.name}
                {data.cycle.status === "open" ? " (open)" : ""}
              </span>
            </div>
          )}
        </div>
        <Tabs
          label="View"
          panelId="insights-panel"
          tabs={tabs}
          value={tab}
          onChange={(k) => set({ tab: k === "overview" ? "" : k })}
        />
      </div>

      {state.error && state.key === key && (
        <div className="flex flex-wrap items-center gap-3">
          <FormError>{state.error}</FormError>
          <button
            type="button"
            className="btn btn-ghost h-8 px-2"
            onClick={() => setReload((n) => n + 1)}
          >
            Retry
          </button>
        </div>
      )}
      {!department && !departments.loading && !courses.loading && (
        <section className="card p-[var(--card-pad)]">
          <h2 className="m-0 text-section font-medium">
            {departments.error ? "Couldn't load the departments" : "No departments yet"}
          </h2>
          <p className="m-0 mt-1 text-body text-muted">
            {departments.error
              ? errorMessage(departments.error)
              : "Add a department first, and its insights appear here."}
          </p>
        </section>
      )}
      {!loaded && !state.error && (department || departments.loading || courses.loading) && (
        <div className="flex flex-col gap-[var(--gap)]" aria-busy="true">
          <span className="skeleton h-28 w-full" />
          <span className="skeleton h-72 w-full" />
        </div>
      )}
      {loaded && data && !data.cycle && (
        <section className="card p-[var(--card-pad)]">
          <h2 className="m-0 text-section font-medium">No feedback cycles yet</h2>
          <p className="m-0 mt-1 text-body text-muted">
            Insights appear once a cycle with teaching forms in this department is published.
          </p>
        </section>
      )}
      <div
        id="insights-panel"
        role="tabpanel"
        aria-labelledby={`insights-panel-tab-${tab}`}
        className="flex flex-col gap-[var(--gap)]"
      >
        {loaded && data?.cycle && tab === "overview" && <OverviewTab data={data} />}
        {loaded && data?.cycle && tab === "bias" && state.bias && (
          <BiasTab panel={state.bias} sarcasm={state.sarcasm} />
        )}
        {loaded && data?.cycle && tab === "actions" && (
          <ActionsTab
            cycleId={data.cycle.id}
            department={{ id: data.department.id, name: data.department.name }}
          />
        )}
      </div>
    </div>
  );
}
