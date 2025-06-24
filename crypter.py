import base64
import hashlib
import os
from cryptography.fernet import Fernet


session_passwords: dict[str, str] = {}


def _derive_key(pwd: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, 100_000)


def encrypt_message(plain: str, pwd: str) -> bytes:
    salt = os.urandom(16)
    key = base64.urlsafe_b64encode(_derive_key(pwd, salt))
    return salt + Fernet(key).encrypt(plain.encode())


def decrypt_message(cipher: bytes, pwd: str) -> str:
    salt, token = cipher[:16], cipher[16:]
    key = base64.urlsafe_b64encode(_derive_key(pwd, salt))
    return Fernet(key).decrypt(token).decode()


def init_session(sid: str, pwd: str) -> None:
    session_passwords[sid] = pwd


def clear_session(sid: str) -> None:
    session_passwords.pop(sid, None)
