from app.services.auth_rate_limit import (
    MAX_FAILED_ATTEMPTS,
    WINDOW_SECONDS,
    clear_login_failures,
    is_login_blocked,
    login_bucket_key,
    record_failed_login,
)


def test_login_bucket_key_normalizes_email_and_hides_plaintext():
    first = login_bucket_key("127.0.0.1", "User@Example.com")
    second = login_bucket_key("127.0.0.1", "user@example.com")
    assert first == second
    assert "user@example.com" not in first


def test_login_is_blocked_after_five_failures_and_expires_after_window():
    key = login_bucket_key("127.0.0.1", "user@example.com")
    clear_login_failures(key)
    for attempt in range(MAX_FAILED_ATTEMPTS):
        record_failed_login(key, now=1000 + attempt)
    assert is_login_blocked(key, now=1004)
    assert not is_login_blocked(key, now=1000 + WINDOW_SECONDS + 1)
    clear_login_failures(key)


def test_successful_login_can_clear_previous_failures():
    key = login_bucket_key("127.0.0.1", "user@example.com")
    clear_login_failures(key)
    for attempt in range(MAX_FAILED_ATTEMPTS):
        record_failed_login(key, now=2000 + attempt)
    assert is_login_blocked(key, now=2005)
    clear_login_failures(key)
    assert not is_login_blocked(key, now=2005)
