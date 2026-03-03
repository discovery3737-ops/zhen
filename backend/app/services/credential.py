"""
Credential 管理：storageState 加密入库、登录校验
"""
import base64
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..config import CREDENTIAL_ENCRYPT_KEY


def _derive_key() -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"crawler_credential_salt",
        iterations=100000,
    )
    pwd = CREDENTIAL_ENCRYPT_KEY.encode().ljust(32, b"0")[:32]
    derived = kdf.derive(pwd)
    return base64.urlsafe_b64encode(derived)


def encrypt_storage_state(state: dict) -> str:
    raw = json.dumps(state, ensure_ascii=False)
    f = Fernet(_derive_key())
    return f.encrypt(raw.encode()).decode()


def decrypt_storage_state(encrypted: str) -> dict:
    f = Fernet(_derive_key())
    raw = f.decrypt(encrypted.encode()).decode()
    return json.loads(raw)
