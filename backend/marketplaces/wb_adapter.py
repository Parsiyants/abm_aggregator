# marketplaces/wb_adapter.py
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from marketplaces.base import BaseMarketplaceAdapter
from repositories.order_repo import OrderRepository
from models.order import Analytics, Order, OrderIn, OrderItem
from utils.time import now_ts, to_timestamp


class WildberriesAdapter(BaseMarketplaceAdapter):
    BASE_URL = "https://marketplace-api.wildberries.ru"
    PRICES_BASE_URL = "https://discounts-prices-api.wildberries.ru"
    SYNC_WINDOW_DAYS = 14

    def __init__(self, cabinet_data: Dict[str, Any], order_repo: OrderRepository):
        super().__init__(cabinet_data, order_repo)
        self.cabinet_id = cabinet_data['_id']
        self.api_key = cabinet_data.get('api_key')

        # Основной клиент (заказы, склады, поставки)
        self.http_client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"{self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )

        # 🔥 ОТДЕЛЬНЫЙ клиент для цен и скидок
        self.prices_client = httpx.AsyncClient(
            base_url=self.PRICES_BASE_URL,
            headers={
                "Authorization": f"{self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )


    # ------------------------------------------------------------------------
    # I. ПОЛЛИНГ
    # ------------------------------------------------------------------------

    async def fetch_new_and_updated_orders(self) -> List[Dict[str, Any]]:
        """
        Возвращает и новые, и обновлённые заказы.
        is_new определяется в upsert_order (не перезаписываем!).
        """
        new_orders = await self._fetch_new_orders()
        updated_orders = await self._update_active_orders_status()
        
        return new_orders + updated_orders

    # ------------------------------------------------------------------------
    # II. РУЧНАЯ ОБРАБОТКА
    # ------------------------------------------------------------------------

    async def update_market_status(self, order_id: str) -> bool:
        """Для WB: переводим заказ в статус 'ready_to_ship'"""
        url = f"/api/v3/orders/status/ready_to_ship"
        payload = {"orderId": order_id}
        
        try:
            response = await self.http_client.patch(url, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ Failed to change WB order status: {e}")
            return False

    async def get_full_details_by_id(self, external_order_id: str) -> Optional[Dict[str, Any]]:
        """WB не предоставляет единого метода — возвращаем None"""
        return None

    async def get_shipping_label(self, order_ids: List[str]) -> Optional[str]:
        """Не используется для WB"""
        return None
    
    async def can_print_label(self, status: str) -> bool:
        """Проверяет, можно ли печатать этикетку"""
        return status in ["new", "processing", "ready_to_ship"]

    # ------------------------------------------------------------------------
    # ПРИВАТНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------

    async def _fetch_new_orders(self) -> List[Dict[str, Any]]:
        """
        Запрашивает /api/v3/orders за последние 14 дней.
        Возвращает заказы с флагом is_new (от upsert_order).
        """
        # 🔥 Окно 14 дней
        date_from = int(
            (datetime.now(timezone.utc) - timedelta(days=self.SYNC_WINDOW_DAYS)).timestamp()
        )
        
        url = "/api/v3/orders"
        params = {
            "dateFrom": date_from,
            "limit": 1000,
            "next": 0,  # WB API требует это поле
        }
        
        saved_orders = []
        next_page = None
        page_count = 0
        max_pages = 20  # Защита от бесконечного цикла

        while page_count < max_pages:
            page_count += 1
            
            if next_page:
                params["next"] = next_page

            try:
                response = await self.http_client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                raw_orders = data.get("orders", []) if isinstance(data, dict) else []

                for raw_order in raw_orders:
                    try:
                        order_in = self._map_to_internal_format(raw_order)
                        saved_result = await self.repo.upsert_order(order_in)
                        
                        # ✅ is_new уже в saved_result — НЕ перезаписываем!
                        saved_orders.append(saved_result)
                        
                    except Exception as e:
                        print(f"❌ Error processing WB order {raw_order.get('id')}: {e}")
                        continue

                # Пагинация
                next_page = response.headers.get("X-Next-Page") or data.get("next")
                if not next_page:
                    break

            except httpx.HTTPStatusError as e:
                error_msg = f"WB API error {e.response.status_code}: {e.response.text[:200]}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
            except httpx.RequestError as e:
                error_msg = f"WB API connection error: {e}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)

        return saved_orders

    async def _update_active_orders_status(self) -> List[Dict[str, Any]]:
        """
        Обновляет статусы активных заказов WB (за последние 14 дней).
        Возвращает только те, у которых статус изменился.
        """
        # 🔥 Только за последние 14 дней
        active_orders = await self.repo.get_active_orders_by_market(
            market_slug=self.market_slug,
            exclude_statuses=["Done", "Cancel"],
            days_back=self.SYNC_WINDOW_DAYS  # ← ограничение по дате
        )
        if not active_orders:
            return []

        # Собираем числовые ID
        order_ids = [
            int(order["order_id"]) 
            for order in active_orders 
            if order["order_id"].isdigit()
        ]
        if not order_ids:
            return []

        url = "/api/v3/orders/status"
        payload = {"orders": order_ids}
        updated_orders = []

        try:
            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            statuses = data.get("orders", [])
            status_map = {str(item["id"]): item for item in statuses}

            for order_doc in active_orders:
                order_id_str = order_doc["order_id"]
                status_info = status_map.get(order_id_str)
                if not status_info:
                    continue

                # 🔥 WB статус (waiting, sorted, sold, canceled)
                new_market_status = status_info.get("wbStatus")
                old_market_status = order_doc.get("market_status")

                if new_market_status != old_market_status:
                    order_in = self._update_order_status_in_model(
                        order_doc, 
                        new_market_status
                    )
                    saved_result = await self.repo.upsert_order(order_in)
                    
                    # ✅ is_new уже False (заказ существовал)
                    if saved_result["status_changed"]:
                        updated_orders.append(saved_result)

        except httpx.HTTPStatusError as e:
            error_msg = f"WB status API error {e.response.status_code}: {e.response.text[:200]}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            print(f"❌ WB _update_active_orders_status error: {e}")
            raise

        return updated_orders

    # ------------------------------------------------------------------------
    # МАППИНГ
    # ------------------------------------------------------------------------

    def _map_to_internal_format(self, raw_order: dict) -> OrderIn:
        """Преобразует заказ WB в OrderIn"""
        order_id = str(raw_order["id"])
        
        created_at_ts = to_timestamp(raw_order.get("createdAt"))
        send_date_ts = created_at_ts + 86400  # +1 день (WB не даёт дату отгрузки)

        # 🔥 Цена делится на 100 (WB присылает в копейках)
        price = float(raw_order.get("price", 0)) / 100

        order_data = Order(
            order_id=order_id,
            market_type=self.market_slug,
            cabinet_name=self.cabinet.get("name"),
            market_status="waiting",  # дефолт, обновится в _update_active_orders_status
            order_date=created_at_ts,
            send_date=send_date_ts,
            price=price,
            order_count=1,  # каждый объект = один товар в количестве 1
            cabinet_id_ref=ObjectId(self.cabinet_id),
        )

        if price and price > 0:
            order_data.analytics = self._calculate_analytics(price, "waiting")

        # WB возвращает артикул, но не название — используем артикул
        article = raw_order.get("article", "")
        
        item = OrderItem(
            order_id_ref="temp_id",
            article=article,
            name=article,  # нет названия — используем артикул
            price=price,
            count=1,
        )

        return OrderIn(order_data=order_data, items_data=[item])

    def _update_order_status_in_model(
        self, 
        existing_order_doc: dict, 
        new_market_status: str
    ) -> OrderIn:
        """Создаёт OrderIn с обновлённым market_status"""
        order_data = Order(
            order_id=existing_order_doc["order_id"],
            market_type=existing_order_doc["market_type"],
            cabinet_name=existing_order_doc["cabinet_name"],
            market_status=new_market_status,
            order_date=existing_order_doc["order_date"],
            send_date=existing_order_doc.get("send_date"),
            price=existing_order_doc["price"],
            order_count=existing_order_doc["order_count"],
            process_status=existing_order_doc.get("process_status", "New"),
            cancellation_type=existing_order_doc.get("cancellation_type"),
            my_send_date=existing_order_doc.get("my_send_date"),
            comment=existing_order_doc.get("comment"),
            raw_data=existing_order_doc.get("raw_data"),
            analytics=existing_order_doc.get("analytics"),
            cabinet_id_ref=existing_order_doc.get("cabinet_id_ref"),
        )

        # Восстанавливаем товары
        items = existing_order_doc.get("items", [])
        if not items:
            items = [OrderItem(
                order_id_ref=str(existing_order_doc["_id"]),
                article="",
                name="",
                price=existing_order_doc.get("price", 0),
                count=1
            )]
        else:
            items = [
                OrderItem(
                    order_id_ref=item.get("order_id_ref", ""),
                    article=item.get("article", ""),
                    name=item.get("name", ""),
                    price=item.get("price", 0),
                    count=item.get("count", 1),
                )
                for item in items
            ]

        return OrderIn(order_data=order_data, items_data=items)

    # ------------------------------------------------------------------------
    # АНАЛИТИКА
    # ------------------------------------------------------------------------
    
    def _calculate_analytics(self, order_price: float, status: str) -> Analytics:
        """Расчёт аналитики для WB"""
        commission_market_percent = 0.25
        commission_payment_percent = 0.02
        processing_fixed = 30.0
        
        logistics_ranges = [
            (300, 50),
            (7000, 100),
            (float('inf'), 200),
        ]

        commission_market_total = order_price * commission_market_percent
        commission_payment_total = order_price * commission_payment_percent

        logistics_total = 200.0
        for max_price, cost in logistics_ranges:
            if order_price <= max_price:
                logistics_total = cost
                break

        total_expenses = (
            commission_market_total +
            commission_payment_total +
            processing_fixed +
            logistics_total
        )

        profit = order_price - total_expenses

        return Analytics(
            commission_market_percent=round(commission_market_percent * 100, 1),
            commission_market_total=round(commission_market_total, 2),
            commission_payment_percent=round(commission_payment_percent * 100, 1),
            commission_payment_total=round(commission_payment_total, 2),
            last_mile_percent=0,
            last_mile_max=0,
            last_mile_total=0,
            processing_fixed=processing_fixed,
            logistics_total=logistics_total,
            penalty=0,
            total_expenses=round(total_expenses, 2),
            profit=round(profit, 2),
        )




    # ═══════════════════════════════════════════════════════════════════════
    # СИНХРОНИЗАЦИЯ ЦЕН И ОСТАТКОВ
    # ═══════════════════════════════════════════════════════════════════════

    async def get_all_goods(self) -> List[Dict[str, Any]]:
        url = "/api/v2/list/goods/filter"
        limit = 1000
        offset = 0
        all_goods = []

        while True:
            params = {"limit": limit, "offset": offset}

            try:
                response = await self.prices_client.get(url, params=params)  # ← prices_client
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                error_msg = f"WB list goods error {e.response.status_code}: {e.response.text[:200]}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
            except Exception as e:
                print(f"❌ WB get_all_goods error: {e}")
                raise

            if data.get("error"):
                raise Exception(f"WB API error: {data.get('errorText', 'unknown')}")

            goods = data.get("data", {}).get("listGoods", [])
            if not goods:
                break

            all_goods.extend(goods)
            if len(goods) < limit:
                break
            offset += limit

        return all_goods


    async def upload_prices(self, price_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not price_updates:
            return {"task_id": None, "count": 0}

        url = "/api/v2/upload/task"
        payload = {"data": price_updates}

        try:
            response = await self.prices_client.post(url, json=payload)  # ← prices_client
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                raise Exception(f"WB API error: {data.get('errorText', 'unknown')}")

            return {
                "task_id": data.get("data", {}).get("id"),
                "count": len(price_updates),
            }
        except httpx.HTTPStatusError as e:
            error_msg = f"WB upload prices error {e.response.status_code}: {e.response.text[:200]}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            print(f"❌ WB upload_prices error: {e}")
            raise


    async def upload_stocks(self, warehouse_id: int, stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not stocks:
            return {"updated": 0}

        url = f"/api/v3/stocks/{warehouse_id}"
        payload = {"stocks": stocks}

        try:
            response = await self.http_client.put(url, json=payload)  # ← http_client (marketplace)
            response.raise_for_status()
            return {"updated": len(stocks)}
        except httpx.HTTPStatusError as e:
            error_msg = f"WB upload stocks error {e.response.status_code}: {e.response.text[:200]}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            print(f"❌ WB upload_stocks error: {e}")
            raise