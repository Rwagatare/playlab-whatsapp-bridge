import hashlib


def pseudonymize_user_id(user_id: str, salt: str) -> str:
    """Return a stable, irreversible hash of a user identifier."""
    digest = hashlib.sha256(f"{salt}:{user_id}".encode("utf-8")).hexdigest()
    return digest
