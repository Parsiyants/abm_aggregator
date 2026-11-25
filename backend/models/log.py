# models/log.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from bson import ObjectId


class PollingLog(BaseModel):
    """Лог одного цикла поллинга"""
    id: Optional[ObjectId] = Field(alias="_id", default=None)
    
    # Время (Unix Timestamp)
    started_at: int  # ← int
    finished_at: Optional[int] = None  # ← int
    duration_seconds: Optional[float] = None
    status: str  # 'pending', 'success', 'partial', 'error'
    
    # Маркет
    market_type: Optional[str] = None
    cabinet_id: Optional[str] = None
    cabinet_name: Optional[str] = None
    
    # Статистика
    orders_touched: int = 0
    orders_created: int = 0
    orders_updated: int = 0
    orders_failed: int = 0
    items_created: int = 0
    items_updated: int = 0
    
    # Ошибки
    errors: List[Dict[str, Any]] = []
    error_message: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class SyncLog(BaseModel):
    """Лог синхронизации с маркетплейсом"""
    id: Optional[ObjectId] = Field(alias="_id", default=None)

    started_at: int
    finished_at: Optional[int] = None
    duration_seconds: Optional[float] = None

    sync_type: str
    market_type: str
    cabinet_id: str
    cabinet_name: str

    # Общая статистика
    total_items: int = 0
    success_count: int = 0
    failed_count: int = 0

    # Детализация (WB: prices + stocks)
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    # ── Плоские поля для WB-синхронизации ──
    yml_items_total: int = 0
    wb_goods_total: int = 0
    matched: int = 0
    unmatched_wb: int = 0

    prices_updated: int = 0
    prices_skipped: int = 0

    stocks_updated: int = 0
    stocks_zeroed: int = 0
    stocks_skipped: int = 0

    status: str = 'pending'
    error_message: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}