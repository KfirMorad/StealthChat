import base64
import hashlib
import os
import ctypes
from cryptography.fernet import Fernet

<<<<<<< HEAD
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
=======

# Passwords stored as bytearrays so they can be zeroed out after use
session_passwords: dict[str, bytearray] = {}


PBKDF2_ITERATIONS = 600_000  # Corrected from 6_000_030 to a secure, standard value
_DERIVED_KEY_LENGTH = 32  # 256 bits, required for Fernet (base64-encoded 32 bytes)


def _zero_bytearray(buf: bytearray) -> None:
    """Overwrite a bytearray in place with zeros to reduce secret exposure in memory."""
    for i in range(len(buf)):
        buf[i] = 0


def decrypt_message(cipher: bytes, pwd: str) -> str:
    salt, token = cipher[:16], cipher[16:]
    raw_key = bytearray(_derive_key(pwd, salt))
    try:
        key = base64.urlsafe_b64encode(bytes(raw_key))
        return Fernet(key).decrypt(token).decode()
    finally:
        _zero_bytearray(raw_key)


def encrypt_message(plain: str, pwd: str) -> bytes:
    salt = os.urandom(16)
    raw_key = bytearray(_derive_key(pwd, salt))
    try:
        key = base64.urlsafe_b64encode(bytes(raw_key))
        token = Fernet(key).encrypt(plain.encode())
    finally:
        # Zero out the raw key material from memory as soon as possible
        _zero_bytearray(raw_key)
>>>>>>> 8d7671c65619a4451ce573ac3a5b2b8882951557
    return salt + token


def _derive_key(pwd: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, PBKDF2_ITERATIONS, dklen=_DERIVED_KEY_LENGTH)


def init_session(sid: str, pwd: str) -> None:
    # Store password as a mutable bytearray so it can be zeroed on clear
    session_passwords[sid] = bytearray(pwd.encode())

def clear_session(sid: str) -> None:
<<<<<<< HEAD
    session_passwords.pop(sid, None)
=======
    buf = session_passwords.pop(sid, None)
    if buf is not None:
        _zero_bytearray(buf)
>>>>>>> 8d7671c65619a4451ce573ac3a5b2b8882951557
