# FacultyLens

Faculty profile generation and student feedback evaluation, using text summarization and sentiment analysis.

Each teacher gets one page with a generated profile next to an analysis of their students' anonymous feedback.

![Faculty page](docs/screenshots/03-faculty-page.png)

## Features

- Sentiment for each of 8 teaching areas, with the students' own sentences as proof
- Abuse hidden and personal details removed before a teacher reads anything
- Anonymous feedback, shown only from 5 responses
- Sarcasm and gender-bias checks
- Action Taken Report as PDF and Word

## Tech stack

React, FastAPI (Python 3.13), MongoDB, Hugging Face Transformers on CPU, Groq (optional).

## Getting started

From `backend`:

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
python -m spacy download en_core_web_sm
```

Copy `.env.example` to `.env` and set `JWT_SECRET` and `STUDENT_HASH_SALT`.

```bash
python -m app.nlp.registry --download
python -m app.seed
uvicorn app.main:app --port 8000
```

From `frontend`:

```bash
npm install
npm run dev
```

Open http://localhost:5173.

## Architecture

![FacultyLens architecture](docs/architecture.png)

## Presentation

[Project presentation (PDF)](docs/presentation/FacultyLens-Presentation.pdf)

## Credits

Evaluation data: J. He, RateMyProfessor.com dataset, Mendeley Data, [doi:10.17632/fvtfjyvw7d.2](https://data.mendeley.com/datasets/fvtfjyvw7d/2), CC BY 4.0.

## License

[MIT](LICENSE)
