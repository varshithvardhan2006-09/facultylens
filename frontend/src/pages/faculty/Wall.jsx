import { Reveal } from "../../components/Reveal";
import { useEffect, useMemo, useState } from "react";
import { FIELD_LABELS } from "../../api/analysis";
import { errorMessage } from "../../api/client";
import { profilesApi } from "../../api/profiles";

/** How many notes each cluster pins up front; "Read all" opens the rest in the drawer. */
const PER_CLUSTER = { positive: 2, negative: 2, neutral: 1 };
const NOTE_CLASS = { positive: "note-praise", negative: "note-criticism", neutral: "note-neutral" };
const TONE_WORD = { positive: "Praise", negative: "Criticism", neutral: "Neutral" };

// Fixed, small tilts and scattered start points, so the wall looks hand-pinned but never jumps.
const TILTS = [-1.4, 1.1, -0.5, 1.6, -1, 0.6, -1.7, 0.9];
const STARTS = [
  [-70, 46, -9],
  [58, -34, 7],
  [-36, -56, 5],
  [80, 38, -6],
  [-90, -20, 8],
  [40, 64, -5],
];

/** The verdict a cluster heading states, from the mention counts alone. */
function verdict({ positive = 0, negative = 0 }) {
  if (positive >= 1.5 * negative && positive > 0) return "praise";
  if (negative >= 1.5 * positive && negative > 0) return "criticism";
  return "mixed";
}
const VERDICT = {
  praise: { text: "Mostly praise", stroke: "var(--edge-praise)", tone: "positive" },
  criticism: { text: "Mostly criticism", stroke: "var(--edge-criticism)", tone: "negative" },
  mixed: { text: "Mixed views", stroke: "var(--edge-neutral)", tone: "neutral" },
};

function VerdictIcon({ kind }) {
  const path =
    kind === "praise" ? "M2 9.5 6 4l4 5.5Z" : kind === "criticism" ? "M2 3.5 6 9l4-5.5Z" : null;
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
      {path ? (
        <path d={path} fill={VERDICT[kind].stroke} />
      ) : (
        <path d="M2 6h8" stroke={VERDICT.mixed.stroke} strokeWidth="2" strokeLinecap="round" />
      )}
    </svg>
  );
}

/** A marker stroke under the heading, a little uneven like a real pen. */
function MarkerLine({ stroke, index }) {
  return (
    <svg
      viewBox="0 0 160 8"
      preserveAspectRatio="none"
      className="h-2 w-28"
      aria-hidden="true"
      style={{ "--i": index }}
    >
      <path
        d="M2 5.2C30 3.4 62 6.4 96 4.4S146 3.6 158 4.8"
        pathLength="1"
        fill="none"
        stroke={stroke}
        strokeWidth="3.2"
        strokeLinecap="round"
        className="marker-line"
      />
    </svg>
  );
}

/** The sentence that mentions the aspect, or the whole answer when there is no marked part. */
function noteText(item) {
  const h = item.highlight;
  const part = h ? item.text.slice(h.start, h.end).trim() : "";
  return part.length >= 12 ? part : item.text;
}

function Note({ item, tone, order }) {
  const [dx, dy, r0] = STARTS[order % STARTS.length];
  return (
    <li
      className={`note settle note-lift ${NOTE_CLASS[tone]} flex flex-col gap-1.5 px-4 py-3`}
      style={{
        "--tilt": `${TILTS[order % TILTS.length]}deg`,
        "--tape-tilt": `${order % 2 ? 4 : -3}deg`,
        "--i": order,
        "--dx": `${dx}px`,
        "--dy": `${dy}px`,
        "--r0": `${r0}deg`,
      }}
    >
      <p className="m-0 line-clamp-5 text-body leading-[1.45]">{noteText(item)}</p>
      <span className="text-small text-muted">
        {TONE_WORD[tone]} · {FIELD_LABELS[item.field] ?? item.field}
        {item.possibly_sarcastic && " · possibly sarcastic"}
      </span>
    </li>
  );
}

