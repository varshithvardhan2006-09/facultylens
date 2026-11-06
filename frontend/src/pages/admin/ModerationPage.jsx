import { useCallback, useEffect, useState } from "react";
import { FIELD_LABELS, MODERATION_CHANGED, analysisApi } from "../../api/analysis";
import { errorMessage } from "../../api/client";
import { formatDate } from "../../api/feedback";
import { FormError, Select, TextArea } from "../../components/forms";
import { PageHeader } from "../../components/PageHeader";
import { Tabs } from "../../components/Tabs";

const KIND = {
  hidden: ["pill-negative", "Hidden"],
  review: ["pill-warning", "Needs review"],
};
const DECISION = {
  approve: ["pill-positive", "Shown to faculty"],
  hide: ["pill-neutral", "Kept hidden"],
  redact: ["pill-neutral", "Edited version shown"],
};
const HARM = {
  toxicity: "toxic",
  severe_toxicity: "severely toxic",
  obscene: "obscene",
  identity_attack: "identity attack",
  insult: "insult",
  threat: "threat",
  sexual_explicit: "sexual",
};

/** The redacted answer with the sentences the model flagged marked in place. */
function Marked({ text, flagged }) {
  const parts = [];
  let at = 0;
  for (const span of [...flagged].sort((a, b) => a.start - b.start)) {
    if (span.start < at) continue;
    if (span.start > at) parts.push(<span key={`t${at}`}>{text.slice(at, span.start)}</span>);
    parts.push(
      <mark
        key={`m${span.start}`}
        className="swipe rounded-chip bg-transparent px-0.5 text-[var(--pill-negative-ink)] [--swipe:var(--pill-negative-bg)]"
        title={`Abuse score ${span.score.toFixed(2)}`}
      >
        {text.slice(span.start, span.end)}
      </mark>,
    );
    at = span.end;
  }
  if (at < text.length) parts.push(<span key={`t${at}`}>{text.slice(at)}</span>);
  return <p className="m-0 max-w-[72ch] text-body leading-6 whitespace-pre-wrap">{parts}</p>;
}

const TILTS = [-0.9, 0.7, -0.4, 1, -0.6, 0.5];

