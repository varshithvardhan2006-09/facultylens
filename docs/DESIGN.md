# FacultyLens design system

Redesigned on 2026-10-21 as the **Affinity Wall**, replacing the Phase 0 "achromatic ledger". Every page reuses it. Tokens are in `frontend/src/styles/tokens.css` (raw values per theme) and mapped to Tailwind utilities in `frontend/src/styles/index.css` (`@theme inline`). Change values there, never inline in components. The approved Figma file is [FacultyLens: Affinity Wall redesign](https://www.figma.com/design/3hl9JFkm5nwpkk5iwdjy7K) (variables, the Note / Button / NavItem / Pill components, and five screens).

## Direction

**Feedback is sorted the way researchers sort it by hand.** Every student comment is a paper note, clustered under the teaching aspect it talks about, with a marker heading that states the verdict. It was chosen through impeccable's direction round (seed `42001c6f43eb851a`, candidate 4) over a lens/highlighter and a metro direction, and it refuses the usual dashboard of white stat tiles and one big table.

- **The wall:** a pale sage ground (`#dde5e1`) under white paper cards.
- **The board:** a deep green (`#183f3a`) carries the rail, page headers and summary strips, like the board the notes are pinned to.
- **Notes:** tinted paper with a strip of tape, tilted a degree or two. Sentiment lives in the paper colour and in its words (Praise / Criticism / Neutral), never in colour alone. (Until 2026-10-22 notes also had a coloured left edge; it was removed under the house rules.)
- **Highlighter yellow** (`#ffd84d`) is reserved for "where you are": the current nav item and the chosen rating.
- **Its signature moment:** on load, notes fly in from scattered positions and settle into their clusters.

## Colour

| Role | Light | Dark | Use |
|---|---|---|---|
| `--ground` (wall) | `#dde5e1` | `#0e1816` | page |
| `--surface` (paper) | `#ffffff` | `#16221f` | cards, tables, drawer |
| `--raised` / `--active` | `#eef3f0` / `#cfdad5` | `#1c2a26` / `#26362f` | hover, next-step boxes, skeletons |
| `--border` / `--rule` / `--control` | `#c3cfca` / `#e2e9e6` / `#7f8c88` | `#2a3a35` / `#21302b` / `#6c7d77` | card edge / row rule / input border (3.5:1) |
| `--text` / `--muted` / `--faint` | `#16201e` / `#46524f` / `#56625f` | `#eef4f1` / `#adbeb8` / `#97aaa3` | three text tiers, all ≥ 4.5:1 on wall and paper |
| `--board` / `--board-2` | `#183f3a` / `#22524b` | `#12302c` / `#1a413b` | rail, headers, summary strips; hover on the board |
| `--on-board` / `--on-board-muted` | `#f3f7f5` / `#b8cec7` | `#eef4f1` / `#a9c4bc` | text on the board (10.7:1 / 7.0:1) |
| `--note-praise` + `--edge-praise` | `#cdf1e5` + `#0f7f6c` | `#173b33` + `#3fbfa2` | praise notes |
| `--note-criticism` + `--edge-criticism` | `#ffd8cc` + `#cf4b29` | `#3f241b` + `#f07a57` | criticism notes |
| `--note-neutral` + `--edge-neutral` | `#eceeed` + `#7c8582` | `#252d2a` + `#8f9a96` | neutral notes, blank answer notes |
| `--highlight` | `#ffd84d` | `#ffd84d` | "where you are" only, ink text on it |
| `--tape` | `#f4e7b8` | `#5b5338` | the tape strip on notes |
| `--primary` | `#16201e` | `#eef4f1` | the one primary button |
| `--focus` | `#0b6b5b` | `#5fd0b8` | 2px ring; on the board it turns highlighter yellow |

**Sentiment in charts** follows the notes: positive `--sent-positive` (teal), negative `--sent-negative` (coral), neutral grey. Teal against coral differs in hue and lightness for the common colour-vision deficiencies, and every sentiment mark still carries a text label or legend. On the deep board the split bar uses the note papers (mint, peach, muted grey) because the edge colours vanish against the board green.

**Two compared groups** (bias panel) keep the validated categorical blue/orange pair, so they are never read as praise and criticism.

**Status pills:** pale tint plus dark ink of the same hue (positive, negative, warning, neutral), pill-shaped.

All text pairs above were checked for WCAG AA in both themes when the tokens were generated. Theme: the OS setting by default; `<html data-theme="light|dark">` overrides it both ways (the rail's Theme switch, a per-viewer `localStorage` convenience applied before first paint).

## Type

- **Figtree Variable** (self-hosted via @fontsource, works offline) for the interface.
- **Kalam Bold** (self-hosted) for headings written on the wall: page titles (`.font-marker text-marker`, 28/34), cluster and column headings (22/28), the net-sentiment figure, and the sign-in promise.
- Monospace (system `ui-monospace`) only for IDs and model keys.
- Fixed rem scale: `text-small` 12/16, `text-body` 14/20, `text-section` 16/24, `text-lead` 18/26, `text-title` 24/32, `text-marker` 28/34, `text-kpi` 30/36.
- Weights 400 / 600 / 700. `.num` (tabular figures) on every number that lines up or updates.
- Sentence case everywhere; no tracked uppercase labels, no eyebrow labels.

## Space, shape and depth

- 4px base. `--gap` 12px between sibling cards, card padding 20px, canvas padding 32px on desktop and 16px on a phone. Content column max 1184px.
- Radius: paper, inputs, buttons, nav items and tabs 6px; notes 3px. Only status labels are fully rounded, so nothing you can press looks like a pill (changed on 2026-10-22, a departure from the Figma frames).
- Depth is physical: paper sits on the wall with a short offset shadow (`--shadow-paper`), notes lift a little more (`--shadow-note`) and lift further on hover (`--shadow-lift`). No zero-offset glows, no gradients, no glass.

## Shell

- A 248px rail on the deep board: mark, name and institution at the top, the account and theme switch at the bottom. The current page is a highlighter-yellow 6px block; the moderation badge is a small peach pill with its count.
- The mark (`components/Mark.jsx`, `public/mark.svg`) is two tilted notes, praise over criticism, taped to the board.
- **Below 1024px** the rail folds into a 48px board-green top bar (mark, screen name, menu) and a full-screen `<dialog>` sheet; Esc closes it and focus returns to the trigger.
- **Signed-out screens** (`StandaloneLayout`): the board on the left with the promise "Every comment, sorted and heard." and the privacy facts pinned as notes; the form on paper on the wall to the right. Phones stack them.

## Components (in `styles/index.css`)

- `.btn` + `.btn-primary` (ink), `.btn-secondary` (sage), `.btn-ghost`: 38px tall, 6px corners.
- `.pill` + `.pill-positive|negative|warning|neutral`.
- `.card`: white paper, 1px border, 6px radius, paper shadow.
- `.board`: the deep green strip for page headers and summaries.
- `.note` + `.note-praise|criticism|neutral`: tinted paper, tape, `--tilt`, even padding on all sides. `.note-lift` straightens and lifts it on hover.
- `.here`: highlighter fill for "where you are".
- `.skeleton`: a flat bar at the real size of the value it replaces, no shimmer.
- Tables keep their Phase 1 rules (sentence-case headers, 44px rows, 1px rules, two-line rows on phones).

## The key screens

- **Faculty My page** (`pages/faculty/FacultyPage.jsx`, `Wall.jsx`): profile on a board header at the left; cycle and course pickers; a board strip with net sentiment, the split bar, responses and the best-rated aspect; then **the wall**: one cluster per aspect students wrote about, ordered by how often, each with a Kalam heading, a marker stroke in the verdict colour, the verdict in words with a drawn ▲/▼ icon, the note and rating counts, and up to five real redacted sentences as notes (two praise, two criticism, one neutral). "Read n notes in full" opens the evidence drawer, where each answer's highlight takes its own sentiment's tint. Aspects nobody wrote about are listed in one line. The written summary, next steps and emotion panels follow.
  - The API supplies note ids per aspect (`insights.aspects[k].note_ids`); the text still comes only from `/evidence`, so the moderation, redaction and minimum-response rules are unchanged.
- **IQAC home** (`pages/admin/AdminHome.jsx`): the open cycle on a board header (responded, to moderate, analysed, actions approved), then its work sorted into four columns of task notes: Needs a decision, Ready to run, Waiting on people, Done. Every count comes from the cycles, analysis, moderation and NAAC status APIs.
- **Student form**: the course on a board header, the 1–5 scale with the chosen rating in highlighter, and the free-text answers written on blank neutral notes.

- **Landing page** (`pages/LandingPage.jsx`, shown at `/` to signed-out visitors only): the hero pattern from the user's references (Rootline-style). A marker heading, one plain sentence, Sign in and "How privacy works", then a real screenshot of the faculty page (`public/landing-wall.jpg`, demo data, captioned as such) with notes naming real teaching aspects pinned over both edges and the board rising behind it. Deliberately without the references' glows, grain, eyebrow labels or pill buttons. The side notes appear from 1280px up.
- **Every other screen** opens with the shared board header (`PageHeader`: marker title, one sentence in board-muted, actions on the right). On the board, buttons invert: the primary is pale on green, the secondary is `--board-2`.
- **Tabs** (`components/Tabs.jsx`) are a row of 6px tabs on the wall; the current tab wears the highlighter, and the arrow keys move between tabs. Used on moderation, labelling and department insights. Tabs inside a card (the import review) keep the underline style.
- **Moderation queue**: each flagged answer is a held note (neutral paper, the flagged sentence marked in coral) in a two-column wall, with its decision buttons under it. The main button follows the check: "Keep hidden" for answers it hid, "Show to faculty" for answers it only wants read. A decided note lifts and fades out in 160ms before the gap closes (instant under reduced motion).
- **Labelling**: the comment is one large note on the left, sticky while you work. Its paper follows the sentiment you choose (mint, peach, grey), instantly and with no animation, because the 1/2/3 keys drive it. The form sits on paper to the right.
- **List screens** (users, departments, courses, cycles, analysis, NAAC report, evaluation, system status) keep their tables and forms on paper under the board header. Tables are the right shape for that data; they take the new tokens.

## History: page notes from Phases 1–8

These notes describe how each page was laid out when it was built. Their structure still holds; where they name the old ledger colours, fonts or the grey active pill, the Affinity Wall tokens above now apply.

### Phase 1 additions

- **Forms** (`components/forms.jsx`):
  - The label sits above a 40px control (1px `--control` border, 6px radius, `--focus` ring); a hint or error goes underneath.
  - An error replaces the hint, is linked with `aria-describedby` and announced with `role="alert"`.
  - Validation happens inline as the user types (mismatch, too short). The submit button stays disabled until the form can succeed.
  - `FormError` shows one sentence after a negative pill.
- **Panels instead of modals.** Add, edit and bulk-add open as an inline `Panel` under the page title (`components/PageHeader.jsx`), never a modal. The only dialog is the phone menu sheet. Deactivation uses the browser's native `confirm()`.
- **One-time secrets** (`CredentialsNotice`):
  - The panel stays until the admin clicks "I've saved them".
  - It offers "Download CSV" as the primary action, with the warning in `--warning` ink.
  - Temporary passwords are monospace and `select-all`.
- **Signed-out screens** (`StandaloneLayout`):
  - The brand row, a 400px form column, and an aside of real product facts on desktop (stacked on phones), all on one centred 1184px column.
  - The login aside explains anonymity, moderation, minimum responses and profile approval in plain words. It makes no numeric claims.
- **Account row** at the sidebar foot: name, role (and roll number for students), "Change password" and "Sign out" as underlined text actions.
- **Row actions** are ghost buttons at 12px. A destructive action uses `text-negative`.
- **Status pills on users:** Active (positive), Temporary password (warning), Deactivated (neutral).
- **Monospace** only for roll numbers, model IDs and temporary passwords. These are keys, which the app rules allow.
- **Checks (Phase 1):**
  - Taste `lint --app`: 0 FAIL.
  - Login `inspect --app`: 0 FAIL, and 1 defended WARN (the empty area under the sign-in form is the screen's single rest).
  - impeccable `detect`: no findings.
  - Signed-in screens checked through Playwright at 1440, 768 and 390.

### Phase 2 additions

- **Review queue** (`pages/profile/ReviewPanel.jsx`):
  - A card above the page body whenever imports are pending. Its heading is the count ("35 imported items wait for your review").
  - Underline tabs per kind, with counts.
  - Group actions on the right: "Reject all N" as ghost, "Accept all N" as secondary.
  - Each row shows the title, a grey meta line, a provenance pill, and Reject / Accept.
  - The list scrolls inside the card past 520px.
  - Decisions save immediately and merge into the form without touching unsaved edits.
- **Provenance pill** (`SourceTag`): a neutral pill saying "ORCID" or "Semantic Scholar". It is never coloured: it shows where a fact came from, not a status. Manual items show nothing.
- **Row editor** (`RowListEditor`):
  - On desktop, one muted header row with aligned 36px inputs per item.
  - The actions column (pill + Remove) is 168px.
  - Phones stack each item with its own small labels. Every input has an aria-label naming its row ("Year (qualification 2)").
- **Tag input:** chips are neutral pills with a 20px remove button. Enter or comma adds a tag; Backspace on an empty input removes the last.
- **Long lists** (publications) are a readable list rather than an input grid. Edit expands an inline form on a `--raised` panel, and a filter box appears past 8 items.
- **Save model:**
  - A single "Save changes" primary in the title row, enabled only when the form differs from the last save.
  - The status line beside it reads "Unsaved changes", "Saving…" or "All changes saved".
  - `beforeunload` warns on unsaved edits.
- **Two-column page:** `minmax(0,1fr) 360px`. The right rail (import, courses taught) comes first in the DOM, so on phones it sits above the long sections.

### Phase 3 additions

- **Rating control** (`components/LikertScale.jsx`):
  - Five equal segments, each showing its number *and* word (Poor, Fair, Good, Very good, Excellent), so colour never carries the meaning.
  - Native radios share one name inside a labelled `role="radiogroup"`: arrow keys change the value and Tab moves to the next question.
  - The selected segment is the near-black primary; segments are at least 48px tall for thumbs.
  - On desktop the question sits left and the scale right; on phones the scale goes underneath.
- **Missing answers:**
  - A missing rating shows only a quiet "Choose a rating." note in `--negative` under its question. There are no red borders on every row.
  - A single `role="alert"` summary above Submit lists the missing questions as links that focus them.
  - The live progress counter ("6 of 8 rated") is in the card header.
- **Anonymity copy:** every student screen says plainly how answers are stored ("without your name or roll number; a one-way code only stops a second submission"). Never "100% anonymous" or other claims.
- **One primary per list:** in a list of forms only the first pending row gets the primary button; the rest are secondary.
- **Rate bar** (`components/RateBar.jsx`):
  - A part-of-whole bar at its true ratio in `--chart-main`, 6px tall on an `--active` track.
  - The label reads "212 of 288 responses" on the left and the percentage on the right.
  - It shows a grey dash when nothing is eligible, and is used for response rates everywhere.
- **Cycle status:** pills read Draft (neutral), Open (positive), Closed (neutral). Publishing explains what it will create before the button, and why offerings are skipped.

### Phase 4 additions

- **Analysis runner** (`pages/admin/AnalysisPage.jsx`):
  - The screen's question is "how much of this cycle is analysed, and what did it flag?".
  - A cycle select, then one divided card with three figures (Responses, Analysed, Waiting) at `text-lead`. It stays three across even on a phone.
  - The one primary button, "Analyse waiting responses", is disabled when nothing waits or a run is active.
  - While a run is active, a progress card shows a `RateBar` in `--chart-main`, elapsed time and ms per response, polling every 2 s. The coverage figures and the jobs-table row follow the live job.
  - After a run, a findings list (hidden, review, PII redacted, possibly sarcastic) with right-aligned tabular counts and a "Review flagged answers →" link.
  - Recent runs as a table; Time and Per response hide below 1024px.
  - Job pills: Queued/Running (neutral), Done (positive), Failed (negative, with the error under the run name), Interrupted (warning).
- **Moderation queue** (`pages/admin/ModerationPage.jsx`):
  - One card with underline tabs ("Waiting for a decision 18", "Decided") and a kind filter.
  - Each item shows a kind pill (Hidden negative, Needs review warning), the abuse score in tabular figures, and the harm label in words. A meta line follows: course · teacher · which answer.
  - The redacted text has the flagged sentence marked in place: a `<mark>` in the negative pill's tint and ink, with its score in the title.
  - When no flagged sentence reads as negative, a muted note says it may be a false alarm (see MODEL_CHECK.md).
  - Actions: "Show to faculty" (secondary), "Keep hidden"/"Hide" and "Edit and show" (ghost). Edit opens an inline textarea labelled with what faculty will see. There is no primary button in a list of decisions.
  - Decided items show the decision pill, time and edited text.
- **Nav count:** "Moderation 18" is a small surface chip on the nav row. It appears only when items are pending, refreshes after every decision (a window event) and each minute, and is read as "18 pending".

### Phase 5 additions

- **Unified faculty page** (`pages/faculty/*`, `/me` and `/faculty/:id`):
  - Two columns: the profile (360px, sticky on desktop) and the feedback insights. They stack on tablets and phones, profile first.
  - The name is the page's one serif title.
  - Staff outside the department get the profile and one sentence saying feedback is private.
- **Profile column:**
  - headline and department meta;
  - the short bio with a "Read the full bio" toggle;
  - research areas as neutral pills;
  - recent publications (title linked to its DOI or URL, venue · year in tabular figures, TL;DR muted);
  - achievements with the year right-aligned;
  - teaching highlights.
  - Sections are separated by a 1px rule, not cards.
- **Insights order** (each block answers one question):
  1. Cycle and course pickers with the response `RateBar`.
  2. Net sentiment, the screen's one `text-kpi` figure, signed to 2 decimals, beside the sentiment split as a labelled 100% bar (negative, neutral, positive with 2px gaps and percentages underneath).
  3. "What students said": the overall sentence, then Strengths and Areas to improve as two cards. Each item has an aspect pill, the text, "Next step:" for improvements, and an underlined "Show the evidence (n)" text button. An automatic digest sits in a `--raised` well, labelled as automatic. A muted line says how the text was written.
  4. Teaching aspects as one table: aspect + mentions, a diverging comment bar (criticism left of a 1px centre line, praise right, neutral split across it, 2px gaps, 3px outer radius), the mean rating ("4.2 / 5") and a ratings-vs-comments pill (Agree positive, Mixed neutral, Disagree warning, Too few neutral). The pill's title gives Spearman ρ and n. On phones the bar moves under the aspect name.
  5. Emotion mix (Recharts horizontal bars, the top emotion in `--chart-main` and the rest in `--chart-muted`, values labelled at the bar ends, an `sr-only` table) beside a caveats card: possibly sarcastic count with "Read them", and the hidden-by-moderation count.
- **Evidence drawer** (`components/EvidenceDrawer.jsx`):
  - A native modal `<dialog>` pinned to the right edge (max 520px, full height, 1px left border).
  - It enters 16px from the right over `--dur-sheet` and closes on Esc, Close or a backdrop click; focus returns to the opener.
  - Each answer shows which question it answered, then the redacted text with the supporting sentence as a `<mark>` in a 22% tint of the item's sentiment colour. Text stays in ink, never the sentiment colour.
  - The answers are introduced by a sentence explaining they are moderated and redacted.
- **Generated profile review** (`/profile/review`):
  - The draft's fields on the left, and on the right a rail of saved facts with "cited" pills for the facts this version references.
  - The status pill (Draft warning, Approved positive, Superseded neutral), version, date and how it was written.
  - "Generate new draft" (secondary) and "Approve and publish" (the one primary, owner only; an admin gets "Save edits").
  - Bios auto-grow (`field-sizing: content`), with live word counts against the 60 / 150 targets.
  - Rejected AI claims are listed in a `--raised` note when the template was used instead.
- **Code splitting:** the unified page and Recharts load as their own chunk (`React.lazy`), so other screens don't download the chart library.

### Phase 6 additions

- **Department insights** (`/insights`, `pages/insights/*`, lazy-loaded):
  - HoDs see their own department and the title is its name; admins get a department picker.
  - The cycle picker and tabs (Overview, Bias & sarcasm) are kept in the URL (`?department&cycle&tab`), so a view can be reloaded or shared.
  - The tabs are underlined, matching the moderation queue.
- **Overview:**
  - A divided stat strip: response `RateBar`, net sentiment as the screen's one `text-kpi`, and hidden by moderation.
  - A sortable teacher table: header buttons with `aria-sort` and a small ▲/▼; empty values always sort last. Columns: name linked to `/faculty/:id`, responses, net sentiment, rating, top strength / area to improve as neutral pills, and possibly sarcastic.
    - A teacher below the minimum gets one muted line instead of numbers.
    - The table scrolls sideways inside its card under 880px.
    - It has no gender column.
  - Then the department aspects (the shared `Aspects` table without the agreement column).
- **Bias & sarcasm panel:**
  - **Caveat:** always first, a `--raised` note with a 1px border in ink ("Read with care. …"). It never uses alarm colour, and it stays visible in every state.
  - **Too small:** one card with the group sizes and why nothing is shown. There are no zeros and no empty charts.
  - **Two group hues** (`--group-1` blue, `--group-2` orange; categorical slots 1–2, checked with the dataviz validator in both modes; fixed order women, men). Every group mark also carries a text label or a legend with the teacher counts.
  - **Gendered language:** Recharts grouped horizontal bars with direct value labels, an `sr-only` table and a disclosure for the word lists.
  - **Rating gap:** a dot-and-whisker per aspect on a zero-centred track (1px centre line, 2px interval, 10px dot with a surface ring). It uses `--chart-main` when the interval excludes 0 and `--chart-muted` with "no clear difference" when it doesn't. The numbers are always written out ("−0.08 (could be −0.61 to +0.40)").
  - **Emotion mix:** paired thin bars per emotion on one scale, with percentages.
  - **Sarcasm:** a rate per group, plus a per-teacher list (not grouped by gender).
  - **Method:** a "How these numbers are made" disclosure.
- **My page:** "Across your courses" (only with two or more offerings in a cycle). Each course name selects that course below; an "All courses" line closes the table.

### Phase 7 additions

- **NAAC report builder** (`/admin/reports`): the cycle picker, then "Draft action items" (secondary; its title says edited and approved rows are never overwritten). Below that are two columns:
  - **Left:** the Action Taken rows grouped by department in cards. Each card header shows "n of m approved" and a ghost "Add an action".
  - **Right (sticky):** "Ready to export?" as a checklist with small round marks (✓ in the positive tint when done; screen-reader text says "Done"/"Not yet"), then the Export card.
- **Export card:**
  - "Download PDF" (the one primary) and "Word (.docx)" (secondary) unlock only when the report is ready. The reason sits under them in muted text ("3 actions still need approval").
  - Draft previews are always-on underlined text buttons below a rule, so a preview never competes with the final export.
  - Files download as blobs with the session token; a status line names the file.
- **Action Taken row** (`components/ActionTable.jsx`, shared with the HoD tab):
  - **Pills:** a status pill (Needs approval warning, Approved positive) and a neutral "Teaching · Pace & syllabus coverage" pill. Then the evidence count, and who drafted it (template or AI model, and whether it was edited).
  - **Body:** the issue as body text, then Action / Responsible / Timeline as a small definition list (three columns on desktop).
  - **Row actions:** small buttons. Approve (secondary) or Reopen (ghost), Edit, "Show the comments" (opens the evidence drawer with the row's own loader), and Delete for manual rows (admin only, after a native confirm).
  - **Editing** happens in place on a `--raised` panel built from `Field` controls, with "Save and approve", "Save as draft" and Cancel.
- **HoD "Action taken" tab** on Department insights: one paragraph saying what the rows are for and how many still need approval, then the same table for their department.
- **The printed report** keeps the app's restraint: DejaVu Sans, black ink, the sentiment trio and the single chart blue in the charts, light grey table headings, and the draft mark at 10% opacity across each page.

### Phase 8 additions

- **Segmented choice** (`components/Segmented.jsx`): native radios in a labelled radiogroup, drawn as equal joined segments like the rating scale. The selected segment is the primary ink. A `quiet` value (a default such as "Not mentioned") is only a grey `--active` tone, so eight untouched rows don't shout.
- **Labelling** (`/label`, only for accounts the admin marks as annotator or adjudicator; a nav item appears for them):
  - Underlined tabs: Label comments / Settle disagreements, Write reference summaries, Check summaries. The tab is kept in the URL.
  - Each task opens with a `RateBar` ("12 of 300 labelled"). The comment sits in a `--raised` figure at `text-section` size and 72ch.
  - Labelling is keyboard-first: keys 1, 2 and 3 choose the sentiment and Enter saves. The hint says so at the foot of the form.
  - Skipping asks for a reason with three small secondary buttons.
  - Adjudication shows both annotators' labels as two small cards, then a blank form. It is never prefilled, so neither side anchors the decision.
  - Grounding checks show each generated point with its quotes under a 2px rule and a Supported / Not supported segmented choice.
- **Evaluation** (`/admin/evaluation`, lazy-loaded with Recharts):
  - One card per question, in this order: labelling progress (a divided stat strip and a `RateBar` per annotator), sentiment, aspects, moderation and redaction, summaries, survey, and data and its limits.
  - **Sentiment chart:** horizontal bars of macro-F1 per model on a 0–1 scale, with value labels at the bar ends. The best model is in `--chart-main` and the rest in `--chart-muted`. There is no legend, because it is a single series and the title names it. The full table follows.
  - **Confusion matrix:** a table with tinted cells (`--chart-main` mixed into the surface by count) and the number always printed in each cell.
  - **Pending sections:** a section without data says what it needs ("this needs 100 gold-labelled comments") and shows a `RateBar` of progress. It never shows an empty chart or a zero.
- **Survey** (`/survey`): four `LikertScale` questions and an optional comment, reached from one muted line at the foot of the teacher's own My page.

## States (every block)

- **Loading:** final layout with skeleton bars.
- **Error:** inside the failed block. One sentence saying what failed and how to recover, plus a Retry text button; never a full-screen banner.
- **Missing value:** a grey en dash at text size.
- **Zero:** printed as `0`.
- **Empty:** the frame and header stay, with one sentence.
- **Refreshing:** keeps the old values, disables the button ("Checking…"), and updates the "Checked hh:mm:ss" stamp.

## Motion

- **One authored moment:** notes settle onto the wall. Each note starts from a scattered offset (`--dx`, `--dy`, `--r0`), slightly scaled down and transparent, and lands at its tilt in 400ms on the strong ease-out, staggered 40ms across the whole wall (`.settle`). The cluster's marker stroke draws itself as its notes land (`.marker-line`). It plays once per load: on the faculty page, the IQAC home board and the sign-in board.
- **Notes wait until you can see them** (2026-10-23, at the user's request): every group of settling notes is wrapped in `components/Reveal.jsx`. A group that starts below the screen holds its notes at their first frame and lets them settle once it scrolls into view (15% visible); a wall cluster only starts watching after its notes have loaded. Groups already on screen settle at once. The landing page's side notes wait for the reader's first scroll (and until half of each group sits in the top 70% of the screen), because on a tall screen they are visible under the heading before anyone looks at them. This is the one scroll-linked behaviour allowed: it delays the existing note moment so it isn't missed, and never fades whole sections in.
- **Supporting moments** (added 2026-10-22, the same scale as the notes: once, meaningful, under about 0.7s):
  - the highlighter (`.here`) is drawn on left to right wherever it appears: the current page, the current tab, the chosen rating;
  - highlighted sentences in the evidence drawer and moderation queue are swept in like a highlighter pen (`.swipe`), one after another;
  - headline numbers count up once (`components/CountUp.jsx`); screen readers get the final value straight away;
  - sentiment, response and diverging bars grow out of the edge they are measured from (`.grow-x`);
  - in labelling, a saved note lifts up and away in 200ms (`.note-leave`) before the next one settles;
  - the landing and sign-in promise is written in line by line (`.write-in`);
  - after submitting feedback, the student sees their course pinned as a note settling onto the page.
- Everything else is feedback, not entrance: `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`; press 140ms (`scale(0.97)` on `:active`), UI 180ms, the sheet and drawer 240ms from the edge they belong to (`@starting-style`).
- Hover effects (note lift, button shadow) are gated behind `(hover: hover) and (pointer: fine)`. Keyboard-driven changes (labelling keys) never animate.
- `prefers-reduced-motion`: notes arrive with a 150ms fade in place, no travel; the marker stroke is drawn already; transitions drop to 1ms.

## Charts (from Phase 5)

Recharts, styled to these tokens, never library defaults.
- One hue per chart (`--chart-main`); comparison series in `--chart-ink` / `--chart-muted`.
- Sentiment uses the diverging trio above.
- 2px lines with no area gradients; 3–5 faint gridlines; no legend for a single series. A legend plus direct labels whenever there are 2 or more series.
- A crosshair tooltip on hover; a table view for accessibility; an empty chart draws its zero line with one sentence.

## Checks used

- 2026-10-22 house rules: no gradients or purple, no emoji or text glyphs as icons (arrows, ticks and sort marks are drawn SVG in `components/icons.jsx`), no em dashes in interface copy, no pill-shaped buttons, no scroll or cursor effects, no AI credit tags, no coloured left edges, no button fades on hover (the fill shifts instead), no label above a heading, favicon set, privacy, terms and cookie pages linked from sign-in and the rail.

- Affinity Wall (2026-10-21): token contrast pairs checked in both themes; every role's main screens visited in light and dark, at 1440 and 390, with no console errors; screenshots in `docs/screenshots` retaken. design-taste `lint --app` on the changed files: 0 FAIL; its shadow warnings are the paper and note depth this world chose (offset, soft blur) and the mono warning is the model-key token.

- design-taste-frontend `lint.mjs --app` and `inspect.mjs --app`: 0 FAIL, 0 WARN at 1440/768/390 on the status page. Mono is used for model IDs only.
- impeccable `detect`: no findings.
- Browser: light and dark, keyboard (skip link, radio group, dialog Esc/focus return), and the API-down error state all checked in the desktop app's browser.
- Phase 9: design-taste `lint --app` on the Phase 8 pages gave 0 FAIL and 2 WARN, both defended:
  - the shadow is on a chart tooltip, which floats;
  - the monospace text is the `model_version` key.
- Phase 9 fresh-clone run: every role's screens were visited with no console errors.
