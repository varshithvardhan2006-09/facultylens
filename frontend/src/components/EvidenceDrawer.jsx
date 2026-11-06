import { useEffect, useRef, useState } from "react";
import { FIELD_LABELS } from "../api/analysis";
import { errorMessage } from "../api/client";
import { profilesApi } from "../api/profiles";
import { FormError } from "./forms";

const TINT = {
  positive: "color-mix(in srgb, var(--sent-positive) 22%, transparent)",
  negative: "color-mix(in srgb, var(--sent-negative) 22%, transparent)",
  neutral: "color-mix(in srgb, var(--sent-neutral) 26%, transparent)",
};

/** One redacted answer with its supporting sentence marked in place. */
function Answer({ item, tone, index }) {
  const { text, highlight } = item;
  const parts = highlight
    ? [
        text.slice(0, highlight.start),
        <mark
          key="m"
          className="swipe rounded-chip bg-transparent px-0.5 text-text"
          style={{
            "--swipe": TINT[tone] ?? TINT.neutral,
            "--swipe-delay": `${200 + Math.min(index, 8) * 70}ms`,
          }}
        >
          {text.slice(highlight.start, highlight.end)}
        </mark>,
        text.slice(highlight.end),
      ]
    : [text];
  return (
    <li className="flex flex-col gap-1.5 border-t border-rule py-4 first:border-t-0 first:pt-0">
      <span className="text-small text-muted">
        {FIELD_LABELS[item.field] ?? item.field}
        {item.possibly_sarcastic && " · possibly sarcastic"}
        {item.edited_by_admin && " · shortened by the moderator"}
      </span>
      <p className="m-0 text-body leading-6 whitespace-pre-wrap">{parts}</p>
    </li>
  );
}

/**
 * Right-side sheet listing the redacted answers behind a strength, an improvement or the
 * possibly-sarcastic count, or an Action Taken row (with request.load). A native modal <dialog>: Esc closes it and focus returns to the
 * button that opened it.
 */
export function EvidenceDrawer({ facultyId, request, onClose }) {
  const ref = useRef(null);
  const [state, setState] = useState({ key: null, items: null, error: null });
  const key = request ? request.ids.join(",") : null;

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (request && !dialog.open) dialog.showModal();
    if (!request && dialog.open) dialog.close();
  }, [request]);

  const load = request?.load;
  useEffect(() => {
    if (!key) return undefined;
    let alive = true;
    // A request may bring its own loader (an Action Taken row); otherwise ids are a teacher's.
    (load ? load() : profilesApi.evidence(facultyId, key.split(",")))
      .then((items) => alive && setState({ key, items, error: null }))
      .catch(
        (err) =>
          alive &&
          setState({ key, items: null, error: errorMessage(err, "Couldn't load the evidence.") }),
      );
    return () => {
      alive = false;
    };
  }, [facultyId, key, load]);

  const loaded = state.key === key;
  return (
    // A click on the backdrop closes it too; keyboard users have Esc and the Close button.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <dialog
      ref={ref}
      aria-labelledby="evidence-title"
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="drawer m-0 ml-auto h-dvh max-h-none w-full max-w-[520px] border-0 border-l border-border bg-surface p-0 text-text shadow-xl backdrop:bg-black/30"
    >
      {request && (
        <div className="flex h-full flex-col">
          <div className="flex items-start justify-between gap-4 border-b border-rule px-[var(--card-pad)] py-4">
            <div className="flex min-w-0 flex-col gap-1">
              <h2 id="evidence-title" className="m-0 font-marker text-[1.375rem] leading-7">
                {request.title}
              </h2>
              <span className="text-small text-muted">{request.kicker}</span>
            </div>
            <button
              type="button"
              className="btn btn-ghost h-9 w-9 shrink-0 px-0"
              aria-label="Close"
              onClick={onClose}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  d="M3.5 3.5l9 9M12.5 3.5l-9 9"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-[var(--card-pad)] py-4">
            <p className="m-0 mb-4 text-small text-muted">
              Students&apos; own words, after moderation. Names, phone numbers and roll numbers are
              replaced with placeholders. The marked sentence is the one that supports this point.
            </p>
            {!loaded ? (
              <div className="flex flex-col gap-4" aria-busy="true">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="skeleton h-16 w-full" />
                ))}
              </div>
            ) : state.error ? (
              <FormError>{state.error}</FormError>
            ) : state.items.length === 0 ? (
              <p className="m-0 text-body text-muted">
                These answers are no longer shown (a moderator hid them, or the data changed).
              </p>
            ) : (
              <ul className="m-0 list-none p-0">
                {state.items.map((item, i) => (
                  <Answer
                    index={i}
                    key={item.id}
                    item={item}
                    tone={request.toneFromItem ? item.sentiment : request.tone}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </dialog>
  );
}
