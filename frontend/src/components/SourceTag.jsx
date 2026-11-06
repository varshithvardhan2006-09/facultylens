const LABELS = { orcid: "ORCID", s2: "Semantic Scholar" };

/** Where a profile fact came from. Quiet: it is provenance, not status. */
export function SourceTag({ source }) {
  if (!source || source === "manual") return null;
  return <span className="pill pill-neutral">{LABELS[source] ?? source}</span>;
}
