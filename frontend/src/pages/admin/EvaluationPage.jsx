import { useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { errorMessage } from "../../api/client";
import { ASPECTS, evaluationApi, labelsApi } from "../../api/evaluation";
import { FormError } from "../../components/forms";
import { PageHeader } from "../../components/PageHeader";
import { RateBar } from "../../components/RateBar";
import { Segmented } from "../../components/Segmented";
import { useAsync } from "../../hooks/useAsync";

const ASPECT_LABEL = Object.fromEntries(ASPECTS);
const f3 = (v) => (v === null || v === undefined ? "–" : v.toFixed(3));

function Section({ id, title, intro, children }) {
  return (
    <section aria-labelledby={id} className="card">
      <div className="flex flex-col gap-1 border-b border-rule px-[var(--card-pad)] py-3">
        <h2 id={id} className="m-0 text-section font-medium">
          {title}
        </h2>
        {intro && <p className="m-0 max-w-[80ch] text-small text-muted">{intro}</p>}
      </div>
      <div className="flex flex-col gap-4 p-[var(--card-pad)]">{children}</div>
    </section>
  );
}

/** A section with no numbers yet says exactly what it is waiting for. */
function Pending({ section }) {
  return (
    <div className="flex max-w-[480px] flex-col gap-2">
      <p className="m-0 text-body">
        Not measured yet: this needs {section.need} {section.what}.
      </p>
      <RateBar value={section.have} total={section.need} label={section.what} />
    </div>
  );
}

function Stat({ label, value, note }) {
  return (
    <div className="flex flex-col gap-1 bg-surface p-4">
      <span className="text-small text-muted">{label}</span>
      <span className="num text-lead font-medium">{value}</span>
      {note && <span className="text-small text-muted">{note}</span>}
    </div>
  );
}

function Progress() {
  const progress = useAsync(labelsApi.progress);
  if (progress.error)
    return (
      <FormError>{errorMessage(progress.error, "Couldn't load labelling progress.")}</FormError>
    );
  if (progress.loading) return <span className="skeleton h-24 w-full" aria-busy="true" />;
  const p = progress.data;
  const agree = p.agreement;
  const labellers = p.annotators.filter((a) => a.mode === "annotator");
  return (
    <>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-border bg-rule md:grid-cols-4">
        <Stat label="Comments in the set" value={p.items} />
        <Stat
          label="Gold labels"
          value={p.gold}
          note={
            p.disagreements
              ? `${p.disagreements} disagreement${p.disagreements === 1 ? "" : "s"} to settle`
              : null
          }
        />
        <Stat
          label="Agreement on sentiment (kappa)"
          value={agree.status === "ok" ? f3(agree.sentiment) : "–"}
          note={
            agree.status === "ok"
              ? `${agree.pairs} comments labelled twice`
              : `From ${agree.min_pairs} comments labelled twice (${agree.pairs} so far)`
          }
        />
        <Stat
          label="Reference summaries"
          value={`${p.groups.with_reference} of ${p.groups.total}`}
          note={`${p.groups.grounding_checked} summaries checked for grounding`}
        />
      </div>
      {labellers.length === 0 ? (
        <p className="m-0 text-body text-muted">
          No annotators yet. On the Users page, edit a staff account and set Labelling to
          &ldquo;Annotator&rdquo; (two people) or &ldquo;Adjudicator&rdquo; (one person).
        </p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {labellers.map((a) => (
            <li
              key={a.id}
              className="grid gap-1 md:grid-cols-[200px_minmax(0,1fr)] md:items-center md:gap-6"
            >
              <span className="text-body">{a.name}</span>
              <RateBar value={a.labelled} total={p.items} label="labelled" />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function ModelTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-control border border-border bg-surface px-2.5 py-1.5 text-small shadow-md">
      <span className="font-medium">{row.name}</span>{" "}
      <span className="num text-muted">macro-F1 {f3(row.f1)}</span>
    </div>
  );
}

function Confusion({ name, confusion }) {
  const max = Math.max(...confusion.matrix.flat(), 1);
  return (
    <figure className="m-0 flex flex-col gap-2">
      <figcaption className="text-small text-muted">
        Where {name} goes wrong (rows: true label, columns: predicted)
      </figcaption>
      <table className="w-fit border-separate border-spacing-0.5 text-small">
        <thead>
          <tr>
            <th scope="col" className="sr-only">
              True label
            </th>
            {confusion.labels.map((l) => (
              <th
                key={l}
                scope="col"
                className="px-2 pb-1 text-center font-normal text-muted capitalize"
              >
                {l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {confusion.matrix.map((row, i) => (
            <tr key={confusion.labels[i]}>
              <th scope="row" className="pr-2 text-right font-normal text-muted capitalize">
                {confusion.labels[i]}
              </th>
              {row.map((v, j) => {
                const share = v / max;
                return (
                  <td
                    key={j}
                    className="num h-10 w-16 rounded-chip text-center"
                    style={{
                      background: `color-mix(in oklab, var(--chart-main) ${Math.round(share * 85)}%, var(--surface))`,
                      color: share > 0.5 ? "var(--primary-ink)" : "var(--text)",
                    }}
                  >
                    {v}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

function Sentiment({ results }) {
  const [which, setWhich] = useState("benchmark");
  const section = results.sentiment[which];
  return (
    <Section
      id="sentiment-h"
      title="Sentiment: classical baselines against the transformer"
      intro="Macro-F1 averages the three classes equally, so a model can't score well by always saying positive. The negation slice is the test comments containing not, never, no and similar words."
    >
      <div className="max-w-[440px]">
        <Segmented
          size="sm"
          name="sentiment-set"
          label="Which labels"
          options={[
            ["benchmark", "Scored against star ratings"],
            ["gold", "Human gold labels"],
          ]}
          value={which}
          onChange={setWhich}
        />
      </div>
      {which === "benchmark" && (
        <p className="m-0 max-w-[80ch] text-small text-muted">
          Each comment is labelled from that student&apos;s own star rating (3.5–5 positive, 2.5–3
          neutral, 1–2 negative). A rating isn&apos;t a reading of the comment&apos;s tone, so treat
          these as weak labels; the human gold labels are the real test.
        </p>
      )}
      {section.status !== "ok" ? (
        <Pending section={section} />
      ) : (
        <SentimentResult section={section} />
      )}
    </Section>
  );
}

function SentimentResult({ section }) {
  const rows = Object.entries(section.models).map(([name, m]) => ({ name, f1: m.macro_f1, m }));
  const best = rows.reduce((a, b) => (b.f1 > a.f1 ? b : a));
  return (
    <>
      <p className="m-0 text-small text-muted">
        Trained on <span className="num">{section.n_train}</span>, tested on{" "}
        <span className="num">{section.n_test}</span> comments (
        {Object.entries(section.test_distribution)
          .map(([k, v]) => `${v} ${k}`)
          .join(", ")}
        ). No teacher&apos;s comments are on both sides of the split.
      </p>
      <div className="h-[200px]" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            accessibilityLayer={false}
            data={rows}
            layout="vertical"
            margin={{ top: 0, right: 48, bottom: 0, left: 0 }}
            barCategoryGap={8}
          >
            <XAxis type="number" hide domain={[0, 1]} />
            <YAxis
              type="category"
              dataKey="name"
              width={250}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
            />
            <Tooltip
              content={<ModelTooltip />}
              cursor={{ fill: "var(--raised)" }}
              isAnimationActive={false}
            />
            <Bar
              dataKey="f1"
              radius={[0, 4, 4, 0]}
              isAnimationActive={false}
              label={{ position: "right", fill: "var(--text)", fontSize: 12, formatter: f3 }}
            >
              {rows.map((r) => (
                <Cell key={r.name} fill={r === best ? "var(--chart-main)" : "var(--chart-muted)"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-body">
          <caption className="sr-only">Sentiment results per model</caption>
          <thead>
            <tr className="text-left text-small text-muted">
              <th scope="col" className="py-2 font-normal">
                Model
              </th>
              <th scope="col" className="py-2 text-right font-normal">
                Accuracy
              </th>
              <th scope="col" className="py-2 text-right font-normal">
                Macro-F1
              </th>
              <th scope="col" className="py-2 text-right font-normal">
                F1 negative
              </th>
              <th scope="col" className="py-2 text-right font-normal">
                F1 neutral
              </th>
              <th scope="col" className="py-2 text-right font-normal">
                F1 positive
              </th>
              <th scope="col" className="py-2 text-right font-normal">
                Negation slice
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ name, m }) => (
              <tr key={name} className="h-11 border-t border-rule">
                <th scope="row" className="pr-4 text-left font-normal">
                  {name}
                </th>
                <td className="num text-right">{f3(m.accuracy)}</td>
                <td className={`num text-right ${name === best.name ? "font-semibold" : ""}`}>
                  {f3(m.macro_f1)}
                </td>
                <td className="num text-right">{f3(m.per_class.negative.f1)}</td>
                <td className="num text-right">{f3(m.per_class.neutral.f1)}</td>
                <td className="num text-right">{f3(m.per_class.positive.f1)}</td>
                <td className="num text-right">
                  {m.negation ? `${f3(m.negation.macro_f1)} (${m.negation.n})` : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Confusion name={best.name} confusion={best.m.confusion} />
    </>
  );
}

function BinaryTable({ caption, rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-body">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="text-left text-small text-muted">
            <th scope="col" className="py-2 font-normal">
              Check
            </th>
            <th scope="col" className="py-2 text-right font-normal">
              Precision
            </th>
            <th scope="col" className="py-2 text-right font-normal">
              Recall
            </th>
            <th scope="col" className="py-2 text-right font-normal">
              F1
            </th>
            <th scope="col" className="py-2 text-right font-normal">
              Cases
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, b]) => (
            <tr key={label} className="h-11 border-t border-rule">
              <th scope="row" className="pr-4 text-left font-normal">
                {label}
              </th>
              <td className="num text-right">{f3(b.precision)}</td>
              <td className="num text-right">{f3(b.recall)}</td>
              <td className="num text-right">{f3(b.f1)}</td>
              <td className="num text-right">{b.support}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const PII_LABELS = {
  FACULTY: "Teacher's own name",
  NAME: "Other people's names",
  PHONE: "Phone numbers",
  ROLL: "Roll numbers",
  EMAIL: "Email addresses",
  URL: "Links",
  "PERSON (name or teacher)": "Any person's name",
  ANY: "Any personal detail",
};

function Moderation({ section }) {
  const m = section.moderation;
  return (
    <Section
      id="moderation-h"
      title="Moderation and redaction"
      intro="On a hand-built set of 50 sentences with edge cases (harsh but fair criticism, harmless uses of words like stupid, Indian names and titles, phone numbers and OU roll numbers in several forms). It's small: a sanity check, not a benchmark."
    >
      <BinaryTable
        caption="Moderation and redaction results"
        rows={[
          [`Abuse hidden (score ≥ ${m.hide_threshold})`, m.hidden],
          ...Object.entries(section.pii.per_kind).map(([k, b]) => [
            `Redacted: ${PII_LABELS[k] ?? k}`,
            b,
          ]),
        ]}
      />
      <p className="m-0 text-small text-muted">
        {m.false_alarms.length
          ? `${m.false_alarms.length} fair comments were hidden by mistake (they wait in the moderation queue for a person).`
          : "No fair comment was hidden."}{" "}
        {m.missed.length
          ? `${m.missed.length} abusive comments were missed.`
          : "No abusive comment was missed."}
      </p>
    </Section>
  );
}

function Aspects({ section }) {
  return (
    <Section
      id="aspects-h"
      title="Teaching aspects"
      intro="Does the app find the aspects people marked, and read their polarity right? The similarity threshold is tuned on the training comments only."
    >
      {section.status !== "ok" ? (
        <Pending section={section} />
      ) : (
        <>
          <p className="m-0 text-small text-muted">
            Tuned threshold {section.tuned_aspect_sim} (in use: {section.current_aspect_sim}).
            Polarity macro-F1 {f3(section.test_with_current.polarity?.macro_f1)}.
          </p>
          <BinaryTable
            caption="Aspect detection per aspect"
            rows={Object.entries(section.test_with_current.per_aspect).map(([k, b]) => [
              ASPECT_LABEL[k] ?? k,
              b,
            ])}
          />
        </>
      )}
    </Section>
  );
}

function Summaries({ section }) {
  const g = section.grounding;
  return (
    <Section
      id="summaries-h"
      title="Summaries"
      intro="The app's strengths and areas to improve for 20 teachers, compared with summaries people wrote themselves (ROUGE counts shared words, BERTScore shared meaning)."
    >
      <p className="m-0 text-small text-muted">
        {section.groups} teachers;{" "}
        {Object.entries(section.engines ?? {})
          .map(
            ([engine, n]) =>
              `${n} written by ${engine === "fallback" ? "the built-in templates" : engine}`,
          )
          .join(", ")}
        . LLM comparison: {section.llm}.
      </p>
      {section.status !== "ok" ? (
        <Pending section={section} />
      ) : (
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-border bg-rule md:grid-cols-4">
          <Stat label="ROUGE-1" value={f3(section.rouge1)} />
          <Stat label="ROUGE-2" value={f3(section.rouge2)} />
          <Stat label="ROUGE-L" value={f3(section.rougeL)} />
          <Stat
            label="BERTScore F1"
            value={f3(section.bertscore_f1)}
            note={section.bertscore_model}
          />
        </div>
      )}
      <p className="m-0 text-body">
        {g.status === "pending"
          ? "Grounding: not checked yet. Annotators check each point against the sentences it cites."
          : `Grounding: ${(g.supported_rate * 100).toFixed(1)}% of ${g.checked_bullets} checked points are supported by the sentences they cite.`}
      </p>
    </Section>
  );
}

function Survey({ section }) {
  return (
    <Section
      id="survey-h"
      title="Faculty survey"
      intro="Teachers rate My page from 1 to 5. Demo accounts are left out."
    >
      {section.status === "pending" ? (
        <Pending section={section} />
      ) : (
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-border bg-rule md:grid-cols-4">
          {Object.entries(section.questions).map(([q, v]) => (
            <Stat
              key={q}
              label={q[0].toUpperCase() + q.slice(1)}
              value={v.mean.toFixed(2)}
              note={`${section.n} answers`}
            />
          ))}
        </div>
      )}
    </Section>
  );
}

export function EvaluationPage() {
  const results = useAsync(evaluationApi.results);
  const r = results.data;
  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader title="Evaluation">
        How well the models do on real comments, scored against people&apos;s labels. Numbers come
        from the last run of <code className="font-mono text-small">python -m ml.evaluate</code>;
        run it again on the server after more labelling.
      </PageHeader>

      <Section
        id="progress-h"
        title="Labelling progress"
        intro="Live. Two annotators label the same comments on their own; a third settles disagreements."
      >
        <Progress />
      </Section>

      {results.error ? (
        <FormError>{errorMessage(results.error, "Couldn't load the results.")}</FormError>
      ) : results.loading ? (
        <span className="skeleton h-96 w-full" aria-busy="true" />
      ) : r.status === "not_run" ? (
        <p className="m-0 text-body">
          The evaluation hasn&apos;t been run yet. On the server, run{" "}
          <code className="font-mono text-small">python -m ml.import_items --rmp</code> once, then{" "}
          <code className="font-mono text-small">python -m ml.evaluate</code>.
        </p>
      ) : (
        <>
          <p className="m-0 -mt-4 text-small text-muted">
            Last run {new Date(r.generated_at).toLocaleString()} · models{" "}
            <span className="font-mono">{r.model_version}</span>
          </p>
          <Sentiment results={r} />
          <Aspects section={r.aspects} />
          <Moderation section={r.moderation_pii} />
          <Summaries section={r.summaries} />
          <Survey section={r.survey} />
          <Section id="data-h" title="Data and its limits">
            <ul className="m-0 flex max-w-[80ch] flex-col gap-2 pl-5 text-body">
              <li>
                Public comments: {r.dataset.name} by {r.dataset.author} (
                <a href={r.dataset.url} target="_blank" rel="noreferrer">
                  DOI {r.dataset.doi}
                </a>
                , {r.dataset.licence}). Names were removed before storage; only the comment, the
                star rating and a one-way teacher key are kept.
              </li>
              <li>
                They are reviews of US college teachers, not Indian engineering colleges. This
                college&apos;s own comments join the labelling queue as they are collected (
                {r.data.app_items} so far).
              </li>
              <li>Demo (synthetic) feedback is never used here.</li>
              {r.performance.status === "ok" && (
                <li>
                  Speed on this CPU: {Math.round(r.performance.per_response_ms_mean)} ms per
                  response on average, peak memory {r.performance.peak_rss_mb} MB (see
                  MODEL_CHECK.md).
                </li>
              )}
            </ul>
          </Section>
        </>
      )}
    </div>
  );
}
