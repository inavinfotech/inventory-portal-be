from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ApplicationBase(BaseModel):
    name: str
    is_active: Optional[bool] = True
    is_live_mode: Optional[bool] = False
    allowed_domains: Optional[str] = "*"

class ApplicationCreate(ApplicationBase):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None

class ApplicationUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    is_live_mode: Optional[bool] = None
    allowed_domains: Optional[str] = None

class AppStatusUpdate(BaseModel):
    is_active: bool

class AppModeUpdate(BaseModel):
    is_live_mode: bool

class AppDomainsUpdate(BaseModel):
    allowed_domains: str

class Application(ApplicationBase):
    id: str
    api_key: str
    api_secret: Optional[str] = None  # For one-time reveal during creation
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
