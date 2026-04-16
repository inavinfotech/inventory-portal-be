from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.auth import LoginRequest, Token
from app.core.config import settings
from app.auth.security import create_access_token
import secrets

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    if login_data.email != settings.ADMIN_EMAIL or not secrets.compare_digest(login_data.password, settings.ADMIN_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Email or Password",
        )
    
    access_token = create_access_token(data={"sub": login_data.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/verify")
async def verify_token(user: dict = Depends(lambda: {"status": "valid"})):
    # You might want to add real token verification dependency here later
    return {"status": "valid"}
