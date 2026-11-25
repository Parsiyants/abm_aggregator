# models/sync.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from bson import ObjectId


class YmlItem(BaseModel):
    """Товар из YML-файла"""
    offer_id: str
    vendor: str
    vendor_code: str
    name: str
    price: float
    instock: int
    warehouse_id: int


class PriceUpdate(BaseModel):
    """Обновление цены для WB"""
    nmID: int
    price: int
    discount: int


class StockUpdate(BaseModel):
    """Обновление остатка для WB"""
    chrtId: int
    amount: int


class SyncResult(BaseModel):
    """Результат синхронизации одного кабинета"""
    success: bool
    cabinet_id: str
    cabinet_name: str
    warehouse_id: Optional[int] = None
    yml_items_total: int = 0
    wb_goods_total: int = 0
    matched: int = 0
    unmatched_wb: int = 0
    prices_updated: int = 0
    stocks_updated: int = 0
    duration_seconds: float = 0
    errors: List[str] = Field(default_factory=list)