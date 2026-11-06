import { ArrowLeftIcon, ArrowRightIcon } from "../../components/icons";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { errorMessage } from "../../api/client";
import { editable, profilesApi, toPayload } from "../../api/profiles";
import { Field, FormError, TextInput } from "../../components/forms";
import { PageHeader, Panel } from "../../components/PageHeader";
import { TagInput } from "../../components/TagInput";
import { useAuth } from "../../context/auth";
import { useUnsavedWarning } from "../../hooks/useUnsavedWarning";
import { ImportPanel } from "./ImportPanel";
import { PublicationsEditor } from "./PublicationsEditor";
import { ReviewPanel } from "./ReviewPanel";
import { RowListEditor } from "./RowListEditor";

const SECTIONS = ["qualifications", "experience", "publications", "achievements"];

const QUALIFICATION_FIELDS = [
  { key: "degree", label: "Degree", span: 1, placeholder: "M.Tech" },
  { key: "specialisation", label: "Specialisation", span: 1.4, placeholder: "Computer Science" },
  { key: "institution", label: "Institution", span: 2, wide: true },
  { key: "year", label: "Year", type: "year", span: 0.6 },
];
const EXPERIENCE_FIELDS = [
  { key: "role", label: "Role", span: 1.4, placeholder: "Assistant Professor" },
  { key: "institution", label: "Institution", span: 2, wide: true },
  { key: "department", label: "Department", span: 1.2 },
  { key: "from_year", label: "From", type: "year", span: 0.6 },
  { key: "to_year", label: "To", type: "year", span: 0.6, placeholder: "now" },
];
const ACHIEVEMENT_FIELDS = [
  {
    key: "kind",
    label: "Kind",
    type: "select",
    span: 1,
    options: [
      ["award", "Award"],
      ["patent", "Patent"],
      ["funded_project", "Funded project"],
      ["certification", "Certification"],
      ["fdp", "FDP / workshop"],
      ["other", "Other"],
    ],
  },
  { key: "title", label: "Title", span: 2.4, wide: true },
  { key: "detail", label: "Detail (optional)", span: 2, wide: true },
  { key: "year", label: "Year", type: "year", span: 0.6 },
];

/** Bring server-side changes (accepted imports, new pending items) in without losing local edits. */
function mergeServer(form, server) {
  const next = { ...form };
  for (const section of SECTIONS) {
    const known = new Set(form[section].map((x) => x.id).filter(Boolean));
    const added = server[section].filter((x) => !known.has(x.id));
    next[section] = [...form[section], ...added];
  }
  const tags = new Set(form.interests.map((t) => t.toLowerCase()));
  next.interests = [
    ...form.interests,
    ...server.interests.filter((t) => !tags.has(t.toLowerCase())),
  ];
  return next;
}

