import { SourceTag } from "../../components/SourceTag";

const control =
  "h-9 w-full min-w-0 rounded-control border border-control bg-surface px-2.5 text-body text-text " +
  "transition-colors duration-150 hover:border-muted focus-visible:border-focus " +
  "focus-visible:outline-2 focus-visible:outline-offset-0 placeholder:text-faint";

/**
 * Editable rows for small lists (qualifications, experience, achievements).
 * `fields`: [{ key, label, type: "text" | "year" | "select", options, span, placeholder }].
 * Desktop shows one header row and aligned columns; phones stack each row's fields.
 */
export function RowListEditor({ fields, items, onChange, emptyText, addLabel, newItem, noun }) {
  const cols = fields.map((f) => `${f.span ?? 1}fr`).join(" ");
  const update = (index, key, value) =>
    onChange(items.map((item, i) => (i === index ? { ...item, [key]: value } : item)));

  return (
    <div className="flex flex-col gap-3">
      {items.length === 0 ? (
        <p className="m-0 text-body text-muted">{emptyText}</p>
      ) : (
        <div className="flex flex-col">
          <div
            className="hidden gap-2 pb-1.5 text-small text-muted md:grid"
            style={{ gridTemplateColumns: `${cols} 168px` }}
            aria-hidden="true"
          >
            {fields.map((f) => (
              <span key={f.key}>{f.label}</span>
            ))}
            <span />
          </div>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {items.map((item, index) => (
              <li
                key={item.id ?? `new-${index}`}
                className="grid grid-cols-2 gap-2 border-rule max-md:border-b max-md:pb-3 md:grid-cols-[var(--cols)_168px] md:items-center"
                style={{ "--cols": cols }}
              >
                {fields.map((f) => {
                  const label = `${f.label} (${noun} ${index + 1})`;
                  const value = item[f.key] ?? "";
                  const common = {
                    "aria-label": label,
                    value,
                    onChange: (e) => update(index, f.key, e.target.value),
                    className: control,
                  };
                  return (
                    <div key={f.key} className={f.wide ? "max-md:col-span-2" : ""}>
                      <span
                        className="mb-1 block text-small text-muted md:hidden"
                        aria-hidden="true"
                      >
                        {f.label}
                      </span>
                      {f.type === "select" ? (
                        <select {...common} className={`${control} cursor-pointer`}>
                          {f.options.map(([v, l]) => (
                            <option key={v} value={v}>
                              {l}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          {...common}
                          inputMode={f.type === "year" ? "numeric" : undefined}
                          maxLength={f.type === "year" ? 4 : (f.maxLength ?? 200)}
                          placeholder={f.placeholder}
                        />
                      )}
                    </div>
                  );
                })}
                <div className="flex items-center justify-end gap-1 max-md:col-span-2 max-md:justify-between">
                  <SourceTag source={item.source} />
                  <button
                    type="button"
                    className="btn btn-ghost h-8 px-2 text-small"
                    aria-label={`Remove ${noun} ${index + 1}`}
                    onClick={() => onChange(items.filter((_, i) => i !== index))}
                  >
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <button
          type="button"
          className="btn btn-secondary h-8"
          onClick={() => onChange([...items, newItem()])}
        >
          {addLabel}
        </button>
      </div>
    </div>
  );
}
