import { Reveal } from "../components/Reveal";
import { Link } from "react-router";
import { getHealth } from "../api/client";
import { Mark } from "../components/Mark";
import { PolicyLinks } from "../components/StandaloneLayout";
import { useAsync } from "../hooks/useAsync";

// The notes either side of the screenshot carry real aspect names, never invented quotes.
const LEFT = [
  ["note-praise", "Subject knowledge", -6, [-90, 40, -12]],
  ["note-criticism", "Pace & coverage", 4, [-70, -30, 9]],
  ["note-neutral", "Assessment", -3, [-110, 10, -6]],
];
const RIGHT = [
  ["note-criticism", "Punctuality", 5, [90, 30, 10]],
  ["note-praise", "Doubt clearing", -4, [70, -40, -8]],
  ["note-praise", "Clarity", 7, [110, 20, 6]],
];

const STEPS = [
  "Students fill a short form for each course: a set of ratings from 1 to 5 and a few lines in their own words. It is stored without their name.",
  "Every comment is checked first. Names, phone numbers and roll numbers are replaced, and abusive comments are held back for the administrator.",
  "Language models running on the college's own computer read each sentence, work out which teaching aspect it talks about, and whether it is praise or criticism.",
  "Each teacher sees their comments sorted by aspect, heads of department see their own department, and the college office exports the feedback report.",
];

function Cluster({ notes, side, offset }) {
  return (
    <Reveal
      as="ul"
      threshold={0.5}
      rootMargin="0px 0px -30% 0px"
      afterScroll
      aria-hidden="true"
      className={`relative z-20 m-0 hidden list-none flex-col gap-6 p-0 pt-16 xl:flex ${
        side === "left" ? "-mr-14 items-end" : "-ml-14 items-start"
      }`}
    >
      {notes.map(([kind, label, tilt, [dx, dy, r0]], i) => (
        <li
          key={label}
          className={`note settle ${kind} w-[176px] px-4 pt-5 pb-7`}
          style={{
            "--tilt": `${tilt}deg`,
            "--tape-tilt": `${i % 2 ? 4 : -3}deg`,
            "--i": offset + i,
            "--dx": `${dx}px`,
            "--dy": `${dy}px`,
            "--r0": `${r0}deg`,
          }}
        >
          <span className="font-marker text-lead leading-6">{label}</span>
        </li>
      ))}
    </Reveal>
  );
}

/**
 * What a signed-out visitor sees at "/": one plain promise, the real faculty page as the
 * picture, notes pinned either side, and the way in.
 */
export function LandingPage() {
  const health = useAsync(getHealth);
  const institution = health.data?.institution;
  return (
    <div className="flex min-h-dvh flex-col bg-ground">
      <header className="mx-auto flex w-full max-w-[1184px] items-center justify-between gap-4 px-4 pt-5 md:px-[var(--pad)] md:pt-7">
        <div className="flex items-center gap-2.5">
          <Mark size={30} />
          <div className="leading-tight">
            <div className="text-section font-bold tracking-[-0.01em]">FacultyLens</div>
            <div className="min-h-4 text-small text-muted">{institution ?? ""}</div>
          </div>
        </div>
        <Link to="/login" className="btn btn-primary">
          Sign in
        </Link>
      </header>

      <main id="main" className="flex flex-1 flex-col">
        <section
          aria-labelledby="landing-h"
          className="mx-auto flex w-full max-w-[1184px] flex-col items-center gap-5 px-4 pt-14 text-center md:px-[var(--pad)] md:pt-20"
        >
          <h1
            id="landing-h"
            className="m-0 max-w-[16ch] font-marker text-[2.75rem] leading-[1.08] md:text-[4rem]"
          >
            <span className="write-in block">Every comment,</span>
            <span className="write-in block [--write-delay:420ms]">sorted and heard.</span>
          </h1>
          <p className="m-0 max-w-[56ch] text-lead text-muted">
            Students rate their teachers and write freely. FacultyLens removes names, holds back
            abuse, and sorts every comment under the teaching aspect it talks about, so each teacher
            sees what to keep and what to fix.
          </p>
          <div className="flex flex-wrap justify-center gap-3 pt-2">
            <Link to="/login" className="btn btn-primary h-11 px-6">
              Sign in
            </Link>
            <Link to="/privacy" className="btn btn-secondary h-11 px-6">
              How privacy works
            </Link>
          </div>
        </section>

        {/* The picture: the real faculty page on the wall, with the board rising behind it. */}
        <div className="relative mt-14 overflow-x-clip md:mt-16">
          <div aria-hidden="true" className="absolute inset-x-0 top-1/2 bottom-0 bg-board" />
          <div className="relative mx-auto grid max-w-[1360px] items-start px-4 md:px-[var(--pad)] xl:grid-cols-[200px_minmax(0,1fr)_200px]">
            <Cluster notes={LEFT} side="left" offset={0} />
            <figure className="relative z-10 m-0">
              <img
                src="/landing-wall.jpg"
                width="1440"
                height="900"
                alt="A teacher's page in FacultyLens: net sentiment and response count on a dark green strip, then student comments sorted under teaching aspects such as assessment, subject knowledge and punctuality, each marked mostly praise or mostly criticism."
                className="block h-auto w-full rounded-card border border-border shadow-[var(--shadow-lift)]"
              />
              <figcaption className="pt-3 pb-10 text-center text-small text-on-board-muted">
                The faculty page, with demo data.
              </figcaption>
            </figure>
            <Cluster notes={RIGHT} side="right" offset={3} />
          </div>
        </div>

        <section aria-labelledby="intro-h" className="bg-board text-on-board">
          <div className="mx-auto grid max-w-[1184px] gap-x-16 gap-y-10 px-4 pt-8 pb-16 md:px-[var(--pad)] lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <div className="flex flex-col gap-4">
              <h2 id="intro-h" className="m-0 font-marker text-[2rem] leading-tight">
                What FacultyLens is
              </h2>
              <p className="m-0 max-w-[52ch] text-lead text-on-board-muted">
                FacultyLens is a B.Tech mini project that helps a college run student feedback on
                teaching. For every teacher it brings two things together on one page: a profile
                written from their qualifications and publications, and an honest reading of what
                students said about their classes.
              </p>
            </div>
            <div className="flex flex-col gap-4">
              <h3 className="m-0 font-marker text-[1.5rem] leading-tight">How it works</h3>
              <ol className="m-0 flex list-none flex-col gap-5 p-0">
                {STEPS.map((text, i) => (
                  <li key={i} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
                    <span aria-hidden="true" className="font-marker text-[1.5rem] leading-7">
                      {i + 1}
                    </span>
                    <p className="m-0 max-w-[60ch] text-body leading-6">{text}</p>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-board text-on-board">
        <div className="mx-auto flex max-w-[1184px] flex-col gap-3 border-t border-board-rule px-4 py-6 md:flex-row md:items-center md:justify-between md:px-[var(--pad)]">
          <div className="flex flex-col gap-1 text-small text-on-board-muted">
            <span>FacultyLens{institution ? ` · ${institution}` : ""}</span>
            <span>Made by Rohnith, Varshith and Akhil</span>
          </div>
          <PolicyLinks onBoard />
        </div>
      </footer>
    </div>
  );
}
