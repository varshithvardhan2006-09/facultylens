import { currentAcademicYear } from "../../lib/academicYear";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { errorMessage } from "../../api/client";
import { feedbackApi, formatDate } from "../../api/feedback";
import { Field, FormError, Select, TextInput } from "../../components/forms";
import { PageHeader, Panel } from "../../components/PageHeader";
import { CycleStatus } from "../../components/CycleStatus";
import { RateBar } from "../../components/RateBar";
import { useAsync } from "../../hooks/useAsync";

const loadCycles = () => feedbackApi.cycles();

function toLocalInput(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function NewCycle({ onCancel }) {
  const navigate = useNavigate();
  const year = currentAcademicYear();
  const month = new Date().getMonth();
  const term = month >= 5 && month <= 10 ? "odd" : "even";
  const today = new Date();
  const [form, setForm] = useState({
    academic_year: year,
    term,
    name: `${year} ${term === "odd" ? "Odd" : "Even"} Sem`,
    opens_at: toLocalInput(today),
    closes_at: toLocalInput(new Date(today.getTime() + 21 * 86400000)),
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => {
    const next = { ...form, [k]: e.target.value };
    if (k === "term" || k === "academic_year") {
      next.name = `${next.academic_year} ${next.term === "odd" ? "Odd" : "Even"} Sem`;
    }
    setForm(next);
  };

  async function submit(event) {
    event.preventDefault();
    if (!form.opens_at || !form.closes_at) {
      setError("Choose both the opening and the closing date.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const cycle = await feedbackApi.createCycle({
        ...form,
        opens_at: new Date(`${form.opens_at}T00:00:00`).toISOString(),
        closes_at: new Date(`${form.closes_at}T23:59:00`).toISOString(),
      });
      navigate(`/admin/cycles/${cycle.id}`);
    } catch (err) {
      setError(errorMessage(err, "Couldn't create the cycle."));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1fr_0.8fr_1.4fr_1fr_1fr]">
        <Field label="Academic year">
          {(a) => <TextInput {...a} value={form.academic_year} onChange={set("academic_year")} />}
        </Field>
        <Field label="Term" hint="Odd: semesters 1, 3, 5, 7">
          {(a) => (
            <Select {...a} value={form.term} onChange={set("term")}>
              <option value="odd">Odd semester</option>
              <option value="even">Even semester</option>
            </Select>
          )}
        </Field>
        <Field label="Name">
          {(a) => <TextInput {...a} value={form.name} onChange={set("name")} />}
        </Field>
        <Field label="Opens">
          {(a) => <TextInput {...a} type="date" value={form.opens_at} onChange={set("opens_at")} />}
        </Field>
        <Field label="Closes" hint="End of that day">
          {(a) => (
            <TextInput {...a} type="date" value={form.closes_at} onChange={set("closes_at")} />
          )}
        </Field>
      </div>
      <FormError>{error}</FormError>
      <div className="flex gap-2">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Creating…" : "Create draft"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export function CyclesPage() {
  const cycles = useAsync(loadCycles);
  const [adding, setAdding] = useState(false);
  const list = cycles.data ?? [];

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <PageHeader
        title="Feedback cycles"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            aria-expanded={adding}
            onClick={() => setAdding(!adding)}
          >
            New cycle
          </button>
        }
      >
        A cycle is one round of feedback, usually per semester. Publishing it creates a teaching
        form for every teacher of every offering in that term, and one syllabus form per offering.
      </PageHeader>

      {adding && (
        <Panel title="New feedback cycle">
          <NewCycle onCancel={() => setAdding(false)} />
        </Panel>
      )}

      <section aria-label="Cycles" className="card overflow-hidden">
        {cycles.error ? (
          <div className="flex flex-wrap items-center gap-3 p-[var(--card-pad)]">
            <FormError>Couldn&apos;t load cycles.</FormError>
            <button type="button" className="btn btn-ghost h-8 px-2" onClick={cycles.reload}>
              Retry
            </button>
          </div>
        ) : cycles.data && list.length === 0 ? (
          <p className="m-0 p-[var(--card-pad)] text-body text-muted">
            No cycles yet. Create one for this semester, check the preview, then publish it.
          </p>
        ) : (
          <table className="w-full border-collapse text-body">
            <thead className="max-md:sr-only">
              <tr className="text-left text-small text-muted">
                <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                  Cycle
                </th>
                <th scope="col" className="h-10 px-3 font-medium">
                  Status
                </th>
                <th scope="col" className="h-10 px-3 font-medium">
                  Open
                </th>
                <th scope="col" className="h-10 px-3 text-right font-medium">
                  Forms
                </th>
                <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                  Responses
                </th>
              </tr>
            </thead>
            <tbody>
              {(cycles.data ? list : [null, null]).map((c, i) =>
                c ? (
                  <tr
                    key={c.id}
                    className="border-t border-rule hover:bg-raised max-md:flex max-md:flex-col max-md:gap-1 max-md:px-4 max-md:py-3"
                  >
                    <td className="h-14 px-[var(--card-pad)] max-md:h-auto max-md:p-0">
                      <Link
                        to={`/admin/cycles/${c.id}`}
                        className="font-medium no-underline hover:underline"
                      >
                        {c.name}
                      </Link>
                    </td>
                    <td className="px-3 max-md:p-0">
                      <CycleStatus status={c.status} />
                    </td>
                    <td className="num px-3 text-muted max-md:p-0 max-md:text-small">
                      {formatDate(c.opens_at)} – {formatDate(c.closes_at)}
                    </td>
                    <td className="num px-3 text-right max-md:p-0 max-md:text-left max-md:text-small">
                      {c.counts.teaching_forms + c.counts.curriculum_forms}
                      <span className="md:hidden"> forms</span>
                    </td>
                    <td className="px-[var(--card-pad)] py-2 max-md:p-0">
                      <RateBar value={c.counts.responses} total={c.counts.eligible} />
                    </td>
                  </tr>
                ) : (
                  <tr key={i} className="border-t border-rule">
                    <td colSpan={5} className="h-14 px-[var(--card-pad)]">
                      <span className="skeleton h-4 w-full max-w-[640px]" />
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