export function ProfileEditorPage() {
  const { facultyId: routeId } = useParams();
  const { user: me } = useAuth();
  const facultyId = routeId ?? me.id;
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(null); // JSON of the last saved payload
  const [loadError, setLoadError] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  const load = useCallback(() => {
    profilesApi
      .get(facultyId)
      .then((p) => {
        const f = editable(p);
        setProfile(p);
        setForm(f);
        setSaved(JSON.stringify(toPayload(f)));
      })
      .catch((err) => setLoadError(errorMessage(err)));
  }, [facultyId]);

  useEffect(() => {
    load();
  }, [load]);

  const dirty = useMemo(() => form && JSON.stringify(toPayload(form)) !== saved, [form, saved]);

  useUnsavedWarning(dirty);

  // Wait for the link to be fully typed: every request tells the photo's host someone is here.
  const [previewUrl, setPreviewUrl] = useState("");
  const typedPhoto = form?.photo_url ?? "";
  useEffect(() => {
    const timer = setTimeout(() => setPreviewUrl(typedPhoto), 800);
    return () => clearTimeout(timer);
  }, [typedPhoto]);

  const set = (key) => (value) => {
    setJustSaved(false);
    setForm((f) => ({ ...f, [key]: value }));
  };

  // Accepting an import saves on the server at once: merge it into both the form and the
  // saved baseline, so it doesn't count as an unsaved change but local edits still do.
  const onServerProfile = useCallback((server) => {
    setProfile(server);
    setForm((f) => mergeServer(f, server));
    setSaved((s) => JSON.stringify(toPayload(mergeServer(JSON.parse(s), server))));
  }, []);

  async function save() {
    setSaving(true);
    setSaveError(null);
    try {
      const server = await profilesApi.save(facultyId, toPayload(form));
      const f = editable(server);
      setProfile(server);
      setForm(f);
      setSaved(JSON.stringify(toPayload(f)));
      setJustSaved(true);
    } catch (err) {
      setSaveError(errorMessage(err, "Couldn't save the profile."));
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto flex max-w-[1184px] flex-col gap-3">
        <h1 className="m-0 font-marker text-marker">Profile data</h1>
        <div className="flex flex-wrap items-center gap-3">
          <FormError>{loadError}</FormError>
          <button
            type="button"
            className="btn btn-ghost h-8 px-2"
            onClick={() => {
              setLoadError(null);
              load();
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!profile || !form) {
    return (
      <div className="mx-auto flex max-w-[1184px] flex-col gap-8" aria-busy="true">
        <div className="flex flex-col gap-2">
          <span className="skeleton h-8 w-72" />
          <span className="skeleton h-4 w-96 max-w-full" />
        </div>
        <span className="skeleton h-48 w-full" />
      </div>
    );
  }

  const u = profile.user;
  const ownPage = !routeId;
  const counts = Object.fromEntries(SECTIONS.map((s) => [s, form[s].length]));

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-8">
      <div className="flex flex-col gap-3">
        {!ownPage && (
          <Link to="/admin/users" className="w-fit text-body text-muted hover:text-text">
            <ArrowLeftIcon /> Users
          </Link>
        )}
        <PageHeader
          title={ownPage ? "My profile" : u.name}
          actions={
            <>
              <span className="text-small text-on-board-muted" role="status" aria-live="polite">
                {saving
                  ? "Saving…"
                  : dirty
                    ? "Unsaved changes"
                    : justSaved
                      ? "All changes saved"
                      : ""}
              </span>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!dirty || saving}
                onClick={save}
              >
                Save changes
              </button>
            </>
          }
        >
          {[ownPage ? u.name : null, form.designation, u.department_code, u.email]
            .filter(Boolean)
            .join(" · ")}
          <span className="mt-1 block">
            These facts are what {ownPage ? "your" : "their"} generated profile will be written
            from. Only accepted, saved items are used.{" "}
            <Link
              to={ownPage ? "/profile/review" : `/admin/faculty/${facultyId}/profile/review`}
              className="font-medium text-on-board"
            >
              Generated profile <ArrowRightIcon />
            </Link>
            {" · "}
            <Link
              to={ownPage ? "/me" : `/faculty/${facultyId}`}
              className="font-medium text-on-board"
            >
              {ownPage ? "My page" : "Their page"} <ArrowRightIcon />
            </Link>
          </span>
        </PageHeader>
        <FormError>{saveError}</FormError>
      </div>

      {profile.pending_imports.length > 0 && (
        <ReviewPanel
          facultyId={facultyId}
          pending={profile.pending_imports}
          onDecided={onServerProfile}
        />
      )}

      <div className="grid gap-[var(--gap)] lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
        <div className="flex flex-col gap-[var(--gap)] lg:order-2">
          <ImportPanel facultyId={facultyId} profile={profile} onResult={onServerProfile} />
          <Panel title="Courses taught">
            {profile.courses_taught.length === 0 ? (
              <p className="m-0 text-body text-muted">
                No course offerings assigned yet. The IQAC coordinator assigns teachers to courses.
              </p>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                {profile.courses_taught.map((c) => (
                  <li key={c.id} className="flex flex-col">
                    <span className="font-medium">
                      {c.code} · {c.name}
                    </span>
                    <span className="num text-small text-muted">
                      {c.academic_year} · Sem {c.semester} · Section {c.section}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="flex min-w-0 flex-col gap-[var(--gap)] lg:order-1">
          <Panel title="About">
            <div className="flex flex-col gap-5">
              <div className="grid gap-4 md:grid-cols-2">
                <Field
                  label="Designation"
                  hint="As printed on your college ID, e.g. Associate Professor."
                >
                  {(a) => (
                    <TextInput
                      {...a}
                      value={form.designation}
                      maxLength={120}
                      onChange={(e) => set("designation")(e.target.value)}
                    />
                  )}
                </Field>
                <Field
                  label="Photo link (optional)"
                  hint="An https:// link to a square photo of you that you have the right to use. The site hosting it can see when it is viewed."
                >
                  {(a) => (
                    <div className="flex items-center gap-3">
                      <div className="grid size-10 shrink-0 place-items-center overflow-hidden rounded-full bg-active text-small font-medium text-muted">
                        {previewUrl.startsWith("https://") ? (
                          <img
                            src={previewUrl}
                            alt={`${u.name}, preview`}
                            referrerPolicy="no-referrer"
                            className="size-full object-cover"
                          />
                        ) : (
                          u.name
                            .split(/\s+/)
                            .filter(
                              (w) => /^[A-Za-z]/.test(w) && !/^(dr|prof|mr|ms|mrs)\.?$/i.test(w),
                            )
                            .slice(0, 2)
                            .map((w) => w[0])
                            .join("")
                        )}
                      </div>
                      <TextInput
                        {...a}
                        type="url"
                        value={form.photo_url}
                        onChange={(e) => set("photo_url")(e.target.value)}
                      />
                    </div>
                  )}
                </Field>
              </div>
              <TagInput
                label="Research interests"
                hint="Press Enter after each one. Up to 30."
                placeholder="e.g. Natural language processing"
                value={form.interests}
                onChange={set("interests")}
              />
            </div>
          </Panel>

          <Panel title={`Qualifications (${counts.qualifications})`}>
            <RowListEditor
              noun="qualification"
              fields={QUALIFICATION_FIELDS}
              items={form.qualifications}
              onChange={set("qualifications")}
              newItem={() => ({
                degree: "",
                specialisation: "",
                institution: "",
                year: "",
                source: "manual",
              })}
              addLabel="Add qualification"
              emptyText="No degrees yet. Add them here or import them from ORCID."
            />
          </Panel>

          <Panel title={`Experience (${counts.experience})`}>
            <RowListEditor
              noun="position"
              fields={EXPERIENCE_FIELDS}
              items={form.experience}
              onChange={set("experience")}
              newItem={() => ({
                role: "",
                institution: "",
                department: "",
                from_year: "",
                to_year: "",
                source: "manual",
              })}
              addLabel="Add position"
              emptyText="No positions yet. Leave “To” empty for your current role."
            />
          </Panel>

          <Panel title={`Publications (${counts.publications})`}>
            <PublicationsEditor items={form.publications} onChange={set("publications")} />
          </Panel>

          <Panel title={`Achievements (${counts.achievements})`}>
            <RowListEditor
              noun="achievement"
              fields={ACHIEVEMENT_FIELDS}
              items={form.achievements}
              onChange={set("achievements")}
              newItem={() => ({ kind: "award", title: "", detail: "", year: "", source: "manual" })}
              addLabel="Add achievement"
              emptyText="Awards, patents, funded projects, certifications and FDPs you attended."
            />
          </Panel>
        </div>
      </div>
    </div>
  );
}
