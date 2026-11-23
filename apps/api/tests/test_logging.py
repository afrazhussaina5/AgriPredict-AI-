"""Tests for log secret redaction."""

from app.core.logging import RedactingFilter, redact_secrets


def test_redacts_secret_key_assignments() -> None:
    message = redact_secrets("loaded SECRET_KEY=abc123 from environment")
    assert "abc123" not in message
    assert "SECRET_KEY=[REDACTED]" in message


def test_redacts_password_and_token_assignments() -> None:
    assert "hunter2" not in redact_secrets("password=hunter2")
    assert "abcd" not in redact_secrets("api_key: abcd")


def test_redacts_otp_values() -> None:
    assert "492817" not in redact_secrets("otp=492817 for +919000000000")


def test_redacts_authorization_headers() -> None:
    message = redact_secrets("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload")
    assert "eyJhbGciOiJIUzI1NiJ9" not in message


def test_ordinary_log_messages_are_untouched() -> None:
    original = "Started server on port 8000"
    assert redact_secrets(original) == original


def test_filter_rewrites_record_message() -> None:
    import logging

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=%s",
        args=("secret-value-xyz",),
        exc_info=None,
    )
    redacting = RedactingFilter()
    assert redacting.filter(record) is True
    assert "secret-value-xyz" not in record.getMessage()
