import { useState } from "react";
import { useSearchParams } from "react-router";
import { errorMessage } from "../../api/client";
import { labelsApi } from "../../api/evaluation";
import { FormError } from "../../components/forms";
import { Tabs } from "../../components/Tabs";
import { PageHeader } from "../../components/PageHeader";
import { RateBar } from "../../components/RateBar";
import { useAuth } from "../../context/auth";
import { GroundingTab, ReferenceTab } from "./GroupTabs";
import { SKIP_REASONS, aspectList, emptyJudgement } from "../../lib/labels";
import { LabelForm } from "./LabelForm";
import { ResolveTab } from "./ResolveTab";
import { useAsync } from "../../hooks/useAsync";
import { Failed } from "./shared";

function LabelTab() {
  const next = useAsync(labelsApi.next);
  const [value, setValue] = useState(emptyJudgement);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [skipping, setSkipping] = useState(false);
  // The id of the note being taken off the wall; it stays lifted until the next one arrives.
  const [leavingId, setLeavingId] = useState(null);
  const item = next.data?.item;
  const progress = next.data?.progress;

  async function save(extra) {
    setBusy(true);
    setError(null);
    try {
      await labelsApi.save({
        item_id: item.id,
        sentiment: extra?.skip_reason ? null : value.sentiment,
        aspects: extra?.skip_reason ? [] : aspectList(value.aspects),
        sarcastic: value.sarcastic,
        ...extra,
      });
      const instant = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      setLeavingId(item.id);
      await new Promise((resolve) => setTimeout(resolve, instant ? 0 : 200));
      setValue(emptyJudgement());
      setSkipping(false);
      next.reload();
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the label."));
    } finally {
      setBusy(false);
    }
  }

  if (next.error) return <Failed error={next.error} onRetry={next.reload} />;
  if (!next.data) return <span className="skeleton h-80 w-full" aria-busy="true" />;
  if (!item)
    return (
      <div className="card flex flex-col gap-3 p-[var(--card-pad)]">
        <RateBar value={progress.mine} total={progress.total} label="labelled" />
        <p className="m-0 text-body">
          {progress.total
            ? "You've labelled every comment in the set. Thank you."
            : "There's nothing to label yet. The admin imports the comments first."}
        </p>
      </div>
    );

  return (
    <form
      className="grid items-start gap-x-10 gap-y-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.sentiment && !busy && !next.refreshing) save();
      }}
    >
      <div className="flex flex-col gap-6 lg:sticky lg:top-8">
        <RateBar value={progress.mine} total={progress.total} label="labelled" />
        {/* The comment as a note; its paper follows the sentiment you pick, instantly. */}
        <figure
          key={item.id}
          className={`note settle m-0 flex flex-col gap-3 px-7 py-6 ${TONE_NOTE[value.sentiment] ?? "note-neutral"} ${leavingId === item.id ? "note-leave" : ""}`}
          style={{ "--tilt": "-0.8deg", "--dy": "36px", "--r0": "-5deg", transition: "none" }}
        >
          <blockquote className="m-0 max-w-[60ch] text-lead leading-8 whitespace-pre-line">
            {item.text}
          </blockquote>
          <figcaption className="text-small text-muted">
            {item.source === "app"
              ? "Student comment (this college)"
              : "Student comment (public dataset)"}
            {value.sentiment && ` · sorted as ${value.sentiment}`}
          </figcaption>
        </figure>
        <p className="m-0 text-small text-muted">Keys 1, 2, 3 choose the sentiment; Enter saves.</p>
      </div>
      <div className="card flex flex-col gap-6 p-[var(--card-pad)]">
        <LabelForm key={item.id} value={value} onChange={setValue} idPrefix="label" />
        {error && <FormError>{error}</FormError>}
        <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-4">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!value.sentiment || busy || next.refreshing}
          >
            {busy ? "Saving…" : "Save and next"}
          </button>
          {!skipping ? (
            <button type="button" className="btn btn-ghost" onClick={() => setSkipping(true)}>
              Skip this comment…
            </button>
          ) : (
            <div
              role="group"
              aria-label="Why skip it?"
              className="flex flex-wrap items-center gap-2"
            >
              <span className="text-small text-muted">Why skip it?</span>
              {SKIP_REASONS.map(([reason, label]) => (
                <button
                  key={reason}
                  type="button"
                  className="btn btn-secondary h-8 px-3 text-small"
                  disabled={busy || next.refreshing}
                  onClick={() => save({ skip_reason: reason })}
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                className="btn btn-ghost h-8 px-2 text-small"
                onClick={() => setSkipping(false)}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </form>
  );
}

const TONE_NOTE = {
  positive: "note-praise",
  negative: "note-criticism",
  neutral: "note-neutral",
};

const TABS = {
  annotator: [
    ["label", "Label comments"],
    ["reference", "Write reference summaries"],
    ["grounding", "Check summaries"],
  ],
  adjudicator: [
    ["resolve", "Settle disagreements"],
    ["reference", "Write reference summaries"],
    ["grounding", "Check summaries"],
  ],
};

export function LabelPage() {
  const { user } = useAuth();
  const tabs = TABS[user.annotator] ?? [];
  const [params, setParams] = useSearchParams();
  const tab = tabs.some(([key]) => key === params.get("tab")) ? params.get("tab") : tabs[0]?.[0];

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader title="Labelling">
        {user.annotator === "adjudicator"
          ? "You settle the comments the two annotators labelled differently. Your decision becomes the gold label the models are scored against."
          : "Label each comment on your own, without discussing it: the evaluation compares your labels with a second annotator's. Students' names and numbers are already removed."}
      </PageHeader>
      <Tabs
        label="Tasks"
        tabs={tabs}
        value={tab}
        onChange={(key) => setParams({ tab: key }, { replace: true })}
      />
      <div role="tabpanel" className={tab === "label" ? "" : "card p-[var(--card-pad)]"}>
        {tab === "label" && <LabelTab />}
        {tab === "resolve" && <ResolveTab />}
        {tab === "reference" && <ReferenceTab />}
        {tab === "grounding" && <GroundingTab />}
      </div>
    </div>
  );
}
