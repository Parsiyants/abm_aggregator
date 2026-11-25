# marketplaces/ozon_adapter.py
from .base import BaseMarketplaceAdapter
from repositories.order_repo import OrderRepository
from models.order import Analytics, Order, OrderItem, OrderIn
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import httpx
import base64
from utils.time import now_ts, to_timestamp


class OzonAdapter(BaseMarketplaceAdapter):
    """Адаптер для взаимодействия с Ozon Seller API."""
    
    OZON_API_URL = "https://api-seller.ozon.ru"
    SYNC_WINDOW_DAYS = 14  # 🔥 Окно синхронизации — 14 дней
    PAGE_LIMIT = 100     # Максимум для /v4/posting/fbs/list
    MAX_PAGES = 50         # Защита от бесконечного цикла

    def __init__(self, cabinet_data: dict, order_repo: OrderRepository):
        super().__init__(cabinet_data, order_repo)
        
        self.headers = {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

        self.client = httpx.AsyncClient(
            base_url=self.OZON_API_URL, 
            headers=self.headers, 
            timeout=30.0
        )

    # ------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------

    async def _post(self, url: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST-запрос с обработкой ошибок"""
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"Ozon API HTTP {e.response.status_code} for {url}: {e.response.text[:200]}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except httpx.RequestError as e:
            error_msg = f"Ozon API Request Error for {url}: {e}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

    
    # ------------------------------------------------------------------------
    # I. ПОЛЛИНГ
    # ------------------------------------------------------------------------

    async def fetch_new_and_updated_orders(self) -> List[Dict[str, Any]]:
        """
        Получает заказы с Ozon за последние 14 дней.

        Новая версия /v4/posting/fbs/list возвращает данные в формате:
            {"has_next": bool, "cursor": str, "postings": [...]}
        Пагинация — курсорная: передаём `cursor` из предыдущего ответа,
        пока `has_next == True`. Параметр `offset` больше не используется.

        is_new определяется в upsert_order — НЕ перезаписываем!
        """

        date_from = (
            datetime.now(timezone.utc) - timedelta(days=self.SYNC_WINDOW_DAYS)
        ).isoformat().replace('+00:00', 'Z')
        date_to = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        url = "/v4/posting/fbs/list"
        payload: Dict[str, Any] = {
            "dir": "asc",
            "filter": {"since": date_from, "to": date_to},
            "limit": self.PAGE_LIMIT,
            "cursor": "",
        }

        processed_orders: List[Dict[str, Any]] = []
        page_count = 0

        while page_count < self.MAX_PAGES:
            page_count += 1

            response_data = await self._post(url, payload)

            if not response_data:
                break

            raw_ozon_orders = response_data.get('postings') or []
            if not raw_ozon_orders:
                break

            for raw_order in raw_ozon_orders:
                try:
                    order_in = self._map_to_internal_format(raw_order)
                    saved_result = await self.repo.upsert_order(order_in)
                    processed_orders.append(saved_result)
                except Exception as e:
                    print(f"❌ Error processing Ozon order {raw_order.get('posting_number')}: {e}")
                    continue

            # Курсорная пагинация
            if not response_data.get('has_next'):
                break

            cursor = response_data.get('cursor')
            if not cursor:
                break
            payload['cursor'] = cursor

        return processed_orders

    # ------------------------------------------------------------------------
    # II. РУЧНАЯ ОБРАБОТКА
    # ------------------------------------------------------------------------

    async def update_market_status(self, order_id: str) -> bool:
        """Переводит заказ из awaiting_packaging в awaiting_deliver"""
        try:
            order_details = await self.get_full_details_by_id(order_id)
            if not order_details:
                raise Exception(f"Не удалось получить детали заказа {order_id}")
            
            products = []
            for product in order_details.get('products', []):
                product_id = product.get('sku')
                quantity = product.get('quantity', 1)
                if product_id:
                    products.append({
                        "product_id": product_id,
                        "quantity": quantity
                    })
            
            if not products:
                raise Exception(f"Нет товаров с product_id для заказа {order_id}")
            
            url = "/v4/posting/fbs/ship"
            payload = {
                "posting_number": order_id,
                "packages": [{"products": products}]
            }
            
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return True
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            print(f"❌ Error changing status for order {order_id}: {e}")
            raise

    async def get_full_details_by_id(self, external_order_id: str) -> Optional[Dict[str, Any]]:
        """Получает полные детали заказа по posting_number"""
        url = "/v3/posting/fbs/get"
        payload = {"posting_number": external_order_id}
        
        try:
            response = await self._post(url, payload)
            
            if not response:
                return None
            
            result = response.get('result')
            if not result:
                print(f"⚠️ Empty result for order {external_order_id}")
                return None
                
            return result
            
        except Exception as e:
            print(f"❌ Error getting order details for {external_order_id}: {e}")
            return None

    async def get_shipping_label(self, posting_numbers: List[str]) -> Optional[str]:
        """
        Получает PDF этикетки для заказов Ozon.
        API возвращает application/pdf напрямую.
        Возвращает base64 строку для передачи на фронт.
        """
        url = "/v2/posting/fbs/package-label"
        payload = {"posting_number": posting_numbers}
        
        try:
            # Отправляем запрос
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            # Проверяем Content-Type
            content_type = response.headers.get('content-type', '')
            print(f"Response Content-Type: {content_type}")
            
            # Если вернулся PDF
            if 'application/pdf' in content_type:
                pdf_bytes = response.content
                if pdf_bytes and pdf_bytes.startswith(b'%PDF'):
                    # Конвертируем в base64 для отправки на фронт
                    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                    return pdf_base64
                else:
                    print(f"Response doesn't look like PDF, first bytes: {pdf_bytes[:20]}")
                    return None
            else:
                # Возможно JSON с ошибкой
                try:
                    error_data = response.json()
                    print(f"API returned error: {error_data}")
                except:
                    print(f"Unexpected response: {response.text[:200]}")
                return None
                
        except httpx.HTTPStatusError as e:
            print(f"HTTP error getting label for {posting_numbers}: {e.response.status_code}")
            return None
        except Exception as e:
            print(f"Error getting label: {e}")
            return None
    
    async def can_print_label(self, status: str) -> bool:
        """Проверяет, можно ли печатать этикетку для Ozon"""
        # Для Ozon печать возможна только в awaiting_deliver
        return status == "awaiting_deliver"
    # ------------------------------------------------------------------------
    # III. МАППИНГ
    # ------------------------------------------------------------------------
    
    @staticmethod
    def _parse_price(price: Any) -> float:
        """
        В новом формате цена приходит объектом: {"amount": "1070", "currency": "RUB"}.
        В старых ответах приходило просто число — поддерживаем оба варианта.
        """
        if isinstance(price, dict):
            price = price.get('amount')

        try:
            return float(price or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _resolve_cancellation_type(raw_order: dict) -> str:
        """
        Определяет инициатора отмены.

        Новый формат: cancellation.cancellation_type == "client" | "seller" | "ozon".
        Старый формат: cancellation.cancellation_initiator == "Клиент" | "Продавец".
        """
        cancellation = raw_order.get('cancellation') or {}
        cancel_type = str(cancellation.get('cancellation_type') or '').lower()
        initiator = str(cancellation.get('cancellation_initiator') or '').lower()

        if cancel_type == 'seller' or 'seller' in cancel_type or 'продав' in initiator:
            return 'seller'

        return 'other'

    def _map_to_internal_format(self, raw_order: dict) -> OrderIn:
        """
        Преобразование сырых данных Ozon (/v4/posting/fbs/list) в OrderIn.

        Особенности нового формата:
        - цена товара — объект {"amount", "currency"} и указана за единицу;
        - появились поля order_number, substatus, delivery_schema, scanit;
        - инициатор отмены — в cancellation.cancellation_type.
        """
        products = raw_order.get('products') or []

        # 🔥 Количество единиц товара в отправлении
        total_count = sum(int(product.get('quantity') or 1) for product in products)

        # 🔥 Сумма заказа: цена за единицу * количество
        total_price = sum(
            self._parse_price(product.get('price')) * int(product.get('quantity') or 1)
            for product in products
        )

        # 🔥 Используем реальную дату создания, с фолбэком на текущее время
        order_date_ts = (
            to_timestamp(raw_order.get('in_process_at'))
            or to_timestamp(raw_order.get('created_at'))
            or now_ts()
        )

        # 🔥 Безопасно парсим дату отгрузки
        send_date_ts = to_timestamp(raw_order.get('shipment_date'))

        status = raw_order.get('status') or ''

        order_data = Order(
            order_id=raw_order['posting_number'],
            order_number=raw_order.get('order_number'),
            market_type=self.market_slug,
            cabinet_name=self.cabinet.get('name'),
            order_date=order_date_ts,          # ← Unix Timestamp
            send_date=send_date_ts,            # ← Unix Timestamp
            market_status=status,
            substatus=raw_order.get('substatus') or None,
            tracking_number=raw_order.get('tracking_number') or None,
            delivery_schema=raw_order.get('delivery_schema') or None,
            scanit=raw_order.get('scanit') or None,
            price=round(total_price, 2),
            order_count=total_count,           # ← Правильное количество
        )

        # Если отменён — определяем инициатора
        if status.lower() == 'cancelled':
            order_data.cancellation_type = self._resolve_cancellation_type(raw_order)

        # Аналитика
        if order_data.price and order_data.price > 0:
            order_data.analytics = self._calculate_analytics(
                order_data.price,
                status,
                order_data.cancellation_type,
            )

        # Цена позиции — за единицу товара
        items_data = [
            OrderItem(
                order_id_ref="temp_id",
                article=item.get('offer_id') or '',
                name=item.get('name') or '',
                price=self._parse_price(item.get('price')),
                count=int(item.get('quantity') or 1),
            )
            for item in products
        ]

        return OrderIn(order_data=order_data, items_data=items_data)
    
    # ------------------------------------------------------------------------
    # IV. АНАЛИТИКА
    # ------------------------------------------------------------------------

    def _calculate_analytics(self, order_price: float, status: str, cancelled_author: str) -> Analytics:
        """Расчёт аналитики"""
        commission_market_percent = 0.42
        commission_payment_percent = 0.035
        last_mile_percent = 0
        last_mile_max = 0
        processing_fixed = 30.0
        commission_penalty = 0.135

        logistics_ranges = [
            (300, 100),
            (7000, 180),
            (float('inf'), 300),
        ]

        commission_market_total = order_price * commission_market_percent
        commission_payment_total = order_price * commission_payment_percent
        last_mile_total = min(order_price * last_mile_percent, last_mile_max)

        logistics_total = 500.0
        for max_price, cost in logistics_ranges:
            if order_price <= max_price:
                logistics_total = cost
                break

        penalty = max((order_price * commission_penalty), 150)

        total_expenses = (
            commission_market_total +
            commission_payment_total +
            last_mile_total +
            processing_fixed +
            logistics_total
        )

        profit = order_price - total_expenses

        if status == 'cancelled':
            if cancelled_author == 'seller':
                return Analytics(
                    commission_market_percent=round(commission_market_percent * 100, 1),
                    commission_market_total=round(commission_market_total, 2),
                    commission_payment_percent=round(commission_payment_percent * 100, 1),
                    commission_payment_total=round(commission_payment_total, 2),
                    last_mile_percent=round(last_mile_percent * 100, 1),
                    last_mile_max=last_mile_max,
                    last_mile_total=0,
                    processing_fixed=0,
                    logistics_total=0,
                    penalty=round(penalty, 2),
                    total_expenses=round(penalty, 2),
                    profit=round(penalty * -1, 2)
                )
            else:
                return Analytics(
                    commission_market_percent=round(commission_market_percent * 100, 1),
                    commission_market_total=round(commission_market_total, 2),
                    commission_payment_percent=round(commission_payment_percent * 100, 1),
                    commission_payment_total=round(commission_payment_total, 2),
                    last_mile_percent=round(last_mile_percent * 100, 1),
                    last_mile_max=last_mile_max,
                    last_mile_total=0,
                    processing_fixed=processing_fixed,
                    logistics_total=round(logistics_total * 2, 2),
                    penalty=0,
                    total_expenses=round(logistics_total * 2 + processing_fixed, 2),
                    profit=round((logistics_total * 2 + processing_fixed) * -1, 2)
                )
        else:
            return Analytics(
                commission_market_percent=round(commission_market_percent * 100, 1),
                commission_market_total=round(commission_market_total, 2),
                commission_payment_percent=round(commission_payment_percent * 100, 1),
                commission_payment_total=round(commission_payment_total, 2),
                last_mile_percent=round(last_mile_percent * 100, 1),
                last_mile_max=last_mile_max,
                last_mile_total=round(last_mile_total, 2),
                processing_fixed=processing_fixed,
                logistics_total=logistics_total,
                penalty=0,
                total_expenses=round(total_expenses, 2),
                profit=round(profit, 2),
            )