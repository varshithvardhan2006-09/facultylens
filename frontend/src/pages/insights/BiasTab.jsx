import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EMOTIONS, pct } from "../../api/insights";

const GROUPS = [
  ["female", "Women", "var(--group-1)"],
  ["male", "Men", "var(--group-2)"],
];

function Caveat({ text }) {
  return (
    <aside
      aria-label="How to read this panel"
      className="rounded-card border border-border bg-raised px-[var(--card-pad)] py-3"
    >
      <p className="m-0 text-body">
        <span className="font-medium">Read with care. </span>
        {text}
      </p>
    </aside>
  );
}

function GroupLegend({ groups }) {
  return (
    <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-small text-muted">
      {GROUPS.map(([key, label, color]) => (
        <li key={key} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-[2px]" style={{ background: color }} />
          {label} <span className="num">({groups[key].teachers} teachers)</span>
        </li>
      ))}
    </ul>
  );
}

function Card({ id, title, children, actions, note }) {
  return (
    <section aria-labelledby={id} className="card p-[var(--card-pad)]">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 id={id} className="m-0 text-section font-medium">
            {title}
          </h2>
          {note && <p className="m-0 max-w-[68ch] text-small text-muted">{note}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

function LanguageTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-control border border-border bg-surface px-2.5 py-1.5 text-small shadow-md">
      <div className="font-medium">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="num text-muted">
          {p.name}: {p.value} per 1,000 answers
        </div>
      ))}
    </div>
  );
}

