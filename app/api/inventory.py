from fastapi import APIRouter, HTTPException, status, Path, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.stock_service import stock_service
from app.db.database import db_helper
from app.auth.deps import get_authenticated_user

router = APIRouter(prefix="/inventory", tags=["inventory"], dependencies=[Depends(get_authenticated_user)])


class StockResponse(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    quantity: int


class StockUpdate(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    quantity: int = Field(..., gt=0)
    reference_id: Optional[str] = Field(None, min_length=1)


class StockAdjust(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    new_quantity: int = Field(..., ge=0)
    reference_id: Optional[str] = Field(None, min_length=1)


class LowStockResponse(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    name: str
    sku: str
    current_quantity: int
    threshold: int


@router.get("/stats")
async def dashboard_stats():
    return await stock_service.get_dashboard_stats()


@router.get("/low-stock", response_model=List[LowStockResponse])
async def get_low_stock():
    async with db_helper.get_db_connection() as db:
        async with db.execute("""
            SELECT p.id, v.id as variant_id, p.name, COALESCE(v.sku, p.sku) as sku,
                   i.quantity, i.low_stock_threshold
            FROM inventory i
            JOIN products p ON i.product_id = p.id
            LEFT JOIN product_variants v ON i.variant_id = v.id
            WHERE i.quantity < i.low_stock_threshold
        """) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "product_id": r[0],
                    "variant_id": r[1],
                    "name": r[2],
                    "sku": r[3],
                    "current_quantity": r[4],
                    "threshold": r[5],
                }
                for r in rows
            ]


@router.get("/{product_id}", response_model=StockResponse)
async def get_stock(
    product_id: str = Path(..., min_length=1),
    variant_id: Optional[str] = Query(None)
):
    quantity = await stock_service.get_stock(product_id, variant_id)
    return {"product_id": product_id, "variant_id": variant_id, "quantity": quantity}


@router.post("/add", response_model=StockResponse)
async def add_stock(update: StockUpdate):
    try:
        new_qty = await stock_service.add_stock(update.product_id, update.quantity, update.reference_id, update.variant_id)
        return {"product_id": update.product_id, "variant_id": update.variant_id, "quantity": new_qty}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/remove", response_model=StockResponse)
async def remove_stock(update: StockUpdate):
    try:
        new_qty = await stock_service.remove_stock(update.product_id, update.quantity, update.reference_id, update.variant_id)
        return {"product_id": update.product_id, "variant_id": update.variant_id, "quantity": new_qty}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/adjust", response_model=StockResponse)
async def adjust_stock(update: StockAdjust):
    try:
        new_qty = await stock_service.adjust_stock(update.product_id, update.new_quantity, update.reference_id, update.variant_id)
        return {"product_id": update.product_id, "variant_id": update.variant_id, "quantity": new_qty}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class BulkItem(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    quantity: int = Field(..., gt=0)
    type: str = Field(..., pattern="^(IN|OUT|ADJUST)$")
    reference_id: Optional[str] = Field(None, min_length=1)


class BulkUpdate(BaseModel):
    updates: List[BulkItem]


class BulkResult(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    status: str
    message: Optional[str] = None
    new_quantity: Optional[int] = None


@router.post("/bulk-update", response_model=List[BulkResult])
async def bulk_update(batch: BulkUpdate):
    results = []
    for item in batch.updates:
        try:
            if item.type == "IN":
                qty = await stock_service.add_stock(item.product_id, item.quantity, item.reference_id, item.variant_id)
            elif item.type == "OUT":
                qty = await stock_service.remove_stock(item.product_id, item.quantity, item.reference_id, item.variant_id)
            else:  # ADJUST
                qty = await stock_service.adjust_stock(item.product_id, item.quantity, item.reference_id, item.variant_id)

            results.append(BulkResult(product_id=item.product_id, variant_id=item.variant_id, status="success", new_quantity=qty))
        except Exception as e:
            results.append(BulkResult(product_id=item.product_id, variant_id=item.variant_id, status="error", message=str(e)))
    return results


@router.post("/bulk-add", response_model=List[dict])
async def bulk_add(batch: BulkUpdate):
    try:
        updates = [
            {"product_id": i.product_id, "variant_id": i.variant_id, "quantity": i.quantity, "reference_id": i.reference_id}
            for i in batch.updates if i.type == "IN"
        ]
        if not updates:
            raise HTTPException(status_code=400, detail="No 'IN' type updates provided")
        return await stock_service.bulk_add_stock(updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk-remove", response_model=List[dict])
async def bulk_remove(batch: BulkUpdate):
    try:
        updates = [
            {"product_id": i.product_id, "variant_id": i.variant_id, "quantity": i.quantity, "reference_id": i.reference_id}
            for i in batch.updates if i.type == "OUT"
        ]
        if not updates:
            raise HTTPException(status_code=400, detail="No 'OUT' type updates provided")
        return await stock_service.bulk_remove_stock(updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
