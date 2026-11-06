import { useEffect, useRef } from "react";
import { ASPECTS } from "../../api/evaluation";
import { Segmented } from "../../components/Segmented";

const SENTIMENTS = [
  ["negative", "Negative", "1"],
  ["neutral", "Neutral", "2"],
  ["positive", "Positive", "3"],
];
const POLARITY = [
  [null, "Not mentioned"],
  ["negative", "Negative"],
  ["neutral", "Neutral"],
  ["positive", "Positive"],
];
function typing(target) {
  return target.closest?.("textarea, select, input:not([type=radio]):not([type=checkbox])");
}

/**
 * One comment's label: overall sentiment (keys 1-3), each teaching aspect it mentions with its
 * polarity, and a "possibly sarcastic" flag. Shared by labelling and by adjudication.
 */
export function LabelForm({ value, onChange, idPrefix, showSarcasm = true }) {
  const set = (patch) => onChange({ ...value, ...patch });
  const root = useRef(null);

  useEffect(() => {
    function onKey(event) {
      if (event.ctrlKey || event.metaKey || event.altKey || typing(event.target)) return;
      if (event.key === "Enter" && event.target.closest?.("button, a, summary") == null) {
        event.preventDefault();
        root.current?.closest("form")?.requestSubmit();
        return;
      }
      const choice = SENTIMENTS.find(([, , key]) => key === event.key);
      if (choice) {
        event.preventDefault();
        onChange({ ...value, sentiment: choice[0] });
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [value, onChange]);

  return (
    <div ref={root} className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <span id={`${idPrefix}-sentiment`} className="text-body font-medium">
          Overall, how does the comment feel about the teacher?
        </span>
        <div className="max-w-[440px]">
          <Segmented
            name={`${idPrefix}-sentiment`}
            labelId={`${idPrefix}-sentiment`}
            options={SENTIMENTS}
            value={value.sentiment}
            onChange={(sentiment) => set({ sentiment })}
          />
        </div>
      </div>

      <fieldset className="m-0 flex min-w-0 flex-col gap-1 border-0 p-0">
        <legend className="mb-1 p-0 text-body font-medium">
          Which teaching aspects does it mention, and how?
        </legend>
        <p className="m-0 mb-2 text-small text-muted">
          Mark an aspect only if the comment talks about it. Leave the rest as not mentioned.
        </p>
        <div className="flex flex-col">
          {ASPECTS.map(([key, label]) => {
            const id = `${idPrefix}-aspect-${key}`;
            return (
              <div
                key={key}
                className="grid gap-1.5 border-t border-rule py-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] md:items-center md:gap-6"
              >
                <span id={id} className="text-body">
                  {label}
                </span>
                <Segmented
                  size="sm"
                  name={id}
                  labelId={id}
                  options={POLARITY}
                  quiet={null}
                  value={value.aspects[key] ?? null}
                  onChange={(polarity) => {
                    const aspects = { ...value.aspects };
                    if (polarity) aspects[key] = polarity;
                    else delete aspects[key];
                    set({ aspects });
                  }}
                />
              </div>
            );
          })}
        </div>
      </fieldset>

      {showSarcasm && (
        <label className="flex w-fit cursor-pointer items-center gap-2 text-body">
          <input
            type="checkbox"
            className="size-4 accent-[var(--primary)]"
            checked={value.sarcastic}
            onChange={(e) => set({ sarcastic: e.target.checked })}
          />
          Possibly sarcastic (it says the opposite of what it means)
        </label>
      )}
    </div>
  );
}
