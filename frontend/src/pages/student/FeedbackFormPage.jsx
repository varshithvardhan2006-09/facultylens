import { CheckIcon } from "../../components/icons";
import { ArrowLeftIcon } from "../../components/icons";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { errorMessage } from "../../api/client";
import { feedbackApi, formatDate } from "../../api/feedback";
import { useUnsavedWarning } from "../../hooks/useUnsavedWarning";
import { FormError } from "../../components/forms";
import { LikertScale } from "../../components/LikertScale";

const MAX = 2000;

/** A blank note to write on: the comment students leave is pinned to the wall later. */
function TextQuestion({ id, label, value, onChange, index }) {
  const count = value.length;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-body font-semibold">
        {label} <span className="font-normal text-muted">(optional)</span>
      </label>
      <div
        className="note note-neutral mt-1 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus"
        style={{
          "--tilt": `${index % 2 ? 0.4 : -0.4}deg`,
          "--tape-tilt": `${index % 2 ? 3 : -3}deg`,
        }}
      >
        <textarea
          id={id}
          value={value}
          maxLength={MAX}
          onChange={(e) => onChange(e.target.value)}
          aria-describedby={`${id}-count`}
          className="block min-h-32 w-full resize-y border-0 bg-transparent px-5 py-4 text-body leading-6 text-text outline-none placeholder:text-faint"
        />
      </div>
      <span
        id={`${id}-count`}
        className={`num self-end text-small ${count > MAX - 100 ? "text-warning" : "text-muted"}`}
      >
        {count.toLocaleString("en-IN")} / {MAX.toLocaleString("en-IN")}
      </span>
    </div>
  );
}

function ThankYou({ form }) {
  const [next, setNext] = useState(undefined);
  useEffect(() => {
    let alive = true;
    feedbackApi
      .myForms()
      .then((all) => alive && setNext(all.find((f) => !f.submitted && f.id !== form.id) ?? null))
      .catch(() => alive && setNext(null));
    return () => {
      alive = false;
    };
  }, [form.id]);
  const heading = useRef(null);
  useEffect(() => heading.current?.focus(), []);

  return (
    <div className="mx-auto flex max-w-[640px] flex-col gap-4 pt-8">
      {/* Their feedback, pinned: the same note the wall uses, settling in once. */}
      <div
        aria-hidden="true"
        className="note settle note-praise mb-4 flex w-fit items-center gap-2.5 px-5 pt-5 pb-4"
        style={{ "--tilt": "-2deg", "--dy": "40px", "--r0": "-8deg" }}
      >
        <span className="grid size-6 place-items-center rounded-full bg-[var(--edge-praise)] text-[var(--note-praise)]">
          <CheckIcon />
        </span>
        <span className="font-marker text-lead">
          {form.course.code}
          {form.faculty ? ` · ${form.faculty.name}` : " · syllabus"}
        </span>
      </div>
      <h1 ref={heading} tabIndex={-1} className="m-0 font-marker text-marker outline-none">
        Thank you. Your feedback was recorded.
      </h1>
      <p className="m-0 text-body text-muted">
        It was saved without your name or roll number, so{" "}
        {form.faculty ? form.faculty.name : "your teachers"} won&apos;t see who wrote it. Comments
        are checked for abusive language and personal details before any teacher reads them.
      </p>
      <div className="flex flex-wrap gap-2 pt-2">
        {next && (
          <Link to={`/feedback/${next.id}`} className="btn btn-primary no-underline">
            Next form: {next.course.code}{" "}
            {next.type === "teaching" ? `· ${next.faculty?.name}` : "· syllabus"}
          </Link>
        )}
        <Link to="/" className={`btn ${next ? "btn-ghost" : "btn-primary"} no-underline`}>
          All my forms
        </Link>
      </div>
    </div>
  );
}

