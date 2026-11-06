import { Reveal } from "./Reveal";
import { Link } from "react-router";
import { useAsync } from "../hooks/useAsync";
import { getHealth } from "../api/client";
import { Mark } from "./Mark";
import { ThemeSwitch } from "./ThemeSwitch";

const KINDS = ["note-praise", "note-neutral", "note-criticism", "note-praise"];
const TILTS = [-2, 1.6, 1.1, -1.4];
const STARTS = [
  [-80, 50, -10],
  [70, -40, 8],
  [-50, -60, 6],
  [90, 40, -7],
];

/** The three policy pages, linked wherever someone signs in. */
export function PolicyLinks({ onBoard = false }) {
  const tone = onBoard ? "text-on-board-muted hover:text-on-board" : "text-muted hover:text-text";
  return (
    <nav aria-label="Policies" className="flex flex-wrap gap-x-4 gap-y-1 text-small">
      <Link to="/privacy" className={tone}>
        Privacy
      </Link>
      <Link to="/terms" className={tone}>
        Terms
      </Link>
      <Link to="/cookies" className={tone}>
        Cookies
      </Link>
    </nav>
  );
}

/** Facts pinned as notes: they settle in once, like comments landing on the wall. */
function PinnedNotes({ notes, className = "" }) {
  return (
    <Reveal as="ul" className={`m-0 list-none gap-x-6 gap-y-8 p-0 ${className}`}>
      {notes.map((n, i) => {
        const [dx, dy, r0] = STARTS[i % STARTS.length];
        return (
          <li
            key={n.title}
            className={`note settle ${KINDS[i % KINDS.length]} flex flex-col gap-1.5 px-5 py-4`}
            style={{
              "--tilt": `${TILTS[i % TILTS.length]}deg`,
              "--tape-tilt": `${i % 2 ? 4 : -3}deg`,
              "--i": i + 2,
              "--dx": `${dx}px`,
              "--dy": `${dy}px`,
              "--r0": `${r0}deg`,
            }}
          >
            <span className="text-body font-bold">{n.title}</span>
            <span className="text-small leading-5 text-muted">{n.body}</span>
          </li>
        );
      })}
    </Reveal>
  );
}

/**
 * Signed-out screens: the deep board on the left with the product's promise and its facts
 * pinned as notes; the form on paper, on the wall, to the right. Phones stack them.
 */
export function StandaloneLayout({ children, notes = [] }) {
  const health = useAsync(getHealth);
  const institution = health.data?.institution;
  return (
    <div className="grid min-h-dvh bg-ground lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <section className="flex flex-col gap-10 bg-board px-4 pt-5 pb-10 text-on-board md:px-[var(--pad)] md:pt-8 lg:min-h-dvh lg:px-14 lg:pb-14">
        <header className="flex items-center gap-2.5">
          <Mark size={30} />
          <div className="leading-tight">
            <div className="text-section font-bold tracking-[-0.01em]">FacultyLens</div>
            <div className="min-h-4 text-small text-on-board-muted">{institution ?? ""}</div>
          </div>
        </header>
        <div className="flex max-w-[30rem] flex-col gap-3 lg:mt-10">
          <p className="m-0 font-marker text-[2.5rem] leading-[1.1] md:text-[3.25rem]">
            <span className="write-in block">Every comment,</span>
            <span className="write-in block [--write-delay:420ms]">sorted and heard.</span>
          </p>
          <p className="m-0 max-w-[44ch] text-lead text-on-board-muted">
            Student feedback, read the way researchers sort it by hand: each comment a note,
            clustered under the teaching aspect it talks about.
          </p>
        </div>
        {notes.length > 0 && (
          <PinnedNotes
            notes={notes}
            className="mt-auto hidden max-w-[44rem] lg:grid lg:grid-cols-2"
          />
        )}
      </section>
      <main
        id="main"
        className="flex flex-col gap-10 px-4 pt-10 pb-8 md:px-[var(--pad)] lg:justify-center lg:px-14"
      >
        <div className="card mx-auto w-full max-w-[420px] p-6 md:p-8">{children}</div>
        {notes.length > 0 && (
          <PinnedNotes notes={notes} className="mx-auto grid w-full max-w-[420px] pt-2 lg:hidden" />
        )}
        <div className="mx-auto flex w-full max-w-[420px] flex-col gap-5 lg:mt-6">
          <div className="w-60">
            <ThemeSwitch />
          </div>
          <PolicyLinks />
        </div>
      </main>
    </div>
  );
}
