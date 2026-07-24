from fastapi import APIRouter, HTTPException, status
from app.models.reservation import Reservation, ReservationCreate
from app.services.reservation_service import reservation_service

router = APIRouter(prefix="/inventory", tags=["reservations"])


@router.post("/reserve", response_model=Reservation, status_code=status.HTTP_201_CREATED)
async def reserve_stock(req: ReservationCreate):
    try:
        return await reservation_service.create_reservation(req.product_id, req.quantity, req.variant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/confirm/{reservation_id}", response_model=Reservation)
async def confirm_reservation(reservation_id: str):
    try:
        return await reservation_service.confirm_reservation(reservation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/release/{reservation_id}", response_model=Reservation)
async def release_reservation(reservation_id: str):
    try:
        return await reservation_service.release_reservation(reservation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{product_id}/available")
async def get_available(product_id: str):
    available = await reservation_service.get_available_stock(product_id)
    return {"product_id": product_id, "available_quantity": available}


@router.get("/", response_model=dict)
async def list_reservations(limit: int = 10, offset: int = 0):
    items, total = await reservation_service.get_reservations(limit, offset)
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.post("/cleanup")
async def cleanup_stale(minutes: int = 30):
    count = await reservation_service.cleanup_stale_reservations(minutes)
    return {"status": "success", "released_count": count}
