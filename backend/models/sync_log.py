# models/sync_log.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class SyncLog(BaseModel):
    """Лог синхронизации с маркетплейсом"""
    id: Optional[ObjectId] = Field(alias="_id", default=None)
    
    # Тип синхронизации
    sync_type: str  # 'prices', 'stocks', 'orders', 'full'
    market_type: str
    cabinet_id: str
    cabinet_name: str
    
    # Время
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Статистика
    total_items: int = 0
    success_count: int = 0
    failed_count: int = 0
    
    # Детали
    items: List[Dict[str, Any]] = []  # [{article, old_price, new_price, status}]
    errors: List[Dict[str, Any]] = []
    
    # Статус
    status: str = 'pending'  # 'pending', 'success', 'partial', 'error'
    
    class Config:
        arbitrary_types_allowed = True