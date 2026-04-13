from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Movement(BaseModel):
    id: int
    product_id: int
    quantity: int
    type: str
    reference_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
