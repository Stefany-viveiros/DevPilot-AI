import pytest
from app.services.auth import hash_password, verify_password, issue_token, read_token

def test_password_hash_is_salted_and_verifiable():
    first = hash_password("uma-senha-muito-forte")
    second = hash_password("uma-senha-muito-forte")
    assert first != second
    assert verify_password("uma-senha-muito-forte", first)
    assert not verify_password("senha-errada", first)

def test_signed_token_round_trip(monkeypatch):
    monkeypatch.setenv("DEVPILOT_AUTH_SECRET", "x" * 48)
    token = issue_token(7, "user@example.com")
    assert read_token(token)["sub"] == 7

def test_token_signature_cannot_be_tampered(monkeypatch):
    monkeypatch.setenv("DEVPILOT_AUTH_SECRET", "x" * 48)
    token = issue_token(7, "user@example.com")
    with pytest.raises(ValueError):
        read_token(token + "tampered")
