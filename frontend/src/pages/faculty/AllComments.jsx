import { useEffect, useState } from "react";
import { FIELD_LABELS } from "../../api/analysis";
import { errorMessage } from "../../api/client";
import { feedbackApi } from "../../api/feedback";

const FIELD_ORDER = ["liked", "improve", "other"];
const SENTIMENT_WORD = { positive: "Positive", negative: "Negative", neutral: "Neutral" };
const FIRST_SHOWN = 5;

/** Identical answers become one line with a count. */
function mergeRepeats(comments) {
  const merged = new Map();
  for (const comment of comments) {
    const key = JSON.stringify([comment.text, comment.sentiment, comment.possibly_sarcastic]);
    const seen = merged.get(key);
    if (seen) seen.count += 1;
    else merged.set(key, { ...comment, count: 1 });
  }
  return [...merged.values()];
}

/** One kind of answer. Sorted by text, so one student's answers can't be lined up across groups. */
function CommentGroup({ field, comments }) {
  const [expanded, setExpanded] = useState(false);
  const sorted = mergeRepeats(comments).sort((a, b) => a.text.localeCompare(b.text));
  const shown = expanded ? sorted : sorted.slice(0, FIRST_SHOWN);
  const heading = `all-comments-${field}`;

  return (
    <section aria-labelledby={heading} className="card flex flex-col gap-3 p-[var(--card-pad)]">
      <h3 id={heading} className="m-0 text-section font-medium">
        {FIELD_LABELS[field] ?? field} <span className="num text-muted">({comments.length})</span>
      </h3>
      <ul className="m-0 flex list-none flex-col p-0">
        {shown.map((comment) => (
          <li
            key={comment.id}
            className="flex flex-col gap-1 border-t border-rule py-3 first:border-t-0 first:pt-0 last:pb-0"
          >
            <p className="m-0 text-body leading-[1.45] [overflow-wrap:anywhere]">{comment.text}</p>
            <span className="text-small text-muted">
              {SENTIMENT_WORD[comment.sentiment] ?? comment.sentiment}
              {comment.possibly_sarcastic && " · possibly sarcastic"}
              {comment.count > 1 && ` · ${comment.count} students wrote this`}
            </span>
          </li>
        ))}
      </ul>
      {sorted.length > FIRST_SHOWN && (
        <button
          type="button"
          className="btn btn-secondary h-8 w-fit"
          aria-expanded={expanded}
          onClick={() => setExpanded((open) => !open)}
        >
          {expanded ? "Show fewer" : "Show all"}
        </button>
      )}
    </section>
  );
}

/**
 * Every answer that passed moderation, including those about no teaching aspect, which the
 * wall can't place. The API already applies the role checks and the minimum-response rule.
 */
export function AllComments({ facultyId, cycleId, courseId }) {
  const key = `${facultyId}:${cycleId}:${courseId}`;
  const [state, setState] = useState({ key: null, comments: null, error: null });
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let alive = true;
    feedbackApi
      .facultyFeedback(facultyId, { cycle: cycleId, course: courseId })
      .then((forms) => {
        if (alive) setState({ key, comments: forms[0]?.comments ?? [], error: null });
      })
      .catch((err) => {
        if (alive) {
          setState({
            key,
            comments: null,
            error: errorMessage(err, "Couldn't load the comments."),
          });
        }
      });
    return () => {
      alive = false;
    };
  }, [key, facultyId, cycleId, courseId, retry]);

  const current = state.key === key ? state : { comments: null, error: null };
  const groups = FIELD_ORDER.map((field) => ({
    field,
    comments: (current.comments ?? []).filter((comment) => comment.field === field),
  })).filter((group) => group.comments.length > 0);

  return (
    <section aria-labelledby="all-comments-h" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 id="all-comments-h" className="m-0 font-marker text-marker">
          All comments
        </h2>
        <p className="m-0 text-small text-muted">
          Every answer that passed moderation, including those about no teaching aspect.
        </p>
      </div>
      {current.error && (
        <p className="m-0 flex flex-wrap items-center gap-3 text-body" role="alert">
          {current.error}
          <button
            type="button"
            className="btn btn-secondary h-8"
            onClick={() => setRetry((n) => n + 1)}
          >
            Try again
          </button>
        </p>
      )}
      {!current.error && current.comments === null && (
        <div aria-busy="true" className="flex flex-col gap-3">
          <span className="skeleton h-24 w-full" />
          <span className="skeleton h-24 w-full" />
        </div>
      )}
      {current.comments !== null && groups.length === 0 && (
        <p className="m-0 text-body text-muted">No written comments to show for this course.</p>
      )}
      {groups.map((group) => (
        <CommentGroup key={`${key}:${group.field}`} field={group.field} comments={group.comments} />
      ))}
    </section>
  );
}
