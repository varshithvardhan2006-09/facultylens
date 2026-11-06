import { useId, useState } from "react";

/** Tags as removable chips; Enter or comma adds, Backspace on an empty field removes the last. */
export function TagInput({ label, hint, value, onChange, max = 30, placeholder }) {
  const id = useId();
  const [draft, setDraft] = useState("");

  function add(text) {
    const tag = text.replace(/\s+/g, " ").trim().slice(0, 60);
    if (!tag || value.some((t) => t.toLowerCase() === tag.toLowerCase()) || value.length >= max) {
      setDraft("");
      return;
    }
    onChange([...value, tag]);
    setDraft("");
  }

  function onKeyDown(e) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-body font-medium">
        {label}
      </label>
      <div className="flex min-h-10 flex-wrap items-center gap-1.5 rounded-control border border-control bg-surface px-2 py-1.5 focus-within:border-focus focus-within:outline-2 focus-within:outline-focus">
        <ul
          className="m-0 flex list-none flex-wrap gap-1.5 p-0"
          aria-label={`${label}: ${value.length}`}
        >
          {value.map((tag) => (
            <li key={tag} className="pill pill-neutral h-7 gap-1 pr-1 text-body">
              {tag}
              <button
                type="button"
                className="grid size-5 cursor-pointer place-items-center rounded-[3px] text-muted hover:bg-control hover:text-text"
                aria-label={`Remove ${tag}`}
                onClick={() => onChange(value.filter((t) => t !== tag))}
              >
                <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                  <path
                    d="M2 2l6 6M8 2 2 8"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </li>
          ))}
        </ul>
        <input
          id={id}
          className="h-7 min-w-40 flex-1 border-0 bg-transparent px-1 text-body text-text outline-none placeholder:text-faint"
          value={draft}
          placeholder={value.length ? "" : placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => draft && add(draft)}
          aria-describedby={hint ? `${id}-hint` : undefined}
        />
      </div>
      {hint && (
        <p id={`${id}-hint`} className="m-0 text-small text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
