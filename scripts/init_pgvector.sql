-- Enable the pgvector extension. The application also runs this automatically
-- on startup, but it is provided here for manual / psql-based setup.
CREATE EXTENSION IF NOT EXISTS vector;