/** Ability vs warmth words, per 1,000 answers, for each group (Recharts, two hues). */
function Language({ panel }) {
  const rows = [
    ["Ability words", "ability"],
    ["Warmth words", "warmth"],
  ].map(([label, key]) => ({
    label,
    female: panel.language.female[`${key}_per_1000`],
    male: panel.language.male[`${key}_per_1000`],
  }));
  return (
    <Card
      id="lang-h"
      title="Gendered language in comments"
      note="How many answers per 1,000 use at least one word from each list. Studies of student evaluations find ability words used more for men and warmth words more for women."
      actions={<GroupLegend groups={panel.groups} />}
    >
      <div className="h-[180px]" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            accessibilityLayer={false}
            data={rows}
            layout="vertical"
            margin={{ top: 0, right: 56, bottom: 0, left: 0 }}
            barCategoryGap={18}
            barGap={2}
          >
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="label"
              width={104}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
            />
            <Tooltip
              content={<LanguageTooltip />}
              cursor={{ fill: "var(--raised)" }}
              isAnimationActive={false}
            />
            {GROUPS.map(([key, label, color]) => (
              <Bar
                key={key}
                dataKey={key}
                name={label}
                fill={color}
                radius={[0, 4, 4, 0]}
                isAnimationActive={false}
              >
                <LabelList
                  dataKey={key}
                  position="right"
                  fill="var(--text)"
                  fontSize={12}
                  formatter={(v) => `${label} ${v}`}
                />
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="sr-only">
        <table>
          <caption>Answers per 1,000 using ability and warmth words, by group</caption>
          <thead>
            <tr>
              <th scope="col">List</th>
              <th scope="col">Women</th>
              <th scope="col">Men</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label}>
                <th scope="row">{r.label}</th>
                <td>{r.female}</td>
                <td>{r.male}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="num m-0 mt-2 text-small text-muted">
        Based on {panel.language.female.answers} answers about women and{" "}
        {panel.language.male.answers} about men.
      </p>
      <ul className="m-0 mt-2 flex list-none flex-col gap-1 p-0 text-small">
        {Object.entries(panel.language.gap_per_1000 ?? {}).map(([name, g]) => (
          <li key={name} className="num">
            <span className="font-medium">{name === "ability" ? "Ability" : "Warmth"} words,</span>{" "}
            women minus men: {g.gap > 0 ? "+" : ""}
            {g.gap} per 1,000 (could be {g.low} to {g.high}) ·{" "}
            {g.clear ? (
              <span className="font-medium">clear difference</span>
            ) : (
              <span className="text-muted">no clear difference</span>
            )}
          </li>
        ))}
      </ul>
      <details className="mt-2 text-small text-muted">
        <summary className="w-fit cursor-pointer">The word lists</summary>
        <p className="m-0 mt-1">
          Ability: {panel.lexicons.ability.join(", ")}. Warmth: {panel.lexicons.warmth.join(", ")}.
        </p>
      </details>
    </Card>
  );
}

const fmt = (v) => (v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2));

/** Rating gap per aspect: a dot (the gap) on its 95% interval, around a zero line. */
function RatingGaps({ panel }) {
  const rows = Object.entries(panel.rating_gaps);
  const reach = Math.max(1, ...rows.map(([, g]) => Math.max(Math.abs(g.low), Math.abs(g.high))));
  const scale = Math.ceil(reach * 2) / 2;
  const x = (v) => `${50 + (50 * v) / scale}%`;
  return (
    <Card
      id="gap-h"
      title="Ratings: women minus men, by aspect"
      note="The dot is the difference in mean 1–5 rating; the line is a 95% interval in which each teacher counts once. A line that crosses the centre means no clear difference."
    >
      <div className="mb-1 grid grid-cols-[minmax(0,180px)_minmax(0,1fr)] gap-3 text-small text-muted max-md:grid-cols-1">
        <span />
        <span className="flex justify-between max-md:hidden">
          <span className="num">−{scale.toFixed(1)} (men higher)</span>
          <span>0</span>
          <span className="num">+{scale.toFixed(1)} (women higher)</span>
        </span>
      </div>
      <ul className="m-0 flex list-none flex-col p-0">
        {rows.map(([key, g]) => (
          <li
            key={key}
            className="grid grid-cols-[minmax(0,180px)_minmax(0,1fr)] items-center gap-x-3 gap-y-1 border-t border-rule py-2.5 first:border-t-0 max-md:grid-cols-1"
          >
            <span className="text-body">{g.label}</span>
            <div className="flex flex-col gap-1">
              <div
                className="relative h-4"
                role="img"
                aria-label={`${g.label}: difference ${fmt(g.gap)}, 95% interval ${fmt(g.low)} to ${fmt(g.high)}${g.clear ? "" : ", no clear difference"}`}
              >
                <span
                  className="absolute top-0 bottom-0 left-1/2 w-px bg-control"
                  aria-hidden="true"
                />
                <span
                  className="absolute top-1/2 h-0.5 -translate-y-1/2 rounded-full"
                  style={{
                    left: x(g.low),
                    width: `calc(${x(g.high)} - ${x(g.low)})`,
                    background: g.clear ? "var(--chart-main)" : "var(--chart-muted)",
                  }}
                />
                <span
                  className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface"
                  style={{
                    left: x(g.gap),
                    background: g.clear ? "var(--chart-main)" : "var(--chart-muted)",
                  }}
                />
              </div>
              <span className="num text-small text-muted">
                {fmt(g.gap)} (could be {fmt(g.low)} to {fmt(g.high)}) ·{" "}
                {g.clear ? (
                  <span className="font-medium text-text">clear difference</span>
                ) : (
                  "no clear difference"
                )}{" "}
                · {g.teachers[0]} and {g.teachers[1]} teachers
              </span>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Paired bars per emotion, both groups on one scale, values labelled. */
function Emotions({ panel }) {
  const keys = Object.keys(panel.emotion_mix.female);
  const max = Math.max(
    0.01,
    ...keys.flatMap((k) => GROUPS.map(([g]) => panel.emotion_mix[g][k] ?? 0)),
  );
  const ordered = [...keys].sort(
    (a, b) =>
      (panel.emotion_mix.female[b] ?? 0) +
      (panel.emotion_mix.male[b] ?? 0) -
      ((panel.emotion_mix.female[a] ?? 0) + (panel.emotion_mix.male[a] ?? 0)),
  );
  return (
    <Card
      id="emo-h"
      title="Emotion in the comments, by group"
      note="Average share of each emotion across answers."
    >
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {ordered.map((k) => (
          <li key={k} className="grid grid-cols-[88px_minmax(0,1fr)] items-center gap-3">
            <span className="text-small text-muted">{EMOTIONS[k] ?? k}</span>
            <div className="flex flex-col gap-[2px]">
              {GROUPS.map(([g, label, color]) => {
                const v = panel.emotion_mix[g][k] ?? 0;
                return (
                  <div key={g} className="flex items-center gap-2" title={`${label}: ${pct(v)}`}>
                    <span
                      className="h-2.5 rounded-r-[3px]"
                      style={{ width: `${(85 * v) / max}%`, background: color }}
                    />
                    <span className="num text-small text-muted">{pct(v)}</span>
                  </div>
                );
              })}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Sarcasm({ panel, sarcasm }) {
  return (
    <Card
      id="sarc-h"
      title="Possibly sarcastic answers"
      note="Praise the irony model reads as sarcastic counts half in every score. The model over-flags short sincere praise, so treat these as prompts to read, not findings."
    >
      <div className="grid gap-[var(--gap)] md:grid-cols-[220px_minmax(0,1fr)]">
        <dl className="m-0 flex flex-col gap-3">
          {GROUPS.map(([g, label, color]) => (
            <div key={g} className="flex flex-col gap-0.5">
              <dt className="flex items-center gap-1.5 text-small text-muted">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-[2px]"
                  style={{ background: color }}
                />
                About {label.toLowerCase()}
              </dt>
              <dd className="num m-0 text-lead font-medium">
                {pct(panel.sarcasm[g].rate)}
                <span className="text-small font-normal text-muted">
                  {" "}
                  {panel.sarcasm[g].flagged} of {panel.sarcasm[g].answers}
                </span>
              </dd>
            </div>
          ))}
        </dl>
        {sarcasm?.teachers?.length > 0 && (
          <table className="w-full border-collapse text-body">
            <caption className="mb-1 text-left text-small text-muted">
              By teacher, highest first
            </caption>
            <tbody>
              {sarcasm.teachers.map((t) => (
                <tr key={t.id} className="border-t border-rule">
                  <th scope="row" className="py-2 pr-3 text-left font-normal">
                    {t.name}
                  </th>
                  <td className="num py-2 text-right">
                    {pct(t.rate)}
                    <span className="text-small text-muted">
                      {" "}
                      · {t.flagged} of {t.answers}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  );
}

export function BiasTab({ panel, sarcasm }) {
  const g = panel.groups;
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Caveat text={panel.caveat} />
      {panel.status === "too_small" ? (
        <section className="card flex flex-col gap-2 p-[var(--card-pad)]">
          <h2 className="m-0 text-section font-medium">Groups too small to compare</h2>
          <p className="num m-0 max-w-[68ch] text-body text-muted">
            The comparison needs at least {panel.needed.teachers} teachers and{" "}
            {panel.needed.answers} analysed answers in each group. This department has{" "}
            {g.female.teachers} women ({g.female.answers} answers) and {g.male.teachers} men (
            {g.male.answers} answers) with enough feedback, so nothing is shown: with fewer people,
            a group comparison would point at individuals.
            {panel.excluded_teachers > 0 &&
              ` ${panel.excluded_teachers} teacher${panel.excluded_teachers === 1 ? "" : "s"} without a recorded gender ${panel.excluded_teachers === 1 ? "is" : "are"} not included.`}
          </p>
        </section>
      ) : (
        <>
          <Language panel={panel} />
          <RatingGaps panel={panel} />
          <div className="grid gap-[var(--gap)] lg:grid-cols-2">
            <Emotions panel={panel} />
            <Sarcasm panel={panel} sarcasm={sarcasm} />
          </div>
          <details className="card p-[var(--card-pad)] text-body">
            <summary className="cursor-pointer font-medium">How these numbers are made</summary>
            <div className="mt-2 flex max-w-[72ch] flex-col gap-2 text-muted">
              <p className="m-0">
                Only answers that passed moderation are counted, after names and other personal
                details were removed. Teachers are grouped by the gender recorded by the IQAC
                office; it is never shown next to a name.
                {panel.excluded_teachers > 0 &&
                  ` ${panel.excluded_teachers} teacher(s) without a recorded gender are left out.`}
              </p>
              <p className="m-0">
                The rating intervals treat each teacher as one data point (their average rating),
                because many ratings of one teacher are not independent of each other. With only a
                few teachers per group the intervals are wide on purpose: a difference between a
                handful of people says more about those people than about a pattern.
              </p>
            </div>
          </details>
        </>
      )}
    </div>
  );
}
