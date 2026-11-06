/**
 * Page-level tabs as a row of pills on the wall; the current one wears the highlighter.
 * `tabs` is [[key, label, count?]]. Arrow keys move between tabs.
 */
export function Tabs({ label, tabs, value, onChange, className = "" }) {
  function onKeyDown(event) {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const at = tabs.findIndex(([key]) => key === value);
    const [key] = tabs[(at + step + tabs.length) % tabs.length];
    onChange(key);
    event.currentTarget.parentElement.querySelector(`[data-tab="${key}"]`)?.focus();
  }
  return (
    <div
      role="tablist"
      aria-label={label}
      className={`flex w-fit max-w-full gap-1 overflow-x-auto rounded-button bg-active p-1 ${className}`}
    >
      {tabs.map(([key, text, count]) => {
        const active = key === value;
        return (
          <button
            key={key}
            data-tab={key}
            type="button"
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onKeyDown={onKeyDown}
            className={`h-9 shrink-0 cursor-pointer rounded-button px-4 text-body whitespace-nowrap transition-[background-color,color,transform] duration-150 active:scale-[0.97] ${
              active ? "here font-semibold" : "text-muted hover:bg-surface hover:text-text"
            }`}
            onClick={() => onChange(key)}
          >
            {text}
            {count != null && <span className="num"> {count}</span>}
          </button>
        );
      })}
    </div>
  );
}
