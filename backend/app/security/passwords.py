"""Password hashing backed by pwdlib's Argon2id recommendation."""

from pwdlib import PasswordHash


_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return a new Argon2id hash for a plaintext password."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id password hash."""
    return _password_hash.verify(password, password_hash)
