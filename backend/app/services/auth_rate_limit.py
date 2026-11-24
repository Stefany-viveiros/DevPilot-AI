"""Limitação simples de tentativas de login para execução em instância única.

Em produção com múltiplos workers/instâncias, substituir por armazenamento compartilhado
(como Redis) e aplicar também limites no proxy reverso.
"""
from collections import defaultdict, deque
from hashlib import sha256
from threading import Lock
from time import monotonic

MAX_FAILED_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60
_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def login_bucket_key(remote_address: str, email: str) -> str:
    normalized = f"{remote_address.strip()}:{email.strip().lower()}"
    return sha256(normalized.encode("utf-8")).hexdigest()


def is_login_blocked(key: str, now: float | None = None) -> bool:
    current = monotonic() if now is None else now
    with _lock:
        attempts = _attempts[key]
        while attempts and current - attempts[0] >= WINDOW_SECONDS:
            attempts.popleft()
        return len(attempts) >= MAX_FAILED_ATTEMPTS


def record_failed_login(key: str, now: float | None = None) -> None:
    current = monotonic() if now is None else now
    with _lock:
        attempts = _attempts[key]
        while attempts and current - attempts[0] >= WINDOW_SECONDS:
            attempts.popleft()
        attempts.append(current)
        # Evita crescimento indefinido em processos expostos por muito tempo.
        if len(_attempts) > 10000:
            expired = [bucket for bucket, values in _attempts.items()
                       if not values or current - values[-1] >= WINDOW_SECONDS]
            for bucket in expired:
                _attempts.pop(bucket, None)


def clear_login_failures(key: str) -> None:
    with _lock:
        _attempts.pop(key, None)
