# FastAPI + AI (RAG) Backend

A FastAPI backend demonstrating solid backend practices alongside a basic
**Retrieval-Augmented Generation (RAG)** pipeline:

- 🔐 **JWT authentication** (signup / login) with securely hashed passwords (bcrypt)
- 🐘 **PostgreSQL + pgvector** as the primary database *and* vector store
- 📄 **Document ingestion**: store → chunk → embed → store chunks + embeddings
- 💬 **`/chat` endpoint**: retrieves relevant chunks and answers with an LLM (Anthropic Claude)
- 🧯 **Custom exception middleware** that logs unhandled errors to the database and returns clean JSON
- 🧱 Clean, modular project structure

**Good-to-have items implemented:** Redis (caching + job status), Kafka (background ingestion via a message broker), Docker / Docker Compose, background jobs, streaming LLM responses (SSE), and unit tests.

---

## Table of contents

1. [Architecture](#architecture)
2. [Tech stack](#tech-stack)
3. [Quick start (Docker)](#quick-start-docker)
4. [Local setup (without Docker)](#local-setup-without-docker)
5. [Configuration (.env)](#configuration-env)
6. [API reference](#api-reference)
7. [Database schema & indexing choices](#database-schema--indexing-choices)
8. [Ingestion modes (sync / background / Kafka)](#ingestion-modes)
9. [Embedding providers](#embedding-providers)
10. [Running the tests](#running-the-tests)
11. [Project structure](#project-structure)

---

## Architecture

```
                 ┌──────────────┐
   HTTP client ─▶│  FastAPI app │
                 └──────┬───────┘
        ┌───────────────┼─────────────────────────┐
        ▼               ▼                           ▼
   /auth (JWT)   /documents (ingest)           /chat (RAG)
        │               │                           │
        │        chunk → embed → store        embed query
        │               │                     → vector search (pgvector)
        │               │                     → build prompt
        ▼               ▼                     → Anthropic Claude
   ┌─────────┐   ┌──────────────┐                   │
   │ users   │   │ documents    │◀── background ────┘ answer (+ optional SSE stream)
   │ table   │   │ + chunks     │    task / Kafka
   └─────────┘   │ (embeddings) │        worker
                 └──────────────┘
        ▲                                     ▲
        │        Redis (cache + job status)   │
        └────────── error_logs table ◀── exception middleware
```

The **agent loop is intentionally simple** (single-shot retrieve-then-answer),
which is the classic RAG shape the assignment asks for.

---

## Tech stack

| Concern            | Choice                                             |
| ------------------ | -------------------------------------------------- |
| Web framework      | FastAPI + Uvicorn                                  |
| DB / ORM           | PostgreSQL + **pgvector**, SQLAlchemy 2 (async), asyncpg |
| Auth               | JWT (PyJWT) + bcrypt (passlib)                     |
| Embeddings         | Pluggable: `local` (offline), `voyage`, `openai`  |
| LLM                | Anthropic **Claude** (`claude-opus-5` by default), streaming |
| Cache / jobs       | Redis                                              |
| Message broker     | Kafka (aiokafka)                                   |
| Containers         | Docker + Docker Compose                            |
| Tests              | pytest + pytest-asyncio                            |

---

## Quick start (Docker)

The fastest way to run everything (Postgres + pgvector, Redis, and the API):

```bash
# 1. Create your env file
cp .env.example .env
# (optional) add ANTHROPIC_API_KEY to .env to enable real LLM answers in /chat

# 2. Build & start (db + redis + api). Kafka is optional — see below.
docker compose up --build
```

- API: <http://localhost:8000>
- Interactive docs (Swagger UI): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

The API container automatically creates the `vector` extension, all tables, and
the vector index on startup.

### Enabling the Kafka ingestion worker

```bash
# Also starts Kafka + a dedicated ingestion worker
docker compose --profile kafka up --build
# and set INGEST_MODE=kafka in your .env
```

---

## Local setup (without Docker)

**Prerequisites:** Python 3.11+, a PostgreSQL 14+ instance with the `pgvector`
extension available, and (optionally) Redis and Kafka.

```bash
# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit DATABASE_URL, JWT_SECRET_KEY, and (optionally) ANTHROPIC_API_KEY

# 4. (once) enable pgvector in your database — the app also does this on startup
psql "$DATABASE_URL" -f scripts/init_pgvector.sql   # or: CREATE EXTENSION vector;

# 5. Run the API (tables + index are created automatically on startup)
uvicorn app.main:app --reload
```

Run the Kafka worker (only if `INGEST_MODE=kafka`) in a second terminal:

```bash
python -m app.workers.kafka_consumer
```

---

## Configuration (.env)

All configuration is via environment variables (see **`.env.example`** for the
full, documented list). The most important ones:

| Variable                 | Description                                              | Default |
| ------------------------ | ------------------------------------------------------- | ------- |
| `DATABASE_URL`           | Async Postgres URL (`postgresql+asyncpg://...`)         | local dev URL |
| `JWT_SECRET_KEY`         | Secret used to sign JWTs — **change this**              | `change-me` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime                                       | `1440` |
| `EMBEDDING_PROVIDER`     | `local` \| `voyage` \| `openai`                         | `local` |
| `EMBEDDING_DIM`          | Vector dimension (must match provider/model)            | `384` |
| `ANTHROPIC_API_KEY`      | Enables real LLM answers in `/chat`                     | *(empty)* |
| `LLM_MODEL`              | Claude model id                                         | `claude-opus-5` |
| `REDIS_URL`              | Redis connection URL                                    | local |
| `INGEST_MODE`            | `sync` \| `background` \| `kafka`                       | `background` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Words per chunk / overlap                         | `200` / `40` |
| `RETRIEVAL_TOP_K`        | Chunks retrieved per query                              | `5` |

> **Note:** `EMBEDDING_DIM` fixes the size of the `chunks.embedding` vector
> column at table-creation time. If you change it after data exists, drop/recreate
> the `chunks` table (or the `pgdata` Docker volume).

---

## API reference

Base URL: `http://localhost:8000`. Full interactive docs at `/docs`.

### Auth

| Method | Path           | Auth | Body                              | Description |
| ------ | -------------- | ---- | --------------------------------- | ----------- |
| POST   | `/auth/signup` | –    | `{email, password}`               | Create a user, returns user + JWT |
| POST   | `/auth/login`  | –    | `{email, password}`               | Returns a JWT access token |
| GET    | `/auth/me`     | ✅   | –                                 | Current user |

### Documents

| Method | Path                          | Auth | Body / Notes                     | Description |
| ------ | ----------------------------- | ---- | -------------------------------- | ----------- |
| POST   | `/documents`                  | ✅   | `{title, text, source?}`         | Ingest a text document (chunk + embed + store) |
| GET    | `/documents`                  | ✅   | –                                | List your documents |
| GET    | `/documents/{id}`             | ✅   | –                                | Get a document |
| GET    | `/documents/{id}/status`      | ✅   | –                                | Ingestion status + chunk count |

### Chat (RAG)

| Method | Path    | Auth | Body                                             | Description |
| ------ | ------- | ---- | ------------------------------------------------ | ----------- |
| POST   | `/chat` | ✅   | `{query, top_k?, document_id?, stream?}`         | Retrieve relevant chunks and answer with the LLM |

Set `"stream": true` to receive a **Server-Sent Events** stream (`sources`,
`token`, `done` events) instead of a single JSON response.

### End-to-end example

```bash
BASE=http://localhost:8000

# 1. Sign up (returns access_token)
TOKEN=$(curl -s -X POST $BASE/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"supersecret123"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Ingest a document
curl -s -X POST $BASE/documents \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"France","text":"Paris is the capital of France. France is a country in Western Europe. The Eiffel Tower is located in Paris."}'

# 3. Ask a question (wait a moment if using background ingestion)
curl -s -X POST $BASE/chat \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"What is the capital of France?"}'
```

---

## Database schema & indexing choices

Three primary tables plus an error-log table.

### `users`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `email` | varchar | **UNIQUE index** |
| `hashed_password` | varchar | bcrypt hash |
| `created_at` | timestamptz | |

### `documents`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `owner_id` | int FK → users | `ON DELETE CASCADE` |
| `title`, `source`, `content` | text | |
| `status` | varchar | `pending`/`processing`/`completed`/`failed` |
| `created_at` | timestamptz | |

### `chunks`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `document_id` | int FK → documents | `ON DELETE CASCADE`, **indexed** |
| `chunk_index` | int | position in document |
| `content` | text | |
| `token_count` | int | |
| `embedding` | `vector(EMBEDDING_DIM)` | pgvector column |
| `created_at` | timestamptz | |

### `error_logs`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `timestamp` | timestamptz | **indexed** |
| `endpoint`, `method` | varchar | **endpoint indexed** |
| `status_code` | int | |
| `error_message` | text | |
| `stack_trace` | text | |
| `user_id` | int | nullable, **indexed** |

### Indexing choices (and *why*)

- **`users.email` — UNIQUE B-tree index.** Login and signup both look users up
  by email; the unique index enforces one account per email *and* makes those
  lookups O(log n).
- **`chunks.embedding` — HNSW index with `vector_cosine_ops`.** This is the
  index that powers retrieval. HNSW (Hierarchical Navigable Small World) gives
  fast **approximate nearest-neighbour** search — the right trade-off for RAG,
  where we want low-latency top-k retrieval and can tolerate approximate results.
  Cosine distance is used because embeddings are L2-normalised, so cosine
  similarity is the natural relevance measure. (IVFFlat is an alternative, but
  HNSW needs no training step and gives better recall out of the box.)
- **`chunks.document_id` — B-tree index.** Speeds up the join to `documents`
  (for owner-scoping during retrieval) and enables efficient re-processing /
  deletion of a document's chunks.
- **`chunks (document_id, chunk_index)` — composite index.** Fetch a document's
  chunks in order efficiently.
- **`documents (owner_id, created_at)` — composite index.** "List my documents,
  newest first" is a common query; the composite index serves the filter + sort
  in one pass.
- **`error_logs` — indexes on `timestamp`, `endpoint`, and `user_id`.** These are
  the dimensions you filter/aggregate on when investigating incidents (errors
  over time, by endpoint, by affected user).

---

## Ingestion modes

Controlled by `INGEST_MODE`:

| Mode | Behaviour | Infra needed |
|---|---|---|
| `sync` | Chunk + embed inside the request; response returns when done. | Postgres |
| `background` *(default)* | Returns immediately; a FastAPI **BackgroundTask** processes the document. Poll `/documents/{id}/status`. | Postgres |
| `kafka` | Publishes a `document.ingest` event; a separate **Kafka worker** processes it. If Kafka is unreachable, it falls back to a background task. | Postgres + Kafka + worker |

The processing pipeline (`chunk → embed → store chunks`) is identical across all
three modes — only *where* it runs differs.

---

## Embedding providers

Set `EMBEDDING_PROVIDER`:

- **`local`** (default) — a deterministic, dependency-free hashing embedding.
  No API key, works fully offline; ideal for development, demos, and tests.
- **`voyage`** — [Voyage AI](https://www.voyageai.com) (Anthropic's recommended
  embedding provider). Set `VOYAGE_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`.
- **`openai`** — any OpenAI-compatible `/v1/embeddings` endpoint. Set
  `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`.

All providers return L2-normalised vectors so cosine similarity is consistent.

---

## Running the tests

The unit tests run **fully offline** — no Postgres/Redis/Kafka/API key required.
They cover password hashing & JWTs, chunking, embeddings, retrieval scoring, and
prompt construction.

```bash
pip install -r requirements.txt
pytest
```

Integration against the real database is exercised by running the stack via
`docker compose up` and hitting the endpoints (see the end-to-end example above).

---

## Project structure

```
app/
├── main.py                  # FastAPI app: middleware, routers, lifespan (init DB)
├── core/
│   ├── config.py            # Pydantic settings (.env)
│   ├── security.py          # bcrypt hashing + JWT create/decode
│   └── logging.py           # logging setup
├── db/
│   ├── base.py              # SQLAlchemy declarative Base
│   ├── session.py           # async engine + session factory
│   └── init_db.py           # extension + create_all + vector index
├── models/                  # SQLAlchemy models (user, document, chunk, error_log)
├── schemas/                 # Pydantic request/response models
├── api/
│   ├── deps.py              # get_current_user, DB session dependencies
│   └── routes/              # auth, documents, chat, health
├── services/
│   ├── chunking.py          # text -> overlapping chunks
│   ├── embeddings.py        # pluggable embedding providers
│   ├── retrieval.py         # pgvector cosine search + cosine helper
│   ├── ingestion.py         # store -> chunk -> embed -> store chunks
│   ├── llm.py               # Anthropic Claude answering (+ streaming)
│   ├── users.py             # user persistence / auth helpers
│   └── cache.py             # Redis cache + job status (graceful fallback)
├── middleware/
│   └── exception_handler.py # logs unhandled exceptions to the DB
└── workers/
    ├── kafka_producer.py    # publish ingest events
    └── kafka_consumer.py    # consume + process (python -m app.workers.kafka_consumer)
tests/                       # offline unit tests
scripts/init_pgvector.sql    # CREATE EXTENSION vector
Dockerfile, docker-compose.yml, .env.example, requirements.txt
```

---

## Notes & trade-offs

- **`/chat` without an `ANTHROPIC_API_KEY`** returns a clear error — retrieval
  still works, only the final LLM generation needs the key. The default
  `local` embeddings let you exercise ingestion + retrieval with zero keys.
- **Exception middleware only logs true 500s.** FastAPI converts `HTTPException`
  (401/404/422/…) to responses *before* the middleware sees them, so the
  `error_logs` table captures genuinely *unhandled* server errors — which is the
  intent.
- **Response caching.** Non-streaming `/chat` answers are cached in Redis keyed
  by (user, query, top_k, document scope, model). Redis is optional — if it's
  down, requests still succeed (cache simply misses).
```
