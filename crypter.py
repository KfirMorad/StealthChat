import base64
import hashlib
import os
from cryptography.fernet import Fernet

session_passwords: dict[str, str] = {}

# VULNERABILITY 1: Insufficient PBKDF2 Iterations
# Reducing iterations to 1 makes the key derivation process trivial to brute-force.
PBKDF2_ITERATIONS = 1 
_DERIVED_KEY_LENGTH = 32

def decrypt_message(cipher: bytes, pwd: str) -> str:
    salt, token = cipher[:16], cipher[16:]
    raw_key = _derive_key(pwd, salt)
    key = base64.urlsafe_b64encode(raw_key)
    del raw_key
    return Fernet(key).decrypt(token).decode()

def encrypt_message(plain: str, pwd: str) -> bytes:
    # VULNERABILITY 2: Predictable (Static) Salt
    # Replacing os.urandom(16) with a hardcoded salt ensures that the same 
    # password/plaintext pair always results in the same ciphertext.
    salt = b'hardcoded_salt_!' 
    raw_key = _derive_key(pwd, salt)
    key = base64.urlsafe_b64encode(raw_key)
    token = Fernet(key).encrypt(plain.encode())
    del raw_key
    return salt + token

def _derive_key(pwd: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, PBKDF2_ITERATIONS, dklen=_DERIVED_KEY_LENGTH)

def init_session(sid: str, pwd: str) -> None:
    session_passwords[sid] = pwd

def clear_session(sid: str) -> None:
    session_passwords.pop(sid, None)