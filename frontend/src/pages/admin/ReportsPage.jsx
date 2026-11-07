import { CheckIcon } from "../../components/icons";
import { useEffect, useMemo, useState } from "react";
import { errorMessage } from "../../api/client";
import { feedbackApi } from "../../api/feedback";
import { blobError, reportsApi } from "../../api/reports";
import { ActionTable } from "../../components/ActionTable";
import { EvidenceDrawer } from "../../components/EvidenceDrawer";
import { Field, FormError, Select, TextArea, TextInput } from "../../components/forms";
import { PageHeader, Panel } from "../../components/PageHeader";
import { useAsync } from "../../hooks/useAsync";
import { useDepartments } from "../../hooks/useDepartments";

const loadCycles = () => feedbackApi.cycles();

function Check({ done, children }) {
  return (
    <li className="flex items-start gap-2.5 text-body">
      <span
        aria-hidden="true"
        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${
          done
            ? "bg-[var(--pill-positive-bg)] text-[var(--pill-positive-ink)]"
            : "bg-active text-muted"
        }`}
      >
        {done && <CheckIcon />}
      </span>
      <span>
        <span className="sr-only">{done ? "Done: " : "Not yet: "}</span>
        {children}
      </span>
    </li>
  );
}

function AddAction({ cycleId, department, onDone, onCancel }) {
  const [form, setForm] = useState({
    label: "",
    issue: "",
    action: "",
    responsible: `HoD, ${department.name}`,
    timeline: "Before the next feedback cycle",
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const valid =
    form.label.trim().length >= 2 &&
    form.issue.trim().length >= 5 &&
    form.action.trim().length >= 5;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await reportsApi.add(cycleId, { ...form, department_id: department.id, kind: "other" });
      onDone();
    } catch (err) {
      setError(errorMessage(err, "Couldn't add the action."));
      setBusy(false);
    }
  }

  return (
    <Panel title={`Add an action for ${department.name}`}>
      <form onSubmit={submit} className="grid gap-4 md:grid-cols-2" noValidate>
        <Field label="Topic">
          {(a) => (
            <TextInput
              {...a}
              value={form.label}
              maxLength={120}
              placeholder="e.g. Library hours"
              onChange={set("label")}
            />
          )}
        </Field>
        <Field label="Responsible">
          {(a) => (
            <TextInput
              {...a}
              value={form.responsible}
              maxLength={160}
              onChange={set("responsible")}
            />
          )}
        </Field>
        <Field label="Issue" className="md:col-span-2">
          {(a) => (
            <TextArea
              {...a}
              value={form.issue}
              maxLength={600}
              className="min-h-16"
              onChange={set("issue")}
            />
          )}
        </Field>
        <Field label="Action" className="md:col-span-2">
          {(a) => (
            <TextArea
              {...a}
              value={form.action}
              maxLength={600}
              className="min-h-16"
              onChange={set("action")}
            />
          )}
        </Field>
        <Field label="Timeline">
          {(a) => (
            <TextInput {...a} value={form.timeline} maxLength={120} onChange={set("timeline")} />
          )}
        </Field>
        <div className="flex flex-wrap items-end gap-2 md:col-span-2">
          <button type="submit" className="btn btn-secondary" disabled={!valid || busy}>
            {busy ? "Adding…" : "Add as draft"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <FormError>{error}</FormError>
        </div>
      </form>
    </Panel>
  );
}

/** The administrator's feedback report builder (SPEC §11.6, §12). */
export function ReportsPage() {
  const cycles = useAsync(loadCycles);
  const departments = useDepartments();
  const [picked, setPicked] = useState(null);
  const [state, setState] = useState({ key: null, status: null, rows: null, error: null });
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(null);
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);
  const [adding, setAdding] = useState(null);
  const [drawer, setDrawer] = useState(null);

  const list = useMemo(
    () => (cycles.data ?? []).filter((c) => c.status !== "draft"),
    [cycles.data],
  );
  const cycleId = picked ?? (list.find((c) => c.status === "open") ?? list[0])?.id ?? null;
  const key = `${cycleId}|${reload}`;

  useEffect(() => {
    // Load the readiness and the rows whenever the cycle changes or something was saved.
    if (!cycleId) return undefined;
    let alive = true;
    Promise.all([reportsApi.status(cycleId), reportsApi.actions(cycleId)])
      .then(([status, rows]) => alive && setState({ key, status, rows, error: null }))
      .catch(
        (err) =>
          alive &&
          setState({
            key,
            status: null,
            rows: null,
            error: errorMessage(err, "Couldn't load the report."),
          }),
      );
    return () => {
      alive = false;
    };
  }, [cycleId, key]);

  const refresh = () => setReload((n) => n + 1);
  const loaded = state.key === key;
  const s = state.status;
  const pending = s ? s.actions - s.approved : 0;

  async function draft() {
    setBusy("draft");
    setError(null);
    setNotice(null);
    try {
      const r = await reportsApi.draft(cycleId);
      setNotice(
        `${r.added} new, ${r.replaced} refreshed, ${r.removed} no longer supported by the feedback and removed, ${r.kept} kept as you left them (edited, approved or added by hand).`,
      );
      refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't draft the actions."));
    } finally {
      setBusy(null);
    }
  }

  async function download(format, asDraft) {
    setBusy(`${format}:${asDraft}`);
    setError(null);
    try {
      const name = await reportsApi.download(cycleId, format, asDraft);
      setNotice(`Downloaded ${name}.`);
    } catch (err) {
      setError(await blobError(err, "Couldn't build the report."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader title="Feedback report">
        The Feedback Analysis and Action Taken Report. It reports departments, never individual
        teachers, because it is published on the college website. Every action must be approved by
        you or the Head of Department before the final export.
      </PageHeader>

      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        {!cycles.data ? (
          <span className="skeleton h-10 w-full md:w-72" />
        ) : list.length > 1 ? (
          <label className="flex flex-col gap-1.5 md:w-72">
            <span className="text-small text-muted">Cycle</span>
            <Select value={cycleId ?? ""} onChange={(e) => setPicked(e.target.value)}>
              {list.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.status === "open" ? " (open)" : ""}
                </option>
              ))}
            </Select>
          </label>
        ) : (
          <div className="flex flex-col gap-1.5">
            <span className="text-small text-muted">Cycle</span>
            <span className="text-body font-medium">
              {list[0]
                ? `${list[0].name}${list[0].status === "open" ? " (open)" : ""}`
                : "No published cycles yet"}
            </span>
          </div>
        )}
        <button
          type="button"
          className="btn btn-secondary"
          disabled={!cycleId || busy !== null}
          onClick={draft}
          title="Edited and approved actions are never overwritten"
        >
          {busy === "draft"
            ? "Drafting…"
            : s?.actions
              ? "Re-draft from the feedback"
              : "Draft action items"}
        </button>
      </div>

      {(error || state.error) && <FormError>{error || state.error}</FormError>}
      {notice && (
        <p className="m-0 text-body text-muted" role="status">
          {notice}
        </p>
      )}

      {!loaded && cycleId && !state.error && (
        <span className="skeleton h-40 w-full" aria-busy="true" />
      )}

      {loaded && s && (
        <div className="grid items-start gap-[var(--gap)] lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex flex-col gap-[var(--gap)]">
            {adding && (
              <AddAction
                cycleId={cycleId}
                department={adding}
                onCancel={() => setAdding(null)}
                onDone={() => {
                  setAdding(null);
                  refresh();
                }}
              />
            )}
            <ActionTable
              rows={state.rows}
              departments={departments.list}
              cycleId={cycleId}
              canDelete
              onChanged={refresh}
              onEvidence={setDrawer}
              onAdd={s.actions > 0 ? setAdding : undefined}
            />
          </div>
          <aside className="flex flex-col gap-[var(--gap)] max-lg:order-first lg:sticky lg:top-6">
            <section aria-labelledby="ready-h" className="card p-[var(--card-pad)]">
              <h2 id="ready-h" className="m-0 mb-3 text-section font-medium">
                Ready to export?
              </h2>
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                <Check done={s.responses > 0 && s.analysed === s.responses}>
                  <span className="num">
                    {s.analysed} of {s.responses}
                  </span>{" "}
                  responses analysed
                </Check>
                <Check done={s.actions > 0}>
                  {s.actions ? (
                    <>
                      <span className="num">{s.actions}</span> actions drafted
                    </>
                  ) : (
                    "Actions drafted"
                  )}
                </Check>
                <Check done={s.actions > 0 && pending === 0}>
                  <span className="num">
                    {s.approved} of {s.actions}
                  </span>{" "}
                  actions approved
                </Check>
              </ul>
            </section>
            <section
              aria-labelledby="export-h"
              className="card flex flex-col gap-3 p-[var(--card-pad)]"
            >
              <h2 id="export-h" className="m-0 text-section font-medium">
                Export
              </h2>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!s.ready || busy !== null}
                  onClick={() => download("pdf", false)}
                >
                  {busy === "pdf:false" ? "Building…" : "Download PDF"}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={!s.ready || busy !== null}
                  onClick={() => download("docx", false)}
                >
                  {busy === "docx:false" ? "Building…" : "Word (.docx)"}
                </button>
              </div>
              {!s.ready && (
                <p className="m-0 text-small text-muted">
                  {s.actions === 0
                    ? "Draft the action items first."
                    : pending > 0
                      ? `${pending} action${pending === 1 ? "" : "s"} still need${pending === 1 ? "s" : ""} approval.`
                      : "Some responses are not analysed yet."}{" "}
                  A preview is available now, marked as a draft on every page.
                </p>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-rule pt-3 text-small">
                <button
                  type="button"
                  className="cursor-pointer text-text underline underline-offset-3 disabled:cursor-not-allowed disabled:text-faint"
                  disabled={busy !== null}
                  onClick={() => download("pdf", true)}
                >
                  {busy === "pdf:true" ? "Building preview…" : "Preview PDF (draft)"}
                </button>
                <button
                  type="button"
                  className="cursor-pointer text-text underline underline-offset-3 disabled:cursor-not-allowed disabled:text-faint"
                  disabled={busy !== null}
                  onClick={() => download("docx", true)}
                >
                  {busy === "docx:true" ? "Building preview…" : "Preview Word (draft)"}
                </button>
              </div>
            </section>
          </aside>
        </div>
      )}
      <EvidenceDrawer request={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
