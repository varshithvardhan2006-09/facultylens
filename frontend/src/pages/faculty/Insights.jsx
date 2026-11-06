import { CountUp } from "../../components/CountUp";
import { ArrowLeftIcon, ArrowRightIcon } from "../../components/icons";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EMOTIONS, pct, signed } from "../../api/insights";
import { engineLabel } from "../../api/profiles";

const SENT = ["negative", "neutral", "positive"];
const SENT_LABEL = { negative: "Negative", neutral: "Neutral", positive: "Positive" };
const SENT_VAR = {
  negative: "var(--sent-negative)",
  neutral: "var(--sent-neutral)",
  positive: "var(--sent-positive)",
};
const AGREEMENT = {
  agrees: ["pill-positive", "Agree"],
  mixed: ["pill-neutral", "Mixed"],
  disagrees: ["pill-warning", "Disagree"],
  too_few: ["pill-neutral", "Too few"],
};

export function Legend() {
  return (
    <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-small text-muted">
      {SENT.map((s) => (
        <li key={s} className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-[2px]"
            style={{ background: SENT_VAR[s] }}
          />
          {SENT_LABEL[s]}
        </li>
      ))}
    </ul>
  );
}

// On the deep board the split bar uses the note papers, which stay apart from the board green.
const BOARD_FILL = {
  negative: "var(--note-criticism)",
  neutral: "color-mix(in srgb, var(--on-board-muted) 55%, transparent)",
  positive: "var(--note-praise)",
};

/**
 * The board strip at the top of the feedback: net sentiment as the one headline figure, the
 * split as a labelled 100% bar, the response rate and the best-rated aspect.
 */
export function Overall({ insights, responses, eligible }) {
  const weights = insights.sentiment ?? {};
  const total = SENT.reduce((n, s) => n + (weights[s] ?? 0), 0);
  const net = insights.net_score;
  const rated = Object.values(insights.aspects ?? {}).filter((a) => a.likert_mean != null);
  const best = rated.length
    ? rated.reduce((a, b) => (b.likert_mean > a.likert_mean ? b : a))
    : null;
  return (
    <section
      aria-labelledby="overall-h"
      className="board grid gap-x-8 gap-y-5 p-[var(--card-pad)] md:grid-cols-[auto_minmax(0,1fr)] md:p-6"
    >
      <div className="flex flex-col gap-0.5">
        <h2 id="overall-h" className="m-0 text-small font-semibold text-on-board-muted">
          Net sentiment
        </h2>
        <span className="num font-marker text-[2.75rem] leading-none">
          {net == null ? "–" : <CountUp value={net} format={signed} />}
        </span>
        <span className="mt-1 max-w-[30ch] text-small text-on-board-muted">
          Positive share minus negative, from −1 to +1. Possibly sarcastic answers count half.
        </span>
      </div>
      <div className="flex min-w-0 flex-col justify-between gap-4">
        {total > 0 && (
          <div className="flex flex-col gap-2">
            <div
              className="grow-x flex h-3.5 w-full gap-[3px] overflow-hidden rounded-full"
              role="img"
              aria-label={SENT.map(
                (s) => `${SENT_LABEL[s]} ${pct((weights[s] ?? 0) / total)}`,
              ).join(", ")}
            >
              {SENT.map(
                (s) =>
                  (weights[s] ?? 0) > 0 && (
                    <span
                      key={s}
                      title={`${SENT_LABEL[s]}: ${pct(weights[s] / total)}`}
                      style={{ width: `${(100 * weights[s]) / total}%`, background: BOARD_FILL[s] }}
                    />
                  ),
              )}
            </div>
            <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 text-small">
              {SENT.map((s) => (
                <span key={s} className="num">
                  <span className="text-on-board-muted">{SENT_LABEL[s]}</span>{" "}
                  <span className="font-semibold">{pct((weights[s] ?? 0) / total)}</span>
                </span>
              ))}
            </div>
          </div>
        )}
        <dl className="m-0 grid grid-cols-2 gap-4 border-t border-board-rule pt-4">
          {eligible > 0 && (
            <div className="flex flex-col gap-0.5">
              <dt className="text-small text-on-board-muted">Responded</dt>
              <dd className="num m-0 text-lead font-semibold">
                <CountUp value={responses} />{" "}
                <span className="text-body font-normal text-on-board-muted">of {eligible}</span>
              </dd>
            </div>
          )}
          {best && (
            <div className="flex min-w-0 flex-col gap-0.5">
              <dt className="text-small text-on-board-muted">Best rated</dt>
              <dd className="num m-0 truncate text-lead font-semibold" title={best.label}>
                <CountUp value={best.likert_mean} format={(v) => v.toFixed(1)} />{" "}
                <span className="text-body font-normal text-on-board-muted">{best.label}</span>
              </dd>
            </div>
          )}
        </dl>
      </div>
    </section>
  );
}

