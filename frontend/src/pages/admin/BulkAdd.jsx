import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { Field, FormError, TextArea } from "../../components/forms";
import { BULK_TEMPLATE, downloadText } from "../../lib/csv";

/**
 * Bulk add from a CSV file or pasted CSV. "Check" runs the API in dry-run mode and lists
 * per-row problems; nothing is created until every row is valid.
 */
export function BulkAdd({ onCreated, onCancel }) {
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState(null);
  const [checked, setChecked] = useState(null); // { valid_rows } after a clean dry run
  const [rowErrors, setRowErrors] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  function reset() {
    setChecked(null);
    setRowErrors([]);
    setError(null);
  }

  async function onFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    reset();
    setFileName(file.name);
    setText(await file.text());
  }

  async function send(dryRun) {
    setBusy(true);
    setError(null);
    setRowErrors([]);
    const form = new FormData();
    form.append("file", new Blob([text], { type: "text/csv" }), fileName || "users.csv");
    try {
      const res = await api.post(`/users/bulk${dryRun ? "?dry_run=true" : ""}`, form);
      if (dryRun) setChecked(res.data);
      else onCreated(res.data.credentials);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail?.code === "bulk_invalid") {
        setRowErrors(detail.errors);
        setError(detail.message);
      } else {
        setError(errorMessage(err, "Couldn't check the upload."));
      }
      setChecked(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <p className="m-0 max-w-[72ch] text-body text-muted">
        Columns:{" "}
        <span className="font-mono text-[13px]">
          name, email, role, department_code, roll_no, gender
        </span>
        . Roles are admin, hod, faculty or student. Students need a roll number; staff need an
        email. Up to 1,000 rows.{" "}
        <button
          type="button"
          className="cursor-pointer text-text underline underline-offset-3"
          onClick={() => downloadText("facultylens-users-template.csv", BULK_TEMPLATE)}
        >
          Download a template
        </button>
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <label className="btn btn-secondary cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus">
          Choose CSV file
          <input type="file" accept=".csv,text/csv" className="sr-only" onChange={onFile} />
        </label>
        <span className="text-small text-muted">{fileName ?? "or paste the rows below"}</span>
      </div>
      <Field label="CSV rows">
        {(a) => (
          <TextArea
            {...a}
            value={text}
            spellCheck={false}
            className="font-mono"
            placeholder={BULK_TEMPLATE.trim()}
            onChange={(e) => {
              setText(e.target.value);
              setFileName(null);
              reset();
            }}
          />
        )}
      </Field>

      <FormError>{error}</FormError>
      {rowErrors.length > 0 && (
        <div className="max-h-72 overflow-auto rounded-control border border-border">
          <table className="w-full border-collapse text-body">
            <thead>
              <tr className="text-left text-small text-muted">
                <th scope="col" className="h-9 w-20 px-3 text-right font-medium">
                  Row
                </th>
                <th scope="col" className="h-9 px-3 font-medium">
                  What to fix
                </th>
              </tr>
            </thead>
            <tbody>
              {rowErrors.map((e) => (
                <tr key={e.row} className="border-t border-rule align-top">
                  <td className="num px-3 py-2 text-right">{e.row}</td>
                  <td className="px-3 py-2">{e.errors.join(" ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {checked && (
        <p className="m-0 flex items-center gap-2 text-body" role="status">
          <span className="pill pill-positive">Ready</span>
          {checked.valid_rows} {checked.valid_rows === 1 ? "row is" : "rows are"} valid.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {checked ? (
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() => send(false)}
          >
            {busy ? "Adding…" : `Add ${checked.valid_rows} users`}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || !text.trim()}
            onClick={() => send(true)}
          >
            {busy ? "Checking…" : "Check rows"}
          </button>
        )}
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
