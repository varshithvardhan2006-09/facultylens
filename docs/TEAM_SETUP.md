# Team setup: labelling from your own laptop

FacultyLens now keeps its data in one shared cloud database (MongoDB Atlas, free tier), so
everyone on the team can run the app on their own laptop and label into the same place. You
do **not** need MongoDB installed, the 7 GB of models, or the demo data: all of that is
already in the shared database.

Allow about 30 minutes the first time, mostly for downloads.

## What you need

- **Python 3.13** and **Node 22 or newer**
- **Git**
- The **`.env` file**, which the project owner sends you privately. It holds the shared database
  address and its password, so never post it in a group chat, a commit, or a screenshot.

## 1. Get the code

```bash
git clone https://github.com/varshithvardhan2006-09/facultylens.git
```

```bash
cd facultylens
```

(If you already have it, run `git pull` instead.)

## 2. Backend

Run each command on its own line. On Windows PowerShell, `&&` does not work.

```bash
cd backend
```

Windows:

```bash
py -3.13 -m venv .venv
```

```bash
.venv\Scripts\activate
```

Mac or Linux: `python3.13 -m venv .venv`, then `source .venv/bin/activate`.

Install the CPU build of PyTorch first, then the rest:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

```bash
pip install -r requirements.txt
```

Save the `.env` file the project owner sent you as `backend/.env` (same folder as `requirements.txt`).

**Do not run** `python -m app.seed` or `python -m app.nlp.registry --download`. The shared
database already has the data, and labelling needs no models.

Start the API:

```bash
uvicorn app.main:app --port 8000
```

Leave this window open.

## 3. Frontend

In a second terminal, from the `facultylens` folder:

```bash
cd frontend
```

```bash
npm install
```

```bash
npm run dev
```

Open http://localhost:5173 and sign in with the account the project owner created for you.

## 4. Label

Open **Labelling** in the left rail.

- Keys **1, 2, 3** choose negative, neutral, positive; **Enter** saves and moves on.
- Label **on your own**: don't discuss comments with the other annotator, because the
  evaluation measures how far two people agree without talking.
- Your progress is saved after every comment, so you can stop and continue any time.

## If something goes wrong

| What you see | What to do |
|---|---|
| The API stops with a database or timeout error | Check your internet; the database is in the cloud. Then tell the project owner, in case the network access list needs your connection added. |
| "Invalid credentials" when signing in | Ask the project owner to reset your password on the Users page. |
| `pip` fails on `torch` | Make sure you installed the CPU build first (the `--index-url` line). |
