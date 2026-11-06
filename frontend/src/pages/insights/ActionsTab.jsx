import { useEffect, useState } from "react";
import { errorMessage } from "../../api/client";
import { reportsApi } from "../../api/reports";
import { ActionTable } from "../../components/ActionTable";
import { EvidenceDrawer } from "../../components/EvidenceDrawer";
import { FormError } from "../../components/forms";

/** A HoD's own department's Action Taken rows for the NAAC report: edit and approve here. */
export function ActionsTab({ cycleId, department }) {
  const [state, setState] = useState({ key: null, rows: null, error: null });
  const [reload, setReload] = useState(0);
  const [drawer, setDrawer] = useState(null);
  const key = `${cycleId}|${reload}`;

  useEffect(() => {
    let alive = true;
    reportsApi
      .actions(cycleId)
      .then((rows) => alive && setState({ key, rows, error: null }))
      .catch(
        (err) =>
          alive &&
          setState({ key, rows: null, error: errorMessage(err, "Couldn't load the actions.") }),
      );
    return () => {
      alive = false;
    };
  }, [cycleId, key]);

  if (state.key !== key) return <span className="skeleton h-40 w-full" aria-busy="true" />;
  if (state.error) return <FormError>{state.error}</FormError>;
  const pending = state.rows.filter((r) => r.status !== "approved").length;
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <p className="m-0 max-w-[72ch] text-body text-muted">
        These are the issues from this cycle&apos;s feedback that go into the NAAC Action Taken
        Report for your department. Edit the action so it is one your department will really take,
        then approve it.{" "}
        {state.rows.length > 0 &&
          (pending
            ? `${pending} still need${pending === 1 ? "s" : ""} your approval.`
            : "All are approved.")}
      </p>
      <ActionTable
        rows={state.rows}
        departments={[department]}
        cycleId={cycleId}
        onChanged={() => setReload((n) => n + 1)}
        onEvidence={setDrawer}
      />
      <EvidenceDrawer request={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
