"""Test configuration.

These tests are designed to run fully offline — no PostgreSQL, Redis, Kafka or
Anthropic API key required. They exercise the pure building blocks of the RAG
pipeline (auth/security, chunking, embeddings, retrieval scoring, prompt
construction). Integration against the real services is done via docker-compose
(see README).
"""
import os

# Ensure deterministic, dependency-free defaults for the test run.
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("EMBEDDING_DIM", "384")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
