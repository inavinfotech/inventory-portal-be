from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ReservationBase(BaseModel):
    product_id: str
    variant_id: Optional[str] = None
    quantity: int = Field(..., gt=0)


class ReservationCreate(ReservationBase):
    pass


class Reservation(ReservationBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
