import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Maps session_id -> derived AES key bytes (never stores raw password)
session_passwords: dict = {}

SALT = b"stealthchat_static_salt_v1"  # per-deployment salt; ideally load from env
ITERATIONS = 200_000
KEY_LEN = 32  # 256-bit AES key


def _derive_key(password: str) -> bytes:
    """Derive a 256-bit AES key from a password using PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        SALT,
        ITERATIONS,
        dklen=KEY_LEN,
    )


def init_session(session_id: str, password: str) -> None:
    """Derive and store the session key. The raw password is never stored."""
    session_passwords[session_id] = _derive_key(password)


def encrypt_message(message: str, password) -> bytes:
    """
    Encrypt *message* with AES-256-GCM.

    *password* may be either a raw password string (for callers that still
    pass the string directly) or pre-derived key bytes stored in
    session_passwords.  Returns nonce + ciphertext + tag as a single bytes
    object suitable for base64 encoding.
    """
    if isinstance(password, str):
        key = _derive_key(password)
    else:
        key = password  # already a derived key

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit random nonce
    ct = aesgcm.encrypt(nonce, message.encode("utf-8"), None)
    return nonce + ct


def decrypt_message(ciphertext: bytes, password) -> str:
    """
    Decrypt a message produced by encrypt_message.

    Returns the plaintext string, or raises an exception on failure
    (wrong key, tampered data, etc.).
    """
    if isinstance(password, str):
        key = _derive_key(password)
    else:
        key = password

    if len(ciphertext) < 13:  # 12-byte nonce + at least 1 byte
        raise ValueError("Ciphertext too short")

    nonce, ct = ciphertext[:12], ciphertext[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
