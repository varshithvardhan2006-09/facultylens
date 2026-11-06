import { ArrowLeftIcon, ArrowRightIcon } from "../../components/icons";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { errorMessage } from "../../api/client";
import { formatDate } from "../../api/feedback";
import { engineLabel, profilesApi } from "../../api/profiles";
import { Field, FormError, TextArea, TextInput } from "../../components/forms";
import { PageHeader } from "../../components/PageHeader";
import { TagInput } from "../../components/TagInput";
import { useAuth } from "../../context/auth";

const STATUS = {
  draft: ["pill-warning", "Draft"],
  approved: ["pill-positive", "Approved"],
  superseded: ["pill-neutral", "Superseded"],
};

const words = (text) => (text.trim() ? text.trim().split(/\s+/).length : 0);

function toForm(fields) {
  return {
    headline: fields.headline ?? "",
    bio_short: fields.bio_short ?? "",
    bio_long: fields.bio_long ?? "",
    research_areas: fields.research_areas ?? [],
    key_achievements: (fields.key_achievements ?? []).join("\n"),
    teaching_highlights: fields.teaching_highlights ?? [],
  };
}

function toPayload(form) {
  return {
    ...form,
    headline: form.headline.trim(),
    bio_short: form.bio_short.trim(),
    bio_long: form.bio_long.trim(),
    key_achievements: form.key_achievements
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
  };
}

