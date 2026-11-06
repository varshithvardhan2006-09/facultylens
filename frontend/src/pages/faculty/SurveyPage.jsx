import { useState } from "react";
import { Link } from "react-router";
import { errorMessage } from "../../api/client";
import { surveyApi } from "../../api/evaluation";
import { Field, FormError, TextArea } from "../../components/forms";
import { LikertScale } from "../../components/LikertScale";
import { PageHeader } from "../../components/PageHeader";
import { useAsync } from "../../hooks/useAsync";

const QUESTIONS = [
  ["usefulness", "Usefulness", "My page helps me understand my students' feedback."],
  [
    "accuracy",
    "Accuracy",
    "The strengths and areas to improve match what students actually wrote.",
  ],
  [
    "fairness",
    "Fairness",
    "The page presents the feedback fairly, without overstating criticism or praise.",
  ],
  ["actionability", "Actionability", "The suggested next steps are things I can actually do."],
];

/** The faculty usefulness survey (SPEC §8.7): four ratings and a comment, one per teacher. */
export function SurveyPage() {
  const mine = useAsync(surveyApi.mine);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [tried, setTried] = useState(false);

  const answers = draft?.answers ?? mine.data?.answers ?? {};
  const comment = draft?.comment ?? mine.data?.comment ?? "";
  const missing = QUESTIONS.filter(([key]) => !answers[key]);
  const update = (patch) => {
    setSaved(false);
    setDraft({ answers, comment, ...patch });
  };

  async function submit(event) {
    event.preventDefault();
    setTried(true);
    if (missing.length) {
      document.getElementById(`survey-${missing[0][0]}`)?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await surveyApi.save({ answers, comment: comment.trim() || null });
      setSaved(true);
      setDraft(null);
      mine.reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save your answers."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-[880px] flex-col gap-8">
      <PageHeader title="Was My page useful?">
        Four quick ratings about <Link to="/me">My page</Link>. They help judge whether FacultyLens
        is worth using; your answers are reported only as counts and averages across teachers.
      </PageHeader>
      {mine.error ? (
        <FormError>{errorMessage(mine.error, "Couldn't load your answers.")}</FormError>
      ) : mine.loading ? (
        <span className="skeleton h-96 w-full" aria-busy="true" />
      ) : (
        <form className="card flex flex-col gap-6 p-[var(--card-pad)]" onSubmit={submit} noValidate>
          {mine.data.answered && !draft && !saved && (
            <p className="m-0 text-small text-muted">
              You answered on {new Date(mine.data.updated_at).toLocaleDateString()}. You can change
              your answers.
            </p>
          )}
          {QUESTIONS.map(([key, label, question]) => (
            <LikertScale
              key={key}
              id={`survey-${key}`}
              name={key}
              label={label}
              question={question}
              value={answers[key]}
              onChange={(v) => update({ answers: { ...answers, [key]: v } })}
              invalid={tried && !answers[key]}
            />
          ))}
          <Field
            label="Anything else? (optional)"
            hint="What helped, what was wrong, what you missed."
          >
            {(props) => (
              <TextArea
                {...props}
                rows={4}
                maxLength={2000}
                value={comment}
                onChange={(e) => update({ comment: e.target.value })}
              />
            )}
          </Field>
          {error && <FormError>{error}</FormError>}
          {tried && missing.length > 0 && (
            <p role="alert" className="m-0 text-small text-negative">
              Rate {missing.map(([, label]) => label.toLowerCase()).join(", ")} first.
            </p>
          )}
          <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-4">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "Saving…" : mine.data.answered ? "Update my answers" : "Send my answers"}
            </button>
            {saved && (
              <span role="status" className="text-small text-muted">
                Saved. Thank you.
              </span>
            )}
          </div>
        </form>
      )}
    </div>
  );
}
