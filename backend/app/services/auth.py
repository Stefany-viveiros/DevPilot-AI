import base64
import hashlib
import hmac
import json
import os
import secrets
import time

ITERATIONS = 310000

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(iterations))
        return hmac.compare_digest(base64.urlsafe_b64encode(digest).decode(), expected)
    except (ValueError, TypeError):
        return False

def _secret() -> bytes:
    value = os.getenv("DEVPILOT_AUTH_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("Defina DEVPILOT_AUTH_SECRET com pelo menos 32 caracteres aleatórios.")
    return value.encode()

def issue_token(user_id: int, email: str, lifetime_seconds: int = 3600) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"sub": user_id, "email": email, "exp": int(time.time()) + lifetime_seconds}, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return payload + "." + signature

def read_token(token: str) -> dict:
    try:
        payload, signature = token.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Assinatura inválida.")
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(data["exp"]) <= int(time.time()):
            raise ValueError("Token expirado.")
        return data
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Token inválido ou expirado.") from exc
