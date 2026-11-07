import { useState } from "react";
import { errorMessage } from "../api/client";
import { reportsApi } from "../api/reports";
import { Field, FormError, TextArea, TextInput } from "./forms";

const STATUS = {
  draft: ["pill-warning", "Needs approval"],
  approved: ["pill-positive", "Approved"],
};
const KIND = { teaching: "Teaching", curriculum: "Curriculum", other: "Other" };

function Editor({ row, cycleId, onSaved, onCancel }) {
  const [form, setForm] = useState({
    issue: row.issue,
    action: row.action,
    responsible: row.responsible,
    timeline: row.timeline,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const valid =
    form.issue.trim().length >= 5 &&
    form.action.trim().length >= 5 &&
    form.responsible.trim().length >= 2;

  async function save(approve) {
    setBusy(true);
    setError(null);
    try {
      await reportsApi.edit(cycleId, row.id, {
        ...form,
        ...(approve ? { status: "approved" } : {}),
      });
      onSaved();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the action."));
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-3 rounded-control bg-raised p-3 md:grid-cols-2">
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
      <Field label="Timeline">
        {(a) => (
          <TextInput {...a} value={form.timeline} maxLength={120} onChange={set("timeline")} />
        )}
      </Field>
      <div className="flex flex-wrap items-center gap-2 md:col-span-2">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={!valid || busy}
          onClick={() => save(true)}
        >
          Save and approve
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={!valid || busy}
          onClick={() => save(false)}
        >
          Save as draft
        </button>
        <button type="button" className="btn btn-ghost" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
        <FormError>{error}</FormError>
      </div>
    </div>
  );
}

function Row({ row, cycleId, canDelete, onChanged, onEvidence }) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [cls, text] = STATUS[row.status] ?? STATUS.draft;

  async function act(fn) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (err) {
      setError(errorMessage(err, "That didn't work."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="flex flex-col gap-2 border-t border-rule px-[var(--card-pad)] py-4 first:border-t-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-small">
        <span className={`pill ${cls}`}>{text}</span>
        <span className="pill pill-neutral">
          {KIND[row.kind] ?? row.kind} · {row.label}
        </span>
        {row.evidence_count > 0 && (
          <span className="num text-muted">
            {row.evidence_count}{" "}
            {row.kind === "curriculum" && row.key !== "comments" ? "responses" : "comments"}
          </span>
        )}
        {row.source && row.source !== "manual" && (
          <span className="text-muted">
            · drafted by {row.source.startsWith("groq") ? "the AI model" : "template"}
            {row.edited ? ", edited" : ""}
          </span>
        )}
      </div>
      {editing ? (
        <Editor
          row={row}
          cycleId={cycleId}
          onSaved={() => {
            setEditing(false);
            onChanged();
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <>
          <p className="m-0 max-w-[80ch] text-body">{row.issue}</p>
          <dl className="m-0 grid gap-x-6 gap-y-1 text-body md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
            <div className="flex flex-col">
              <dt className="text-small text-muted">Action</dt>
              <dd className="m-0">{row.action}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-small text-muted">Responsible</dt>
              <dd className="m-0">{row.responsible}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-small text-muted">Timeline</dt>
              <dd className="m-0">{row.timeline}</dd>
            </div>
          </dl>
          <div className="flex flex-wrap items-center gap-2">
            {row.status === "draft" ? (
              <button
                type="button"
                className="btn btn-secondary h-8 px-3 text-small"
                disabled={busy}
                onClick={() => act(() => reportsApi.edit(cycleId, row.id, { status: "approved" }))}
              >
                Approve
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-ghost h-8 px-3 text-small"
                disabled={busy}
                onClick={() => act(() => reportsApi.edit(cycleId, row.id, { status: "draft" }))}
              >
                Reopen
              </button>
            )}
            <button
              type="button"
              className="btn btn-ghost h-8 px-3 text-small"
              disabled={busy}
              onClick={() => setEditing(true)}
            >
              Edit
            </button>
            {row.evidence_ids?.length > 0 && (
              <button
                type="button"
                className="btn btn-ghost h-8 px-3 text-small"
                onClick={() =>
                  onEvidence({
                    ids: row.evidence_ids,
                    load: () => reportsApi.evidence(cycleId, row.id),
                    tone: "negative",
                    kicker: `${KIND[row.kind] ?? ""} · ${row.label}`,
                    title: row.issue,
                  })
                }
              >
                Show the comments
              </button>
            )}
            {canDelete && row.source === "manual" && (
              <button
                type="button"
                className="btn btn-ghost h-8 px-3 text-small text-negative"
                disabled={busy}
                onClick={() => {
                  if (window.confirm("Delete this action?"))
                    act(() => reportsApi.remove(cycleId, row.id));
                }}
              >
                Delete
              </button>
            )}
            <FormError>{error}</FormError>
          </div>
        </>
      )}
    </li>
  );
}

/** Action Taken rows grouped by department, each editable and approvable in place. */
export function ActionTable({
  rows,
  departments,
  cycleId,
  canDelete = false,
  onChanged,
  onEvidence,
  onAdd,
}) {
  // Rows must show even if the department list failed to load.
  const known = new Set(departments.map((d) => d.id));
  const unlisted = [...new Set(rows.map((r) => r.department_id))]
    .filter((id) => !known.has(id))
    .map((id) => ({ id, name: "Department" }));
  const groups = [...departments, ...unlisted]
    .map((d) => ({ ...d, rows: rows.filter((r) => r.department_id === d.id) }))
    .filter((g) => g.rows.length > 0 || onAdd);
  if (groups.length === 0) {
    return (
      <section className="card p-[var(--card-pad)]">
        <h2 className="m-0 text-section font-medium">No actions yet</h2>
        <p className="m-0 mt-1 text-body text-muted">
          The administrator drafts the Action Taken Report from this cycle&apos;s feedback.
        </p>
      </section>
    );
  }
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      {groups.map((g) => {
        const approved = g.rows.filter((r) => r.status === "approved").length;
        return (
          <section key={g.id} aria-labelledby={`atr-${g.id}`} className="card overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-[var(--card-pad)] py-3">
              <h2 id={`atr-${g.id}`} className="m-0 text-section font-medium">
                {g.name}
              </h2>
              <div className="flex items-center gap-3">
                <span className="num text-small text-muted">
                  {approved} of {g.rows.length} approved
                </span>
                {onAdd && (
                  <button
                    type="button"
                    className="btn btn-ghost h-8 px-2 text-small"
                    onClick={() => onAdd(g)}
                  >
                    Add an action
                  </button>
                )}
              </div>
            </div>
            {g.rows.length === 0 ? (
              <p className="m-0 px-[var(--card-pad)] py-4 text-body text-muted">
                No issue in this department met the drafting rules. Add one if the department wants
                to record an action.
              </p>
            ) : (
              <ul className="m-0 list-none p-0">
                {g.rows.map((row) => (
                  <Row
                    key={row.id}
                    row={row}
                    cycleId={cycleId}
                    canDelete={canDelete}
                    onChanged={onChanged}
                    onEvidence={onEvidence}
                  />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
