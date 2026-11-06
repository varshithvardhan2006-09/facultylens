import { useState } from "react";
import { Field, Select, TextArea, TextInput } from "../../components/forms";
import { SourceTag } from "../../components/SourceTag";

const PUB_TYPES = [
  ["journal", "Journal article"],
  ["conference", "Conference paper"],
  ["book", "Book"],
  ["chapter", "Book chapter"],
  ["preprint", "Preprint"],
  ["thesis", "Thesis"],
  ["other", "Other"],
];
const TYPE_LABEL = Object.fromEntries(PUB_TYPES);
const BLANK = { title: "", venue: "", year: "", type: "journal", doi: "", authors: [], url: "" };

function PublicationForm({ initial, onDone, onCancel }) {
  const [p, setP] = useState({ ...BLANK, ...initial, authors: initial?.authors ?? [] });
  const set = (k) => (e) => setP({ ...p, [k]: e.target.value });
  return (
    <div className="flex flex-col gap-4 rounded-control bg-raised p-4">
      <Field label="Title">
        {(a) => <TextInput {...a} value={p.title} onChange={set("title")} />}
      </Field>
      <div className="grid gap-4 md:grid-cols-[2fr_1fr_1fr]">
        <Field label="Journal, conference or publisher">
          {(a) => <TextInput {...a} value={p.venue ?? ""} onChange={set("venue")} />}
        </Field>
        <Field label="Year">
          {(a) => (
            <TextInput
              {...a}
              inputMode="numeric"
              maxLength={4}
              value={p.year ?? ""}
              onChange={set("year")}
            />
          )}
        </Field>
        <Field label="Type">
          {(a) => (
            <Select {...a} value={p.type ?? "other"} onChange={set("type")}>
              {PUB_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="DOI (optional)" hint="Like 10.1109/ACCESS.2024.1234567">
          {(a) => <TextInput {...a} value={p.doi ?? ""} onChange={set("doi")} spellCheck={false} />}
        </Field>
        <Field label="Link (optional)">
          {(a) => <TextInput {...a} type="url" value={p.url ?? ""} onChange={set("url")} />}
        </Field>
      </div>
      <Field label="Authors (optional)" hint="One per line, in the order printed on the paper.">
        {(a) => (
          <TextArea
            {...a}
            className="min-h-20"
            value={(p.authors ?? []).join("\n")}
            onChange={(e) => setP({ ...p, authors: e.target.value.split("\n") })}
          />
        )}
      </Field>
      <div className="flex gap-2">
        <button
          type="button"
          className="btn btn-primary h-8"
          disabled={!p.title.trim()}
          onClick={() => onDone({ ...p, authors: p.authors.map((x) => x.trim()).filter(Boolean) })}
        >
          Keep
        </button>
        <button type="button" className="btn btn-ghost h-8" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export function PublicationsEditor({ items, onChange }) {
  const [editing, setEditing] = useState(null); // index, or "new"
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const visible = items
    .map((p, index) => ({ p, index }))
    .filter(
      ({ p }) => !q || `${p.title} ${p.venue ?? ""} ${p.year ?? ""}`.toLowerCase().includes(q),
    );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="btn btn-secondary h-8"
          onClick={() => setEditing("new")}
          disabled={editing === "new"}
        >
          Add publication
        </button>
        {items.length > 8 && (
          <div className="w-full max-w-xs">
            <TextInput
              type="search"
              aria-label="Filter publications"
              placeholder="Filter by title, venue or year"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        )}
      </div>
      {editing === "new" && (
        <PublicationForm
          onCancel={() => setEditing(null)}
          onDone={(p) => {
            onChange([{ ...p, source: "manual" }, ...items]);
            setEditing(null);
          }}
        />
      )}
      {items.length === 0 && editing !== "new" ? (
        <p className="m-0 text-body text-muted">
          No publications yet. Import them from ORCID or Semantic Scholar, or add them by hand.
        </p>
      ) : (
        <ol className="m-0 flex list-none flex-col p-0">
          {visible.map(({ p, index }) => (
            <li
              key={p.id ?? `new-${index}`}
              className="border-t border-rule py-3 first:border-t-0 first:pt-0"
            >
              {editing === index ? (
                <PublicationForm
                  initial={p}
                  onCancel={() => setEditing(null)}
                  onDone={(next) => {
                    onChange(items.map((x, i) => (i === index ? { ...x, ...next } : x)));
                    setEditing(null);
                  }}
                />
              ) : (
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between md:gap-6">
                  <div className="flex min-w-0 flex-col gap-1">
                    <span className="font-medium text-pretty">{p.title}</span>
                    <span className="text-small text-muted">
                      {[TYPE_LABEL[p.type] ?? "Other", p.venue, p.year].filter(Boolean).join(" · ")}
                      {p.citations != null && (
                        <span className="num">
                          {" "}
                          · {p.citations.toLocaleString("en-IN")} citations
                        </span>
                      )}
                    </span>
                    {p.authors?.length > 0 && (
                      <span className="text-small text-muted">
                        {p.authors.slice(0, 6).join(", ")}
                        {p.authors.length > 6 ? ", …" : ""}
                      </span>
                    )}
                    {p.tldr && <span className="text-small text-text">{p.tldr}</span>}
                    {p.doi && (
                      <a
                        className="w-fit text-small text-muted underline"
                        href={`https://doi.org/${p.doi}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        doi:{p.doi}
                      </a>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <SourceTag source={p.source} />
                    <button
                      type="button"
                      className="btn btn-ghost h-8 px-2 text-small"
                      onClick={() => setEditing(index)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost h-8 px-2 text-small"
                      aria-label={`Remove ${p.title}`}
                      onClick={() => onChange(items.filter((_, i) => i !== index))}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
          {q && visible.length === 0 && (
            <li className="text-body text-muted">No publication matches “{query}”.</li>
          )}
        </ol>
      )}
    </div>
  );
}
