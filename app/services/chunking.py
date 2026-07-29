"""Text chunking.

Splits raw document text into overlapping, word-based chunks. Overlap keeps
context continuous across chunk boundaries so retrieval doesn't lose meaning
that straddles a split.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass
class TextChunk:
    index: int
    content: str
    token_count: int


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[TextChunk]:
    """Split ``text`` into overlapping chunks of ~``chunk_size`` words.

    Args:
        text: The document text.
        chunk_size: Max words per chunk (defaults to settings.CHUNK_SIZE).
        overlap: Words shared between consecutive chunks (settings.CHUNK_OVERLAP).
    """
    chunk_size = settings.CHUNK_SIZE if chunk_size is None else chunk_size
    overlap = settings.CHUNK_OVERLAP if overlap is None else overlap

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    words = text.split()
    if not words:
        return []

    step = chunk_size - overlap
    chunks: list[TextChunk] = []
    index = 0
    start = 0
    while start < len(words):
        window = words[start : start + chunk_size]
        content = " ".join(window).strip()
        if content:
            chunks.append(
                TextChunk(index=index, content=content, token_count=len(window))
            )
            index += 1
        start += step

    return chunks