/** Every fact the generator could use, with the ones this version cites marked. */
function FactsRail({ facts, cited }) {
  const groups = [
    [
      "Qualifications",
      facts.qualifications,
      (q) => `${q.degree}, ${q.institution}${q.year ? ` (${q.year})` : ""}`,
    ],
    [
      "Experience",
      facts.experience,
      (e) => `${e.role}, ${e.institution}${e.from_year ? ` (from ${e.from_year})` : ""}`,
    ],
    [
      "Publications",
      facts.publications.slice(0, 8),
      (p) => `${p.title}${p.year ? ` (${p.year})` : ""}`,
    ],
    ["Achievements", facts.achievements, (a) => `${a.title}${a.year ? ` (${a.year})` : ""}`],
  ];
  return (
    <aside aria-label="Facts used" className="card flex flex-col gap-5 p-[var(--card-pad)]">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-section font-medium">Your saved facts</h2>
        <p className="m-0 text-small text-muted">
          The draft may only use these. Items marked “cited” are referenced by this version.
        </p>
      </div>
      {groups.map(([title, items, line]) => (
        <section key={title} aria-label={title} className="flex flex-col gap-2">
          <h3 className="m-0 text-small font-medium text-muted">
            {title} <span className="num">{items.length}</span>
          </h3>
          {items.length === 0 ? (
            <p className="m-0 text-small text-faint">None saved.</p>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {items.map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-3 text-small">
                  <span className="min-w-0">{line(item)}</span>
                  {cited.has(item.id) && <span className="pill pill-neutral shrink-0">cited</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
      <Link to={facts.editLink} className="text-small text-muted hover:text-text">
        Edit facts <ArrowRightIcon />
      </Link>
    </aside>
  );
}

export function ProfileReviewPage() {
  const { facultyId: routeId } = useParams();
  const { user: me } = useAuth();
  const facultyId = routeId ?? me.id;
  const isOwner = facultyId === me.id;
  const [versions, setVersions] = useState(null);
  const [facts, setFacts] = useState(null);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    // Load (or reload after a change) the versions and the facts they were written from.
    let alive = true;
    Promise.all([profilesApi.versions(facultyId), profilesApi.get(facultyId)])
      .then(([v, p]) => {
        if (!alive) return;
        setVersions(v);
        setFacts({
          ...p,
          editLink: routeId ? `/admin/faculty/${facultyId}/profile` : "/profile",
        });
        setError(null);
      })
      .catch((err) => alive && setError(errorMessage(err, "Couldn't load the generated profile.")));
    return () => {
      alive = false;
    };
  }, [facultyId, routeId, reload]);

  const current = useMemo(() => {
    if (!versions?.length) return null;
    return versions.find((v) => v.version === selected) ?? versions[0];
  }, [versions, selected]);

  const [formFor, setFormFor] = useState(null);
  if (current && formFor !== `${current.version}:${current.edited_at ?? current.created_at}`) {
    // Reset the form whenever another version (or a fresh copy of it) is shown.
    setFormFor(`${current.version}:${current.edited_at ?? current.created_at}`);
    setForm(toForm(current.fields));
  }

  const editable = current?.status === "draft";
  const dirty =
    editable &&
    form &&
    JSON.stringify(toPayload(form)) !== JSON.stringify(toPayload(toForm(current.fields)));
  const cited = useMemo(() => new Set(Object.values(current?.sources ?? {}).flat()), [current]);
  const valid = form && form.headline.trim() && form.bio_short.trim() && form.bio_long.trim();
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function act(kind) {
    setBusy(kind);
    setError(null);
    try {
      if (kind === "generate") {
        const v = await profilesApi.generate(facultyId);
        setSelected(v.version);
      } else {
        if (dirty) await profilesApi.editVersion(facultyId, current.version, toPayload(form));
        if (kind === "approve") await profilesApi.approve(facultyId, current.version);
      }
      setReload((n) => n + 1);
    } catch (err) {
      setError(errorMessage(err, "That didn't work. Try again."));
    } finally {
      setBusy(null);
    }
  }

  const [statusCls, statusText] = STATUS[current?.status] ?? STATUS.draft;

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <div className="flex flex-col gap-3">
        <Link
          to={routeId ? `/admin/faculty/${facultyId}/profile` : "/profile"}
          className="w-fit text-body text-muted hover:text-text"
        >
          <ArrowLeftIcon /> Profile facts
        </Link>
        <PageHeader
          title="Generated profile"
          actions={
            versions?.length > 0 && (
              <>
                <span className="text-small text-muted" role="status" aria-live="polite">
                  {busy === "generate"
                    ? "Writing a draft…"
                    : busy
                      ? "Saving…"
                      : dirty
                        ? "Unsaved edits"
                        : ""}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busy !== null}
                  onClick={() => act("generate")}
                >
                  Generate new draft
                </button>
                {editable && !isOwner && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!dirty || !valid || busy !== null}
                    onClick={() => act("save")}
                  >
                    Save edits
                  </button>
                )}
                {editable && isOwner && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!valid || busy !== null}
                    onClick={() => act("approve")}
                  >
                    Approve and publish
                  </button>
                )}
              </>
            )
          }
        >
          A draft written only from the saved facts{facts ? ` of ${facts.user.name}` : ""}. Edit
          anything you like.{" "}
          {isOwner
            ? "Approving publishes it to colleagues; feedback details stay private."
            : "Only the faculty member can approve and publish it."}
        </PageHeader>
        <FormError>{error}</FormError>
      </div>

      {versions && versions.length === 0 && (
        <section className="card flex flex-col items-start gap-3 p-[var(--card-pad)]">
          <h2 className="m-0 text-section font-medium">No draft yet</h2>
          <p className="m-0 max-w-[64ch] text-body text-muted">
            The draft uses only accepted, saved facts: qualifications, experience, publications,
            achievements, research interests, and the strengths students mention most.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy !== null}
            onClick={() => act("generate")}
          >
            {busy === "generate" ? "Writing a draft…" : "Generate a draft"}
          </button>
        </section>
      )}

      {!versions && !error && (
        <div className="grid gap-[var(--gap)] lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="card flex flex-col gap-4 p-[var(--card-pad)]">
            <span className="skeleton h-10 w-full" />
            <span className="skeleton h-28 w-full" />
            <span className="skeleton h-40 w-full" />
          </div>
          <span className="skeleton h-80 w-full" />
        </div>
      )}

      {current && form && facts && (
        <div className="grid items-start gap-[var(--gap)] lg:grid-cols-[minmax(0,1fr)_360px]">
          <section
            aria-label={`Version ${current.version}`}
            className="card flex flex-col gap-5 p-[var(--card-pad)]"
          >
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-small text-muted">
              <span className={`pill ${statusCls}`}>{statusText}</span>
              <span className="num">
                Version {current.version} · {formatDate(current.created_at, true)}
              </span>
              <span>{engineLabel(current.engine)}</span>
              {current.edited && <span>· edited</span>}
            </div>
            {current.rejected_claims?.length > 0 && (
              <p className="m-0 rounded-control bg-raised px-3 py-2 text-small text-muted">
                The AI draft mentioned things that are not in the saved facts (
                {current.rejected_claims.slice(0, 3).join("; ")}), so the template was used instead.
              </p>
            )}

            <Field label="Headline">
              {(a) => (
                <TextInput
                  {...a}
                  value={form.headline}
                  maxLength={200}
                  readOnly={!editable}
                  onChange={set("headline")}
                />
              )}
            </Field>
            <Field label="Short bio" hint={`${words(form.bio_short)} words · aim for about 60`}>
              {(a) => (
                <TextArea
                  className="[field-sizing:content]"
                  {...a}
                  value={form.bio_short}
                  maxLength={900}
                  readOnly={!editable}
                  onChange={set("bio_short")}
                />
              )}
            </Field>
            <Field label="Full bio" hint={`${words(form.bio_long)} words · aim for about 150`}>
              {(a) => (
                <TextArea
                  {...a}
                  className="min-h-48 [field-sizing:content]"
                  value={form.bio_long}
                  maxLength={2200}
                  readOnly={!editable}
                  onChange={set("bio_long")}
                />
              )}
            </Field>
            {editable ? (
              <TagInput
                label="Research areas"
                hint="Press Enter after each one."
                max={12}
                value={form.research_areas}
                onChange={(research_areas) => setForm({ ...form, research_areas })}
              />
            ) : (
              <div className="flex flex-col gap-1.5">
                <span className="text-body font-medium">Research areas</span>
                <div className="flex flex-wrap gap-1.5">
                  {form.research_areas.map((t) => (
                    <span key={t} className="pill pill-neutral">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <Field label="Key achievements" hint="One per line.">
              {(a) => (
                <TextArea
                  className="min-h-16 [field-sizing:content]"
                  {...a}
                  value={form.key_achievements}
                  readOnly={!editable}
                  onChange={set("key_achievements")}
                />
              )}
            </Field>
            <div className="flex flex-col gap-2">
              <span className="text-body font-medium">Teaching highlights</span>
              {form.teaching_highlights.length === 0 ? (
                <p className="m-0 text-small text-muted">
                  None yet. Highlights come from the strengths students mention most, once a course
                  has enough analysed responses.
                </p>
              ) : (
                <ul className="m-0 flex list-none flex-col gap-2 p-0">
                  {form.teaching_highlights.map((h, i) => (
                    <li key={h.text} className="flex items-center justify-between gap-3 text-body">
                      <span>{h.text}</span>
                      {editable && (
                        <button
                          type="button"
                          className="btn btn-ghost h-8 shrink-0 px-2 text-small"
                          onClick={() =>
                            setForm({
                              ...form,
                              teaching_highlights: form.teaching_highlights.filter(
                                (_, j) => j !== i,
                              ),
                            })
                          }
                        >
                          Remove
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <div className="flex flex-col gap-[var(--gap)]">
            <FactsRail facts={facts} cited={cited} />
            {versions.length > 1 && (
              <section aria-label="Versions" className="card p-[var(--card-pad)]">
                <h2 className="m-0 mb-2 text-section font-medium">Versions</h2>
                <ul className="m-0 flex list-none flex-col p-0">
                  {versions.map((v) => (
                    <li key={v.version}>
                      <button
                        type="button"
                        aria-current={v.version === current.version ? "true" : undefined}
                        onClick={() => setSelected(v.version)}
                        className={`flex h-10 w-full cursor-pointer items-center justify-between gap-3 rounded-control px-2 text-left text-body ${
                          v.version === current.version ? "bg-active" : "hover:bg-raised"
                        }`}
                      >
                        <span className="num">
                          Version {v.version}
                          <span className="text-muted"> · {formatDate(v.created_at)}</span>
                        </span>
                        <span className={`pill ${(STATUS[v.status] ?? STATUS.draft)[0]}`}>
                          {(STATUS[v.status] ?? STATUS.draft)[1]}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
