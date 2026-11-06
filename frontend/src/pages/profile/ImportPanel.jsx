import { useState } from "react";
import { errorMessage } from "../../api/client";
import { profilesApi } from "../../api/profiles";
import { Field, FormError, TextInput } from "../../components/forms";
import { Panel } from "../../components/PageHeader";

const ORCID_RE = /(\d{4})-?(\d{4})-?(\d{4})-?(\d{3}[\dXx])/;

function stamp(log) {
  if (!log) return null;
  const when = new Date(log.at).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
  return `Last import ${when}: ${log.added} new, ${log.skipped} already known${log.enriched ? `, ${log.enriched} filled in` : ""}.`;
}

function summary(result, source) {
  const added = Object.values(result.added).reduce((a, b) => a + b, 0);
  if (!added && !result.enriched)
    return `Nothing new from ${source}: every item is already on your profile, waiting for review, or rejected.`;
  const parts = Object.entries(result.added).map(([k, n]) => `${n} ${k}${n === 1 ? "" : "s"}`);
  return `${parts.join(", ") || "No new items"} from ${source} waiting for your review${result.enriched ? `; ${result.enriched} pending papers gained citation counts` : ""}.`;
}

function OrcidImport({ facultyId, profile, onResult }) {
  const [value, setValue] = useState(profile.orcid ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);
  const valid = ORCID_RE.test(value);

  async function run(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const result = await profilesApi.importOrcid(facultyId, value.trim());
      setDone(summary(result, "ORCID"));
      onResult(result.profile);
    } catch (err) {
      setError(errorMessage(err, "The ORCID import failed. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={run} className="flex flex-col gap-3" noValidate>
      <Field
        label="ORCID iD"
        hint={
          stamp(profile.import_log?.orcid) ??
          "Works, employment, education and keywords from your public ORCID record."
        }
        error={value && !valid ? "An ORCID iD looks like 0000-0002-1825-0097." : null}
      >
        {(a) => (
          <TextInput
            {...a}
            value={value}
            placeholder="0000-0002-1825-0097"
            spellCheck={false}
            onChange={(e) => setValue(e.target.value)}
          />
        )}
      </Field>
      <div>
        <button type="submit" className="btn btn-primary h-9" disabled={!valid || busy}>
          {busy ? "Fetching from ORCID…" : "Import from ORCID"}
        </button>
      </div>
      <FormError>{error}</FormError>
      {done && (
        <p className="m-0 text-small" role="status">
          {done}
        </p>
      )}
    </form>
  );
}

function S2Import({ facultyId, profile, onResult }) {
  const [query, setQuery] = useState(profile.user.name);
  const [candidates, setCandidates] = useState(null);
  const [busy, setBusy] = useState(null); // "search" | author id
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  async function search(event) {
    event.preventDefault();
    setBusy("search");
    setError(null);
    setDone(null);
    try {
      setCandidates(await profilesApi.searchS2(facultyId, query.trim()));
    } catch (err) {
      setError(errorMessage(err, "The search failed. Try again."));
    } finally {
      setBusy(null);
    }
  }

  async function pick(authorId) {
    setBusy(authorId);
    setError(null);
    try {
      const result = await profilesApi.importS2(facultyId, authorId);
      setDone(summary(result, "Semantic Scholar"));
      setCandidates(null);
      onResult(result.profile);
    } catch (err) {
      setError(errorMessage(err, "The Semantic Scholar import failed. Try again."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={search} className="flex flex-col gap-3" noValidate>
        <Field
          label="Semantic Scholar"
          hint={
            stamp(profile.import_log?.s2) ??
            "Search your name, then pick the author that is you. Adds papers with citation counts."
          }
        >
          {(a) => <TextInput {...a} value={query} onChange={(e) => setQuery(e.target.value)} />}
        </Field>
        <div>
          <button
            type="submit"
            className="btn btn-secondary h-9"
            disabled={query.trim().length < 2 || busy}
          >
            {busy === "search" ? "Searching…" : "Find author"}
          </button>
        </div>
      </form>
      <FormError>{error}</FormError>
      {done && (
        <p className="m-0 text-small" role="status">
          {done}
        </p>
      )}
      {candidates && (
        <div className="flex flex-col gap-2" aria-live="polite">
          {candidates.length === 0 ? (
            <p className="m-0 text-small text-muted">
              No authors match. Try your name as it appears on your papers.
            </p>
          ) : (
            <>
              <p className="m-0 text-small text-muted">
                {candidates.length} authors found. Same names are common; check the sample titles.
              </p>
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                {candidates.map((c) => (
                  <li key={c.author_id} className="rounded-control border border-border p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-medium">{c.name}</div>
                        <div className="num text-small text-muted">
                          {c.paper_count.toLocaleString("en-IN")} papers
                          {c.h_index != null ? ` · h-index ${c.h_index}` : ""}
                          {c.affiliations.length ? ` · ${c.affiliations.join(", ")}` : ""}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="btn btn-primary h-8 shrink-0 px-3"
                        disabled={Boolean(busy)}
                        onClick={() => pick(c.author_id)}
                      >
                        {busy === c.author_id ? "Importing…" : "This is me"}
                      </button>
                    </div>
                    {c.sample_titles.length > 0 && (
                      <ul className="m-0 mt-2 list-disc pl-5 text-small text-muted">
                        {c.sample_titles.map((t) => (
                          <li key={t}>{t}</li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function ImportPanel({ facultyId, profile, onResult }) {
  return (
    <Panel title="Import from research databases">
      <div className="flex flex-col gap-6">
        <OrcidImport facultyId={facultyId} profile={profile} onResult={onResult} />
        <div className="border-t border-rule pt-5">
          <S2Import facultyId={facultyId} profile={profile} onResult={onResult} />
        </div>
        <p className="m-0 text-small text-muted">
          Imported items wait for your review. Nothing appears on your profile until you accept it.
        </p>
      </div>
    </Panel>
  );
}
