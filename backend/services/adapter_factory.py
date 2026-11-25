# backend/services/adapter_factory.py

from marketplaces.yandex_adapter import YandexMarketAdapter
from marketplaces.base import BaseMarketplaceAdapter
from marketplaces.ozon_adapter import OzonAdapter
from marketplaces.wb_adapter import WildberriesAdapter

from repositories.order_repo import OrderRepository
from repositories.reference_repo import ReferenceRepository
from typing import Dict, Type, Optional
from functools import lru_cache 

# 1. МАППИНГ: Связь market_slug с классом адаптера
ADAPTER_MAP: Dict[str, Type[BaseMarketplaceAdapter]] = {
    "ozon": OzonAdapter,
    "yandex": YandexMarketAdapter,
    "wb": WildberriesAdapter, 
}

class AdapterFactory:
    """
    Фабрика для динамического создания и получения экземпляров адаптеров.
    Отвечает за поиск конфигурации кабинета и инстанцирование нужного класса.
    """
    def __init__(self):
        # Репозитории создаются один раз для Фабрики
        self.reference_repo = ReferenceRepository()
        self.order_repo = OrderRepository()

    async def get_adapter_for_cabinet_id(self, cabinet_id: str) -> Optional[BaseMarketplaceAdapter]:
        """
        Находит данные кабинета по _id, создает и возвращает соответствующий адаптер.
        Используется в роутерах для действий с заказами.
        """
        # 1. Получаем данные кабинета из БД
        # Используем репозиторий для получения всех данных: slug, api_key и т.д.
        cabinet_data = await self.reference_repo.get_by_id("cabinets", cabinet_id)
        
        if not cabinet_data:
            return None

        market_slug = cabinet_data.get('market_slug')
        
        # 2. Выбираем класс адаптера по market_slug
        AdapterClass = ADAPTER_MAP.get(market_slug)
        
        if not AdapterClass:
            # Ошибка: в базе есть кабинет, но нет класса для него
            print(f"ERROR: Adapter class not found for slug: {market_slug}")
            return None
            
        # 3. Создаем и возвращаем экземпляр адаптера, передавая ему все, что нужно:
        # - Данные кабинета (для ключей API)
        # - OrderRepository (для чтения/записи заказов)
        return AdapterClass(cabinet_data, self.order_repo)


@lru_cache()
def get_adapter_factory() -> AdapterFactory:
    """
    Вспомогательная функция для инъекции зависимости (FastAPI Depends).
    Кеширует инстанс Фабрики, чтобы избежать повторного создания.
    """
    return AdapterFactory()