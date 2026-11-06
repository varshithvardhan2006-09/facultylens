# FacultyLens: project notes for Claude

These notes carry Claude's working memory from the original laptop. Read them at the start of a session
on a new machine, after `CLAUDE.md` and `docs/SPEC.md`. They describe where the project stands and the
decisions already made; do not re-ask the user about anything settled here.

Last updated: 2026-10-29.

## Where the project stands

Everything in `docs/SPEC.md` is built and pushed to `main` on GitHub (`varshithvardhan2006-09/facultylens`).
On top of the nine SPEC phases:

- **Affinity Wall redesign** (approved by the team).
  Student comments are notes on a sage wall, clustered by teaching aspect. Fonts: Figtree and Kalam.
  `docs/DESIGN.md` is the source of truth for the design. Reuse `.note`, `.board`, `.here`, `.settle`
  and `components/Reveal.jsx` on any new screen.
- **Legal pages**: `/privacy`, `/terms`, `/cookies`, and a consent step on the student form.
  `PRIVACY_CONTACT` in `.env` names the contact.
- **Landing page** at `/` for signed-out visitors, with a team credit (Rohnith, Varshith, Akhil).
- **Motion**:
  - notes settle in when their group scrolls into view;
  - the highlighter swipes in;
  - the numbers count up;
  - the bars grow.

  Everything respects reduced motion.
- **Videos** in `videos/` (Remotion), with an offline Kokoro voice and synthesised music. See
  `videos/README.md`. Both are rendered and approved. The MP4s are not in git and are rebuilt with
  `npm run render:*`.
- **Admin CLI**: `python -m app.cli create-admin | backup <folder> | restore <folder> [--replace]`.

Quality at the last full check (2026-10-22):
- 555 backend tests passed;
- eslint, prettier, ruff and the build were clean;
- npm audit and pip-audit found 0 vulnerabilities;
- there are no secrets in the git history.

## What is left

1. **Team labelling** (the only thing blocking final results):
   - Rohnith and Varshith are the annotators; Akhil is the adjudicator.
   - Needed:
     - 30 comments labelled by both annotators;
     - 100 gold labels;
     - 20 reference summaries;
     - grounding checks;
     - 5 faculty survey answers.
2. Then run `python -m ml.evaluate` and update `ml/results/RESULTS.md` and the README with **real numbers
   only**. Never invent labels or metrics.
3. Loose ends:
   - `.impeccable/` is ignored on purpose.

## Databases

- **Local MongoDB** (`mongodb://127.0.0.1:27017`, database `facultylens`) is the default and what the
  app uses for demos.
- **MongoDB Atlas** (free tier) holds a copy, so the
  teammates can label from their own laptops.
  - It is **switched off**: its network access list is empty, and `.env` uses the local database. The
    Atlas address sits commented out in `.env`.
  - Turn it on only when the user asks. To do that:
    1. Swap the comment in `.env`.
    2. Restart the API.
    3. Have the user re-add network access in Atlas themselves (a security setting).
  - Atlas also has labelling accounts that the local database lacks. Their details are kept outside git.
- Before teammates connect to Atlas, reset the demo admin's password there.
- Teammate setup: `docs/TEAM_SETUP.md`. They need GitHub collaborator access (the repo is private) and
  the `.env` file sent privately.

## Rules that matter

- **Secrets**:
  - Never print, paste or commit `MONGODB_URI`, `GROQ_API_KEY`, `JWT_SECRET` or `STUDENT_HASH_SALT`.
  - `.env` is gitignored.
  - When the user must supply a secret, open the file in their editor and let them paste it.
- **Passwords and accounts**:
  - Do not type passwords into websites or create accounts for the user.
  - Do not change security settings in Atlas, GitHub and the like. Guide the user to do it.
- **Git**:
  - Commit after each working step and push only when the user says so.
  - Never force-push.
- **Web design house rules**: `docs/claude/USER_CLAUDE.md` (also installed as `~/.claude/CLAUDE.md`).
  - They apply to every project and override design skills and mock-ups. Tell the user when they do.
  - One allowed exception: a page's signature animation may wait until it scrolls into view.
- **Demo data is synthetic** and must be labelled as demo data wherever it is shown publicly (videos,
  screenshots).

## About the user

- Rohnith, B.Tech student at MVSR Engineering College, building this mini project with Varshith and
  Akhil.
- Uses Windows, PowerShell, VS Code and Chrome. Prefers short, plain explanations and one step at a time
  when following instructions in a web console.
- Roll number format: `2451-24-751-999` (2451 = college code, 24 = year of admission, 751 = CSIT branch, 999 =
  roll). Branch codes 733 and 735 are also used.
