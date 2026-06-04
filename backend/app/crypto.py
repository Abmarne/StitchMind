from cryptography.fernet import Fernet
from app.config import ENCRYPTION_KEY_PATH

def get_encryption_key() -> bytes:
    """Gets or generates a symmetric key for local encryption."""
    if not ENCRYPTION_KEY_PATH.exists():
        key = Fernet.generate_key()
        ENCRYPTION_KEY_PATH.write_bytes(key)
    else:
        key = ENCRYPTION_KEY_PATH.read_bytes()
    return key

def encrypt_value(value: str) -> str:
    """Encrypts a string value using the local symmetric key."""
    if not value:
        return ""
    key = get_encryption_key()
    fernet = Fernet(key)
    return fernet.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value: str) -> str:
    """Decrypts a string value using the local symmetric key."""
    if not encrypted_value:
        return ""
    key = get_encryption_key()
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_value.encode()).decode()
