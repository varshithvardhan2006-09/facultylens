const LABELS = { orcid: "ORCID", s2: "Semantic Scholar", manual: "Added by hand" };

/** Where a profile fact came from. Quiet: it is provenance, not status. */
export function SourceTag({ source }) {
  if (!source || source === "manual") return null;
  return <span className="pill pill-neutral">{LABELS[source] ?? source}</span>;
}

export const SOURCE_LABELS = LABELS;
