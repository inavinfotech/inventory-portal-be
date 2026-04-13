from pydantic import BaseModel, Field
from typing import List, Optional

class StockUpdateItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    reference_id: Optional[str] = None

class BulkStockUpdate(BaseModel):
    updates: List[StockUpdateItem]
    reference_id: Optional[str] = None