/** One aspect's comments as a diverging bar: negative left of the centre line, positive right. */
function DivergingBar({ polarity, scale, label }) {
  const { negative = 0, neutral = 0, positive = 0 } = polarity;
  // Each half spans `scale` mentions; neutral is split evenly across the centre line.
  const w = (n) => `${(100 * n) / scale}%`;
  const describe = `${label}: ${negative} negative, ${neutral} neutral, ${positive} positive mentions`;
  return (
    <div
      className="relative flex h-4 w-full items-center"
      role="img"
      aria-label={describe}
      title={describe}
    >
      <span
        className="absolute top-[-3px] bottom-[-3px] left-1/2 w-px bg-control"
        aria-hidden="true"
      />
      <div className="grow-x grow-x-from-right flex h-3 w-1/2 justify-end gap-[2px] pr-px">
        {negative > 0 && (
          <span
            className="rounded-l-[3px]"
            style={{ width: w(negative), background: SENT_VAR.negative }}
          />
        )}
        {neutral > 0 && <span style={{ width: w(neutral / 2), background: SENT_VAR.neutral }} />}
      </div>
      <div className="grow-x flex h-3 w-1/2 gap-[2px] pl-px">
        {neutral > 0 && <span style={{ width: w(neutral / 2), background: SENT_VAR.neutral }} />}
        {positive > 0 && (
          <span
            className="rounded-r-[3px]"
            style={{ width: w(positive), background: SENT_VAR.positive }}
          />
        )}
      </div>
    </div>
  );
}

