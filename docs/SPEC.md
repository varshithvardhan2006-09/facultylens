# FacultyLens — Product & Technical Specification

**Project:** Faculty Profile Generation and Student Feedback Evaluation based on Text Summarization and Sentiment Analysis
**Domain:** Artificial Intelligence & Natural Language Processing · **Version:** 1.0 (October 2026)

This is the single source of truth for what to build. `CLAUDE.md` holds the working rules.

---

## 1. Problem and goal
Colleges collect student feedback every semester, but the free-text comments are read manually or not at all. Faculty profiles are maintained by hand in static pages. feedback report asks institutions to show that feedback was *collected, analysed, acted on and published*.

FacultyLens automates all of this:
- It generates a structured, readable profile for each faculty member.
- It analyses anonymous student feedback down to individual teaching aspects, protecting students (anonymity) and faculty (moderation, redaction).
- It puts both on one page, and exports a ready-to-submit feedback report.

### Novelty (what must exist for the project's claims to be true)
1. A **unified profile page**: LLM-written research and academic profile + aspect-level teaching insights for the same person.
2. **Aspect sentiment with evidence**: every strength or improvement links to the redacted sentences that support it.
3. **Moderation + PII redaction** before any faculty member sees a comment.
4. A **bias & sarcasm panel** that flags unreliable signals instead of hiding them.
5. A **Feedback Analysis + Action Taken Report** export.
6. **Rigorous evaluation**: a classical baseline vs transformer, two-annotator Cohen's kappa, ROUGE/BERTScore, and a faculty usefulness survey.

---

## 2. Users and roles
| Role | Can do |
|---|---|
| **admin** (administrator) | Manage departments, users, courses, feedback cycles and forms. See moderation queue (incl. hidden toxic comments with reasons). Run analysis and reports, view the bias panel institution-wide, run evaluation and labelling. |
| **hod** | View faculty pages, analytics and the bias panel for own department. Approve Action Taken entries. |
| **faculty** | Edit own profile data, import from ORCID / Semantic Scholar, review and approve the generated profile. See only moderated + redacted feedback for own courses (once the minimum response count is reached). Respond to improvement areas. Fill the usefulness survey. |
| **student** | Log in with roll number, see open feedback forms for enrolled courses, submit once per form. Never sees analysis. |

Authentication uses JWT access tokens (60 min) and refresh tokens (7 days), bcrypt passwords, and a forced password change on first login. Login is rate-limited.

---

## 3. Core user flows
1. **Admin setup:** create department → add faculty and students (single form + bulk add via a JSON/CSV *user list* — this is user import, not feedback upload) → create courses and map faculty and student enrolments → create a feedback cycle (e.g., "2026-27 Odd Sem") → publish forms.
2. **Faculty profile:** faculty enter qualifications, experience, research interests, publications and achievements, or paste an ORCID iD / Semantic Scholar author ID to import publications → click *Generate profile* → review the LLM draft side by side with source facts → edit → approve → the profile becomes visible.
3. **Student feedback:** student logs in → sees pending forms → answers Likert questions (1–5) for each teaching aspect and three free-text questions → submits (one response per student per form, enforced by a salted hash) → gets a thank-you screen. No analysis is visible to the student.
4. **Analysis (automatic):** each submission is queued → background pipeline (§5) runs → results are cached in MongoDB. Admin can also re-run analysis for a cycle.
5. **Faculty page:** after the cycle closes (or once responses ≥ minimum), faculty/HoD/admin open the unified page: profile on the left, feedback insights on the right.
6. **Feedback report:** admin picks a cycle → system builds the Feedback Analysis report and drafts an Action Taken Report → admin and HoD edit actions → export PDF/DOCX.

---

## 4. Feedback form design
Each **teaching-aspect** question has a Likert rating (1–5) and the aspect is also detected in free text. The two are cross-checked as a consistency signal.

**Fixed aspect taxonomy (8):**
| key | Aspect | Example seed phrases for aspect detection |
|---|---|---|
| `knowledge` | Subject knowledge | knows the subject, expert, deep knowledge, concepts |
| `clarity` | Clarity of explanation | explains clearly, easy to understand, confusing, fast explanation |
| `punctuality` | Punctuality & regularity | on time, late, cancels class, regular |
| `interaction` | Interaction & doubt clearing | clears doubts, approachable after class, answers questions, interactive |
| `practical` | Examples & practical relevance | real-world examples, practical, industry, lab, applications |
| `assessment` | Assessment & feedback fairness | fair marking, internals, assignments, evaluation, feedback on tests |
| `behaviour` | Behaviour & approachability | polite, rude, friendly, strict, respectful, motivating |
| `pace` | Pace & syllabus coverage | completes syllabus, too fast, rushed, slow, covers portions |

**Free-text questions:** (1) What did you like most about this course/teacher? (2) What should the teacher improve? (3) Any other comments?

