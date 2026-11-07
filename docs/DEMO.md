# FacultyLens: 5-minute demo

A walkthrough in role order: student, faculty, HoD, then the admin. Each stop has what to click and the one thing to say. All people in the demo data are fictional; the college, departments and course codes are MVSR Engineering College's real ones.

## Before the demo (10–15 minutes, once)

1. MongoDB is running on `127.0.0.1:27017`, and the backend venv is set up (README, Getting started).
2. In `backend`, load the demo data:

   ```bash
   python -m app.seed
   ```

3. Start the API and the frontend (README, Getting started). Sign in as the admin (`admin@demo.facultylens.in`).
4. Prepare the analysis and the report:
   - **Analysis**, then **Analyse waiting responses**. This takes about 3 minutes and loads every model.
   - **Feedback report**, then **Draft action items**.

   Both stay done, so do this before the audience arrives.
5. Optional, for the Evaluation stop: run these once in `backend`.

   ```bash
   python -m ml.import_items --rmp
   ```

   ```bash
   python -m ml.evaluate
   ```

   This needs the public dataset CSV; see the README section on evaluation.
6. Open four browser profiles or private windows and sign each one in. Every demo account uses the password in `DEMO_PASSWORD` (`backend/.env.example`).

   | Window | Sign in as |
   |---|---|
   | Student | `2451-24-733-006` (still has a form to fill) |
   | Faculty | `kavitha.reddy@demo.facultylens.in` |
   | HoD | `padma.rao@demo.facultylens.in` |
   | Admin | `admin@demo.facultylens.in` |

## The walkthrough

**0:00. The problem (20 s).** Colleges collect teaching feedback, but it ends up as a spreadsheet nobody reads. Teachers never see what students actually meant, and a faculty profile lives somewhere else. FacultyLens joins the two and keeps students anonymous.

**0:20. Student (40 s).** Open **Feedback forms**, then the Automata Languages and Computation form.
- Show the 8 ratings, each with a number and a word, and the three short questions.
- *Say:* "The form stores a one-way code, never the roll number. It only stops a second submission."
- Submit. The form now reads **Submitted** and can't be sent again; the server refuses a second response.

**1:00. Faculty: My page (60 s).** This is the heart of the project.
- The approved profile sits beside this course's feedback: net sentiment and its split, strengths and areas to improve.
- Click **Show the evidence**. The drawer opens with the students' own sentences, the supporting one marked.
- *Say:* "Every point is grounded. With no AI key it is written from counts; with Groq, each point must cite real sentences or it is dropped. Names, phone numbers and roll numbers are already replaced, and abusive answers wait for a person."

**2:00. HoD: Department insights (60 s).**
- **Overview:** every teacher's responses, sentiment and rating, sortable.
- **Bias & sarcasm:** read the caveat aloud. Show the gendered-language bars and a rating-gap row ("no clear difference"), then switch the department to ECE (admin) or explain the "too few teachers" state.
- *Say:* "This panel tests the feedback, not the teachers. It hides itself when groups are too small, and it never names anyone."

**3:00. Admin: Moderation (30 s).**
- Show a hidden answer with the flagged sentence marked, and one marked "may be a false alarm".
- *Say:* "The model hid all the planted abuse, but also a compliment containing the word 'stupid'. That's why a person decides."

**3:30. Admin: Feedback report (50 s).**
- Show the Action Taken rows, grouped by department, with "raised in 4 of 6 CSE courses".
- Approve one, then **Preview PDF**: the draft watermark, the charts and the anonymised comments.
- *Say:* "The report is built for publication: departments only, no teacher named, and the final export unlocks only when every action is approved."

**4:20. Admin: Evaluation (40 s).**
- Show the benchmark table: classical baselines against the transformer. The transformer is most accurate, but TF-IDF + Logistic Regression has the best macro-F1.
- Point out the honest **pending** sections.
- *Say:* "Labels from two annotators give Cohen's kappa. Nothing here is estimated: sections without human labels say so."

**5:00. Close.** Everything ran on a CPU, offline after the first model download, with no paid API.

## If something goes wrong

| Problem | What to do |
|---|---|
| No internet | Everything works except Groq (it falls back to templates) and ORCID / Semantic Scholar imports. |
| No Groq key | Expected. Summaries say "built from the feedback statistics". |
| The first analysis is slow | Models load once, taking about 45 s. Analyse before the demo (step 4). |
| An empty page right after the cycle opens | Feedback shows only after 5 responses per course. That is the privacy rule, not a bug. |
| "Not available for your account" | Wrong window. Each role sees its own screens. |
