/** The page's board strip: marker title, one sentence under it, actions on the right. */
export function PageHeader({ title, children, actions }) {
  return (
    <header className="board flex flex-col gap-4 px-[var(--card-pad)] py-5 md:flex-row md:items-center md:justify-between md:gap-8 md:px-6">
      <div className="flex max-w-[72ch] flex-col gap-1.5">
        <h1 className="m-0 font-marker text-marker">{title}</h1>
        {children && <div className="m-0 text-body text-on-board-muted">{children}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** A titled card section; the header line holds the title and optional controls. */
export function Panel({ title, actions, children, className = "" }) {
  return (
    <section
      className={`card ${className}`}
      aria-label={typeof title === "string" ? title : undefined}
    >
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-[var(--card-pad)] py-3">
          {title && <h2 className="m-0 text-section font-bold">{title}</h2>}
          {actions}
        </div>
      )}
      <div className="p-[var(--card-pad)]">{children}</div>
    </section>
  );
}
