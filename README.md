# FacultyLens

[![CI](https://github.com/varshithvardhan2006-09/facultylens/actions/workflows/ci.yml/badge.svg)](https://github.com/varshithvardhan2006-09/facultylens/actions/workflows/ci.yml)

Faculty profile generation and student feedback evaluation, using text summarization and sentiment analysis.

FacultyLens gives each teacher one page that puts a generated profile next to an analysis of their students' anonymous feedback. It runs on an ordinary CPU.

![Faculty page](docs/screenshots/03-faculty-page.png)

## Features

- **Faculty page:** the teacher's profile next to the feedback for each course.
- **Sentiment per teaching area:** every strength or area to improve links to the sentences behind it.
- **Privacy:** abuse is hidden and personal details are removed before a teacher reads anything. Comments stay hidden below 5 responses.
- **Anonymous:** students are stored only as a one-way code per form.
- **Bias and sarcasm panel:** flags answers that may be sarcastic and checks for gender bias.
- **Feedback report:** an Action Taken Report, exported as PDF and Word.
- **Works without an LLM:** Groq writes the summaries; without it, a local model and templates do.

## Tech stack

| Area | Tools |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Recharts |
| Backend | Python 3.13, FastAPI, Pydantic |
| Database | MongoDB |
| NLP | Hugging Face Transformers on CPU PyTorch, sentence-transformers, spaCy, NLTK, scikit-learn |
| LLM (optional) | Groq |
| Reports | fpdf2, python-docx |

## Getting started

You need Python 3.13, Node 22, MongoDB and about 7 GB of free disk for the models. No GPU is needed.

**Backend**, from the `backend` folder (on Mac or Linux, use `python3.13` and `source .venv/bin/activate`):

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
python -m spacy download en_core_web_sm
```

Copy `.env.example` to `.env` and set `JWT_SECRET` and `STUDENT_HASH_SALT` to random strings of at least 32 characters. `GROQ_API_KEY` is optional.

```bash
python -m app.nlp.registry --download
python -m app.seed
uvicorn app.main:app --port 8000
```

The seed prints the demo accounts. All demo people and comments are fictional.

**Frontend**, in a second terminal from the `frontend` folder:

```bash
npm install
npm run dev
```

Open http://localhost:5173, sign in as the admin and run **Analysis**.

## How it works

![FacultyLens architecture](docs/architecture.png)

The React app talks to the FastAPI server. When a student submits a form, a background worker removes personal details, checks for abuse, and scores sentiment, sarcasm, emotion and the 8 teaching areas. Results are saved in MongoDB per model version, so nothing is scored twice.

| Role | What they do |
|---|---|
| Student | Gives anonymous feedback on teaching and the syllabus |
| Faculty | Reads their feedback, and edits and approves their profile |
| Head of department | Sees department results and the bias panel, and approves report actions |
| Admin | Manages users, courses and cycles, moderates comments, and exports the report |

## Evaluation

Sentiment accuracy on public RateMyProfessors reviews, labelled by each student's star rating:

| Model | Accuracy | Macro-F1 |
|---|---:|---:|
| VADER | 0.741 | 0.517 |
| TF-IDF + Logistic Regression | 0.789 | 0.671 |
| TF-IDF + Random Forest | 0.764 | 0.552 |
| Twitter-RoBERTa (used in the app) | 0.815 | 0.647 |
| DistilBERT (fine-tuned on CPU) | 0.807 | 0.653 |

Human-labelled scores are still pending. Full results: [RESULTS.md](backend/ml/results/RESULTS.md).

## Testing

```bash
pytest -q
ruff check .
```

Run these in `backend` (they need a local MongoDB). In `frontend`, run `npm run lint` and `npm run build`. CI runs all of these on every push.

## Deployment

Serve it over HTTPS and set `COOKIE_SECURE=true`, `API_DOCS=false` and `FRONTEND_ORIGIN` in `.env`. Skip the seed and create the first admin with `python -m app.cli create-admin`. Never commit `.env`.

## Documentation

- [Project presentation (PDF)](docs/presentation/FacultyLens-Presentation.pdf)
- [Requirements](docs/SPEC.md)
- [Demo script](docs/DEMO.md)
- [Setting up a new laptop](SETUP_NEW_LAPTOP.md)
- [Postman collection](postman/FacultyLens.postman_collection.json)

## Credits

Evaluation data: J. He, *Big Data Set from RateMyProfessor.com for Professors' Teaching Evaluation*, Mendeley Data, [doi:10.17632/fvtfjyvw7d.2](https://data.mendeley.com/datasets/fvtfjyvw7d/2), CC BY 4.0. Pretrained models belong to their authors on Hugging Face.

## License

[MIT](LICENSE)
