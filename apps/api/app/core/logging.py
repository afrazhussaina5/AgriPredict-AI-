"""Logging setup with automatic secret redaction.

Every log line passes through :func:`redact_secrets` so credential-shaped
values (``SECRET_KEY=...``, ``Authorization: Bearer ...`` and similar) can
never reach the terminal, CI output, or a log file.
"""

import logging
import re
import sys

_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(secret|password|passwd|token|api[_-]?key|apikey|authorization|auth|"
    r"credential[s]?|otp)((?:[_-]\w+)*)(\s*[=:]\s*)(\S+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+\S+")


def redact_secrets(text: str) -> str:
    """Mask values that look like credentials.

    Order matters: the Bearer pattern must run FIRST. If the key/value pattern
    ran first it would consume the word "Bearer" in a header such as
    ``Authorization: Bearer <token>`` and leave the token itself in the log.
    """

    def _replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}[REDACTED]"

    text = _BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    return _KEY_VALUE_PATTERN.sub(_replace, text)


class RedactingFilter(logging.Filter):
    """Rewrite log records so secrets never reach a log sink."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            # Never let logging itself crash the application.
            return True
        record.msg = redact_secrets(message)
        record.args = ()
        return True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger. Redaction is handled by the root handler."""
    return logging.getLogger(name)


def configure_logging(level: str = "INFO") -> None:
    """Install one stdout handler with redaction enabled (idempotent)."""
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, "_agripredict_handler", False):
            root.setLevel(level.upper())
            return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    handler.addFilter(RedactingFilter())
    handler._agripredict_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level.upper())
