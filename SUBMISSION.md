# Submission Checklist & Handover Notes

Status as of **28 July 2026**.

This file tracks three things:

1. What the assignment asks for, and where each requirement is implemented.
2. What is **still outstanding** before this can be submitted.
3. Things worth doing later (not required for submission).

---

## 1. What the assignment expects

Source: `FastAPI_AI_RAG_Assignment.pdf` — *Backend Assignment – FastAPI + AI (RAG)*.

### Mandatory requirements

| # | Requirement | Status | Where it lives |
|---|-------------|--------|----------------|
| 1 | JWT auth with signup + login; passwords securely hashed | Done | `app/api/routes/auth.py`, `app/core/security.py` (bcrypt via passlib, PyJWT) |
| 2 | PostgreSQL or MongoDB as the primary database | Done | PostgreSQL + pgvector — `app/db/`, `docker-compose.yml` |
| 3 | Appropriate schemas + suitable indexes, **documented in the README** | Done | `app/models/*.py`; rationale in `README.md` → *Database schema & indexing choices* |
| 4 | Ingest endpoint: store doc → chunk → embed → store chunks + embeddings | Done | `POST /documents` in `app/api/routes/documents.py`, pipeline in `app/services/ingestion.py` |
| 5 | `/chat` endpoint: retrieve relevant chunks + answer with an LLM | Done | `app/api/routes/chat.py`, `app/services/retrieval.py`, `app/services/llm.py` |
| 6 | Custom middleware logging unhandled exceptions to the DB (timestamp, endpoint, method, error message, stack trace, user id) + proper JSON error response | Done | `app/middleware/exception_handler.py`, `app/models/error_log.py` |
| 7 | Clean, modular project structure | Done | `app/{api,core,db,models,schemas,services,middleware,workers}` |

### "Good to have" — all six implemented

| Item | Where |
|------|-------|
| Redis | `app/services/cache.py` — response cache + ingestion job status, degrades gracefully if Redis is down |
| Kafka / message broker | `app/workers/kafka_producer.py`, `app/workers/kafka_consumer.py` (`INGEST_MODE=kafka`) |
| Docker / Docker Compose | `Dockerfile`, `docker-compose.yml` (db + redis + api, optional `--profile kafka`) |
| Background jobs for ingestion | FastAPI `BackgroundTasks` (`INGEST_MODE=background`, the default) |
| Streaming LLM responses | SSE via `"stream": true` on `/chat` — `sources` / `token` / `done` events |
| Unit tests | `tests/` — 23 tests, run fully offline (no DB, Redis, Kafka or API key needed) |

### Submission format required by the PDF

- A **GitHub repository** link.
- A **README** with setup instructions — `README.md` ✅
- A **`.env.example`** file — `.env.example` ✅

---

## 2. Outstanding work — required before submitting

> **This is the blocker.** All the code is written and tests pass, but the assignment
> is submitted as a GitHub repo link, and this machine has no Git installed and no
> repository initialised.

### Step 0 — Install Git (one time)

Git is not on this machine. Verify with `git --version`; if it errors, install it:

```powershell
winget install --id Git.Git -e
```

This may raise a Windows admin (UAC) prompt. **Close and reopen the terminal afterwards**
so `git` lands on your `PATH`.

### Step 1 — Sanity checks before the first commit

Run from `D:\project`:

```powershell
# Tests must pass (expect 23 passed)
.\.venv\Scripts\python.exe -m pytest -q

# Confirm no real .env exists (it must NEVER be committed)
Test-Path .env
```

`.gitignore` already excludes `.env`, `.venv/`, `__pycache__/`, and `.pytest_cache/`.
Only `.env.example` is tracked (it is force-included via `!.env.example`).

### Step 2 — Create the GitHub repository

On <https://github.com/new>:

- Name it something like `fastapi-rag-backend`.
- **Do not** tick "Add a README", "Add .gitignore", or "Choose a license" — the repo
  must start empty, otherwise the first push is rejected and needs a merge.
