from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.schemas.application import (
    ApplicationCreate,
    Application as ApplicationSchema,
    AppStatusUpdate,
    AppModeUpdate,
    AppDomainsUpdate,
)
from app.services.application_service import application_service

router = APIRouter(prefix="/apps", tags=["Applications"])

@router.post("", response_model=ApplicationSchema, status_code=status.HTTP_201_CREATED)
async def create_app(app_in: ApplicationCreate):
    db_app, plain_secret = await application_service.create_application(app_in)
    
    # Return with plain secret for one-time reveal
    response_data = dict(db_app)
    response_data["api_secret"] = plain_secret
    return response_data

@router.get("", response_model=List[ApplicationSchema])
async def list_apps(limit: int = 100, offset: int = 0):
    return await application_service.get_applications(limit, offset)

@router.get("/{app_id}", response_model=ApplicationSchema)
async def get_app(app_id: str):
    app = await application_service.get_application_by_id(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app

@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app(app_id: str):
    success = await application_service.delete_application(app_id)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    return None
