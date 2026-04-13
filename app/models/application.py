from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.database import Base
import uuid

class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    api_key = Column(String, unique=True, index=True)
    api_secret = Column(String)
    is_active = Column(Boolean, default=True)
    is_live_mode = Column(Boolean, default=False)
    allowed_domains = Column(String, default="*")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
