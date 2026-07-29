"""Tests for text chunking."""
import pytest

from app.services.chunking import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_single_small_chunk():
    chunks = chunk_text("hello world", chunk_size=200, overlap=40)
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].content == "hello world"
    assert chunks[0].token_count == 2


def test_multiple_chunks_with_overlap():
    words = " ".join(str(i) for i in range(100))
    chunks = chunk_text(words, chunk_size=30, overlap=10)
    # step = 20 -> starts at 0,20,40,60,80 -> 5 chunks
    assert len(chunks) == 5
    assert [c.index for c in chunks] == [0, 1, 2, 3, 4]
    # Verify overlap: last 10 words of chunk 0 == first 10 words of chunk 1.
    c0_words = chunks[0].content.split()
    c1_words = chunks[1].content.split()
    assert c0_words[-10:] == c1_words[:10]


def test_no_overlap():
    words = " ".join(str(i) for i in range(60))
    chunks = chunk_text(words, chunk_size=20, overlap=0)
    assert len(chunks) == 3
    # Reassembling all chunks reproduces the original words exactly.
    reassembled = " ".join(c.content for c in chunks)
    assert reassembled == words


def test_invalid_overlap_raises():
    with pytest.raises(ValueError):
        chunk_text("a b c", chunk_size=10, overlap=10)
    with pytest.raises(ValueError):
        chunk_text("a b c", chunk_size=0)
