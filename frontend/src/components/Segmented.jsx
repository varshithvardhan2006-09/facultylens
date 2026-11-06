/**
 * A small set of mutually exclusive choices drawn as joined segments: native radios sharing
 * one name inside a labelled radiogroup (arrow keys move between them), styled like the
 * rating scale. `options` is [[value, label, hint?]]; the selected segment is the primary ink,
 * except the `quiet` value (a default such as "not mentioned"), which is only a grey tone.
 */
export function Segmented({ name, label, labelId, options, value, onChange, size = "md", quiet }) {
  const height = size === "sm" ? "min-h-8 text-small" : "min-h-10 text-body";
  return (
    <div
      role="radiogroup"
      aria-label={labelId ? undefined : label}
      aria-labelledby={labelId}
      className="grid w-full gap-1"
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      {options.map(([v, text, hint]) => {
        const checked = value === v;
        return (
          <label
            key={String(v)}
            className={`flex cursor-pointer items-center justify-center gap-1.5 rounded-control border px-2 text-center transition-[background-color,border-color,transform] duration-150 select-none active:scale-[0.97] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus ${height} ${
              checked && v === quiet
                ? "border-control bg-active font-medium text-text"
                : checked
                  ? "border-primary bg-primary text-primary-ink"
                  : "border-control bg-surface text-text hover:bg-raised"
            }`}
          >
            <input
              type="radio"
              name={name}
              checked={checked}
              onChange={() => onChange(v)}
              className="sr-only"
            />
            <span>{text}</span>
            {hint && (
              <kbd
                className={`font-sans text-[11px] ${checked ? "opacity-80" : "text-faint"}`}
                aria-hidden="true"
              >
                {hint}
              </kbd>
            )}
          </label>
        );
      })}
    </div>
  );
}
