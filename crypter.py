import base64
import hashlib
import os
from cryptography.fernet import Fernet


session_passwords: dict[str, str] = {}


PBKDF2_ITERATIONS = 600_0030
_DERIVED_KEY_LENGTH = 32  # 256 bits, required for Fernet (base64-encoded 32 bytes)


def encrypt_message(plain: str, pwd: str) -> bytes:
    salt = os.urandom(16)
    raw_key = _derive_key(pwd, salt)
    key = base64.urlsafe_b64encode(raw_key)
    token = Fernet(key).encrypt(plain.encode())
    # Zero out the raw key material from memory as soon as possible
    del raw_key
    return salt + token

def _derive_key(pwd: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, PBKDF2_ITERATIONS, dklen=_DERIVED_KEY_LENGTH)

def decrypt_message(cipher: bytes, pwd: str) -> str:
    salt, token = cipher[:16], cipher[16:]
    raw_key = _derive_key(pwd, salt)
    key = base64.urlsafe_b64encode(raw_key)
    del raw_key
    return Fernet(key).decrypt(token).decode()


def init_session(sid: str, pwd: str) -> None:
    session_passwords[sid] = pwd


def clear_session(sid: str) -> None:
    session_passwords.pop(sid, None)
