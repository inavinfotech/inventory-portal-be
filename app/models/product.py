from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ProductVariantBase(BaseModel):
    sku: str
    weight: str
    price: float = Field(..., gt=0)

class ProductVariantCreate(ProductVariantBase):
    pass

class ProductVariantUpdate(ProductVariantBase):
    id: Optional[int] = None

class ProductVariant(ProductVariantBase):
    id: int
    product_id: int
    stock: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    sku: str
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    images: Optional[List[str]] = None
    stock: int = 0

class ProductCreate(ProductBase):
    variants: Optional[List[ProductVariantCreate]] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    images: Optional[List[str]] = None
    variants: Optional[List[ProductVariantUpdate]] = None

class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    variants: List[ProductVariant] = []

    class Config:
        from_attributes = True

