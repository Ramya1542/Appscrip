"""Tests for LLM prompt construction and guard rails (no API calls)."""
import pytest

from app.services.llm import (
    build_context_block,
    build_user_message,
    generate_answer,
)
from app.services.retrieval import ScoredChunk


def _chunks():
    return [
        ScoredChunk(document_id=1, chunk_index=0, content="Paris is the capital of France.", score=0.9),
        ScoredChunk(document_id=1, chunk_index=1, content="France is in Europe.", score=0.8),
    ]


def test_context_block_numbers_passages():
    block = build_context_block(_chunks())
    assert "[1]" in block
    assert "[2]" in block
    assert "Paris is the capital of France." in block


def test_context_block_empty():
    assert "no relevant context" in build_context_block([]).lower()


def test_user_message_contains_query_and_context():
    msg = build_user_message("What is the capital of France?", _chunks())
    assert "What is the capital of France?" in msg
    assert "Paris is the capital of France." in msg


async def test_generate_answer_requires_api_key(monkeypatch):
    # With no ANTHROPIC_API_KEY configured, the client construction must fail loudly.
    from app.services import llm

    monkeypatch.setattr(llm.settings, "ANTHROPIC_API_KEY", "", raising=False)
    monkeypatch.setattr(llm, "_client", None, raising=False)
    with pytest.raises(RuntimeError):
        await generate_answer("hi", _chunks())
