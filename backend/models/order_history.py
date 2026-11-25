# models/order_history.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from bson import ObjectId


class OrderHistoryEntry(BaseModel):
    """Запись в истории заказа"""
    id: Optional[ObjectId] = Field(alias="_id", default=None)
    
    # Связь с заказом
    order_id_ref: str
    order_id: str
    market_type: str
    
    # Событие
    event_type: str
    event_source: str
    
    # Что изменилось
    changes: Dict[str, Any] = {}
    
    # Пользователь
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    comment: Optional[str] = None
    
    # Статусы
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    
    # Время (Unix Timestamp)
    created_at: int  # ← int
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}