**Curriculum feedback form (for the feedback report):** students also rate syllabus relevance, course outcomes clarity, lab/practical adequacy, and reference material (Likert), plus one comment box. The report states that only the *student* stakeholder group is collected in this version.

---

## 5. NLP pipeline (runs in background tasks, CPU-only)
For each new response, in batches:

1. **Preprocess (NLTK):** normalise unicode and whitespace, expand common contractions, fix repeated characters ("sooo" → "so"), language check (flag non-English for the admin), sentence split (`nltk.sent_tokenize`). Keep the original text. Stopword removal and lemmatisation are used **only** for the TF-IDF baseline and word clouds — never feed stemmed text to transformers.
2. **PII redaction:** spaCy `en_core_web_sm` PERSON entities (except the course faculty's own name, which becomes `[FACULTY]`), regex for phone numbers, emails, roll-number pattern (`ROLL_NO_REGEX` in config), URLs → `[NAME] [PHONE] [EMAIL] [ROLL] [URL]`.
3. **Moderation:** toxicity model on each sentence. Max score ≥ `TOX_HIDE` (0.70) → comment hidden from faculty/HoD and sent to the admin moderation queue with the label. `TOX_REVIEW` (0.40)–0.70 → visible but queued for admin review. Admin can approve, hide, or redact further.
4. **Overall sentiment:** 3-class (positive / neutral / negative) with probabilities, per comment and per sentence.
5. **Aspect detection:** embed each sentence (MiniLM) and compute cosine similarity to each aspect's prototype embeddings (mean of seed-phrase embeddings). Assign an aspect if similarity ≥ `ASPECT_SIM` (0.35, tune on labelled data) **or** a lexicon keyword matches (the lexicon is the seed-phrase column of the §4 aspect table, matched case-insensitively on word boundaries). A sentence can have up to 2 aspects.
6. **Aspect polarity:** ABSA model on (sentence, aspect label) → positive / neutral / negative + confidence. The sentence is stored as **evidence** with character offsets for highlighting.
7. **Emotion:** 7-class emotion distribution per comment (for the bias & sarcasm panel).
8. **Sarcasm/irony:** irony probability per comment. If irony ≥ `SARC_FLAG` (0.70) and sentiment is positive, mark `sentiment_uncertain=true`. Down-weight these comments ×0.5 in aggregates and show them in a "possibly sarcastic" list.
9. **Store** results in `analyses` with `model_version` so re-runs are idempotent.

**Aggregation** (per faculty × course × cycle, cached in `aggregates`, recomputed on new data):
- response count
- sentiment distribution
- net sentiment score = (pos − neg) / total
- per-aspect: mention count, polarity split, mean Likert, Likert–text agreement (Spearman)
- top evidence sentences per aspect (highest confidence, deduplicated)
- emotion mix
- sarcasm-flag rate
- toxic-hidden count

**Summaries (Groq LLM, grounded):** the input is the aggregate JSON plus at most 40 redacted, moderated evidence sentences with IDs. The output is validated JSON:
```json
{ "strengths": [{"text": "...", "aspect": "clarity", "evidence_ids": ["..."]}],
  "improvements": [{"text": "...", "aspect": "pace", "evidence_ids": ["..."], "suggested_action": "..."}],
  "overall_summary": "2-3 sentences" }
```
Reject any item with no valid evidence IDs. **No-LLM fallback:** use the HF summariser on the concatenated positive and negative evidence, plus templated sentences built from the aspect aggregates.

---

## 6. Models (CPU-friendly; all go through `app/nlp/registry.py`)
| Task | `ML_MODE=light` (default) | `ML_MODE=full` |
|---|---|---|
| Sentiment (3-class) | `cardiffnlp/twitter-roberta-base-sentiment-latest` | same, or fine-tuned DistilBERT from §8 if it scores better |
| Sentence embeddings (aspect detection) | `sentence-transformers/all-MiniLM-L6-v2` | `sentence-transformers/all-mpnet-base-v2` |
| Aspect polarity (ABSA) | `yangheng/deberta-v3-base-absa-v1.1` | same |
| Toxicity | `unitary/unbiased-toxic-roberta` | same |
| Emotion | `j-hartmann/emotion-english-distilroberta-base` | same |
| Sarcasm / irony | `cardiffnlp/twitter-roberta-base-irony` | same |
| Summarisation fallback (no LLM) | `sshleifer/distilbart-cnn-12-6` | `facebook/bart-large-cnn` |
| NER for PII | spaCy `en_core_web_sm` | spaCy `en_core_web_sm` |
| LLM (profiles, summaries, ATR) | Groq `GROQ_MODEL` (default `openai/gpt-oss-120b`) → fallback `GROQ_FALLBACK_MODEL` (default `openai/gpt-oss-20b`) | same |

Notes:
- Verify each model ID loads during Phase 0 and record the real RAM and latency in `docs/MODEL_CHECK.md`. If a model is too slow on CPU (> 1.5 s per comment in batches of 16), propose a lighter alternative.
- Groq's model list changes. `llama-3.3-70b-versatile` (the kit's original default) was shut down on the free tier on 2026-08-16. Groq's recommended replacement is `openai/gpt-oss-120b`, checked on 2026-10-19 at https://console.groq.com/docs/models and /docs/deprecations. Read the IDs from `.env` and handle "model not found / decommissioned" by switching to the fallback and logging a warning.
- Both gpt-oss models are reasoning models. Call them with `reasoning_effort="low"` (faster, and lighter on free-tier token limits) and `response_format={"type": "json_object"}`, and still validate the output with Pydantic.
- Licences: the emotion and irony models list no licence on Hugging Face; say so in the report's limitations.
- Optional speed-up (only if needed): dynamic int8 quantisation via `torch.quantization.quantize_dynamic` on Linear layers. Measure the accuracy change before keeping it.

