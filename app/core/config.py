from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Inventory Management System"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    ALLOWED_ORIGINS: list[str] = ["*"]
    DASHBOARD_TOKEN: str = "admin-token" # Change in production
    
    # Auth
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480 # 8 hours
    ADMIN_EMAIL: str = "admin@tianaluxora.com"
    ADMIN_PASSWORD: str = "admin123"
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./inventory.db"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
