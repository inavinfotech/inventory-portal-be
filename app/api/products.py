from fastapi import APIRouter, HTTPException, Query, status, Path, Response
from typing import List
from app.models.product import Product, ProductCreate
from app.models.common import PaginatedResponse
from app.services.product_service import product_service
from app.auth.deps import get_current_app
from fastapi import Depends

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(get_current_app)])

@router.get("/", response_model=PaginatedResponse[Product])
async def list_products(
    limit: int = Query(10, gt=0, le=100),
    offset: int = Query(0, ge=0)
):
    items, total = await product_service.get_products(limit, offset)
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: int = Path(..., gt=0)):
    product = await product_service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.post("/", response_model=Product)
async def create_product(product: ProductCreate, response: Response):
    existing = await product_service.get_product_by_sku(product.sku)
    if existing:
        response.status_code = status.HTTP_200_OK
        return existing
    
    response.status_code = status.HTTP_201_CREATED
    return await product_service.create_product(product)
