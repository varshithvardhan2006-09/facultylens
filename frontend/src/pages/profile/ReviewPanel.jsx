import { useState } from "react";
import { errorMessage } from "../../api/client";
import { profilesApi } from "../../api/profiles";
import { FormError } from "../../components/forms";
import { SourceTag } from "../../components/SourceTag";

const KINDS = [
  ["publication", "Publications"],
  ["experience", "Experience"],
  ["qualification", "Qualifications"],
  ["interest", "Interests"],
];

function describe(item) {
  const d = item.data;
  switch (item.kind) {
    case "publication":
      return {
        title: d.title,
        meta: [
          d.venue,
          d.year,
          d.citations != null ? `${d.citations} citations` : null,
          d.doi && `doi:${d.doi}`,
        ]
          .filter(Boolean)
          .join(" · "),
      };
    case "experience":
      return {
        title: `${d.role}, ${d.institution}`,
        meta: [d.department, d.from_year && `${d.from_year}–${d.to_year ?? "present"}`]
          .filter(Boolean)
          .join(" · "),
      };
    case "qualification":
      return {
        title: `${d.degree}, ${d.institution}`,
        meta: [d.specialisation, d.year].filter(Boolean).join(" · "),
      };
    default:
      return { title: d.tag, meta: "Research interest" };
  }
}

/** Pending imports grouped by kind; accept or reject one at a time or a whole group. */
export function ReviewPanel({ facultyId, pending, onDecided }) {
  const present = KINDS.filter(([k]) => pending.some((p) => p.kind === k));
  const [tab, setTab] = useState(present[0]?.[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [skipped, setSkipped] = useState([]);
  const current = present.some(([k]) => k === tab) ? tab : present[0]?.[0];
  const items = pending.filter((p) => p.kind === current);

  async function decide(accept, reject) {
    setBusy(true);
    setError(null);
    try {
      const saved = await profilesApi.decide(facultyId, accept, reject);
      setSkipped(saved.skipped_imports ?? []);
      onDecided(saved);
    } catch (err) {
      setError(errorMessage(err, "Couldn't save your decision. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby="review-h">
      <div className="flex flex-col gap-1 border-b border-rule px-[var(--card-pad)] py-4">
        <h2 id="review-h" className="m-0 text-section font-medium">
          {pending.length} imported {pending.length === 1 ? "item waits" : "items wait"} for your
          review
        </h2>
        <p className="m-0 text-small text-muted">
          Accept what is yours and correct. Rejected items won&apos;t be suggested again.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-[var(--card-pad)]">
        <div role="tablist" aria-label="Kind of item" className="-mb-px flex gap-4 overflow-x-auto">
          {present.map(([kind, label]) => {
            const n = pending.filter((p) => p.kind === kind).length;
            const active = kind === current;
            return (
              <button
                key={kind}
                type="button"
                role="tab"
                aria-selected={active}
                className={`h-11 cursor-pointer border-b-2 text-body whitespace-nowrap transition-colors ${
                  active
                    ? "border-text font-medium text-text"
                    : "border-transparent text-muted hover:text-text"
                }`}
                onClick={() => setTab(kind)}
              >
                {label} <span className="num">{n}</span>
              </button>
            );
          })}
        </div>
        <div className="flex gap-1 py-2">
          <button
            type="button"
            className="btn btn-ghost h-8 px-2 text-small"
            disabled={busy}
            onClick={() =>
              decide(
                [],
                items.map((i) => i.id),
              )
            }
          >
            Reject all {items.length}
          </button>
          <button
            type="button"
            className="btn btn-secondary h-8 px-3 text-small"
            disabled={busy}
            onClick={() =>
              decide(
                items.map((i) => i.id),
                [],
              )
            }
          >
            Accept all {items.length}
          </button>
        </div>
      </div>
      {error && (
        <div className="px-[var(--card-pad)] pt-3">
          <FormError>{error}</FormError>
        </div>
      )}
      {skipped.length > 0 && (
        <div className="px-[var(--card-pad)] pt-3 text-small">
          <p className="m-0 font-medium">These stayed here because they need fixing first:</p>
          <ul className="m-0 mt-1 pl-4 text-muted">
            {skipped.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
      <ul className="m-0 max-h-[520px] list-none overflow-auto p-0" role="tabpanel">
        {items.map((item) => {
          const { title, meta } = describe(item);
          return (
            <li
              key={item.id}
              className="flex flex-col gap-2 border-t border-rule px-[var(--card-pad)] py-3 first:border-t-0 md:flex-row md:items-center md:justify-between md:gap-6"
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="font-medium text-pretty">{title}</span>
                {meta && <span className="text-small text-muted">{meta}</span>}
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <SourceTag source={item.source} />
                <button
                  type="button"
                  className="btn btn-ghost h-8 px-2 text-small"
                  disabled={busy}
                  onClick={() => decide([], [item.id])}
                >
                  Reject
                </button>
                <button
                  type="button"
                  className="btn btn-secondary h-8 px-3 text-small"
                  disabled={busy}
                  onClick={() => decide([item.id], [])}
                >
                  Accept
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