---

## 7. Faculty profile generation
**Inputs (`faculty_profiles` collection):**
- name, designation, department, email, photo URL
- qualifications (degree, specialisation, institution, year)
- experience (role, institution, from, to)
- research interests (tags)
- publications (title, venue, year, type, DOI, authors, citations, tldr)
- achievements (awards, patents, funded projects, certifications, FDPs)
- courses taught
- optional `gender` (admin-only field, used **only** for department-level aggregate bias checks and never displayed on profiles)

**Import services:**
- **ORCID Public API v3.0** (no key needed for public data): `GET https://pub.orcid.org/v3.0/{orcid}/works` and `/employments`, `/educations` with `Accept: application/json`. Map to the schema and deduplicate by DOI or normalised title.
- **Semantic Scholar Graph API:** author search → `GET /graph/v1/author/{id}/papers?fields=title,year,venue,citationCount,externalIds,tldr`. An optional `S2_API_KEY` raises rate limits. Respect 429 responses with backoff.
- Imported items are shown to the faculty member as **pending** until they accept them.

**Generation (Groq, grounded):** extract facts → derive top research keywords (TF-IDF over titles + tldrs + interest tags) → prompt the LLM with *only* these facts → JSON output:
```json
{ "headline": "...", "bio_short": "≈60 words", "bio_long": "≈150 words",
  "research_areas": ["..."], "key_achievements": ["..."],
  "teaching_highlights": ["from feedback strengths only, each with evidence_ids"],
  "sources": {"bio_long": ["fact_ids"]} }
```
- **Validation:** every number, year, venue and award in the output must exist in the input facts; otherwise regenerate once, then fall back to the template.
- **Workflow:** the faculty member can edit any field and must approve. Versions are kept in `profile_versions`.
- **No-LLM fallback:** a deterministic template profile built from the facts.

---

## 8. Evaluation module (core to the project's novelty claim)
1. **Data:** real comments collected through the app (anonymised, moderated). Optionally, a public English course-review dataset — Claude must find it, verify that it exists, and check its licence before use. Never fabricate labelled data. Synthetic seed data is marked `is_synthetic=true` and is **excluded** from all evaluation.
2. **Labelling tool (admin page):** two annotators independently label N comments (target ≥ 300) for sentiment and aspects/polarity. Compute **Cohen's kappa** per task. A third person resolves disagreements to form the gold set. Split gold data 80/20 (stratified) with a fixed seed.
3. **Sentiment:**
   - Baselines: VADER, TF-IDF + Logistic Regression, TF-IDF + Random Forest.
   - Transformers: the pretrained Cardiff model (zero-shot) and an optional DistilBERT fine-tuned on CPU (≤ 3 epochs) if the gold set is ≥ 300.
   - Report accuracy, **macro-F1**, per-class F1 and the confusion matrix.
   - Report a **negation slice** separately (e.g., "not engaging but informative").
4. **Aspects:** detection precision/recall/F1 per aspect, polarity macro-F1, and tuning of `ASPECT_SIM` on the train split only.
5. **Moderation & PII:** precision/recall on a small hand-built test set of 50 sentences that includes edge cases.
6. **Summaries:** 20 faculty-course groups with human-written reference strengths/improvements. Report **ROUGE-1/2/L** and **BERTScore F1**, LLM vs no-LLM fallback. Also report evidence-grounding rate = % of bullets whose evidence actually supports them (manual check).
7. **Faculty usefulness survey** (in-app, 5–10 faculty): 5-point Likert on usefulness, accuracy, fairness, and actionability, plus a comment box.
8. **Performance:** mean and p95 latency per comment and peak RAM on the demo CPU.
9. `python -m ml.evaluate` writes `ml/results/*.json`, `*.png` charts and `RESULTS.md`. The admin Evaluation page reads these files. All numbers in the README come from here.

---

