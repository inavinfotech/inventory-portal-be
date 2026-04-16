from fastapi import Depends, HTTPException, Header, status
from app.services.application_service import application_service
from typing import Optional

async def get_current_app(
    x_api_key: str = Header(None),
    x_api_secret: str = Header(None)
):
    if not x_api_key or not x_api_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key and Secret are required"
        )
    
    app = await application_service.get_application_by_api_key(x_api_key)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    
    from app.auth.security import verify_secret
    if not verify_secret(x_api_secret, app["api_secret"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Secret"
        )
    
    return app

from app.core.config import settings

async def verify_dashboard_auth(
    authorization: str = Header(None)
):
    # Simplified for now, could be expanded to JWT like order-portal
    if authorization == f"Bearer {settings.DASHBOARD_TOKEN}":
        return True
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Dashboard authentication required"
    )

async def get_authenticated_user(
    x_api_key: Optional[str] = Header(None),
    x_api_secret: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    # Try dashboard auth first
    if authorization == f"Bearer {settings.DASHBOARD_TOKEN}":
        return {"type": "user", "name": "admin"}
    
    # Otherwise try app auth
    if x_api_key and x_api_secret:
        return await get_current_app(x_api_key, x_api_secret)
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials required"
    )
