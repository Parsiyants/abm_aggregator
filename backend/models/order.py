# models/order.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MongoBase(BaseModel):
    id: Optional[str] = Field(None, alias="_id")

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda dt: dt.isoformat()}


# --- ПОЗИЦИИ В ЗАКАЗЕ (OrderItems) ---
class OrderItem(MongoBase):
    """Модель для отдельной позиции в заказе."""

    order_id_ref: str = Field(..., description="ID родительского заказа в нашей базе.")

    article: str = Field(..., description="Артикул товара.")
    name: str = Field(..., description="Название товара.")
    price: float = Field(..., description="Цена продажи за единицу.")
    count: int = Field(..., description="Количество.")

    purchase: Optional[float] = None
    provider: Optional[str] = Field(default=None, description="Название поставщика(ов).")
    status: Optional[str] = Field(default=None, description="Ваш детальный статус.")

    # ── временные поля — всегда int (Unix Timestamp) ──
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class OrderItemHandle(BaseModel):
    item_id: str = Field(..., alias="item_id")
    purchase: Optional[float] = None
    provider: Optional[str] = None
    status: Optional[str] = None


class OrderHandleRequest(BaseModel):
    # ── на входе принимаем datetime (Pydantic парсит ISO) ──
    my_send_date: Optional[datetime] = None
    comment: Optional[str] = None
    items: List[OrderItemHandle] = Field(default_factory=list)


class ItemStatusUpdate(BaseModel):
    item_id: str
    status: str


class BulkItemStatusUpdate(BaseModel):
    updates: List[ItemStatusUpdate]


class Analytics(BaseModel):
    """Аналитика и расходы по заказу (считается один раз при создании)."""
    commission_market_percent: float
    commission_market_total: float
    commission_payment_percent: float
    commission_payment_total: float
    last_mile_percent: float
    last_mile_max: float
    last_mile_total: float
    processing_fixed: float
    logistics_total: float
    penalty: float = 0
    total_expenses: float
    profit: float


class Order(MongoBase):
    """Основная модель Заказа. Все временные поля — int (Unix Timestamp)."""

    order_id: str
    order_number: Optional[str] = Field(
        None, description="Номер заказа на маркетплейсе (без индекса отправления)."
    )
    market_type: str
    cabinet_name: str

    # ── Все даты: int ──
    order_date: int = Field(..., description="Дата создания заказа (Unix Timestamp).")
    send_date: Optional[int] = Field(None, description="Ожидаемая дата отгрузки (Unix Timestamp).")
    my_send_date: Optional[int] = Field(None, description="Наша дата отгрузки (Unix Timestamp).")

    market_status: str
    substatus: Optional[str] = Field(
        None, description="Детализированный статус отправления на маркетплейсе."
    )
    process_status: str = Field(default="New")
    cancellation_type: Optional[str] = None

    # ── доставка ──
    tracking_number: Optional[str] = None
    delivery_schema: Optional[str] = Field(None, description="Схема доставки (fbs, fbo...).")
    scanit: Optional[str] = Field(None, description="Штрихкод отправления.")

    price: Optional[float] = None
    order_count: Optional[float] = 1

    comment: Optional[str] = None
    analytics: Optional[Analytics] = None

    # ── служебные ──
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class OrderIn(BaseModel):
    order_data: Order
    items_data: List[OrderItem]


class StatusStatItem(BaseModel):
    status: str
    count: int


class MarketStatusStats(BaseModel):
    market_type: str
    total: int
    statuses: List[StatusStatItem]


class StatusStatsResponse(BaseModel):
    markets: List[MarketStatusStats]
    total_orders: int