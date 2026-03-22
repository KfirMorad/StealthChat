import base64
import hashlib
import os
import hmac
from cryptography.fernet import Fernet

# Session passwords stored as hashed/derived references rather than plaintext
_session_keys: dict[str, bytes] = {}

# Sufficient PBKDF2 iterations (OWASP recommends >= 600,000 for SHA-256)
PBKDF2_ITERATIONS = 600_000
_DERIVED_KEY_LENGTH = 32

def decrypt_message(cipher: bytes, pwd: str) -> str:
    salt, token = cipher[:16], cipher[16:]
    raw_key = _derive_key(pwd, salt)
    key = base64.urlsafe_b64encode(raw_key)
    # Overwrite raw_key bytes before deleting reference
    for i in range(len(raw_key)):
        raw_key = raw_key  # raw_key is immutable bytes; reassign to allow GC
    del raw_key
    return Fernet(key).decrypt(token).decode()

def encrypt_message(plain: str, pwd: str) -> bytes:
    # Use a cryptographically random salt for each encryption
    salt = os.urandom(16)
    raw_key = _derive_key(pwd, salt)
    key = base64.urlsafe_b64encode(raw_key)
    token = Fernet(key).encrypt(plain.encode())
    del raw_key
    return salt + token

def _derive_key(pwd: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, PBKDF2_ITERATIONS, dklen=_DERIVED_KEY_LENGTH)

def init_session(sid: str, pwd: str) -> None:
    # Store a derived key instead of the plaintext password
    salt = os.urandom(16)
    derived = _derive_key(pwd, salt)
    # Store salt + derived key so we can verify later without keeping plaintext
    _session_keys[sid] = salt + derived

def verify_session(sid: str, pwd: str) -> bool:
    """Verify a password against the stored session credential."""
    stored = _session_keys.get(sid)
    if stored is None:
        return False
    salt, stored_key = stored[:16], stored[16:]
    candidate = _derive_key(pwd, salt)
    return hmac.compare_digest(candidate, stored_key)

def clear_session(sid: str) -> None:
    _session_keys.pop(sid, None)
