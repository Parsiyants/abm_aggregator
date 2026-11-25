from abc import ABC, abstractmethod
from typing import List, Optional
from repositories.order_repo import OrderRepository
from models.order import OrderIn

# Абстрактный класс для всех адаптеров маркетплейсов
class BaseMarketplaceAdapter(ABC):
    """
    Определяет минимальный набор методов, которые должен реализовать
    любой адаптер маркетплейса (Ozon, WB, Yandex).
    """

    def __init__(self, cabinet_data: dict, order_repo: OrderRepository):
        """
        Инициализирует адаптер данными кабинета (API-ключи, client_id и т.д.)
        и объектом репозитория для сохранения данных.
        """
        self.cabinet = cabinet_data
        self.repo = order_repo
        self.api_key = cabinet_data.get('api_key')
        self.client_id = cabinet_data.get('client_id')
        self.market_slug = cabinet_data.get('market_slug')

    # ------------------------------------------------------------------------
    # I. МЕТОДЫ ДЛЯ ПОЛЛИНГА (ФОНОВЫЙ ОПРОС)
    # ------------------------------------------------------------------------

    @abstractmethod
    async def fetch_new_and_updated_orders(self) -> int:
        """
        Основной метод для фонового опроса.
        Должен получить заказы за последние 14 дней и вызвать upsert_order.
        Возвращает: количество обработанных заказов.
        """
        pass

    # ------------------------------------------------------------------------
    # II. МЕТОДЫ ДЛЯ РУЧНОЙ ОБРАБОТКИ
    # ------------------------------------------------------------------------
    
    @abstractmethod
    async def get_full_details_by_id(self, external_order_id: str) -> dict:
        """Получает полные детали заказа по запросу."""
        pass

    @abstractmethod
    async def update_market_status(self, external_order_id: str, new_market_status: str) -> bool:
        """Изменяет статус заказа на стороне маркетплейса."""
        pass

    @abstractmethod
    async def get_shipping_label(self, external_ids: List[str]) -> Optional[bytes]:
        """Получает этикетку для отгрузки в виде байтов (PDF)."""
        pass

    @abstractmethod
    async def can_print_label(self, status: str) -> bool:
        """Проверяет, можно ли печатать этикетку для данного статуса"""
        pass

    # Вспомогательный метод маппинга будет в конкретных адаптерах.