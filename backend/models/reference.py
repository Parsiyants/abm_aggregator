from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# --- Вспомогательный класс для ID MongoDB ---
class MongoBase(BaseModel):
    # Позволяет Pydantic корректно работать с ObjectId MongoDB
    id: Optional[str] = Field(None, alias="_id")

    class Config:
        populate_by_name = True
        json_encoders = {
            # Конвертируем datetime в ISO-формат для JSON
            datetime: lambda dt: dt.isoformat()
        }

# --- 1. MARKETPLACES ---
class Marketplace(MongoBase):
    """Справочник: Маркетплейсы."""
    name: str = Field(..., description="Человекочитаемое название (Ozon, Wildberries)")
    slug: str = Field(..., description="Технический ключ для Адаптера (ozon, wb)")
    color: str = Field(default="#cccccc", description="HEX-код цвета для UI")
    active: bool = Field(default=True, description="Активность для фонового опроса")

# --- 2. CABINETS (МАГАЗИНЫ / Учетные записи) ---
class Cabinet(MongoBase):
    """Справочник: Учетные записи / Магазины."""
    market_slug: str = Field(..., description="Slug маркетплейса (связь с Marketplace)")
    name: str = Field(..., description="Имя магазина/кабинета (например, abmauto)")
    api_key: str = Field(..., description="API ключ или токен (в продакшене должен быть зашифрован)")
    client_id: Optional[str] = Field(None, description="ID клиента/продавца (если требуется API)")
    business_id: Optional[str] = Field(None, description="Business ID клиента/продавца (если требуется API)")
    suffix: Optional[str] = Field(None, description="Идентификатор для группировки/склада")
    model: str = Field(..., description="Модель работы (FBS, DBS, Express)")
    active: bool = Field(default=True)
    last_poll_time: Optional[datetime] = Field(None, description="Время последнего успешного опроса")


# --- 3. MY STATUSES ---
class MyStatus(MongoBase):
    """Справочник: Ваши внутренние статусы обработки (для OrderItem)."""
    name: str = Field(..., description="Название статуса (В наличии, Заказан)")
    code: str = Field(..., description="Технический код статуса (in_stock, ordered)")
    color: str = Field(default="#999999")
    index: int = Field(default=10)
    active: bool = Field(default=True)


# --- 4. PROVIDERS ---
class Provider(MongoBase):
    """Справочник: Поставщики."""
    name: str = Field(..., description="Название поставщика")
    index: int = Field(default=10, description="Порядок для сортировки")
    active: bool = Field(default=True)