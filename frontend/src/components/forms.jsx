import { useId } from "react";

/**
 * Form field: label above, control, then a hint or an error (the error replaces the hint and
 * is linked with aria-describedby). Controls are 40px tall, 1px --control border, 6px radius.
 */
export function Field({ label, hint, error, children, className = "" }) {
  const id = useId();
  const describedBy = error || hint ? `${id}-note` : undefined;
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-body font-medium">
        {label}
      </label>
      {children({ id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })}
      {(error || hint) && (
        <p
          id={describedBy}
          className={`m-0 text-small ${error ? "text-negative" : "text-muted"}`}
          role={error ? "alert" : undefined}
        >
          {error || hint}
        </p>
      )}
    </div>
  );
}

const control =
  "h-10 w-full min-w-0 rounded-control border border-control bg-surface px-3 text-body text-text " +
  "transition-colors duration-150 placeholder:text-faint hover:border-muted " +
  "focus-visible:border-focus focus-visible:outline-2 focus-visible:outline-offset-0 " +
  "aria-[invalid=true]:border-negative disabled:cursor-not-allowed disabled:opacity-60";

export function TextInput(props) {
  return <input className={control} {...props} />;
}

export function Select({ children, ...props }) {
  return (
    <select className={`${control} cursor-pointer pr-8`} {...props}>
      {children}
    </select>
  );
}

export function TextArea({ className = "", ...props }) {
  return (
    <textarea className={`${control} h-auto min-h-28 py-2 leading-5 ${className}`} {...props} />
  );
}

/** One-sentence error for a whole form or block, with the negative pill. */
export function FormError({ children }) {
  if (!children) return null;
  return (
    <p className="m-0 flex items-start gap-2 text-body" role="alert">
      <span className="pill pill-negative shrink-0">Error</span>
      <span className="pt-0.5">{children}</span>
    </p>
  );
}