## 9. Data model (MongoDB collections)
| Collection | Key fields | Indexes |
|---|---|---|
| `users` | `_id, role, name, email?, roll_no?, department_id, password_hash, must_change_pw, is_active, created_at, last_login_at?, gender? (faculty/HoD, admin-only)` | unique `email` (partial: where set; students may have none), unique `roll_no` (sparse), `role+department_id` |
| `departments` | `_id, name, code` | unique `code` |
| `courses` (course **offering**) | `_id, code, name, department_id, academic_year, semester, section, faculty_ids[], student_ids[]` | **unique** `code+academic_year+semester+section`; `faculty_ids`; `student_ids` |
| `refresh_tokens` | `jti_hash (sha256), user_id, created_at, expires_at, revoked` | unique `jti_hash`; TTL on `expires_at` |
| `faculty_profiles` | `user_id, designation, photo_url, interests[], qualifications[], experience[], publications[], achievements[]` (every item has an `id` and a `source`: manual/orcid/s2), `orcid?, s2_author_id?, pending_imports[{id, kind, source, data, key}], rejected_keys[], import_log{orcid, s2}, updated_at` | unique `user_id` |
| `profile_versions` | `user_id, version, generated(json), edited(json), status(draft/approved), llm_model, created_at` | `user_id+version` |
| `feedback_cycles` | `_id, name, academic_year, term, opens_at, closes_at, status` | — |
| `forms` | `_id, cycle_id, course_id, faculty_id, type(teaching/curriculum), questions[]` | `cycle_id+course_id+faculty_id` |
| `responses` | `_id, form_id, student_hash, likert{aspect:int}, texts{liked,improve,other}, submitted_at, is_synthetic` | **unique** `form_id+student_hash` |
| `analyses` | `response_id, model_version, redacted_texts, pii_found[], toxicity{}, moderation_status, sentiment{label,probs}, sentences[{text,start,end,aspects[{key,polarity,conf}]}], emotion{}, irony, sentiment_uncertain` | `response_id+model_version` |
| `aggregates` | `faculty_id, course_id, cycle_id, stats{}, summary{}, updated_at` | `faculty_id+course_id+cycle_id` |
| `moderation_queue` | `analysis_id, reason, score, status, reviewed_by` | `status` |
| `action_taken` | `cycle_id, faculty_id, course_id, issue, aspect, action, owner, timeline, status, evidence_ids[]` | `cycle_id` |
| `labels` | `response_id, annotator_id, sentiment, aspects[]` | `response_id+annotator_id` |
| `survey_responses` | `faculty_id, answers{}, comment` | — |
| `audit_log` | `actor, actor_role, action, target, details, at` | `at` |

*Changed in Phase 1 (agreed with the user, 2026-10-20):* a course is an **offering** with a section, so a faculty member's feedback comes only from their own section's students; users are deactivated (`is_active=false`) instead of deleted; refresh tokens are opaque, stored hashed and rotated. Added endpoints: `POST /auth/logout`, `POST /users/{id}/reset-password`, `PATCH /departments/{id}`, `GET /courses/{id}`, `PATCH /courses/{id}`. `POST /auth/refresh` returns 204 when there is no session cookie.

*Changed in Phase 2 (2026-10-20):* imports never write straight into the profile: each item waits in `pending_imports` until the owner accepts or rejects it, and a dedup key (DOI, else normalised title + year; role + institution; degree + institution; tag) stops re-imports from suggesting anything already accepted, pending or rejected. A Semantic Scholar paper that duplicates a pending ORCID work fills in its citations and TL;DR instead. Added endpoints: `GET /faculty/{id}/semantic-scholar/search` (author candidates, because names collide), `POST /faculty/{id}/imports/{item}/reject`, `POST /faculty/{id}/imports/bulk`. Semantic Scholar's author-papers endpoint rejects `tldr`, so TL;DRs come from `POST /paper/batch` and are best-effort without `S2_API_KEY`.

*Changed in Phase 3 (agreed with the user, 2026-10-20):*
- **Anonymity code:** the one-response-per-form code is `HMAC-SHA256(STUDENT_HASH_SALT, "<student_id>:<form_id>")` instead of `sha256(student_id + SALT)`. It differs on every form, so one student's responses can't be linked to each other.
- **Responses** store `type, likert, texts, submitted_on, is_synthetic` and the code. There is no student id, IP or user agent. `submitted_on` is a date with no time.
- **Forms:** `forms.faculty_id` is null for curriculum forms, and `forms` has a unique `cycle_id+course_id+faculty_id+type` index.
- **Cycle terms:** a cycle has a `term` (odd/even). Publishing creates forms for that academic year's offerings whose semester parity matches.
- **Added endpoints:** `GET /cycles/{id}`, `GET /cycles/{id}/preview`, `GET /cycles/{id}/forms`. `GET /cycles` is readable by faculty and HoDs (counts for admin only).
- **Comments before Phase 4:** `GET /feedback/faculty/{id}` returns no comment text until the Phase 4 pipeline has moderated and redacted it (`comments_status: "awaiting_analysis"`). Rating averages appear only from `MIN_RESPONSES_FOR_DISPLAY` responses.
- **Seed:** `python -m app.seed` creates synthetic demo data with every document marked `is_synthetic`.

