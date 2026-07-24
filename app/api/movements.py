from fastapi import APIRouter, Query
from typing import List, Optional
from app.models.movement import Movement
from app.models.common import PaginatedResponse
from app.services.movement_service import movement_service
from app.auth.deps import get_authenticated_user
from fastapi import Depends

router = APIRouter(
    prefix="/inventory/movements",
    tags=["inventory"],
    dependencies=[Depends(get_authenticated_user)]
)


@router.get("/", response_model=PaginatedResponse[Movement])
async def list_movements(
    product_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None, pattern="^(IN|OUT|ADJUST)$"),
    reference_id: Optional[str] = Query(None),
    limit: int = Query(10, gt=0, le=100),
    offset: int = Query(0, ge=0)
):
    items, total = await movement_service.get_movements(
        product_id=product_id,
        type=type,
        reference_id=reference_id,
        limit=limit,
        offset=offset
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }
