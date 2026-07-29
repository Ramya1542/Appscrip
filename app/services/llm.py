"""LLM answer generation using Anthropic Claude.

Builds a grounded RAG prompt from retrieved chunks and asks Claude to answer
using only that context. Supports both a full-response call and token streaming.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.core.logging import get_logger
from app.services.retrieval import ScoredChunk

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the provided "
    "context passages. If the answer is not contained in the context, say you "
    "don't have enough information to answer. Be concise and cite passages by "
    "their [n] number when relevant."
)

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. Set it in your .env to use /chat."
        )
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def build_context_block(chunks: list[ScoredChunk]) -> str:
    if not chunks:
        return "(no relevant context found)"
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[{i}] (document {c.document_id}, chunk {c.chunk_index})\n{c.content}")
    return "\n\n".join(parts)


def build_user_message(query: str, chunks: list[ScoredChunk]) -> str:
    context = build_context_block(chunks)
    return (
        f"Context passages:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer using only the context above."
    )


async def generate_answer(query: str, chunks: list[ScoredChunk]) -> str:
    """Return a complete answer string from Claude."""
    client = _get_client()
    message = await client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(query, chunks)}],
    )
    return "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )


async def stream_answer(query: str, chunks: list[ScoredChunk]) -> AsyncIterator[str]:
    """Yield answer text incrementally from Claude (for SSE streaming)."""
    client = _get_client()
    async with client.messages.stream(
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(query, chunks)}],
    ) as stream:
        async for text in stream.text_stream:
            yield text
