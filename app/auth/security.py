from passlib.hash import sha256_crypt
import secrets

def verify_secret(plain_secret: str, hashed_secret: str) -> bool:
    return sha256_crypt.verify(plain_secret, hashed_secret)

def get_secret_hash(secret: str) -> str:
    return sha256_crypt.hash(secret)

def generate_api_key() -> str:
    return f"inv_key_{secrets.token_hex(6)}"

def generate_api_secret() -> str:
    return f"inv_sec_{secrets.token_hex(12)}"
