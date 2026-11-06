import { useState } from "react";
import { errorMessage } from "../../api/client";
import { ASPECTS, labelsApi } from "../../api/evaluation";
import { FormError } from "../../components/forms";
import { useAsync } from "../../hooks/useAsync";
import { Failed } from "./shared";
import { aspectList, emptyJudgement } from "../../lib/labels";
import { LabelForm } from "./LabelForm";

const ASPECT_LABEL = Object.fromEntries(ASPECTS);

function Judgement({ title, label }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-control border border-border p-3">
      <span className="text-small text-muted">{title}</span>
      <span className="text-body font-medium capitalize">{label.sentiment}</span>
      <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
        {label.aspects.length === 0 && <li className="text-small text-muted">No aspects marked</li>}
        {label.aspects.map((a) => (
          <li key={a.key} className="pill pill-neutral">
            {ASPECT_LABEL[a.key]}: {a.polarity}
          </li>
        ))}
        {label.sarcastic && <li className="pill pill-warning">Possibly sarcastic</li>}
      </ul>
    </div>
  );
}

/** The adjudicator settles each comment the two annotators labelled differently. */
export function ResolveTab() {
  const next = useAsync(labelsApi.disagreements);
  const [value, setValue] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const item = next.data?.items?.[0];

  if (next.error) return <Failed error={next.error} onRetry={next.reload} />;
  if (!next.data) return <span className="skeleton h-80 w-full" aria-busy="true" />;
  if (!item)
    return (
      <p className="m-0 text-body">
        No disagreements are waiting. New ones appear as both annotators label the same comments.
      </p>
    );

  // Start blank, so neither annotator's label anchors the decision.
  const current = value?.id === item.id ? value.judgement : emptyJudgement();

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await labelsApi.resolve({
        item_id: item.id,
        sentiment: current.sentiment,
        aspects: aspectList(current.aspects),
      });
      setValue(null);
      next.reload();
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the decision."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault();
        if (current.sentiment && !busy && !next.refreshing) save();
      }}
    >
      <p className="m-0 text-small text-muted">
        <span className="num">{next.data.total}</span> comment{next.data.total === 1 ? "" : "s"} to
        settle.
      </p>
      <figure className="m-0 rounded-card border border-border bg-raised p-5">
        <blockquote className="m-0 max-w-[72ch] text-section leading-7 whitespace-pre-line">
          {item.text}
        </blockquote>
      </figure>
      <div className="grid gap-[var(--gap)] md:grid-cols-2">
        <Judgement title="Annotator A" label={item.a} />
        <Judgement title="Annotator B" label={item.b} />
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="m-0 text-section font-medium">Your decision</h3>
      </div>
      <LabelForm
        key={item.id}
        value={current}
        onChange={(judgement) => setValue({ id: item.id, judgement })}
        idPrefix="resolve"
        showSarcasm={false}
      />
      {error && <FormError>{error}</FormError>}
      <div className="border-t border-rule pt-4">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!current.sentiment || busy || next.refreshing}
        >
          {busy ? "Saving…" : "Save decision and next"}
        </button>
      </div>
    </form>
  );
}
