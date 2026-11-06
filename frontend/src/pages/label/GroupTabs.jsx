import { useState } from "react";
import { errorMessage } from "../../api/client";
import { labelsApi } from "../../api/evaluation";
import { FormError, TextArea } from "../../components/forms";
import { RateBar } from "../../components/RateBar";
import { Segmented } from "../../components/Segmented";
import { useAsync } from "../../hooks/useAsync";
import { Failed } from "./shared";

const POINTS = 4;

function PointList({ title, hint, values, onChange, idPrefix }) {
  return (
    <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
      <legend className="p-0 text-body font-medium">{title}</legend>
      <p className="m-0 text-small text-muted">{hint}</p>
      {values.map((text, i) => (
        <TextArea
          key={i}
          rows={2}
          aria-label={`${title} ${i + 1}`}
          id={`${idPrefix}-${i}`}
          value={text}
          maxLength={300}
          placeholder={i === 0 ? "One point per box" : "Optional"}
          onChange={(e) => onChange(values.map((v, j) => (j === i ? e.target.value : v)))}
        />
      ))}
    </fieldset>
  );
}

/** A person reads one teacher's comments and writes the summary a good reader would write. */
export function ReferenceTab() {
  const next = useAsync(labelsApi.nextGroup);
  const blank = () => ({ strengths: Array(POINTS).fill(""), improvements: Array(POINTS).fill("") });
  const [draft, setDraft] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const group = next.data?.group;
  const progress = next.data?.progress;
  const filled = (list) => list.map((s) => s.trim()).filter(Boolean);
  const ready = filled(draft.strengths).length > 0 && filled(draft.improvements).length > 0;

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await labelsApi.saveReference(group.id, {
        strengths: filled(draft.strengths),
        improvements: filled(draft.improvements),
      });
      setDraft(blank());
      next.reload();
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the summary."));
    } finally {
      setBusy(false);
    }
  }

  if (next.error) return <Failed error={next.error} onRetry={next.reload} />;
  if (!next.data) return <span className="skeleton h-80 w-full" aria-busy="true" />;
  if (!group)
    return (
      <div className="flex flex-col gap-3">
        <RateBar value={progress.mine} total={progress.total} label="written" />
        <p className="m-0 text-body">
          {progress.total
            ? "You've written a summary for every teacher. Thank you."
            : "No teacher groups are imported yet."}
        </p>
      </div>
    );

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready && !busy) save();
      }}
    >
      <RateBar value={progress.mine} total={progress.total} label="written" />
      <p className="m-0 max-w-[72ch] text-body text-muted">
        Read all of this teacher&apos;s comments, then write what a careful reader would take away:
        what students value and what they want changed. Write it yourself, in your own words, and
        don&apos;t look at the app&apos;s summary first. It becomes the reference the generated
        summaries are scored against.
      </p>
      <div className="grid items-start gap-[var(--gap)] lg:grid-cols-2">
        <ol className="m-0 flex max-h-[560px] list-none flex-col gap-2 overflow-y-auto rounded-card border border-border bg-raised p-4">
          {group.comments.map((text, i) => (
            <li key={i} className="flex gap-3 border-b border-rule pb-2 last:border-0 last:pb-0">
              <span className="num w-5 shrink-0 text-right text-small text-faint">{i + 1}</span>
              <span className="text-body">{text}</span>
            </li>
          ))}
        </ol>
        <div className="flex flex-col gap-6">
          <PointList
            title="Strengths"
            hint="What students praise, one point per box (up to 4)."
            values={draft.strengths}
            onChange={(strengths) => setDraft({ ...draft, strengths })}
            idPrefix="strength"
          />
          <PointList
            title="Areas to improve"
            hint="What students want changed (up to 4)."
            values={draft.improvements}
            onChange={(improvements) => setDraft({ ...draft, improvements })}
            idPrefix="improvement"
          />
        </div>
      </div>
      {error && <FormError>{error}</FormError>}
      <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-4">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!ready || busy || next.refreshing}
        >
          {busy ? "Saving…" : "Save and next teacher"}
        </button>
        {!ready && (
          <span className="text-small text-muted">
            Write at least one strength and one area to improve.
          </span>
        )}
      </div>
    </form>
  );
}

/** Is each generated bullet supported by the evidence it cites? */
export function GroundingTab() {
  const next = useAsync(labelsApi.nextGrounding);
  const [checks, setChecks] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const group = next.data?.group;
  const progress = next.data?.progress;
  const done = group && group.bullets.every((_, i) => typeof checks[i] === "boolean");

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await labelsApi.saveGrounding({
        group_id: group.id,
        checks: group.bullets.map((_, index) => ({ index, supported: checks[index] })),
      });
      setChecks({});
      next.reload();
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the checks."));
    } finally {
      setBusy(false);
    }
  }

  if (next.error) return <Failed error={next.error} onRetry={next.reload} />;
  if (!next.data) return <span className="skeleton h-80 w-full" aria-busy="true" />;
  if (!group)
    return (
      <div className="flex flex-col gap-3">
        {progress.total > 0 && (
          <RateBar value={progress.mine} total={progress.total} label="checked" />
        )}
        <p className="m-0 text-body">
          {progress.total
            ? "You've checked every generated summary. Thank you."
            : "No generated summaries yet. They appear after the admin runs the evaluation once."}
        </p>
      </div>
    );

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault();
        if (done && !busy) save();
      }}
    >
      <RateBar value={progress.mine} total={progress.total} label="checked" />
      <p className="m-0 max-w-[72ch] text-body text-muted">
        For each point the app wrote about a teacher, read the student sentences it cites. Is the
        point supported by them? Judge only what the quotes say, not what you think of the teacher.
      </p>
      <ol className="m-0 flex list-none flex-col gap-[var(--gap)] p-0">
        {group.bullets.map((bullet, i) => {
          const id = `bullet-${i}`;
          return (
            <li key={i} className="flex flex-col gap-3 rounded-card border border-border p-4">
              <div className="flex flex-col gap-1">
                <span className="text-small text-muted">
                  {bullet.kind === "strength" ? "Strength" : "Area to improve"}
                </span>
                <span id={id} className="text-body font-medium">
                  {bullet.text}
                </span>
              </div>
              {bullet.evidence.length ? (
                <ul className="m-0 flex list-none flex-col gap-1.5 border-l-2 border-rule p-0 pl-3">
                  {bullet.evidence.map((quote, j) => (
                    <li key={j} className="text-body text-muted">
                      &ldquo;{quote}&rdquo;
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="m-0 text-small text-muted">This point cites no sentences.</p>
              )}
              <div className="max-w-[360px]">
                <Segmented
                  size="sm"
                  name={id}
                  labelId={id}
                  options={[
                    [true, "Supported"],
                    [false, "Not supported"],
                  ]}
                  value={checks[i] ?? null}
                  onChange={(v) => setChecks({ ...checks, [i]: v })}
                />
              </div>
            </li>
          );
        })}
      </ol>
      {error && <FormError>{error}</FormError>}
      <div className="border-t border-rule pt-4">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!done || busy || next.refreshing}
        >
          {busy ? "Saving…" : "Save and next summary"}
        </button>
      </div>
    </form>
  );
}
