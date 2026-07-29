"""Tests for the local embedding provider."""
import math

import pytest

from app.services.embeddings import LocalHashEmbeddingProvider
from app.services.retrieval import cosine_similarity


@pytest.fixture
def provider():
    return LocalHashEmbeddingProvider(dim=384)


async def test_dimension_and_determinism(provider):
    v1 = await provider.embed_query("the quick brown fox")
    v2 = await provider.embed_query("the quick brown fox")
    assert len(v1) == 384
    assert v1 == v2  # deterministic


async def test_vectors_are_normalized(provider):
    vec = await provider.embed_query("machine learning and neural networks")
    norm = math.sqrt(sum(x * x for x in vec))
    assert norm == pytest.approx(1.0, abs=1e-6)


async def test_batch_embedding(provider):
    texts = ["alpha beta", "gamma delta", "alpha beta gamma"]
    vecs = await provider.embed_documents(texts)
    assert len(vecs) == 3
    assert all(len(v) == 384 for v in vecs)


async def test_similar_texts_more_similar_than_dissimilar(provider):
    query = "cats are wonderful pets that enjoy sleeping"
    similar = "pets like cats enjoy sleeping a lot"
    dissimilar = "quantum chromodynamics describes the strong nuclear force"

    q = await provider.embed_query(query)
    s = await provider.embed_query(similar)
    d = await provider.embed_query(dissimilar)

    sim_similar = cosine_similarity(q, s)
    sim_dissimilar = cosine_similarity(q, d)
    assert sim_similar > sim_dissimilar
