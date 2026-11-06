import { LIKERT_LABELS } from "../api/feedback";

/**
 * A 1-5 rating: native radios sharing one name (arrow keys move between them) inside a
 * labelled radiogroup, drawn as five equal segments. Each segment shows its number and word,
 * so neither colour nor position carries the meaning alone.
 */
export function LikertScale({ id, name, label, question, value, onChange, invalid }) {
  const labelId = `${id}-label`;
  const hintId = `${id}-hint`;
  return (
    <div
      id={id}
      tabIndex={-1}
      className="grid scroll-mt-24 gap-3 outline-none md:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] md:items-center md:gap-8"
    >
      <div className="flex flex-col gap-0.5">
        <span id={labelId} className="text-body font-medium">
          {label}
        </span>
        <span id={hintId} className="text-small text-muted">
          {question}
        </span>
        {invalid && <span className="text-small text-negative">Choose a rating.</span>}
      </div>
      <div
        role="radiogroup"
        aria-labelledby={labelId}
        aria-describedby={hintId}
        aria-invalid={invalid || undefined}
        aria-required="true"
        className="grid w-full grid-cols-5 gap-1.5"
      >
        {[1, 2, 3, 4, 5].map((v) => {
          const checked = value === v;
          return (
            <label
              key={v}
              className={`flex min-h-12 cursor-pointer flex-col items-center justify-center gap-0.5 rounded-control border px-1 py-1.5 text-center transition-[background-color,border-color,transform] duration-150 select-none active:scale-[0.97] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus ${
                checked
                  ? "here border-text font-semibold"
                  : "border-control bg-surface text-text hover:bg-raised"
              }`}
            >
              <input
                type="radio"
                name={name}
                value={v}
                checked={checked}
                onChange={() => onChange(v)}
                className="sr-only"
                aria-label={`${v}, ${LIKERT_LABELS[v]}`}
              />
              <span className="num text-section leading-none font-semibold" aria-hidden="true">
                {v}
              </span>
              <span
                className={`text-[11px] leading-tight ${checked ? "" : "text-muted"}`}
                aria-hidden="true"
              >
                {LIKERT_LABELS[v]}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
