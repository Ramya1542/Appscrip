"""Tests for password hashing and JWT handling."""
import time

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    password = "s3cur3-passw0rd"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_password_hash_is_salted():
    # Two hashes of the same password differ (random salt) but both verify.
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    assert verify_password("same-password", h1)
    assert verify_password("same-password", h2)


def test_jwt_roundtrip():
    token = create_access_token(subject=42)
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_jwt_expired_raises():
    token = create_access_token(subject=1, expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


def test_jwt_tampered_raises():
    token = create_access_token(subject=1)
    tampered = token + "x"
    with pytest.raises(jwt.PyJWTError):
        decode_token(tampered)
