from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


# ─────────────────────────────────────────────
#  Variant Option
# ─────────────────────────────────────────────

class VariantOption(BaseModel):
    id: str
    variant_type_id: str
    value: str
    display_order: int = 0

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
#  Variant Type  (the "niche")
# ─────────────────────────────────────────────

class VariantTypeBase(BaseModel):
    name: str
    display_order: int = 0

class VariantTypeCreate(VariantTypeBase):
    options: List[str] = Field(..., min_length=1, description="List of option values for this type")

class VariantType(VariantTypeBase):
    id: str
    product_id: str
    options: List[str] = []        # flattened to just the values for API response

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
#  Product Variant
# ─────────────────────────────────────────────

class ProductVariantBase(BaseModel):
    sku: str
    price: float = Field(..., gt=0)
    images: Optional[List[str]] = None

class ProductVariantCreate(ProductVariantBase):
    initial_stock: Optional[int] = 0
    # attributes: map of type_name → option_value, e.g. {"Color": "Red", "Size": "M"}
    attributes: Optional[Dict[str, str]] = None

class ProductVariantUpdate(BaseModel):
    id: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = None
    images: Optional[List[str]] = None
    attributes: Optional[Dict[str, str]] = None

class ProductVariant(ProductVariantBase):
    id: str
    product_id: str
    stock: int = 0
    reserved: int = 0
    images: Optional[List[str]] = []
    # Dynamic attributes map, e.g. {"Color": "Red", "Size": "M"}
    attributes: Dict[str, str] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
#  Product
# ─────────────────────────────────────────────

class ProductBase(BaseModel):
    name: str
    sku: str
    description: Optional[str] = None
    base_price: float = Field(..., gt=0)
    discounted_price: Optional[float] = Field(None, gt=0)
    images: Optional[List[str]] = None

class ProductCreate(ProductBase):
    variant_types: Optional[List[VariantTypeCreate]] = None
    variants: Optional[List[ProductVariantCreate]] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[float] = Field(None, gt=0)
    discounted_price: Optional[float] = None
    images: Optional[List[str]] = None
    variant_types: Optional[List[VariantTypeCreate]] = None
    variants: Optional[List[ProductVariantUpdate]] = None

class Product(ProductBase):
    id: str
    stock: int = 0
    reserved: int = 0
    variant_types: List[VariantType] = []
    variants: List[ProductVariant] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
