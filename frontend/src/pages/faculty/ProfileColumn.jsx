import { ArrowRightIcon } from "../../components/icons";
import { useState } from "react";
import { Link } from "react-router";

const KIND = {
  award: "Award",
  patent: "Patent",
  funded_project: "Funded project",
  certification: "Certification",
  fdp: "FDP / workshop",
  other: "",
};

function Section({ title, children }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2 border-t border-rule pt-4">
      <h2 className="m-0 text-small font-medium text-muted">{title}</h2>
      {children}
    </section>
  );
}

/** Left column: the approved profile, or plain facts until one is approved. */
export function ProfileColumn({ profile, isOwner, reviewLink, showHighlights = true }) {
  const [long, setLong] = useState(false);
  const fields = profile.fields;
  const meta = [profile.designation, profile.department?.name].filter(Boolean).join(" · ");

  return (
    <article
      aria-label="Profile"
      className="card flex flex-col gap-4 overflow-hidden p-[var(--card-pad)]"
    >
      <header className="-mx-[var(--card-pad)] -mt-[var(--card-pad)] flex items-start gap-4 bg-board px-[var(--card-pad)] pt-5 pb-4 text-on-board">
        {profile.photo_url && (
          <img
            src={profile.photo_url}
            alt={profile.name}
            referrerPolicy="no-referrer"
            width="64"
            height="64"
            className="h-16 w-16 shrink-0 rounded-card object-cover"
          />
        )}
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="m-0 font-marker text-marker">{profile.name}</h1>
          {fields?.headline && fields.headline !== meta && (
            <p className="m-0 text-body">{fields.headline}</p>
          )}
          {meta && <p className="m-0 text-small text-on-board-muted">{meta}</p>}
        </div>
      </header>

      {fields ? (
        <div className="flex flex-col gap-2">
          <p className="m-0 text-body leading-6">{long ? fields.bio_long : fields.bio_short}</p>
          {fields.bio_long && fields.bio_long !== fields.bio_short && (
            <button
              type="button"
              className="w-fit cursor-pointer text-small text-muted underline underline-offset-3 hover:text-text"
              aria-expanded={long}
              onClick={() => setLong(!long)}
            >
              {long ? "Show the short bio" : "Read the full bio"}
            </button>
          )}
        </div>
      ) : (
        <p className="m-0 rounded-control bg-raised px-3 py-2 text-small text-muted">
          No approved profile yet.{" "}
          {isOwner && (
            <Link to={reviewLink} className="font-medium text-text">
              Generate and approve yours <ArrowRightIcon />
            </Link>
          )}
        </p>
      )}

      {fields?.research_areas?.length > 0 && (
        <Section title="Research areas">
          <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
            {fields.research_areas.map((t) => (
              <li key={t} className="pill pill-neutral">
                {t}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {profile.publications.length > 0 && (
        <Section title={`Recent publications · ${profile.publication_count} in all`}>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {profile.publications.map((p) => (
              <li key={p.id ?? p.title} className="flex flex-col gap-0.5">
                <span className="text-body font-medium">
                  {p.url || p.doi ? (
                    <a
                      href={p.url ?? `https://doi.org/${p.doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-text no-underline hover:underline"
                    >
                      {p.title}
                    </a>
                  ) : (
                    p.title
                  )}
                </span>
                <span className="num text-small text-muted">
                  {[p.venue, p.year].filter(Boolean).join(" · ")}
                </span>
                {p.tldr && <span className="text-small text-muted">{p.tldr}</span>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {profile.achievements.length > 0 && (
        <Section title="Achievements">
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
            {profile.achievements.slice(0, 8).map((a) => (
              <li key={a.id ?? a.title} className="flex justify-between gap-3 text-body">
                <span>
                  {a.title}
                  {KIND[a.kind] && <span className="text-muted"> · {KIND[a.kind]}</span>}
                </span>
                {a.year && <span className="num shrink-0 text-muted">{a.year}</span>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {showHighlights && fields?.teaching_highlights?.length > 0 && (
        <Section title="Teaching highlights">
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0 text-body">
            {fields.teaching_highlights.map((h) => (
              <li key={h.text}>{h.text}</li>
            ))}
          </ul>
        </Section>
      )}

      {isOwner && fields && (
        <Link to={reviewLink} className="w-fit text-small text-muted hover:text-text">
          Edit or regenerate the profile <ArrowRightIcon />
        </Link>
      )}
    </article>
  );
}
