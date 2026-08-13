from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
from datetime import datetime
import re

SKU_PATTERN = re.compile(r"^[A-Za-z0-9\-_.]+$")

def validate_sku_value(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    s = v.strip()
    if not s:
        raise ValueError("SKU ID cannot be empty or blank")
    if len(s) > 64:
        raise ValueError(f"SKU ID length exceeds limit (max 64 characters allowed, got {len(s)})")
    if not SKU_PATTERN.match(s):
        raise ValueError("SKU ID must strictly contain only alphanumeric characters, hyphens, underscores, or dots with no spaces")
    return s


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
    mrp: Optional[float] = Field(None, gt=0)
    images: Optional[List[str]] = None

    @field_validator("sku")
    @classmethod
    def validate_variant_sku(cls, v: str) -> str:
        return validate_sku_value(v)

class ProductVariantCreate(ProductVariantBase):
    initial_stock: Optional[int] = 0
    # attributes: map of type_name → option_value, e.g. {"Color": "Red", "Size": "M"}
    attributes: Optional[Dict[str, str]] = None

class ProductVariantUpdate(BaseModel):
    id: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    mrp: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = None
    images: Optional[List[str]] = None
    attributes: Optional[Dict[str, str]] = None

    @field_validator("sku")
    @classmethod
    def validate_variant_update_sku(cls, v: Optional[str]) -> Optional[str]:
        return validate_sku_value(v)

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

    @field_validator("sku")
    @classmethod
    def validate_product_sku(cls, v: str) -> str:
        return validate_sku_value(v)

class ProductCreate(ProductBase):
    variant_types: Optional[List[VariantTypeCreate]] = None
    variants: Optional[List[ProductVariantCreate]] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[float] = Field(None, gt=0)
    discounted_price: Optional[float] = None
    images: Optional[List[str]] = None
    variant_types: Optional[List[VariantTypeCreate]] = None
    variants: Optional[List[ProductVariantUpdate]] = None

    @field_validator("sku")
    @classmethod
    def validate_product_update_sku(cls, v: Optional[str]) -> Optional[str]:
        return validate_sku_value(v)

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
