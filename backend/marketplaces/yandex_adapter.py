# marketplaces/yandex_adapter.py
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from bson import ObjectId
import base64

from marketplaces.base import BaseMarketplaceAdapter
from repositories.order_repo import OrderRepository
from models.order import Analytics, OrderIn, Order, OrderItem
from utils.time import now_ts, to_timestamp


class YandexMarketAdapter(BaseMarketplaceAdapter):
    SYNC_WINDOW_DAYS = 14  # 🔥 Окно синхронизации — 14 дней

    def __init__(self, cabinet_data: Dict[str, Any], order_repo: OrderRepository):
        super().__init__(cabinet_data, order_repo)
        
        self.cabinet_id = cabinet_data['_id']
        self.auth_token = cabinet_data.get('api_key') 
        self.business_id = cabinet_data.get('business_id')
        self.campaign_id = cabinet_data.get('client_id') 
        
        self.base_url = "https://api.partner.market.yandex.ru"
        
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Api-Key": f"{self.auth_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0
        )

    # ------------------------------------------------------------------------
    # I. ПОЛЛИНГ
    # ------------------------------------------------------------------------

    async def fetch_new_and_updated_orders(self) -> List[Dict[str, Any]]:
        """
        Получает заказы через Business API за последние 14 дней.
        is_new определяется в upsert_order — НЕ перезаписываем!
        """
        if not self.business_id:
            raise Exception(f"business_id not found for cabinet {self.cabinet.get('name')}")

        endpoint = f"/v1/businesses/{self.business_id}/orders"

        # 🔥 Окно 14 дней
        date_from_dt = datetime.now(timezone.utc) - timedelta(days=self.SYNC_WINDOW_DAYS)
        date_from = date_from_dt.strftime('%d-%m-%Y')  # Формат Яндекс: DD-MM-YYYY
        
        payload = {
            "orderStatuses": ["PROCESSING", "DELIVERY", "PICKUP", "DELIVERED", "CANCELLED"],
            "fromDate": date_from,
        }
        
        processed_orders = []
        next_page_token = None
        page_count = 0
        max_pages = 20  # Защита от бесконечного цикла

        while page_count < max_pages:
            page_count += 1
            
            if next_page_token:
                payload["paging"] = {"nextPageToken": next_page_token}

            try:
                response = await self.http_client.post(endpoint, json=payload)
                
                # Обрабатываем ошибки авторизации отдельно
                if response.status_code == 401:
                    raise Exception(
                        f"Яндекс API: неверный API-ключ для кабинета '{self.cabinet.get('name')}'"
                    )
                if response.status_code == 403:
                    raise Exception(
                        f"Яндекс API: доступ запрещён для кабинета '{self.cabinet.get('name')}'"
                    )
                
                response.raise_for_status()
                data = response.json()
                
            except httpx.HTTPStatusError as e:
                raise Exception(f"Yandex API HTTP error {e.response.status_code}: {e.response.text[:200]}")
            except httpx.RequestError as e:
                raise Exception(f"Yandex API connection error: {e}")
            
            orders = data.get('orders', [])
            
            for order_raw in orders:
                # Фильтруем по campaign_id (у одного бизнеса может быть несколько магазинов)
                if str(order_raw.get('campaignId')) != str(self.campaign_id):
                    continue

                try:
                    order_in = self._map_to_internal_format(order_raw)
                    saved_result = await self.repo.upsert_order(order_in)
                    
                    # ✅ is_new уже в saved_result — НЕ перезаписываем!
                    processed_orders.append(saved_result)
                    
                except Exception as e:
                    print(f"❌ Error processing Yandex order {order_raw.get('orderId')}: {e}")
                    continue

            # Пагинация
            next_page_token = data.get('paging', {}).get('nextPageToken')
            if not next_page_token:
                break

        return processed_orders

    # ------------------------------------------------------------------------
    # II. РУЧНАЯ ОБРАБОТКА
    # ------------------------------------------------------------------------

    async def update_market_status(self, order_id: str) -> bool:
        """Переводит заказ в статус READY_TO_SHIP"""
        if not self.business_id:
            raise Exception(f"business_id not found for cabinet {self.cabinet.get('name')}")
        
        endpoint = f"/v1/businesses/{self.business_id}/orders/{order_id}/status"
        payload = {"status": "READY_TO_SHIP"}
        
        try:
            response = await self.http_client.put(endpoint, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ Failed to change status for order {order_id}: {e}")
            return False

    async def get_full_details_by_id(self, external_order_id: str) -> Optional[Dict[str, Any]]:
        """Получение деталей заказа"""
        endpoint = f"/v1/businesses/{self.business_id}/orders/{external_order_id}"
        try:
            response = await self.http_client.get(endpoint)
            response.raise_for_status()
            return response.json().get('order')
        except Exception as e:
            print(f"❌ Yandex Error getting details: {e}")
            return None

    async def can_print_label(self, status: str) -> bool:
        """Проверяет, можно ли печатать этикетку"""
        return status in ["PROCESSING", "READY_TO_SHIP", "DELIVERY"]

    async def get_shipping_label(self, order_ids: List[str]) -> Optional[str]:
        """Получает этикетки для заказов Яндекса"""
        if not self.business_id:
            raise Exception(f"business_id not found for cabinet {self.cabinet.get('name')}")
        
        try:
            report_id = await self._generate_labels_report(order_ids)
            if not report_id:
                return None
            
            file_url = await self._wait_for_report_and_get_file(report_id)
            if not file_url:
                return None
            
            pdf_base64 = await self._download_pdf_as_base64(file_url)
            return pdf_base64
            
        except Exception as e:
            print(f"❌ Error getting Yandex shipping label: {e}")
            return None

    # ------------------------------------------------------------------------
    # III. МАППИНГ
    # ------------------------------------------------------------------------

    def _map_to_internal_format(self, raw_order: dict) -> OrderIn:
        """Преобразование формата Business API"""
        
        prices = raw_order.get('prices', {})
        payment = prices.get('payment', {}).get('value', 0)
        subsidy = prices.get('subsidy', {}).get('value', 0) if prices.get('subsidy') else 0
        total_price = float(payment + subsidy)

        delivery = raw_order.get('delivery', {})
        shipment_date_str = delivery.get('shipment', {}).get('shipmentDate')

        # Unix Timestamp
        order_data = Order(
            order_id=str(raw_order.get('orderId') or raw_order.get('id')),
            market_type=self.market_slug,
            cabinet_name=self.cabinet.get('name'),
            market_status=raw_order.get('status'),
            order_date=to_timestamp(raw_order.get('creationDate')),
            send_date=to_timestamp(shipment_date_str),
            price=total_price,
            order_count=len(raw_order.get('items', [])),
            cabinet_id_ref=ObjectId(self.cabinet_id),
        )

        # Инициатор отмены
        if raw_order.get('status') == 'CANCELLED':
            order_data.cancellation_type = 'seller' if raw_order.get('substatuses') == 'SHOP_FAILED' else 'other'

        # Аналитика
        if order_data.price and order_data.price > 0:
            order_data.analytics = self._calculate_analytics(
                order_data.price, 
                raw_order.get('status'), 
                raw_order.get('substatuses')
            )
        
        items_data = []
        for item in raw_order.get('items', []):
            it_prices = item.get('prices', {})
            it_payment = it_prices.get('payment', {}).get('value', 0)
            it_subsidy = it_prices.get('subsidy', {}).get('value', 0) if it_prices.get('subsidy') else 0
            
            items_data.append(OrderItem(
                order_id_ref="temp_id",
                article=item.get('offerId'),
                name=item.get('offerName'),
                price=float(it_payment + it_subsidy),
                count=item.get('count', 1)
            ))
        
        return OrderIn(order_data=order_data, items_data=items_data)

    # ------------------------------------------------------------------------
    # IV. АНАЛИТИКА
    # ------------------------------------------------------------------------

    def _calculate_analytics(self, order_price: float, status: str, order_substatus: str) -> Analytics:
        """Расчёт аналитики"""
        commission_market_percent = 0.42
        commission_payment_percent = 0.035
        commission_penalty = 0.75
        last_mile_percent = 0.05
        last_mile_max = 1000.0
        processing_fixed = 30.0

        logistics_ranges = [
            (300, 140),
            (7000, 200),
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

        total_expenses = (
            commission_market_total +
            commission_payment_total +
            last_mile_total +
            processing_fixed +
            logistics_total
        )

        penalty = max(150, min(5000, commission_market_total * commission_penalty))
        profit = order_price - total_expenses

        if status == 'CANCELLED':
            if order_substatus == 'SHOP_FAILED':
                return Analytics(
                    commission_market_percent=round(commission_market_percent * 100, 1),
                    commission_market_total=0,
                    commission_payment_percent=round(commission_payment_percent * 100, 1),
                    commission_payment_total=0,
                    last_mile_percent=round(last_mile_percent * 100, 1),
                    last_mile_max=last_mile_max,
                    last_mile_total=0,
                    processing_fixed=0,
                    logistics_total=0,
                    penalty=penalty,
                    total_expenses=round(penalty, 2),
                    profit=round(penalty * -1, 2),
                )
            else:
                return Analytics(
                    commission_market_percent=round(commission_market_percent * 100, 1),
                    commission_market_total=0,
                    commission_payment_percent=round(commission_payment_percent * 100, 1),
                    commission_payment_total=0,
                    last_mile_percent=round(last_mile_percent * 100, 1),
                    last_mile_max=last_mile_max,
                    last_mile_total=0,
                    processing_fixed=15,
                    logistics_total=round(logistics_total * 2, 2),
                    penalty=0,
                    total_expenses=round(logistics_total + logistics_total + 15 + 0.12, 2),
                    profit=round((logistics_total + logistics_total + 15 + 0.12) * -1, 2),
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

    # ------------------------------------------------------------------------
    # V. ЭТИКЕТКИ
    # ------------------------------------------------------------------------

    async def _generate_labels_report(self, order_ids: List[str]) -> Optional[str]:
        """Генерация отчёта с этикетками"""
        endpoint = "/v2/reports/documents/labels/generate"
        payload = {
            "businessId": int(self.business_id),
            "orderIds": [int(order_id) for order_id in order_ids]
        }
        
        try:
            response = await self.http_client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
            
            report_id = data.get('result', {}).get('reportId')
            if not report_id:
                print(f"❌ No reportId in response: {data}")
                return None
                
            return report_id
            
        except Exception as e:
            print(f"❌ Failed to generate labels report: {e}")
            return None
    
    async def _wait_for_report_and_get_file(self, report_id: str, max_wait_seconds: int = 60) -> Optional[str]:
        """Ожидает готовности отчёта"""
        endpoint = f"/v2/reports/info/{report_id}"
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < max_wait_seconds:
            try:
                response = await self.http_client.get(endpoint)
                response.raise_for_status()
                data = response.json()
                
                result = data.get('result', {})
                status = result.get('status')
                file_url = result.get('file')
                
                if status == "DONE" and file_url:
                    return file_url
                elif status == "ERROR":
                    print(f"❌ Report generation failed: {result}")
                    return None
                else:
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"❌ Error checking report status: {e}")
                await asyncio.sleep(2)
        
        print(f"❌ Timeout waiting for report {report_id}")
        return None
    
    async def _download_pdf_as_base64(self, file_url: str) -> Optional[str]:
        """Скачивает PDF и конвертирует в base64"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(file_url)
                response.raise_for_status()
                return base64.b64encode(response.content).decode('utf-8')
        except Exception as e:
            print(f"❌ Failed to download PDF: {e}")
            return None