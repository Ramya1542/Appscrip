# Commands & Deployment Guide

Every command needed to set up, run, test, and push this project. Commands are
shown for **Windows PowerShell** first (this project was built on Windows), with
macOS/Linux (bash) variants where they differ.

> Run all commands from the project root: `D:\project`

---

## 0. One-time prerequisites

Install the tools you don't already have (Windows, via `winget`):

```powershell
winget install --id Python.Python.3.11 --scope user -e   # Python 3.11
winget install --id Git.Git -e                            # Git
winget install --id Docker.DockerDesktop -e               # Docker Desktop (optional but recommended)
winget install --id GitHub.cli -e                         # GitHub CLI (optional, for easy repo push)
```

macOS (Homebrew):

```bash
brew install python@3.11 git gh
brew install --cask docker
```

Verify:

```powershell
python --version    # or: py --version
git --version
docker --version    # if installed
```

---

## 1. Configure environment

```powershell
Copy-Item .env.example .env          # Windows PowerShell
# macOS/Linux:  cp .env.example .env
```

Then edit `.env` and set at least:

- `JWT_SECRET_KEY` — any long random string
- `ANTHROPIC_API_KEY` — **only** needed for real `/chat` answers (ingestion + retrieval work without it)

Generate a strong JWT secret:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 2. Run with Docker (recommended — one command)

Brings up PostgreSQL+pgvector, Redis, and the API together:

```powershell
docker compose up --build
```

- API:        http://localhost:8000
- Swagger UI:  http://localhost:8000/docs
- Health:      http://localhost:8000/health

### Useful Docker commands

```powershell
docker compose up -d --build          # run in the background
docker compose logs -f api            # tail the API logs
docker compose ps                     # list running services
docker compose down                   # stop and remove containers
docker compose down -v                # stop AND delete the database volume (fresh start)
```

### Enable the Kafka ingestion worker (optional good-to-have)

```powershell
# set INGEST_MODE=kafka in .env first, then:
docker compose --profile kafka up --build
```

---

## 3. Run locally without Docker

### 3a. Create a virtual environment & install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # PowerShell
# If activation is blocked, run once:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3b. Start a PostgreSQL + pgvector database

Easiest is a single Docker container just for the DB:

```powershell
docker run --name rag-pg -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag `
  -e POSTGRES_DB=ragdb -p 5432:5432 -d pgvector/pgvector:pg16
```

(If you have your own Postgres, ensure the `vector` extension is available and set
`DATABASE_URL` in `.env` accordingly. The app runs `CREATE EXTENSION vector` on startup.)

### 3c. Run the API

```powershell
uvicorn app.main:app --reload
```

The app creates the pgvector extension, all tables, and the vector index on startup.

### 3d. (Optional) Run the Kafka ingestion worker

Only if `INGEST_MODE=kafka` (needs a running Kafka broker):

```powershell
python -m app.workers.kafka_consumer
```

---

## 4. Run the tests

```powershell
pytest                 # quiet
pytest -v              # verbose (per-test)
```

Tests run fully offline — no database, Redis, Kafka, or API key required.

---

## 5. Try the API end-to-end (curl)

PowerShell note: use `curl.exe` (not the `curl` alias) or the examples below.

```powershell
$BASE = "http://localhost:8000"

# 1. Sign up -> capture the JWT
$signup = curl.exe -s -X POST "$BASE/auth/signup" `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"demo@example.com\",\"password\":\"supersecret123\"}' | ConvertFrom-Json
$TOKEN = $signup.access_token

# 2. Ingest a document
curl.exe -s -X POST "$BASE/documents" `
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" `
  -d '{\"title\":\"France\",\"text\":\"Paris is the capital of France. The Eiffel Tower is in Paris.\"}'

# 3. Check ingestion status (background mode)
curl.exe -s "$BASE/documents" -H "Authorization: Bearer $TOKEN"

# 4. Ask a question (needs ANTHROPIC_API_KEY for a real answer)
curl.exe -s -X POST "$BASE/chat" `
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" `
  -d '{\"query\":\"What is the capital of France?\"}'
```

bash equivalent:

```bash
BASE=http://localhost:8000
TOKEN=$(curl -s -X POST $BASE/auth/signup -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"supersecret123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST $BASE/documents -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"France","text":"Paris is the capital of France."}'

curl -s -X POST $BASE/chat -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"query":"What is the capital of France?"}'
```

---

## 6. Push to GitHub

### 6a. (Optional) Remove the assignment PDF before pushing

```powershell
Remove-Item .\FastAPI_AI_RAG_Assignment.pdf   # if you don't want it in the repo
```

### 6b. Initialise the repo and commit

`.gitignore` already excludes `.venv`, `.env`, and caches.

```powershell
cd D:\project
git init
git add .
git commit -m "FastAPI + AI (RAG) backend"
git branch -M main
```

### 6c. Create the GitHub repo and push

**Option A — GitHub CLI (creates the repo for you):**

```powershell
gh auth login                                   # one-time browser login
gh repo create fastapi-rag-backend --public --source=. --remote=origin --push
```

**Option B — Manual (create the repo on github.com first):**

1. Go to https://github.com/new and create an **empty** repo (no README/.gitignore).
2. Then:

```powershell
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

### 6d. Pushing later changes

```powershell
git add .
git commit -m "Describe your change"
git push
```

---

## 7. Handy troubleshooting

```powershell
# See what will be committed (should NOT include .venv or .env)
git status

# If .env was accidentally staged, unstage it
git rm --cached .env

# Recreate the database from scratch (Docker Compose)
docker compose down -v; docker compose up --build

# Free port 8000 if already in use (find the PID, then stop it)
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess

# Reinstall dependencies cleanly
pip install --force-reinstall -r requirements.txt
```

---

## Command quick-reference

| Task | Command |
|---|---|
| Run everything (Docker) | `docker compose up --build` |
| Stop everything | `docker compose down` |
| Fresh DB | `docker compose down -v` |
| Create venv | `python -m venv .venv` |
| Activate venv (Win) | `.\.venv\Scripts\Activate.ps1` |
| Install deps | `pip install -r requirements.txt` |
| Run API locally | `uvicorn app.main:app --reload` |
| Run Kafka worker | `python -m app.workers.kafka_consumer` |
| Run tests | `pytest -v` |
| Commit | `git add . && git commit -m "..."` |
| Push (first time) | `git push -u origin main` |