*Changed in Phase 4 (2026-10-20):*
- **Analysis runs:**
  - Analysis runs in one worker thread per API process, with its own synchronous PyMongo client, instead of FastAPI background tasks. CPU-bound model calls would otherwise block the event loop.
  - Each submission is queued for analysis (`ANALYSIS_ON_SUBMIT=true`); admins run a whole cycle to catch up.
  - Jobs left running when the server stops are marked `interrupted` on start-up; re-running is safe because results are cached per `response_id + model_version`.
- **Added endpoints:** `GET /analysis/summary?cycle=` and `GET /analysis/jobs`.
- **Moderation queue:** items carry the flagged sentence offsets and that sentence's sentiment. The admin sees redacted text only, never the raw answer.
- **Scoring:**
  - **Toxicity** is the max of the 7 harm labels of `unitary/unbiased-toxic-roberta`; the identity-mention labels are ignored.
  - **Teaching aspects:** a sentence gets at most 2. The second must match the lexicon or be within 0.12 similarity of the first.
- **Sarcasm:** `SARC_FLAG` defaults to **0.95** (was 0.70). The tweet-trained irony model scores sincere praise near 0.98; see `docs/MODEL_CHECK.md`.
- **Known limitation:** the toxicity model hides compliments that contain an insulting word ("…without making us feel stupid"). These stay hidden until an admin approves them, and the queue marks them as possible false alarms.

*Changed in Phase 5 (agreed with the user, 2026-10-20):*
- **When summaries run:** after every analysis run and moderation decision, for teaching forms at or above `MIN_RESPONSES_FOR_DISPLAY`. They are stored in a `summaries` collection (unique per form) and rebuilt only when a fingerprint of the form's aggregate changes. The fingerprint also includes whether an LLM is configured, so adding a Groq key upgrades template summaries on the next run. `POST /analysis/summaries?cycle=` (admin) forces a rebuild.
- **No-LLM summary:** strengths and improvements are chosen from the aspect counts (an aspect needs at least 2 mentions) and cite their evidence ids, so they are grounded by construction. Next steps come from a fixed table (`SUGGESTED_ACTIONS` in `feedback_spec.py`). distilbart writes only an optional "digest" of the strongest evidence, labelled as automatic on the page, and the overall sentence is templated from the sentiment split.
- **Profile generation:** the claim check verifies numbers, venue- or award-like phrases and achievement titles against the facts. Research areas must appear in the facts, and highlights must cite real evidence ids.
  - TF-IDF keywords are used only when there are at least 3 publications. Phrases containing a stopword or a generic research word are dropped.
  - Drafts store the rejected claims when the template was used instead.
  - The approved profile (`GET /faculty/{id}/profile`) is readable by all staff, without evidence ids.
- **Added endpoint:** `GET /faculty/{id}/evidence?ids=` resolves evidence ids to redacted, visible answers with highlight offsets.
- **Unified page (§11.4) forms:** the net sentiment "gauge" and the sentiment "donut" are one headline figure plus a labelled 100% bar. The aspect "radar" and the polarity bars are one table: a diverging comment bar per aspect, with the mean rating and a ratings-vs-comments badge on the same row. Ordered-scale shares read better as diverging bars (dataviz guidance), and a table keeps the 8 aspects comparable on one baseline.
- **Demo seed:** each teacher also gets a few synthetic profile facts (qualifications, one current role, 2–4 publications, sometimes an award). Venues and awards are marked "(demo)". A separate RNG leaves the seeded responses unchanged.

*Changed in Phase 6 (agreed with the user, 2026-10-20):*
- **Bias panel scope:** the bias & sarcasm panel is computed for one department at a time. The admin picks any department; comparisons are never pooled across departments, because subjects differ. This is how the roles table's "institution-wide" reads for admins.
- **Thresholds:** `BIAS_MIN_GROUP_FACULTY` (default 3) and `BIAS_MIN_GROUP_ANSWERS` (default 30) per group. Below either, the API returns group sizes only.
  - Only teachers with "female" or "male" recorded form groups. Others are left out and counted.
  - The panel never returns names. The department table never returns gender.
- **Rating gap ("Likert gap with confidence intervals"):** women's mean minus men's per aspect, with a 95% **Welch t-interval over teacher averages** (each teacher counts once). Ratings of one teacher are not independent, so treating responses as the unit would give falsely narrow intervals. A cluster bootstrap was tried first and dropped: with 3 teachers per group it has only 10 distinct resamples, and on the seed it called three aspects "clear" that were really individual teachers' differences.
- **Gendered language:** answers per 1,000 that use at least one ability word or one warmth word (word-boundary match on moderated, redacted text). The lists are in `feedback_spec.py` and shown on the page.
- **Added parameters and behaviour:**
  - `GET /analytics/sarcasm` takes either `department=` (rates per teacher; HoD or admin) or `faculty=` (answer ids for the evidence drawer).
  - Analytics endpoints default to the newest cycle with teaching forms when `cycle=` is omitted.
