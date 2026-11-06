import { Link, NavLink } from "react-router";
import { getHealth } from "../../api/client";
import { Mark } from "../../components/Mark";
import { useAsync } from "../../hooks/useAsync";

const UPDATED = "22 October 2026";
const DOCS = [
  ["/privacy", "Privacy notice"],
  ["/terms", "Terms of use"],
  ["/cookies", "Cookies and storage"],
];

function Section({ title, children }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="m-0 font-marker text-[1.375rem] leading-7">{title}</h2>
      {children}
    </section>
  );
}

function P({ children }) {
  return <p className="m-0 max-w-[70ch] text-body leading-6">{children}</p>;
}

function List({ items }) {
  return (
    <ul className="m-0 flex max-w-[70ch] list-disc flex-col gap-1.5 pl-5 text-body leading-6">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

/** Public pages: the board header with the institution, the three documents as tabs, paper body. */
function LegalLayout({ title, children }) {
  const health = useAsync(getHealth);
  const institution = health.data?.institution ?? "the institution";
  const contact = health.data?.privacy_contact ?? "the IQAC office";
  return (
    <div className="min-h-dvh bg-ground">
      <header className="bg-board text-on-board">
        <div className="mx-auto flex max-w-[880px] flex-col gap-6 px-4 pt-6 pb-8 md:px-[var(--pad)]">
          <Link to="/" className="flex w-fit items-center gap-2.5 no-underline">
            <Mark size={28} />
            <span className="leading-tight">
              <span className="block text-section font-bold">FacultyLens</span>
              <span className="block text-small text-on-board-muted">
                {health.data?.institution}
              </span>
            </span>
          </Link>
          <div className="flex flex-col gap-1.5">
            <h1 className="m-0 font-marker text-marker">{title}</h1>
            <p className="m-0 text-small text-on-board-muted">Last updated {UPDATED}</p>
          </div>
          <nav aria-label="Policies" className="flex flex-wrap gap-1">
            {DOCS.map(([to, label]) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `rounded-button px-3.5 py-1.5 text-body no-underline ${
                    isActive
                      ? "here font-semibold"
                      : "text-on-board-muted hover:bg-board-2 hover:text-on-board"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-[880px] px-4 py-8 md:px-[var(--pad)]">
        <article className="card flex flex-col gap-8 p-6 md:p-10">
          {children({ institution, contact })}
        </article>
        <p className="mt-6 text-small text-muted">
          Questions about these pages: write to {contact}. <Link to="/">Back to FacultyLens</Link>
        </p>
      </main>
    </div>
  );
}

export function PrivacyPage() {
  return (
    <LegalLayout title="Privacy notice">
      {({ institution, contact }) => (
        <>
          <Section title="Who is responsible">
            <P>
              FacultyLens is run by {institution} to collect student feedback on teaching and to
              publish faculty profiles. The institution decides why and how this data is used, and
              is responsible for it. For any question or request about your data, write to {contact}
              .
            </P>
          </Section>

          <Section title="What we collect, and why">
            <List
              items={[
                <>
                  <strong>Account details</strong> (name, college email or roll number, department,
                  role): to sign you in and show you the right forms and pages.
                </>,
                <>
                  <strong>Your password</strong>, stored only as a one-way hash that cannot be
                  turned back into the password.
                </>,
                <>
                  <strong>Feedback you submit</strong> (1–5 ratings and optional written comments):
                  to measure how teaching is going, and to produce the NAAC Criterion 1.4 feedback
                  analysis and action-taken report.
                </>,
                <>
                  <strong>For faculty:</strong> profile details you enter or import (qualifications,
                  experience, publications, achievements, an optional photo link) and, optionally,
                  gender, which is used only for a department-level check of whether feedback
                  language differs between groups. It is never shown next to a teacher&apos;s name.
                </>,
                <>
                  <strong>Basic records</strong>: when you last signed in, and an audit log of
                  administrator actions.
                </>,
              ]}
            />
            <P>
              We do not collect your location, device details or browsing history, and there are no
              adverts or analytics trackers. Your IP address is used briefly to slow down repeated
              failed sign-ins and can appear in the server&apos;s technical logs; it is never stored
              with your feedback.
            </P>
          </Section>

          <Section title="How student feedback stays anonymous">
            <List
              items={[
                "Responses are stored without your name, email or roll number. Only the date (not the time) is kept.",
                "To stop a second submission, the system stores a one-way code made from your account and that one form with a secret key. The code is different for every form, so your answers to different forms cannot be linked to each other.",
                "Before any teacher or head of department reads a comment, an automatic filter replaces names, phone numbers and roll numbers with placeholders, and comments with abusive language are held for the IQAC coordinator. The filter is good but not perfect, so please leave personal details out of what you write.",
                "Teachers see written comments only once enough students have answered that form (5 by default), so small groups are harder to single out.",
                "What you write can still reveal who you are (for example, describing a private conversation). Write with that in mind.",
                "People who run the server and hold the secret key could, with effort, test whether a particular student submitted a particular form. Access to the server is limited to the institution's administrators.",
              ]}
            />
          </Section>

          <Section title="Who can see what">
            <List
              items={[
                "Faculty see the moderated, redacted comments and the totals for their own courses, never who wrote them.",
                "A head of department sees the same for teachers in their own department.",
                "The IQAC coordinator administers the system, decides on held comments, and prepares the NAAC report.",
                "Approved faculty profiles are visible to signed-in staff.",
              ]}
            />
          </Section>

          <Section title="Services outside the institution">
            <List
              items={[
                <>
                  <strong>Groq</strong> (an AI service based in the United States), only if the
                  institution has switched it on: it receives redacted comment sentences and the
                  counts behind them to word the written summaries, and a teacher&apos;s own profile
                  facts to draft their profile. Without it, summaries are written on the
                  institution&apos;s own computer.
                </>,
                <>
                  <strong>ORCID and Semantic Scholar</strong>: only when a teacher chooses to import
                  their publications, and only the identifier or name they search for.
                </>,
                <>
                  <strong>A faculty photo link</strong> is loaded from wherever the teacher hosts
                  it, so that website can see that the photo was viewed.
                </>,
                "The language models that analyse comments run on the institution's own computer. They are downloaded once and do not send your data anywhere.",
              ]}
            />
          </Section>

          <Section title="How long we keep it">
            <P>
              Feedback and reports are kept as accreditation records for as long as the institution
              needs them for NAAC and internal quality review. The IQAC office decides when old
              cycles are deleted. Sign-in sessions expire on their own (see the cookies page).
            </P>
          </Section>

          <Section title="Your rights">
            <P>
              You can ask {contact} to see, correct or delete your account details, and to withdraw
              from the optional parts (such as a faculty profile import). Because feedback is stored
              without your name, a single anonymous response cannot be found and removed afterwards;
              think before you submit. You can also raise a complaint with the institution, and,
              under India&apos;s Digital Personal Data Protection Act, 2023, with the Data
              Protection Board of India.
            </P>
          </Section>

          <Section title="Students under 18">
            <P>
              FacultyLens is meant for college students who are 18 or older. If you are under 18,
              tell {contact} before submitting feedback.
            </P>
          </Section>

          <Section title="Security">
            <P>
              Passwords are hashed, sign-in uses short-lived tokens, the sign-in session cookie
              cannot be read by scripts, and repeated failed sign-ins are slowed down. If a security
              incident affects your data, the institution will tell you and the authorities as the
              law requires.
            </P>
          </Section>

          <Section title="Changes">
            <P>
              If this notice changes, the date at the top will change, and significant changes will
              be announced through the college.
            </P>
          </Section>
        </>
      )}
    </LegalLayout>
  );
}

export function TermsPage() {
  return (
    <LegalLayout title="Terms of use">
      {({ institution, contact }) => (
        <>
          <Section title="About these terms">
            <P>
              FacultyLens is provided by {institution} to its students and staff. By signing in, you
              agree to use it as described here and in the <Link to="/privacy">privacy notice</Link>
              . It is free to use; nothing is sold through it, so there are no payments or refunds.
            </P>
          </Section>

          <Section title="Your account">
            <List
              items={[
                "Accounts are created by the IQAC office. Keep your password to yourself and change the temporary one when asked.",
                "Use only your own account. Tell the IQAC office if you think someone else has used it.",
              ]}
            />
          </Section>

          <Section title="Giving feedback">
            <List
              items={[
                "Be honest, specific and respectful. Feedback is most useful when it describes what happened in class.",
                "Do not write abuse, threats, or personal details about anyone (names, phone numbers, roll numbers). Such comments are held back and may be hidden.",
                "Each form can be answered once.",
              ]}
            />
          </Section>

          <Section title="For staff">
            <List
              items={[
                "Use what you see in FacultyLens only for teaching improvement and quality assurance.",
                "Do not try to work out which student wrote a comment, and do not share comments outside the people entitled to see them.",
                "Profile details you enter or approve should be accurate; you are responsible for what your approved profile says.",
              ]}
            />
          </Section>

          <Section title="Automatic analysis">
            <P>
              Sentiment, teaching aspects, summaries and profile drafts are produced by software and
              can be wrong. Treat them as a starting point for reading the actual comments, not as a
              final judgement of anyone&apos;s teaching. Profile drafts are only published after the
              teacher approves them.
            </P>
          </Section>

          <Section title="Availability">
            <P>
              The institution aims to keep FacultyLens working but does not promise it will always
              be available or free of errors, and may change or withdraw it.
            </P>
          </Section>

          <Section title="Ownership">
            <P>
              The software, its design and its reports belong to the institution and the project
              team. Students keep the right to what they write; by submitting it, you allow the
              institution to use it, after moderation and redaction, for the purposes described in
              the privacy notice. Public data used to test the software is credited in the project
              documentation.
            </P>
          </Section>

          <Section title="Law and contact">
            <P>
              These terms are governed by the laws of India. Questions or complaints: {contact}.
            </P>
          </Section>
        </>
      )}
    </LegalLayout>
  );
}

export function CookiesPage() {
  return (
    <LegalLayout title="Cookies and storage">
      {() => (
        <>
          <Section title="In short">
            <P>
              FacultyLens uses one cookie, only to keep you signed in, and remembers one display
              preference in your browser. There are no advertising, analytics or tracking cookies,
              so there is nothing to opt out of and no cookie banner.
            </P>
          </Section>

          <Section title="What is stored">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-left text-body">
                <thead>
                  <tr className="text-small text-muted">
                    <th scope="col" className="py-2 pr-4 font-semibold">
                      Name
                    </th>
                    <th scope="col" className="py-2 pr-4 font-semibold">
                      Type
                    </th>
                    <th scope="col" className="py-2 pr-4 font-semibold">
                      Why
                    </th>
                    <th scope="col" className="py-2 font-semibold">
                      How long
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-rule align-top">
                    <td className="py-3 pr-4 font-mono text-small">fl_refresh</td>
                    <td className="py-3 pr-4">Cookie, strictly necessary</td>
                    <td className="py-3 pr-4">
                      Keeps you signed in. It holds a random code, cannot be read by scripts on the
                      page, and is sent only to the sign-in service of this site.
                    </td>
                    <td className="py-3">
                      Until you sign out, or 7 days (the institution can change this)
                    </td>
                  </tr>
                  <tr className="border-t border-rule align-top">
                    <td className="py-3 pr-4 font-mono text-small">fl-theme</td>
                    <td className="py-3 pr-4">Browser storage, a preference</td>
                    <td className="py-3 pr-4">
                      Remembers light or dark mode, only if you pick one. It never leaves your
                      device.
                    </td>
                    <td className="py-3">Until you choose “System” or clear your browser data</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Section>

          <Section title="Do we need your consent?">
            <P>
              No. A cookie that is needed to sign you in, and a preference you set yourself, are
              exempt from consent under common cookie rules, and India has no separate cookie law.
              If FacultyLens ever adds analytics or third-party content that sets cookies, it will
              ask first.
            </P>
          </Section>

          <Section title="Turning them off">
            <P>
              You can block or delete cookies in your browser settings, but then you will not be
              able to stay signed in.
            </P>
          </Section>
        </>
      )}
    </LegalLayout>
  );
}