/** Every aspect in one table: what students wrote, how they rated it, and whether the two agree. */
export function Aspects({ insights, showAgreement = true, title = "Teaching aspects" }) {
  const rows = Object.entries(insights.aspects ?? {});
  // Half-width of the bar = the largest one-sided total (neutral is split across the centre).
  const scale = Math.max(
    1,
    ...rows.map(([, a]) =>
      Math.max(
        a.polarity.negative + a.polarity.neutral / 2,
        a.polarity.positive + a.polarity.neutral / 2,
      ),
    ),
  );
  return (
    <section aria-labelledby="aspects-h" className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-[var(--card-pad)] py-3">
        <h2 id="aspects-h" className="m-0 text-section font-medium">
          {title}
        </h2>
        <Legend />
      </div>
      <table className="w-full border-collapse text-body">
        <thead>
          <tr className="text-left text-small text-muted">
            <th scope="col" className="h-10 px-[var(--card-pad)] font-medium max-md:px-4">
              Aspect
            </th>
            <th scope="col" className="h-10 px-3 font-medium max-md:hidden">
              <span className="sr-only">Comments: </span>
              <span aria-hidden="true" className="flex justify-between">
                <span>
                  <ArrowLeftIcon /> criticism
                </span>
                <span>
                  praise <ArrowRightIcon />
                </span>
              </span>
            </th>
            <th
              scope="col"
              className={`h-10 text-right font-medium ${showAgreement ? "px-3" : "pr-[var(--card-pad)] pl-3 max-md:pr-4"}`}
            >
              Rating
            </th>
            {showAgreement && (
              <th scope="col" className="h-10 px-[var(--card-pad)] font-medium max-md:px-4">
                <abbr
                  title="Do the 1–5 ratings and the tone of the comments point the same way? (Spearman correlation)"
                  className="no-underline"
                >
                  Agreement
                </abbr>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, a]) => {
            const [cls, text] = AGREEMENT[a.agreement?.label] ?? AGREEMENT.too_few;
            return (
              <tr key={key} className="border-t border-rule">
                <td className="py-2.5 pl-[var(--card-pad)] max-md:pl-4">
                  <span className="block">{a.label}</span>
                  <span className="num block text-small text-muted">
                    {a.mentions} mention{a.mentions === 1 ? "" : "s"}
                  </span>
                  <span className="mt-1.5 block md:hidden">
                    <DivergingBar polarity={a.polarity} scale={scale} label={a.label} />
                  </span>
                </td>
                <td className="w-[40%] px-3 max-md:hidden">
                  {a.mentions > 0 ? (
                    <DivergingBar polarity={a.polarity} scale={scale} label={a.label} />
                  ) : (
                    <span className="text-small text-faint">No comments on this</span>
                  )}
                </td>
                <td
                  className={`num text-right align-middle whitespace-nowrap ${showAgreement ? "px-3" : "pr-[var(--card-pad)] pl-3 max-md:pr-4"}`}
                >
                  {a.likert_mean == null ? (
                    <span className="text-faint">–</span>
                  ) : (
                    <>
                      <span className="font-medium">{a.likert_mean.toFixed(1)}</span>
                      <span className="text-small text-muted"> / 5</span>
                    </>
                  )}
                </td>
                {showAgreement && (
                  <td className="pr-[var(--card-pad)] pl-3 max-md:pr-4">
                    <span
                      className={`pill ${cls}`}
                      title={
                        a.agreement.rho == null
                          ? `Needs at least 5 students who both rated and commented (have ${a.agreement.n}).`
                          : `Spearman ρ = ${a.agreement.rho.toFixed(2)} over ${a.agreement.n} students.`
                      }
                    >
                      {text}
                    </span>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function SummaryIcon({ kind }) {
  const up = kind === "strength";
  return (
    <svg width="14" height="14" viewBox="0 0 12 12" aria-hidden="true">
      <path
        d={up ? "M2 9.5 6 4l4 5.5Z" : "M2 3.5 6 9l4-5.5Z"}
        fill={up ? "var(--edge-praise)" : "var(--edge-criticism)"}
      />
    </svg>
  );
}

function Item({ item, kind, onEvidence }) {
  return (
    <li className="flex flex-col gap-1.5 border-t border-rule py-3 first:border-t-0 first:pt-0">
      <span className="pill pill-neutral w-fit">{item.aspectLabel}</span>
      <p className="m-0 text-body">{item.text}</p>
      {kind === "improvement" && item.suggested_action && (
        <p className="m-0 rounded-note bg-raised px-3 py-2 text-small text-muted">
          <span className="font-semibold text-text">Next step:</span> {item.suggested_action}
        </p>
      )}
      <button
        type="button"
        className="w-fit cursor-pointer text-small font-medium text-text underline underline-offset-3"
        onClick={(e) => onEvidence(e, item, kind)}
      >
        Show the evidence ({item.evidence_ids.length})
      </button>
    </li>
  );
}

/** Strengths and improvements, each opening the evidence drawer. */
export function Summary({ summary, aspects, onEvidence }) {
  if (!summary) {
    return (
      <section className="card p-[var(--card-pad)]">
        <h2 className="m-0 text-section font-medium">Strengths and areas to improve</h2>
        <p className="m-0 mt-2 text-body text-muted">
          The written summary is prepared after the next analysis run.
        </p>
      </section>
    );
  }
  const withLabels = (items) =>
    items.map((i) => ({ ...i, aspectLabel: aspects?.[i.aspect]?.label ?? i.aspect }));
  const columns = [
    ["Strengths", withLabels(summary.strengths), "strength", "No aspect stands out yet."],
    [
      "Areas to improve",
      withLabels(summary.improvements),
      "improvement",
      "No aspect drew repeated criticism.",
    ],
  ];
  return (
    <section aria-labelledby="summary-h" className="flex flex-col gap-[var(--gap)]">
      <div className="flex flex-col gap-1">
        <h2 id="summary-h" className="m-0 font-marker text-marker">
          What students said
        </h2>
        <p className="m-0 max-w-[72ch] text-lead">{summary.overall_summary}</p>
      </div>
      <div className="grid items-start gap-[var(--gap)] md:grid-cols-2">
        {columns.map(([title, items, kind, empty]) => (
          <section key={title} aria-label={title} className="card p-[var(--card-pad)]">
            <h3 className="m-0 mb-3 flex items-center gap-2 text-section font-bold">
              <SummaryIcon kind={kind} />
              {title}
            </h3>
            {items.length === 0 ? (
              <p className="m-0 text-body text-muted">{empty}</p>
            ) : (
              <ul className="m-0 list-none p-0">
                {items.map((item) => (
                  <Item key={item.text} item={item} kind={kind} onEvidence={onEvidence} />
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
      {summary.digest && (
        <div className="rounded-card bg-raised px-[var(--card-pad)] py-3">
          <p className="m-0 text-small text-muted">Automatic digest of the comments</p>
          <p className="m-0 mt-1 text-body">{summary.digest}</p>
        </div>
      )}
      <p className="m-0 text-small text-muted">{engineLabel(summary.engine)}.</p>
    </section>
  );
}

function EmotionTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-control border border-border bg-surface px-2.5 py-1.5 text-small shadow-md">
      <span className="font-medium">{row.label}</span>{" "}
      <span className="num text-muted">{pct(row.share)} of answers</span>
    </div>
  );
}

/** Emotion mix (one hue, it is a magnitude), the sarcasm count, and what moderation hid. */
export function Footer({ insights, sarcasticCount, onSarcasm }) {
  const rows = Object.entries(insights.emotion_mix ?? {})
    .map(([k, share]) => ({ key: k, label: EMOTIONS[k] ?? k, share }))
    .sort((a, b) => b.share - a.share);
  return (
    <div className="grid gap-[var(--gap)] md:grid-cols-[minmax(0,1fr)_280px]">
      <section aria-labelledby="emotion-h" className="card p-[var(--card-pad)]">
        <h2 id="emotion-h" className="m-0 text-section font-medium">
          Emotion in the comments
        </h2>
        <p className="m-0 mt-1 text-small text-muted">Average share across analysed answers.</p>
        {rows.length > 0 && (
          <div className="mt-3 h-[208px]" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                accessibilityLayer={false}
                data={rows}
                layout="vertical"
                margin={{ top: 0, right: 40, bottom: 0, left: 0 }}
                barCategoryGap={6}
              >
                <XAxis type="number" hide domain={[0, Math.max(...rows.map((r) => r.share))]} />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={72}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "var(--muted)", fontSize: 12 }}
                />
                <Tooltip
                  content={<EmotionTooltip />}
                  cursor={{ fill: "var(--raised)" }}
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="share"
                  radius={[0, 4, 4, 0]}
                  isAnimationActive={false}
                  label={{
                    position: "right",
                    fill: "var(--text)",
                    fontSize: 12,
                    formatter: (v) => pct(v),
                  }}
                >
                  {rows.map((r, i) => (
                    <Cell key={r.key} fill={i === 0 ? "var(--chart-main)" : "var(--chart-muted)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="sr-only">
          <table>
            <caption>Emotion mix</caption>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <th scope="row">{r.label}</th>
                  <td>{pct(r.share)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section aria-label="Caveats" className="card flex flex-col gap-3 p-[var(--card-pad)]">
        <div className="flex flex-col gap-0.5">
          <span className="text-small text-muted">Possibly sarcastic</span>
          <span className="num text-lead font-medium">{sarcasticCount}</span>
          {sarcasticCount > 0 && (
            <button
              type="button"
              className="w-fit cursor-pointer text-small font-medium text-text underline underline-offset-3"
              onClick={onSarcasm}
            >
              Read them
            </button>
          )}
        </div>
        <p className="m-0 text-small text-muted">
          Praise that reads as ironic counts half. The detector over-flags short praise, so read
          before drawing conclusions.
        </p>
        <div className="flex flex-col gap-0.5 border-t border-rule pt-3">
          <span className="text-small text-muted">Hidden by moderation</span>
          <span className="num text-lead font-medium">{insights.hidden_comments}</span>
          {insights.in_review > 0 && (
            <span className="num text-small text-muted">{insights.in_review} awaiting review</span>
          )}
        </div>
      </section>
    </div>
  );
}
