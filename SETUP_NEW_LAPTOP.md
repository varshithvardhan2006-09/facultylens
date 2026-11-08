# Setting up FacultyLens on a new laptop

This guide moves the whole project to another Windows laptop: the code, your secrets, your data, and
the Claude setup, so Claude on the new laptop works exactly as before.

**Quickest way:** once you have cloned the repo and opened it in Claude Code, tell Claude:

> Set up this project using SETUP_NEW_LAPTOP.md.

Claude follows the steps below in order, checks each one, and stops to ask you only where it needs
something it is not allowed to handle itself (secrets, sign-ins, files from the old laptop).

---

## Part 0. Before you leave the old laptop

Copy these to a USB drive or your private cloud storage. They are **not in git**, on purpose.

| What | Where on the old laptop | Why |
|---|---|---|
| `backend/.env` | `C:\Projects\FacultyLens\Facultylens\backend\.env` | Your secrets: JWT secret, student-hash salt, Groq key, database address. **Keep it private.** |
| A fresh data backup | Run the command below, then copy the folder | Users, feedback, analysis results, labels |
| *(Optional)* `facultylens-team-accounts.txt` | `C:\Projects\FacultyLens\` | Teammates' temporary passwords. Delete it once they have signed in. |

Make a fresh backup on the old laptop (from the `backend` folder, with its virtual environment active):

```bash
python -m app.cli backup "../../facultylens-backup-latest"
```

It writes one JSON file per collection, plus `manifest.json` with the counts. Sign-in sessions are left
out, so everyone just signs in again on the new laptop.

> **Keep the same `.env`.** The `STUDENT_HASH_SALT` in it is what stops a student answering the same
> form twice. If the new laptop uses a different salt, restored responses no longer match. Copy the
> file; don't regenerate it.

---

## Part 1. Install the tools (you do this)

Install these on the new laptop, accepting the defaults unless noted.

| Tool | Version | Notes |
|---|---|---|
| Git | latest | Sign in to GitHub when asked; the repo is private. |
| Python | **3.13** | Tick **"Add python.exe to PATH"**. Check with `py -3.13 --version`. |
| Node.js | **22 LTS or newer** | Includes `npm` and `npx`. Check with `node --version`. |
| MongoDB Community Server | **9.0** | Install **as a Windows service**, which starts automatically. MongoDB Compass (the viewer) is optional. |
| VS Code | latest | Your editor. |
| Claude desktop app | latest | Sign in with the same Claude account as before. |

About 9 GB of free disk is needed (7 GB of it for the language models). No graphics card is needed.

---

## Part 2. Get the code

```bash
git clone https://github.com/varshithvardhan2006-09/facultylens.git "C:\Projects\FacultyLens\Facultylens"
```

Open that folder in the Claude desktop app (Code tab). From here, Claude can do Parts 3 to 7.

---

## Part 3. Claude setup

1. **Project rules** are already in the repo: `CLAUDE.md` (working rules) and `docs/SPEC.md`
   (requirements).
2. **Tool connections:**
   - `.mcp.json` is in the repo: Context7 (library docs), Playwright (browser testing) and MongoDB. They
     start through `npx`, so Node must be installed.
   - Hugging Face, Figma and Canva connections need you to sign in from the app (`/mcp`).
3. **Design skills** used on this project (impeccable, design-taste-frontend, emil-design-eng,
   frontend-design, dataviz) come with the Claude app, so check they are listed.
4. **graphify** (optional, the knowledge-graph tool):

   ```bash
   py -3.13 -m pip install --user uv
   ```

   ```bash
   py -3.13 -m uv tool install graphifyy
   ```

   ```bash
   graphify install --platform claude
   ```

---

## Part 4. Backend

Run each command on its own line. In PowerShell, `&&` does not work.

```bash
cd backend
```

```bash
py -3.13 -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

```bash
pip install -r requirements-dev.txt
```

```bash
python -m spacy download en_core_web_sm
```

**Secrets (you do this):** put the `.env` from the old laptop at `backend\.env`. Claude can open the
folder for you, but must never print the file's contents.

- If the old `.env` is lost: `copy .env.example .env`, then set `JWT_SECRET` and `STUDENT_HASH_SALT` to
  long random strings. Restored responses then no longer match their one-response check, which is fine
  for a demo.
- Paste your Groq key into `GROQ_API_KEY` yourself. Without one, the app writes summaries locally
  instead.

Download the language models once (about 7 GB; this is the step that needs a good connection):

```bash
python -m app.nlp.registry --download
```

---

## Part 5. Your data

MongoDB must be running (the Windows service). Pick one option:

**A. Restore your backup** (recommended; everything exactly as it was):

```bash
python -m app.cli restore "C:\path\to\facultylens-backup-latest"
```

It refuses to overwrite a database that already has data unless you add `--replace`, and it checks every
collection's count afterwards.

**B. Fresh demo data** (if you have no backup):

```bash
python -m app.seed
```

Then, after Part 6, sign in as the admin, open **Analysis** and press **Analyse waiting responses**
(about 3 minutes).

**C. Use the shared Atlas database:** set `MONGODB_URI` in `backend\.env` to the Atlas address, keep
exactly one `MONGODB_URI` line active, and restart the API. Add your own IP under **Database & Network
Access** in Atlas yourself. To fill an empty cluster, restore a backup as in option A.

---

## Part 6. Run it

Terminal 1 (backend, with `.venv` active):

```bash
uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
```

```bash
npm install
```

```bash
npm run dev
```

Open http://localhost:5173. Claude can instead start both through the app's preview servers
(`.claude/launch.json`: `api` and `web`).

Demo sign-ins (password: `DEMO_PASSWORD` in `.env.example`):

| Role | Sign in with |
|---|---|
| Admin | `admin@demo.facultylens.in` |
| Head of department | `padma.rao@demo.facultylens.in` |
| Faculty | `kavitha.reddy@demo.facultylens.in` |
| Student | `2451-24-733-002` |

---

## Part 7. Check that everything works

From `backend` (about 5 minutes):

```bash
python -m pytest -q -m "not slow"
```

From `frontend`:

```bash
npm run lint
```

```bash
npm run build
```

What "working" looks like:
- **Tests:** all pass (629 at the last count).
- **Lint:** nothing reported.
- **Build:** succeeds.
- **The app:** `http://localhost:5173` shows the landing page.
- **Signed in as the faculty demo:** My page shows the wall of notes.
- **System status** (as admin): the API and database show as connected.

---

## Instructions for Claude

Follow Parts 3 to 7 in order. Mark each step done only after its check passes. Specifically:

1. **Read first:** `CLAUDE.md`, `docs/SPEC.md`, then this file.
2. **Check the tools from Part 1** (`py -3.13 --version`, `node --version`, `git --version`, and that the
   `MongoDB` Windows service is running). Report anything missing and give the user the download page;
   do not install system software silently.
3. **Stop and ask the user:**
   - for the `.env` file and the backup folder (Part 0);
   - to paste any key or password themselves (open the file in their editor);
   - for every GitHub, Atlas, Hugging Face or Figma sign-in.

   Never type secrets, never print `.env`, never commit it.
4. **Long steps** (pip installs, the model download, the test suite) run in the background.
5. **If a step fails:**
   - read the error, fix the cause, and retry;
   - Windows quirks: use `py -3.13` if `python` is not found, and run one command per line in PowerShell;
   - if MongoDB is not reachable, start the `MongoDB` service.
6. **Finish with Part 7** and report the real results (test count, build, what the app showed).
