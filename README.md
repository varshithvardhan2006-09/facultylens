# FacultyLens

[![CI](https://github.com/varshithvardhan2006-09/facultylens/actions/workflows/ci.yml/badge.svg)](https://github.com/varshithvardhan2006-09/facultylens/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB)
![React 18](https://img.shields.io/badge/React-18-61DAFB)
![MongoDB](https://img.shields.io/badge/MongoDB-8-47A248)

Faculty profile generation and student feedback evaluation, using text summarization and sentiment analysis.

FacultyLens gives each teacher one page that joins a generated profile with evidence-backed insights from anonymous student feedback. It runs on a CPU, and works offline once its models are downloaded.

![Faculty page](docs/screenshots/03-faculty-page.png)

## Features

- **Faculty page:** a fact-checked profile beside each course's feedback.
- **Aspect-level sentiment:** every strength or area to improve links to the sentences behind it.
- **Privacy first:** personal details are redacted and abuse is held for review before a teacher reads anything.
- **Anonymous by design:** students are stored only as a one-way code per form, and comment detail is hidden below 5 responses.
- **Bias and sarcasm panel:** compares feedback across groups and flags answers that may be sarcastic.
- **Feedback report:** department findings and an Action Taken Report, exported as PDF and Word.
- **Works without an LLM:** Groq writes better summaries, but the app falls back to templates without a key.

| Evidence behind every point | Bias and sarcasm panel | Feedback report |
|---|---|---|
| ![Evidence drawer](docs/screenshots/04-evidence-drawer.png) | ![Bias panel](docs/screenshots/06-bias-panel.png) | ![Feedback report](docs/screenshots/08-feedback-report.png) |

## Tech stack

| Area | Tools |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Recharts |
| Backend | FastAPI, Python 3.13, Pydantic |
| Database | MongoDB |
| NLP | Hugging Face Transformers on CPU PyTorch, sentence-transformers, spaCy, scikit-learn, NLTK |
| LLM (optional) | Groq |
| Reports | fpdf2, python-docx, matplotlib |

## Getting started

You need Python 3.13, Node 22+, MongoDB running locally, and about 7 GB of free disk for the models. No GPU is needed; 8 GB of RAM is enough.

Run each command on its own line. Windows PowerShell 5.1 doesn't support `&&`.

**1. Backend,** from the `backend` folder:

```bash
py -3.13 -m venv .venv
```

```bash
.venv\Scripts\activate
```

On Mac or Linux, use `python3.13 -m venv .venv` and `source .venv/bin/activate`.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

```bash
pip install -r requirements-dev.txt
```

```bash
python -m spacy download en_core_web_sm
```

**2. Settings:** copy `.env.example` to `.env`, then set `JWT_SECRET` and `STUDENT_HASH_SALT` to random strings of at least 32 characters. The API won't start with the placeholders. `GROQ_API_KEY` is optional.

**3. Models and demo data:**

```bash
python -m app.nlp.registry --download
```

```bash
python -m app.seed
```

The seed command prints the demo accounts. All the people and comments in the demo data are fictional.

**4. Run the API:**

```bash
uvicorn app.main:app --port 8000
```

**5. Run the frontend,** in a second terminal from the `frontend` folder:

```bash
npm install
```

```bash
npm run dev
```

Open http://localhost:5173, sign in as the admin, and run **Analysis**. The first run takes a few minutes while the models load.

## How it works

![FacultyLens architecture: client, application, AI and data tiers](docs/architecture.png)

| Tier | What runs there |
|---|---|
| **Client** | A React 18 single-page app. Each role gets its own pages, and an Axios client refreshes the session token silently. |
| **Application** | FastAPI on Uvicorn. Every request passes CORS, security headers, rate limiting, JWT authentication with a role check, and validation, then reaches one of 16 routers. Services handle access control, profile generation, the report builder and background jobs. |
| **AI** | A background worker on CPU-only PyTorch. Each answer is normalised, cleared of personal details, moderated, then scored for sentiment, irony, emotion and the 8 teaching aspects; summaries come last. Models load once from the local Hugging Face cache. |
| **Data** | MongoDB, either Atlas or a local server. Results are stored per model version, so nothing is scored twice. |

Outside services are optional. Groq writes the summaries, falling back to a local DistilBART model when it is unavailable, and ORCID and Semantic Scholar supply publications for profiles.

## Who uses it

| Role | What they do |
|---|---|
| Student | Gives anonymous feedback on teaching and the syllabus |
| Faculty | Reads their feedback, and reviews and approves their profile |
| Head of department | Sees department insights and the bias panel, and approves actions |
| Admin | Manages users, courses and cycles, moderates, and exports the Feedback report |

## Evaluation

Measured on public student reviews scored against each student's own star rating, which is a weak label for tone. Synthetic demo data is never used.

| Model | Accuracy | Macro-F1 |
|---|---:|---:|
| VADER | 0.741 | 0.517 |
| TF-IDF + Logistic Regression | 0.789 | **0.671** |
| TF-IDF + Random Forest | 0.764 | 0.552 |
| Twitter-RoBERTa (pretrained) | **0.815** | 0.647 |
| DistilBERT (fine-tuned on CPU) | 0.807 | 0.653 |

Human-labelled scores are still pending. See the [full results](backend/ml/results/RESULTS.md).

## Testing

From `backend`:

```bash
pytest -q
```

```bash
ruff check .
```

From `frontend`:

```bash
npm run lint
```

```bash
npm run build
```

The fast suite needs local MongoDB and uses its own test database. Add `-m slow` to load the real models. CI runs the fast suite, lint and the build on every push.

## Deployment

- Serve the app over HTTPS, with the frontend and API on the same site.
- In `.env`, set `COOKIE_SECURE=true`, `API_DOCS=false` and `FRONTEND_ORIGIN`.
- Run one uvicorn worker with `--no-access-log`, on a server with at least 4 GB of RAM.
- Skip the seed. Create the first admin with `python -m app.cli create-admin`.
- Never commit `.env`.

## Limitations

- English only: code-mixed comments are flagged, not understood.
- The abuse model reacts to words, so fair criticism can be hidden until a person reviews it.
- Generated profiles should be read before approval, because checks can't catch every unsupported phrase.

## Documentation

- [Demo script](docs/DEMO.md)
- [Requirements](docs/SPEC.md)
- [Design system](docs/DESIGN.md)
- [Model speed and memory](docs/MODEL_CHECK.md)
- [Postman collection](postman/FacultyLens.postman_collection.json)

## Credits

- Evaluation data: Jibo He, *Big Data Set from RateMyProfessor.com for Professors' Teaching Evaluation*, Mendeley Data, [DOI 10.17632/fvtfjyvw7d.2](https://data.mendeley.com/datasets/fvtfjyvw7d/2), CC BY 4.0. The raw file isn't included here.
- Pretrained models belong to their authors on Hugging Face; see `backend/app/nlp/registry.py`.

## License

[MIT](LICENSE)