export function FeedbackFormPage() {
  const { formId } = useParams();
  const [form, setForm] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [ratings, setRatings] = useState({});
  const [texts, setTexts] = useState({});
  const [tried, setTried] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [agreed, setAgreed] = useState(false);

  useEffect(() => {
    let alive = true;
    feedbackApi
      .form(formId)
      .then((f) => alive && setForm(f))
      .catch((err) => alive && setLoadError(errorMessage(err)));
    return () => {
      alive = false;
    };
  }, [formId]);

  const likert = form?.questions.filter((q) => q.kind === "likert") ?? [];
  const textQs = form?.questions.filter((q) => q.kind === "text") ?? [];
  const missing = likert.filter((q) => !ratings[q.key]);
  const started = Object.keys(ratings).length > 0 || Object.values(texts).some(Boolean);

  useUnsavedWarning(started && !done);

  async function submit(event) {
    event.preventDefault();
    setTried(true);
    setError(null);
    if (missing.length) {
      document.getElementById(`q-${missing[0].key}`)?.focus();
      return;
    }
    if (!agreed) {
      document.getElementById("consent")?.focus();
      return;
    }
    setBusy(true);
    try {
      await feedbackApi.submit(formId, { likert: ratings, texts });
      setDone(true);
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(errorMessage(err, "Couldn't send your feedback. Try again."));
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto flex max-w-[640px] flex-col gap-3">
        <h1 className="m-0 font-marker text-marker">Feedback form</h1>
        <FormError>{loadError}</FormError>
        <Link to="/" className="text-body text-muted">
          <ArrowLeftIcon /> All my forms
        </Link>
      </div>
    );
  }
  if (!form) {
    return (
      <div className="mx-auto flex max-w-[880px] flex-col gap-6" aria-busy="true">
        <span className="skeleton h-8 w-72" />
        <span className="skeleton h-64 w-full" />
      </div>
    );
  }
  if (done) return <ThankYou form={form} />;

  const course = form.course;
  const notOpenYet = new Date(form.cycle.opens_at) > new Date();
  const closed = form.cycle.status !== "open" || new Date(form.cycle.closes_at) < new Date();

  return (
    <div className="mx-auto flex max-w-[880px] flex-col gap-8">
      <div className="flex flex-col gap-3">
        <Link to="/" className="w-fit text-body text-muted hover:text-text">
          <ArrowLeftIcon /> All my forms
        </Link>
        <header className="board flex flex-col gap-2 p-6">
          <h1 className="m-0 font-marker text-marker">
            {course.code} · {course.name}
          </h1>
          <p className="m-0 text-body text-on-board-muted">
            {form.type === "teaching"
              ? `Teaching feedback for ${form.faculty?.name}`
              : "Feedback on the course and syllabus"}
            {" · "}
            {form.cycle.name} · open until {formatDate(form.cycle.closes_at)}
          </p>
          <p className="m-0 max-w-[68ch] text-body">
            Anonymous: your answers are stored without your name or roll number, and a one-way code
            only stops a second submission. Be honest and specific; it is the most useful thing you
            can give.
          </p>
        </header>
      </div>

      {form.submitted ? (
        <p className="card m-0 flex items-center gap-3 p-[var(--card-pad)] text-body">
          <span className="pill pill-positive">Submitted</span>
          You&apos;ve already given feedback on this form. Each form can be answered once.
        </p>
      ) : closed ? (
        <p className="card m-0 p-[var(--card-pad)] text-body text-muted">
          This feedback cycle is closed.
        </p>
      ) : notOpenYet ? (
        <p className="card m-0 p-[var(--card-pad)] text-body text-muted">
          This feedback cycle opens on {formatDate(form.cycle.opens_at)}.
        </p>
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-[var(--gap)]">
          <section className="card" aria-labelledby="ratings-h">
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule px-[var(--card-pad)] py-3">
              <h2 id="ratings-h" className="m-0 font-marker text-[1.375rem]">
                Ratings
              </h2>
              <span className="num text-small text-muted" aria-live="polite">
                {likert.length - missing.length} of {likert.length} rated
              </span>
            </div>
            <div className="flex flex-col divide-y divide-rule">
              {likert.map((q) => (
                <div key={q.key} className="px-[var(--card-pad)] py-4">
                  <LikertScale
                    id={`q-${q.key}`}
                    name={q.key}
                    label={q.label}
                    question={q.text}
                    value={ratings[q.key]}
                    invalid={tried && !ratings[q.key]}
                    onChange={(v) => setRatings((r) => ({ ...r, [q.key]: v }))}
                  />
                </div>
              ))}
            </div>
          </section>

          <section className="card" aria-labelledby="comments-h">
            <div className="border-b border-rule px-[var(--card-pad)] py-3">
              <h2 id="comments-h" className="m-0 font-marker text-[1.375rem]">
                In your own words
              </h2>
              <p className="m-0 text-small text-muted">
                Leave out names and phone numbers. A filter removes them before teachers read
                comments, but it can miss some.
              </p>
            </div>
            <div className="flex flex-col gap-7 p-[var(--card-pad)]">
              {textQs.map((q, i) => (
                <TextQuestion
                  key={q.key}
                  index={i}
                  id={`t-${q.key}`}
                  label={q.text}
                  value={texts[q.key] ?? ""}
                  onChange={(v) => setTexts((t) => ({ ...t, [q.key]: v }))}
                />
              ))}
            </div>
          </section>

          <div className="flex flex-col gap-3 pb-8">
            {tried && missing.length > 0 && (
              <div className="flex flex-col gap-1 text-body" role="alert">
                <span>
                  {missing.length === 1 ? "One rating is" : `${missing.length} ratings are`}{" "}
                  missing:
                </span>
                <ul className="m-0 flex flex-wrap gap-x-3 gap-y-1 p-0 text-small">
                  {missing.map((q) => (
                    <li key={q.key} className="list-none">
                      <a
                        href={`#q-${q.key}`}
                        className="text-negative underline"
                        onClick={(e) => {
                          e.preventDefault();
                          document.getElementById(`q-${q.key}`)?.focus();
                          document
                            .getElementById(`q-${q.key}`)
                            ?.scrollIntoView({ block: "center" });
                        }}
                      >
                        {q.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <label className="flex max-w-[68ch] cursor-pointer items-start gap-3 text-body">
              <input
                id="consent"
                type="checkbox"
                required
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                aria-invalid={tried && !agreed ? true : undefined}
                aria-describedby={tried && !agreed ? "consent-error" : undefined}
                className="mt-0.5 size-4 shrink-0 accent-[var(--primary)]"
              />
              <span>
                I agree that my answers are stored without my name and used to improve teaching and
                for feedback reports, as described in the{" "}
                <Link to="/privacy" target="_blank" rel="noopener">
                  privacy notice
                  <span className="sr-only"> (opens in a new tab)</span>
                </Link>
                .
              </span>
            </label>
            {tried && !agreed && (
              <p id="consent-error" className="m-0 text-small text-negative" role="alert">
                Tick the box to send your feedback.
              </p>
            )}
            <FormError>{error}</FormError>
            <div>
              <button type="submit" className="btn btn-primary h-11 px-6" disabled={busy}>
                {busy ? "Sending…" : "Submit feedback"}
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
