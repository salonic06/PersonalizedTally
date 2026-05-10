"""Local desktop login — salted-ish SHA-256 (portfolio / single-machine; not IAM-grade)."""

from __future__ import annotations

import hashlib

_PEPPER = "PersonalizedTally.auth.v1"


def hash_password(plain: str) -> str:
    return hashlib.sha256(f"{_PEPPER}|{plain}".encode()).hexdigest()


def verify_password(plain: str, stored_hex: str) -> bool:
    return hash_password(plain) == stored_hex
