from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Inventory Management System"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    ALLOWED_ORIGINS: list[str] = ["http://localhost:8000"]
    DASHBOARD_TOKEN: str = "admin-token" # Change in production
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./inventory.db"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
