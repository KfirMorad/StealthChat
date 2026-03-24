import base64
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# session_passwords stores {session_id: password_string}
session_passwords: dict[str, str] = {}


def _derive_key(password: str) -> bytes:
    """Derive a 32-byte AES key from the password using SHA-256."""
    import hashlib
    return hashlib.sha256(password.encode()).digest()


def init_session(session_id: str, password: str) -> None:
    session_passwords[session_id] = password


def encrypt_message(plaintext: str, password: str) -> bytes:
    """Encrypt plaintext using AES-256-GCM. Returns nonce + tag + ciphertext."""
    key = _derive_key(password)
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
    # nonce is 16 bytes, tag is 16 bytes
    return cipher.nonce + tag + ciphertext


def decrypt_message(data: bytes, password: str) -> str:
    """Decrypt AES-256-GCM encrypted data. Expects nonce + tag + ciphertext."""
    key = _derive_key(password)
    nonce = data[:16]
    tag = data[16:32]
    ciphertext = data[32:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return plaintext.decode("utf-8")
