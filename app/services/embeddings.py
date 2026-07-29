"""Pluggable embedding providers.

Providers:
  * local  -> deterministic hashing embedding (no external calls, offline-safe).
              Great for development, tests and demos without an API key.
  * voyage -> Voyage AI (Anthropic's recommended embedding provider).
  * openai -> any OpenAI-compatible /v1/embeddings endpoint.

All providers expose the same async interface, returning L2-normalised vectors
of dimension ``settings.EMBEDDING_DIM`` so cosine similarity is well-defined.
"""
from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


class EmbeddingProvider(ABC):
    dim: int

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_documents([text])
        return vectors[0]


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Deterministic bag-of-words embedding via feature hashing.

    Each token is hashed to an index in a fixed-size vector (with a sign hash to
    reduce collisions), counts are accumulated, then the vector is L2-normalised.
    Semantically similar texts (shared vocabulary) get similar vectors, which is
    enough for a functional RAG demo without any external dependency.
    """

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            h = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self.dim
            sign = 1.0 if (h[4] & 1) == 0 else -1.0
            vec[idx] += sign
        return _normalize(vec)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class VoyageEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str, dim: int) -> None:
        if not api_key:
            raise ValueError("VOYAGE_API_KEY is required for the 'voyage' provider")
        self.api_key = api_key
        self.model = model
        self.dim = dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
        return [_normalize(item["embedding"]) for item in data]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, base_url: str, model: str, dim: int) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the 'openai' provider")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dim = dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
        return [_normalize(item["embedding"]) for item in data]


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider (singleton)."""
    global _provider
    if _provider is not None:
        return _provider

    provider = settings.EMBEDDING_PROVIDER
    if provider == "voyage":
        _provider = VoyageEmbeddingProvider(
            settings.VOYAGE_API_KEY, settings.EMBEDDING_MODEL, settings.EMBEDDING_DIM
        )
    elif provider == "openai":
        _provider = OpenAIEmbeddingProvider(
            settings.OPENAI_API_KEY,
            settings.OPENAI_BASE_URL,
            settings.EMBEDDING_MODEL,
            settings.EMBEDDING_DIM,
        )
    else:
        if provider != "local":
            logger.warning(
                "Unknown EMBEDDING_PROVIDER=%r, falling back to 'local'.", provider
            )
        _provider = LocalHashEmbeddingProvider(settings.EMBEDDING_DIM)

    logger.info(
        "Embedding provider: %s (dim=%d)", type(_provider).__name__, _provider.dim
    )
    return _provider
