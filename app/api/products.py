from fastapi import APIRouter, HTTPException, Query, status, Path, Response
from typing import List
from app.models.product import Product, ProductCreate
from app.models.common import PaginatedResponse
from app.services.product_service import product_service
from app.auth.deps import get_authenticated_user
from fastapi import Depends, File, UploadFile
import uuid
import os
import shutil
from app.core.config import settings

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(get_authenticated_user)])

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

@router.post("/upload-images", response_model=List[str])
async def upload_images(files: List[UploadFile] = File(...)):
    uploaded_urls = []
    
    # Base directory for uploads
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_dir = os.path.join(base_dir, "uploads", "products")
    
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    for file in files:
        # Generate unique filename
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(upload_dir, filename)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Return the relative URL
        uploaded_urls.append(f"/uploads/products/{filename}")
        
    return uploaded_urls