- **Department overview:** a teacher's top strength and area to improve use the same rule as the summaries (`summarize.choose_aspects`), applied to their combined offerings.
- **Demo seed:** one more CSE teacher (Mr. Naveen Kumar, CS504 Operating Systems). CSE then has 3 women and 3 men and shows the comparison; ECE (2 women, 3 men) shows the "too small" state. He is added last, so earlier responses are identical.

*Changed in Phase 7 (agreed with the user, 2026-10-20):*
- **ATR level:** Action Taken rows are **department × aspect** (and department × curriculum item, plus a "syllabus comments" row when most comments are critical), not teacher × course. The report is published on the college website, so it never names or scores an individual teacher. Teacher-level detail stays inside the app.
- **`action_taken` collection:** `cycle_id, department_id, kind (teaching | curriculum | other), key, label, issue, evidence_count, evidence_ids, action, responsible, timeline, status (draft | approved), source, edited`. It is unique on cycle + department + kind + key.
  - Re-drafting replaces only untouched drafts. It never overwrites an edited or approved row.
  - An edit reopens an approved row.
- **Export gate:** `GET /reports/feedback/{cycle}.pdf|.docx` returns 409 until every row is approved. `?draft=true` gives a preview at any time, marked "DRAFT – not for submission" on every page. Exports are admin-only and audited.
- **Added endpoints:**
  - `POST /reports/feedback/{cycle}/actions` (manual row);
  - `PUT /reports/feedback/{cycle}/actions/{id}` (edit or approve; replaces the single `PUT …/actions`);
  - `DELETE …/actions/{id}` (admin);
  - `GET …/actions/{id}/evidence` (the redacted sentences behind a row, for the admin or the department's HoD);
  - `GET …/status` (readiness).
- **Report sections** follow §12, with the methodology in plain words and the models listed by ID.
  - Charts are rendered with matplotlib.
  - The PDF (fpdf2, with DejaVu Sans from matplotlib for Unicode) and the DOCX (python-docx) are drawn from one list of content blocks, so they say the same thing.
- **HoD approval** happens in a third tab, "Action taken", on Department insights.
- **Dev dependency:** `pypdf` (in `requirements-dev.txt`), used only by tests that read the exported PDF back.

*Changed before Phase 8 (agreed with the user, 2026-10-20): demo data set in the user's college:*
- **Institution:** `INSTITUTION_NAME` defaults to "Maturi Venkata Subba Rao (MVSR) Engineering College".
- **Departments:** the seed creates MVSR's 8 academic units (mvsrec.in/departments.php). Only CSE and ECE get demo staff, students and feedback.
- **Courses:** the seed's offerings use real semester-V course codes and names from MVSR's R21 B.E. scheme, in the same order, so the random draws are unchanged.
- **People stay fictional:** no real teacher's name appears in the seed. "Mr. Suresh Kumar" was renamed "Mr. Farhan Siddiqui" to avoid any chance of matching real staff.
- **Roll numbers:** these use the Osmania University format, `ROLL_NO_REGEX=\b\d{4}-\d{2}-\d{3}-\d{3}\b`, for example 2451-24-751-999 (college code 2451, admission year, branch code, serial).
  - The user confirmed 751 = CSIT.
  - The seed uses 733 (CSE) and 735 (ECE); the user confirmed both on 2026-10-21.
  - The same pattern drives PII redaction.

*Changed in Phase 8 (agreed with the user, 2026-10-21):*
- **Public data:** the evaluation uses the RateMyProfessors sample by Jibo He (Mendeley Data, DOI 10.17632/fvtfjyvw7d.2, CC BY 4.0). The licence was checked on the dataset page.
  - `python -m ml.import_items --rmp` keeps only the comment (redacted by the app's PII step, the professor's name becoming `[FACULTY]`), the student's own star rating and a one-way professor key. The raw CSV is gitignored.
  - Sets: 300 comments to label (balanced by star band), about 3,000 for a benchmark scored against the star ratings (80/20 split by professor), and 20 professors for reference summaries.
  - The app's own real comments join the labelling queue with `--app`, for admin annotators only.
- **Extra benchmark:** sentiment is also scored against each student's star rating (RateMyProfessors bands: 3.5–5 positive, 2.5–3 neutral, 1–2 negative). It is reported as weak labels, in addition to the human gold set, never instead of it.
- **Annotators** are a flag on staff accounts (`annotator: annotator | adjudicator`, set by the admin; never students), not a fifth role. Faculty and HoD annotators see only public comments. Labels from demo accounts never count in `ml.evaluate`.
- **Gold:** an item's gold label is the two annotators' label when they agree on sentiment and every aspect; otherwise it is the adjudicator's decision. The adjudicator's form starts blank.
- **Endpoints added** to §10's `/labels/next`, `POST /labels`, `/evaluation/results` and `POST /survey`:
  - `/labels/progress`, `/labels/disagreements`, `/labels/resolve`;
  - `/labels/groups/next` and `/labels/groups/{id}/reference`;
  - `/labels/grounding/next` and `/labels/grounding`;
  - `/survey/mine`.
- **Fine-tuning:** DistilBERT is fine-tuned on CPU (2 epochs, 128 tokens) only with `ml.evaluate --finetune`, on the benchmark, and on gold once there are 300 gold labels. BERTScore uses `distilbert-base-uncased`, not the 1.4 GB default. Both models are listed in `registry.EVAL_MODELS`, outside `model_version()`, so cached analyses stay valid.
- **`ASPECT_SIM`** tuning is reported, not applied automatically.
- **Moderation/PII set:** the 50 sentences were written by hand for this project, with labels by construction. RESULTS.md says so.

---

## 10. API (all under `/api`; JSON; JWT bearer)
- **auth:** `POST /auth/login`, `POST /auth/refresh`, `POST /auth/change-password`, `GET /auth/me`
- **users/admin:** `GET/POST /users`, `POST /users/bulk`, `PATCH/DELETE /users/{id}`, `GET/POST /departments`, `GET/POST /courses`, `POST /courses/{id}/enrol`
- **profiles:** `GET/PUT /faculty/{id}/profile-data`, `POST /faculty/{id}/import/orcid`, `POST /faculty/{id}/import/semantic-scholar`, `POST /faculty/{id}/imports/{item}/accept`, `POST /faculty/{id}/profile/generate`, `GET /faculty/{id}/profile/versions`, `PUT /faculty/{id}/profile/versions/{v}`, `POST /faculty/{id}/profile/versions/{v}/approve`, `GET /faculty/{id}/profile` (approved, public within the institution)
- **cycles/forms:** `GET/POST /cycles`, `POST /cycles/{id}/publish`, `POST /cycles/{id}/close`, `GET /forms/my` (student), `GET /forms/{id}`
- **feedback:** `POST /forms/{id}/responses` (student; one per form), `GET /feedback/faculty/{id}?cycle=&course=` (moderated + redacted only, min-responses rule)
- **analytics:** `POST /analysis/run?cycle=`, `GET /analysis/status/{job}`, `GET /analytics/faculty/{id}?cycle=&course=`, `GET /analytics/department/{id}?cycle=`, `GET /analytics/bias?department=&cycle=`, `GET /analytics/sarcasm?faculty=&cycle=`
- **unified page:** `GET /faculty/{id}/overview?cycle=` (approved profile + aggregates + summary in one call)
- **moderation:** `GET /moderation/queue`, `POST /moderation/{id}/decision`
- **Feedback report:** `POST /reports/feedback/{cycle}/draft`, `GET/PUT /reports/feedback/{cycle}/actions`, `GET /reports/feedback/{cycle}.pdf`, `GET /reports/feedback/{cycle}.docx`
- **evaluation:** `GET /labels/next`, `POST /labels`, `GET /evaluation/results`, `POST /survey`
- **health:** `GET /health`, `GET /health/models`

---

## 11. Frontend pages (React + Recharts + Tailwind)
1. **Login / change password**
2. **Student:** My forms → Feedback form (Likert per aspect + 3 text boxes, character counter, autosave draft in component state) → Thank-you
3. **Faculty:** Dashboard → **My unified page** → Profile editor (sections + ORCID/S2 import with accept/reject) → Generated profile review (draft vs facts, edit, approve) → Improvement responses → Usefulness survey
4. **Unified faculty page (the hero screen):**
   - **Left:** photo, headline, bio, research areas (chips), recent publications (with tldr), achievements.
   - **Right, top:** cycle and course selectors, response count, net sentiment gauge, sentiment donut.
   - **Right, middle:** aspect radar chart (mean Likert) + aspect polarity stacked bars (text) with a Likert–text agreement badge.
   - **Right, bottom:** strengths and improvements cards. Clicking a card opens the evidence drawer with highlighted redacted sentences.
   - **Footer:** emotion mix bar and a "possibly sarcastic" count with a link to the list.
5. **HoD:** department overview (faculty table with net sentiment, top strength and top improvement per person, sortable), bias & sarcasm panel, ATR approval
6. **Admin:** setup (departments, users, courses, cycles, forms), analysis runner with progress, moderation queue, Feedback report builder (editable ATR table → export), labelling tool, evaluation results, model health
7. **Bias & sarcasm panel:**
   - Gendered-language rates per 1,000 comments (e.g., *brilliant/genius/smart* vs *helpful/caring/organised*) by faculty gender group, at department level only, shown **only if each group has ≥ 3 faculty**.
   - Likert gap between groups with confidence intervals.
   - Emotion mix by group.
   - Sarcasm-flag rate.
   - A permanent caveat banner: the panel indicates possible bias in *student evaluations*, not in faculty.

Charts must use accessible colours (not red/green only), have text labels and empty states, and show loading skeletons.

---

## 12. Feedback report (PDF + DOCX)
1. Cover: institution name (config), cycle, generated date
2. Feedback collection summary: forms, responses, response rate per department and course; stakeholder coverage (students only in this version — stated honestly)
3. Methodology: questionnaire, anonymity, NLP pipeline in plain language, models used, moderation
4. Analysis: institution- and department-level sentiment, aspect scores (charts rendered as PNG via matplotlib for the export), top themes with anonymised sample comments (moderated + redacted only)
5. Curriculum feedback analysis (1.4.1)
6. **Action Taken Report** table: Issue | Aspect | Evidence (count) | Action | Responsible | Timeline | Status. The LLM drafts it from improvements; admin and HoD must edit or approve each row before export.
7. Statement for website publication (1.4.2 option A: collected, analysed, action taken, available on website) + signature blocks for the Administrator and Principal

---

## 13. Non-functional requirements
- **Security:** bcrypt, JWT, role checks on every route, CORS limited to the frontend origin, rate-limited login, input length limits (≤ 2,000 chars per text answer), audit log for admin actions.
- **Privacy:** salted student hashes, minimum-responses rule, redaction before display, no student identity in any analysis output or export. Align with India's DPDP Act principles (purpose limitation, minimal data).
- **Performance on CPU:** a 300-response cycle fully analysed in < 10 min on a 4-core laptop; API p95 < 500 ms for cached analytics; first-run model download documented.
- **Reliability:** the app works with no Groq key (fallbacks) and with no internet after models are downloaded (except the LLM and imports).
- **Testing:** pytest coverage ≥ 70% for `app/`; Postman collection with example requests for every endpoint.
- **Docs:** README with setup for Windows/Mac/Linux, architecture diagram (Mermaid), screenshots, evaluation results table from `ml/results`, limitations, future work (code-mixed support, trends, chatbot).

---

## 14. Build phases (stop after each one for review)
| Phase | Deliverable | Done when |
|---|---|---|
| **0 Scaffold** | Repo structure, venv/requirements (CPU torch), Vite app, Tailwind, MongoDB connection and indexes, `/health`, model registry with `--download`, `docs/MODEL_CHECK.md` (RAM and latency of every model on this PC), pytest and lint setup, `.env.example`, `.gitignore`, first commit | Both servers start; health is green; every model loads on CPU and is measured |
| **1 Auth & admin setup** | Users, roles, JWT, departments, courses, enrolment, bulk user add, admin UI | Can log in as each role; forbidden routes return 403 (tested) |
| **2 Profiles** | Profile data editor, ORCID + Semantic Scholar import with accept/reject | Real ORCID iD imports works correctly |
| **3 Feedback collection** | Cycles, forms (teaching + curriculum), student form UI, one-response rule, min-responses rule, `seed.py` with synthetic demo data | Student submits once; second submit is rejected |
| **4 NLP pipeline** | Preprocess, PII, moderation + queue, sentiment, aspects + evidence, emotion, sarcasm, background jobs, aggregates | Seeded cycle analyses end to end on CPU within the budget; results cached |
| **5 Summaries & profile generation** | `llm.py` (Groq + fallback), grounded summaries, profile generation + validation + approval, **unified faculty page** | Page renders profile + insights; evidence drawer highlights sentences; works with the Groq key removed |
| **6 Analytics & bias panel** | Faculty/department dashboards, bias & sarcasm panel with thresholds and caveats | Charts read from the API; panel hides itself when groups are too small |
| **7 Feedback report** | Draft ATR, editable table, PDF + DOCX export | Exported files open correctly and contain no unredacted text |
| **8 Evaluation** | Labelling tool, kappa, baselines vs transformer, aspect/PII/summary metrics, survey, `RESULTS.md`, evaluation page | `python -m ml.evaluate` produces real results files |
| **9 Polish** | Postman collection, README, screenshots, demo script (`docs/DEMO.md`, 5-minute walkthrough), coverage ≥ 70%, final CPU performance check | Fresh clone → setup → demo works by following the README |

*Changed after Phase 9 (2026-10-21), found when the user added a Groq key:*
- **Summary topics come from the counts.** With the key set, Groq listed a teacher's punctuality as a strength: it cited two real positive sentences, although 12 of 19 punctuality comments were critical. Each point cited a real sentence, but the overall picture was wrong.
  - The counts rule (`summarize.choose_aspects`, shared with the template path, analytics and the Feedback report) now decides which aspects are strengths and which need work.
  - The LLM sees only those aspects, each with its own evidence of the matching polarity, and only writes the wording.
  - Items about any other aspect, or citing evidence outside the aspect, are dropped. A chosen aspect the LLM skipped gets the template sentence (`filled_from_template`).
- **Groq rate limits:** the free tier allows 8,000 tokens a minute. On a 429, `llm.py` waits as long as Groq asks, up to 30 s per call in total, before using the fallback.
- **Tests never call live APIs:** `conftest.py` blanks `GROQ_API_KEY` and `S2_API_KEY`, whatever `.env` holds.