- Copy the HTTPS URL it gives you.

### Step 3 — Initialise, commit, push

```powershell
cd D:\project

git init
git branch -M main
git config user.name  "Ramya1542"
git config user.email "Ramya1542@users.noreply.github.com"

git add .

# Verify .env is NOT in this list, and .env.example IS
git status

git commit -m "FastAPI + RAG backend: JWT auth, pgvector retrieval, /chat, exception middleware"

git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

If the push asks for credentials, use a **GitHub Personal Access Token** as the
password (GitHub no longer accepts account passwords over HTTPS). Create one at
*Settings → Developer settings → Personal access tokens → Tokens (classic)* with
the `repo` scope.

### Step 4 — Verify the pushed repo

Open the repo in a browser and confirm:

- [ ] `README.md` renders, including the **indexing choices** section (requirement #3).
- [ ] `.env.example` is present.
- [ ] `.env` is **absent** — no secrets leaked.
- [ ] `app/`, `tests/`, `Dockerfile`, `docker-compose.yml`, `requirements.txt` are all there.
- [ ] No `__pycache__/`, `.venv/`, or `.pytest_cache/` directories.

### Step 5 — Send the link

Reply to whoever set the assignment with the repository URL before the deadline.
Optionally mention: *"All mandatory requirements plus all six 'good to have' items
are implemented; unit tests run offline with no external services."*

---

## 3. Notes on recent changes

Two settings were updated on 28 July 2026 while reviewing the submission:

- `LLM_MODEL` default changed from `claude-opus-4-8` → **`claude-opus-5`** (current
  Opus-tier model).
- `LLM_MAX_TOKENS` raised from `1024` → **`4096`**. On Claude Opus 5 extended thinking
  is on by default and shares the `max_tokens` budget with the visible answer, so a
  tight 1024 cap risked truncating `/chat` answers mid-sentence.

Both changed in `app/core/config.py` and `.env.example`; the README tables were
updated to match.

The `anthropic` SDK is pinned at `0.40.0` in `requirements.txt`. That version predates
the `output_config` / `effort` parameters, so `app/services/llm.py` deliberately does
**not** pass them — the request shape is kept compatible with the pinned SDK.

---

## 4. Optional future improvements

None of these are required by the assignment. Listed roughly by value.

### Worth doing if the project continues

- **Database migrations.** Tables are currently created with `create_all()` on startup
  (`app/db/init_db.py`). Alembic would be the production answer, especially since
  changing `EMBEDDING_DIM` currently requires dropping the `chunks` table.
- **Integration tests.** The 23 existing tests are pure unit tests. A `testcontainers`
  or docker-compose-backed suite hitting real Postgres + pgvector would cover the
  ingest → retrieve → answer path end to end.
- **CI.** A GitHub Actions workflow running `pytest` on push would show green checks on
  the repo — cheap credibility for a submitted assignment.
- **Rate limiting** on `/auth/login` and `/chat` (e.g. `slowapi` + Redis) to stop brute
  force and runaway LLM spend.
- **Refresh tokens.** Access tokens currently live 24h with no revocation path.

### Nice to have

- **Pagination** on `GET /documents` — it returns every document for the user today.
- **Delete endpoints** for documents and their chunks.
- **Hybrid retrieval** — combine pgvector cosine search with Postgres full-text search
  (`tsvector`) and rerank; usually beats pure dense retrieval on keyword-heavy queries.
- **Upgrade the `anthropic` SDK** past 0.40.0 to gain `output_config={"effort": ...}`,
  which is the main cost/latency lever on Opus 5. Retest `/chat` and the SSE stream
  after upgrading.
- **Structured request logging** with a correlation id shared between the access log
  and the `error_logs` table (the middleware already generates a `request_id` and
  returns it to the client, but does not yet persist it).
- **Kafka consumer resilience** — dead-letter topic and retry/backoff for documents
  that fail processing.
- **Observability** — Prometheus metrics on ingestion latency, retrieval latency, and
  cache hit rate.