function QueueItem({ item, index, onDecided }) {
  const [leaving, setLeaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.text);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [kindCls, kindText] = KIND[item.kind] ?? KIND.review;

  async function decide(action) {
    setBusy(action);
    setError(null);
    try {
      await analysisApi.decide(item.id, action === "redact" ? { action, text: draft } : { action });
      window.dispatchEvent(new Event(MODERATION_CHANGED));
      // The note is taken off the wall: a quick lift and fade, then the list closes the gap.
      const instant = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      setLeaving(true);
      setTimeout(() => onDecided(item.id), instant ? 0 : 160);
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the decision."));
      setBusy(null);
    }
  }

  return (
    <li
      className={`flex flex-col gap-3 transition-[opacity,transform] duration-150 ease-in ${
        leaving ? "-translate-y-2 scale-[0.97] opacity-0" : ""
      }`}
    >
      <div
        className={`note settle note-lift flex flex-col gap-3 px-5 py-4 ${
          item.status === "decided" && item.decision === "approve" ? "note-praise" : "note-neutral"
        }`}
        style={{
          "--tilt": `${TILTS[index % TILTS.length]}deg`,
          "--tape-tilt": `${index % 2 ? 4 : -3}deg`,
          "--i": index % 2,
          "--dy": "28px",
          "--r0": `${index % 2 ? 5 : -5}deg`,
        }}
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-small">
          <span className={`pill ${kindCls}`}>{kindText}</span>
          <span className="num text-muted">
            Abuse score <span className="font-medium text-text">{item.score.toFixed(2)}</span>
            {item.label && ` · ${HARM[item.label] ?? item.label}`}
          </span>
          <span className="text-muted">
            {item.course}
            {item.teacher ? ` · ${item.teacher}` : " · Syllabus form"} ·{" "}
            {FIELD_LABELS[item.field] ?? item.field}
          </span>
        </div>

        {editing ? (
          <div className="flex flex-col gap-2">
            <label htmlFor={`edit-${item.id}`} className="text-small text-muted">
              The version faculty will see. Keep the student&apos;s point; remove only the abuse.
            </label>
            <TextArea
              id={`edit-${item.id}`}
              value={draft}
              maxLength={2000}
              onChange={(e) => setDraft(e.target.value)}
            />
          </div>
        ) : (
          <>
            <Marked text={item.text} flagged={item.flagged} />
            {item.status === "pending" &&
              item.flagged.length > 0 &&
              item.flagged.every((s) => s.sentiment && s.sentiment !== "negative") && (
                <p className="m-0 text-small text-muted">
                  The flagged sentence does not read as negative, so this may be a false alarm (a
                  harsh word inside a compliment or a negation). Read it before deciding.
                </p>
              )}
          </>
        )}
      </div>

      {item.status === "decided" ? (
        <div className="flex flex-wrap items-center gap-3 px-1 text-small text-muted">
          <span className={`pill ${(DECISION[item.decision] ?? DECISION.hide)[0]}`}>
            {(DECISION[item.decision] ?? DECISION.hide)[1]}
          </span>
          <span className="num">{formatDate(item.decided_at, true)}</span>
          {item.edited_text && <span className="text-text">“{item.edited_text}”</span>}
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 px-1">
          {editing ? (
            <>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={!draft.trim() || busy !== null}
                onClick={() => decide("redact")}
              >
                {busy === "redact" ? "Saving…" : "Show edited version"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={busy !== null}
                onClick={() => {
                  setEditing(false);
                  setDraft(item.text);
                }}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className={`btn ${item.kind === "hidden" ? "btn-ghost" : "btn-primary"}`}
                disabled={busy !== null}
                onClick={() => decide("approve")}
              >
                {busy === "approve" ? "Saving…" : "Show to faculty"}
              </button>
              <button
                type="button"
                className={`btn ${item.kind === "hidden" ? "btn-primary" : "btn-ghost"}`}
                disabled={busy !== null}
                onClick={() => decide("hide")}
              >
                {busy === "hide" ? "Saving…" : item.kind === "hidden" ? "Keep hidden" : "Hide"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={busy !== null}
                onClick={() => setEditing(true)}
              >
                Edit and show
              </button>
            </>
          )}
          {error && <FormError>{error}</FormError>}
        </div>
      )}
    </li>
  );
}

export function ModerationPage() {
  const [tab, setTab] = useState("pending");
  const [kind, setKind] = useState("");
  const [queue, setQueue] = useState(null);
  const [error, setError] = useState(null);

  const [version, setVersion] = useState(0);
  const load = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    // Reload whenever the tab or the filter changes, or on Retry.
    let alive = true;
    analysisApi
      .queue({ status: tab, ...(kind ? { kind } : {}) })
      .then((q) => {
        if (!alive) return;
        setQueue(q);
        setError(null);
      })
      .catch((err) => alive && setError(errorMessage(err, "Couldn't load the moderation queue.")));
    return () => {
      alive = false;
    };
  }, [tab, kind, version]);

  function decided(id) {
    // The list may be reloading by now, if the tab or filter changed meanwhile.
    setQueue((q) =>
      q
        ? {
            ...q,
            items: q.items.filter((i) => i.id !== id),
            total: q.total - 1,
            pending: q.pending - 1,
          }
        : q,
    );
  }

  const tabs = [
    ["pending", "Waiting for a decision", queue?.pending],
    ["decided", "Decided", null],
  ];

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader title="Moderation queue">
        Answers the abuse check hid (score 0.70 or more) or wants a person to read (0.40 or more).
        Faculty and HoDs never see a hidden answer. Names, phone numbers and roll numbers are
        already removed, so this is the same text faculty would see.
      </PageHeader>

      <section aria-label="Flagged answers" className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Tabs
            label="Queue"
            tabs={tabs}
            value={tab}
            onChange={(key) => {
              setTab(key);
              setQueue(null);
            }}
          />
          <div className="w-48">
            <Select
              aria-label="Show"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setQueue(null);
              }}
            >
              <option value="">All flagged</option>
              <option value="hidden">Hidden only</option>
              <option value="review">Needs review only</option>
            </Select>
          </div>
        </div>

        <div role="tabpanel">
          {error ? (
            <div className="flex flex-wrap items-center gap-3">
              <FormError>{error}</FormError>
              <button type="button" className="btn btn-ghost h-8 px-2" onClick={load}>
                Retry
              </button>
            </div>
          ) : !queue ? (
            <ul className="m-0 grid list-none gap-8 p-0 md:grid-cols-2" aria-busy="true">
              {[0, 1, 2, 3].map((i) => (
                <li key={i} className="flex flex-col gap-3">
                  <span className="skeleton h-4 w-80 max-w-full" />
                  <span className="skeleton h-5 w-full max-w-[640px]" />
                  <span className="skeleton h-9 w-72 max-w-full" />
                </li>
              ))}
            </ul>
          ) : queue.items.length === 0 ? (
            <p className="m-0 text-body text-muted">
              {tab === "pending"
                ? "Nothing waits for a decision. Answers flagged by the next analysis run appear here."
                : "No decisions yet."}
            </p>
          ) : (
            <>
              <ul className="m-0 grid list-none gap-x-8 gap-y-10 p-0 pt-2 md:grid-cols-2">
                {queue.items.map((item, i) => (
                  <QueueItem key={item.id} item={item} index={i} onDecided={decided} />
                ))}
              </ul>
              {queue.total > queue.items.length && (
                <p className="num m-0 pt-6 text-small text-muted">
                  Showing the {queue.items.length} highest scores of {queue.total}. Decide these and
                  the rest move up.
                </p>
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
