import base64
import hashlib
import os
import ctypes
from cryptography.fernet import Fernet


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
    return salt + token


def _derive_key(pwd: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, PBKDF2_ITERATIONS, dklen=_DERIVED_KEY_LENGTH)


def init_session(sid: str, pwd: str) -> None:
    # Store password as a mutable bytearray so it can be zeroed on clear
    session_passwords[sid] = bytearray(pwd.encode())


def clear_session(sid: str) -> None:
    buf = session_passwords.pop(sid, None)
    if buf is not None:
        _zero_bytearray(buf)
