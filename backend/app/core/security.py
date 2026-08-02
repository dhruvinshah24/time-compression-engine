"""
Security utilities — Time Compression Engine.

Phase 1 stub. Authentication is not implemented in v1.0.0 (research system,
single-user deployment assumed). This module exists so imports don't fail.

Phase 3 will implement JWT verification using python-jose (already in
requirements.txt) and password hashing via passlib[bcrypt].
"""

import logging

logger = logging.getLogger(__name__)


def verify_token(token: str) -> dict | None:
    """
    Verify a JWT access token and return its payload.

    Phase 1 stub — always returns None (no auth enforced).
    Phase 3 will implement real JWT verification.
    """
    # TODO(Phase 3): implement JWT verification with python-jose
    logger.debug("[STUB] verify_token not yet implemented — Phase 3")
    return None


def get_password_hash(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Phase 1 stub — returns the password unchanged (NOT for production use).
    Phase 3 will use passlib[bcrypt].
    """
    # TODO(Phase 3): implement with passlib CryptContext
    logger.warning(
        "[STUB] get_password_hash is a no-op — do not use in production"
    )
    return password
