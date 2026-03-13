"""Security utilities."""

import hashlib
import secrets
import uuid
from typing import Any


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


def generate_token(length: int = 32) -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(length)


def hash_sensitive(data: str) -> str:
    """Hash sensitive data for logging."""
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def mask_string(s: str, visible: int = 4) -> str:
    """Mask a string showing only last N characters."""
    if len(s) <= visible:
        return "*" * len(s)
    return "*" * (len(s) - visible) + s[-visible:]