function Cluster({ aspect, notes, failed, index, firstOrder, onReadAll }) {
  const kind = verdict(aspect.polarity);
  const v = VERDICT[kind];
  const headingId = `cluster-${aspect.key}`;
  const { positive = 0, negative = 0, neutral = 0 } = aspect.polarity;
  const allIds = ["positive", "negative", "neutral"].flatMap((t) => aspect.note_ids?.[t] ?? []);
  return (
    <Reveal
      as="section"
      ready={notes !== null}
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-4"
    >
      <header className="flex flex-col gap-1">
        <h3 id={headingId} className="m-0 font-marker text-[1.375rem] leading-7">
          {aspect.label}
        </h3>
        <MarkerLine stroke={v.stroke} index={index} />
        <p className="num m-0 mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-small text-muted">
          <span className="inline-flex items-center gap-1 font-semibold text-text">
            <VerdictIcon kind={kind} />
            {v.text}
          </span>
          <span aria-hidden="true">·</span>
          <span title={`${positive} praise, ${negative} criticism, ${neutral} neutral`}>
            {aspect.mentions} note{aspect.mentions === 1 ? "" : "s"}
          </span>
          {aspect.likert_mean != null && (
            <>
              <span aria-hidden="true">·</span>
              <span>rated {aspect.likert_mean.toFixed(1)} / 5</span>
            </>
          )}
        </p>
      </header>
      {notes === null ? (
        <div className="flex flex-col gap-3" aria-hidden="true">
          <span className="skeleton h-20 w-full" />
          <span className="skeleton h-16 w-full" />
        </div>
      ) : notes.length === 0 ? (
        <p className="m-0 text-small text-muted">
          {failed ? "Couldn't load these notes." : "These notes are no longer shown."}
        </p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-4 p-0 pt-1">
          {notes.map(({ item, tone }, i) => (
            <Note key={item.id} item={item} tone={tone} order={firstOrder + i} />
          ))}
        </ul>
      )}
      {allIds.length > (notes?.length ?? 0) && (
        <button
          type="button"
          className="w-fit cursor-pointer text-small font-semibold text-text underline underline-offset-3"
          onClick={() => onReadAll(aspect, allIds, v.tone)}
        >
          Read {allIds.length} notes in full
        </button>
      )}
    </Reveal>
  );
}

/**
 * The affinity wall: every teaching aspect students wrote about, as a cluster of their own
 * (redacted) sentences pinned under a marker heading that states the verdict.
 */
export function Wall({ facultyId, insights, onEvidence }) {
  const aspects = useMemo(
    () =>
      Object.entries(insights.aspects ?? {})
        .map(([key, a]) => ({ key, ...a }))
        .sort((a, b) => b.mentions - a.mentions),
    [insights],
  );
  const written = aspects.filter((a) => a.mentions > 0);
  const silent = aspects.filter((a) => a.mentions === 0);

  // One request for every pinned note; a sentence goes on the first wall it appears on.
  const plan = useMemo(() => {
    const used = new Set();
    return written.map((a) => {
      const picks = [];
      for (const tone of ["positive", "negative", "neutral"]) {
        for (const id of (a.note_ids?.[tone] ?? []).slice(0, PER_CLUSTER[tone])) {
          if (used.has(id)) continue;
          used.add(id);
          picks.push({ id, tone });
        }
      }
      return picks;
    });
  }, [written]);
  const ids = plan.flat().map((p) => p.id);
  const key = ids.join(",");
  const [state, setState] = useState({ key: null, items: null, error: null });
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!key) return undefined;
    let alive = true;
    profilesApi
      .evidence(facultyId, key.split(","))
      .then((items) => alive && setState({ key, items, error: null }))
      .catch(
        (err) =>
          alive &&
          setState({ key, items: null, error: errorMessage(err, "Couldn't load the notes.") }),
      );
    return () => {
      alive = false;
    };
  }, [facultyId, key, retry]);

  const byId = state.key === key && state.items ? new Map(state.items.map((i) => [i.id, i])) : null;
  const clusters = written.map((a, i) => ({
    aspect: a,
    notes: byId
      ? plan[i].filter((p) => byId.has(p.id)).map((p) => ({ item: byId.get(p.id), tone: p.tone }))
      : state.error
        ? []
        : null,
  }));

  return (
    <section aria-labelledby="wall-h" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 id="wall-h" className="m-0 font-marker text-marker">
          What students wrote, by aspect
        </h2>
        <p className="m-0 text-small text-muted">
          Their own sentences, after moderation; names and numbers replaced.
        </p>
      </div>
      {state.error && (
        <p className="m-0 flex flex-wrap items-center gap-3 text-body" role="alert">
          {state.error}
          <button
            type="button"
            className="btn btn-secondary h-8"
            onClick={() => setRetry((n) => n + 1)}
          >
            Try again
          </button>
        </p>
      )}
      {written.length === 0 ? (
        <p className="m-0 text-body text-muted">
          No comment mentioned a teaching aspect clearly enough to sort it.
        </p>
      ) : (
        <div className="grid gap-x-8 gap-y-10 sm:grid-cols-2 xl:grid-cols-3">
          {clusters.map(({ aspect, notes }, i) => (
            <Cluster
              key={aspect.key}
              aspect={aspect}
              notes={notes}
              failed={Boolean(state.error)}
              index={i % 3}
              firstOrder={(i % 3) * 2}
              onReadAll={(a, allIds, tone) =>
                onEvidence({
                  ids: allIds,
                  tone,
                  toneFromItem: true,
                  kicker: `Teaching aspect · ${allIds.length} of ${a.mentions} mentions shown`,
                  title: a.label,
                })
              }
            />
          ))}
        </div>
      )}
      {silent.length > 0 && (
        <p className="m-0 text-small text-muted">
          Nothing written about {silent.map((a) => a.label.toLowerCase()).join(", ")}.
        </p>
      )}
    </section>
  );
}
