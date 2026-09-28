from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class TransactionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    amount: float = Field(..., gt=0, description="Nominal harus lebih besar dari 0")
    category: str = Field(..., min_length=1)
    transaction_type: str # 'income' or 'expense'
    transaction_date: datetime
    note: Optional[str] = None

class TransactionUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    transaction_type: Optional[str] = None
    transaction_date: Optional[datetime] = None
    note: Optional[str] = None

class TransactionOut(BaseModel):
    id: int
    title: str
    amount: float
    category: str
    transaction_type: str
    transaction_date: datetime
    note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
