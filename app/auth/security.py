from passlib.hash import sha256_crypt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt
from app.core.config import settings

def verify_secret(plain_secret: str, hashed_secret: str) -> bool:
    return sha256_crypt.verify(plain_secret, hashed_secret)

def get_secret_hash(secret: str) -> str:
    return sha256_crypt.hash(secret)

def generate_api_key() -> str:
    return f"app_{secrets.token_hex(12)}"

def generate_api_secret() -> str:
    return secrets.token_urlsafe(32)[:40]

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    import logging
    logger = logging.getLogger("uvicorn.error")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except Exception as e:
        logger.error(f"JWT Decode Error: {str(e)}")
        return None

