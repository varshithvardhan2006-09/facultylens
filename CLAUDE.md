# CLAUDE.md — FacultyLens (project-scoped, standalone)

> This file is **self-contained** and applies **only to this repository**. It does not import (`@`) or extend any other CLAUDE.md. If any other memory file (global/user/another project) conflicts with this one, **this file wins for this project**. Full requirements live in `docs/SPEC.md` — read both at the start of every session.

## 1. Project
**Title:** Faculty Profile Generation and Student Feedback Evaluation based on Text Summarization and Sentiment Analysis
**Short name:** FacultyLens · **Domain:** AI & NLP · **Type:** B.Tech mini project (Indian engineering college)

One page per faculty member that joins two things no public system currently combines:
1. **Auto-generated faculty profile** — written from qualifications, experience, research interests, publications and achievements (manual entry + optional ORCID / Semantic Scholar import).
2. **Student feedback evaluation** — overall sentiment (positive / negative / neutral), **teaching-aspect sentiment with highlighted evidence**, strengths & areas-for-improvement summaries, **moderation + PII redaction before faculty see anything**, a **bias & sarcasm panel**, and a **NAAC Criterion 1.4 Feedback Analysis + Action Taken Report** export.

### In scope (build all of these)
- F1 Unified faculty profile page (profile + feedback insights side by side)
- F2 Aspect-based sentiment with evidence highlighting
- F3 Moderation (toxicity) + PII redaction pipeline
- F4 NAAC 1.4 report export (PDF + DOCX)
- F5 Bias & sarcasm panel (emotion mix, sarcasm flags, department-level gendered-language check)
- F6 Evaluation module (baseline vs transformer, Cohen's kappa, ROUGE/BERTScore, faculty survey form)

### Out of scope (do NOT build unless I ask)
Code-mixed (Hinglish/Telugu-English) models, semester trend alerts, RAG chatbot, CSV/Excel feedback upload, mobile app, GPU training.

## 2. Fixed tech stack (do not swap without asking me)
- **Frontend:** React 18 + Vite, React Router v7 (`react-router` 7.18+, declarative mode; v6 had unpatched advisories), Axios, **Recharts**, Tailwind CSS
- **Backend:** **FastAPI** on Python 3.13, Pydantic v2 + pydantic-settings, **PyMongo Async API** (`pymongo.AsyncMongoClient`, async MongoDB; Motor is deprecated and past end of life, so don't use it), **PyJWT** (JWT), **pwdlib[bcrypt]** (password hashing; don't use passlib, which is unmaintained), slowapi (rate limit)
- **Database:** **MongoDB** (local `mongodb://localhost:27017` or Atlas free tier)
- **NLP:** **NLTK**, **HuggingFace Transformers** on **PyTorch CPU build**, sentence-transformers, spaCy `en_core_web_sm`, scikit-learn, **Pandas & NumPy**, `rouge-score` + `bert-score`
- **LLM:** **Groq API** (free tier) via the official `groq` Python SDK
- **Reports:** fpdf2 (PDF) + python-docx (DOCX)
- **Tooling:** Git & GitHub, Postman collection, pytest, VS Code

## 3. Hardware rule — CPU first
The demo PC is unknown and probably has **no GPU**. Everything must run acceptably on a 4-core CPU with 8 GB RAM.
- Install **CPU-only PyTorch** (`--index-url https://download.pytorch.org/whl/cpu`).
- Load each model **lazily, once** (module-level singleton) and **never** at import time of `main.py`.
- Run NLP in **FastAPI background tasks**, in **batches**, with `torch.set_num_threads()` from config. Use `torch.inference_mode()`.
- Truncate inputs to 256 tokens for classifiers.
- `ML_MODE=light` (default) uses the smaller models listed in SPEC §6; `ML_MODE=full` may use larger ones. Never require a GPU.
- Cache all analysis results in MongoDB — never re-run a model on a comment that already has results (version results by `model_version`).
- Expose `GET /api/health/models` showing which models are loaded, RAM use, and avg latency.

## 4. Repository layout
```
facultylens/
├── CLAUDE.md
├── docs/SPEC.md
├── backend/
│   ├── app/
│   │   ├── main.py  config.py  db.py  seed.py
│   │   ├── auth/        # JWT, password hashing, role dependencies
│   │   ├── schemas/     # Pydantic models
│   │   ├── routers/     # auth, users, faculty, profiles, forms, feedback, analytics, reports, evaluation, health
│   │   ├── nlp/         # preprocess, sentiment, aspects, summarize, moderation, emotion, sarcasm, bias, profile_gen, llm, registry
│   │   ├── services/    # orcid.py, semantic_scholar.py, naac_report.py
│   │   └── pipeline/    # background analysis jobs
│   ├── ml/              # baseline.py, evaluate.py, data/, results/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/  (src/pages, src/components, src/api, src/context, src/hooks)
└── postman/FacultyLens.postman_collection.json
```

## 5. Commands
| Task | Command |
|---|---|
| Create venv | `cd backend` then Windows `py -3.13 -m venv .venv` · Mac/Linux `python3.13 -m venv .venv` |
| Activate | Windows `.venv\Scripts\activate` · Mac/Linux `source .venv/bin/activate` |
| Install (run one at a time; `&&` fails in Windows PowerShell 5.1) | 1. `pip install torch --index-url https://download.pytorch.org/whl/cpu` 2. `pip install -r requirements.txt` 3. `python -m spacy download en_core_web_sm` |
| Pre-download models | `python -m app.nlp.registry --download` |
| Run API | `uvicorn app.main:app --reload --port 8000` (docs at `/docs`) |
| Seed demo data | `python -m app.seed` |
| Tests | `pytest -q` |
| Evaluation | `python -m ml.evaluate` → writes `ml/results/` |
| Frontend | `cd frontend && npm install && npm run dev` → http://localhost:5173 |

## 6. Working rules for Claude
1. Build **phase by phase** from `docs/SPEC.md` §14. Enter plan mode at the start of each phase, keep a task list, and **stop at the end of each phase** with a short demo checklist for me. Do not start the next phase until I say so.
2. All model calls go through `app/nlp/registry.py` (one place for model IDs, loading and versioning). If a model ID from SPEC fails to download/load, check Hugging Face for the closest working alternative, switch to it, and tell me what changed and why. Load the summarisation fallback with `AutoModelForSeq2SeqLM` + `AutoTokenizer` and call `generate()` directly instead of `pipeline("summarization")`, because pipeline task names changed in Transformers v5. Confirm this works in Phase 0.
3. All LLM calls go through `app/nlp/llm.py`: Groq client with `GROQ_MODEL`, automatic fallback to `GROQ_FALLBACK_MODEL` on model-not-found/deprecation errors, retries with backoff, a timeout, and a **no-LLM fallback** (HF summariser + templates) when `GROQ_API_KEY` is empty or Groq is down. The app must never crash because the LLM is unavailable.
4. LLM outputs must be **grounded**: pass only extracted facts/comments, ask for JSON, validate with Pydantic, and store the comment IDs that support every strength/improvement. Never invent publications or claims.
5. **Privacy:** students are anonymous to faculty. Store only `sha256(student_id + SALT)` for one-response-per-form checks. Faculty and HoD see only **moderated + redacted** text. Hide comment-level detail when a form has fewer than `MIN_RESPONSES_FOR_DISPLAY` (default 5) responses.
6. Roles: `admin` (IQAC), `hod`, `faculty`, `student`. Enforce on every endpoint via dependencies, and test the forbidden cases.
7. Secrets only in `.env`; keep `.env.example` current. Never commit `.env`.
8. Write pytest tests for every router and NLP function; mock heavy models in unit tests and keep one slow, marked integration test per model (`@pytest.mark.slow`).
9. Use Context7 for current library docs (FastAPI, PyMongo Async, Recharts, Transformers, Groq SDK) rather than guessing APIs.
10. UI: clean, academic, accessible (WCAG AA contrast, keyboard navigation), responsive. Every number on screen comes from the API. For **all** UI work, load and follow these skills:
    - `design-taste-frontend`: art direction and the app-screen rules (dashboards, admin views), plus its look-and-fix screenshot loop.
    - `impeccable`: hierarchy, layout, typography, colour, UX copy, empty/loading/error states, accessibility audit.
    - `emil-design-eng`: component polish, motion and interaction details (keep motion subtle and respect `prefers-reduced-motion`).
    - `frontend-design`: overall aesthetic direction.
    - `dataviz`: every Recharts chart (palette, labels, legends, dark mode).

    Settle one design direction (type scale, colour tokens, spacing, component style) when the first UI page is built, record it in `docs/DESIGN.md`, and reuse it on every later page.
11. After any UI change, open it in a real browser (the Playwright MCP, or the Claude desktop app's built-in browser), click through the flow, and fix console errors before reporting done.
12. Keep `postman/FacultyLens.postman_collection.json` updated with every endpoint.
13. Commit after each working step with a clear message. Never force-push.
14. Be honest in reports and the README: report real metrics from `ml/results/`, never made-up numbers.
15. On a new machine, follow `SETUP_NEW_LAPTOP.md` to set the project up.
