# services/wb_sync_service.py
import os
import re
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

from marketplaces.wb_adapter import WildberriesAdapter
from repositories.order_repo import OrderRepository
from repositories.log_repo import LogRepository
from services.yml_parser import YmlParser
from utils.time import now_ts

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════

YML_URL = os.getenv(
    "WB_YML_URL",
    "https://abmauto.ru/get_price?p=049fa8eb6bd4411da3688c19e7cd34b3&FranchiseeId=156881300"
)

# На WB цены отправляем 1в1 из XML. Скидка не применяется.
WB_DISCOUNT = 0

# Лимит элементов в одном запросе к WB
WB_BATCH_SIZE = 1000

# Регулярка суффикса кратности: SANGSIN-SP1399*2  →  ("SANGSIN-SP1399", 2)
# Поддерживаем: *2, *4, *10 и т.п. Число должно быть >= 1.
MULTIPLIER_RE = re.compile(r"\*(\d+)\s*$")


def parse_vendor_code(raw_vendor_code: Optional[str]) -> Tuple[str, int]:
    """
    Разбирает артикул WB на (чистый_артикул, кратность).
    Если суффикса нет или он битый — возвращает (исходный_артикул, 1).
    """
    if not raw_vendor_code:
        return "", 1

    match = MULTIPLIER_RE.search(raw_vendor_code)
    if not match:
        return raw_vendor_code, 1

    try:
        multiplier = int(match.group(1))
    except ValueError:
        return raw_vendor_code, 1

    if multiplier < 1:
        return raw_vendor_code, 1

    clean_code = raw_vendor_code[: match.start()].strip()
    return clean_code, multiplier


def apply_multiplier_to_price(xml_price: float, multiplier: int) -> float:
    """Цена за комплект: xml_price × кратность."""
    if multiplier <= 1:
        return xml_price
    return round(xml_price * multiplier, 2)


def apply_multiplier_to_stock(xml_instock: int, multiplier: int) -> int:
    """
    Остаток в комплектах: floor(xml_instock / кратность).
    Если остаток меньше кратности — 0.
    """
    if multiplier <= 1:
        return max(int(xml_instock), 0)
    if xml_instock <= 0:
        return 0
    return int(xml_instock) // multiplier


class WBSyncService:
    """Сервис синхронизации цен и остатков с Wildberries."""

    def __init__(self, cabinet_data: dict, repo: OrderRepository = None):
        self.cabinet_data = cabinet_data
        self.cabinet_id = cabinet_data.get('_id')
        self.cabinet_name = cabinet_data.get('name')
        self.repo = repo or OrderRepository()
        self.adapter = WildberriesAdapter(cabinet_data, self.repo)
        self.log_repo = LogRepository()

    async def sync_cabinet(self) -> Dict[str, Any]:
        """
        Полный цикл синхронизации для одного кабинета WB.
        """
        started_at = now_ts()
        log_id = await self.log_repo.create_sync_log(
            sync_type="full",
            market_type="wb",
            cabinet_id=str(self.cabinet_id),
            cabinet_name=self.cabinet_name,
        )

        result: Dict[str, Any] = {
            "success": True,
            "cabinet_id": str(self.cabinet_id),
            "cabinet_name": self.cabinet_name,
            "warehouse_id": None,

            # Исходные данные
            "yml_items_total": 0,       # сколько офферов в XML
            "wb_goods_total": 0,        # сколько товаров из WB API
            "matched": 0,               # сколько сопоставилось
            "unmatched_wb": 0,          # сколько товаров WB не нашлось в XML

            # Цены
            "prices_updated": 0,        # реально изменены
            "prices_skipped": 0,        # совпали, не трогали

            # Остатки
            "stocks_updated": 0,        # ненулевые остатки, изменены
            "stocks_zeroed": 0,         # обнуления (нет в XML, либо остаток 0)
            "stocks_skipped": 0,        # остаток совпал, не трогали

            # Ошибки
            "multiplier_errors": 0,     # битые суффиксы *N

            "duration_seconds": 0,
            "errors": [],
        }

        try:
            # ─── ШАГ 1: Парсим YML ───
            print(f"📥 [{self.cabinet_name}] Загружаем YML...")
            parser = YmlParser(YML_URL)
            yml_data = await parser.fetch_and_parse()

            warehouse_id = yml_data.get("warehouse_id")
            yml_items = yml_data.get("items", {})
            result["yml_items_total"] = len(yml_items)
            result["warehouse_id"] = warehouse_id

            if not warehouse_id:
                raise Exception("Не удалось получить warehouse_id из YML (тег <company>)")

            print(f"✅ [{self.cabinet_name}] YML: {len(yml_items)} товаров, склад {warehouse_id}")

            # ─── ШАГ 2: Получаем товары из WB ───
            print(f"📥 [{self.cabinet_name}] Загружаем товары из WB...")
            wb_goods = await self.adapter.get_all_goods()
            result["wb_goods_total"] = len(wb_goods)
            print(f"✅ [{self.cabinet_name}] WB: {len(wb_goods)} товаров")

            # ─── ШАГ 3: Сопоставление + формирование апдейтов ───
            price_updates: List[Dict[str, Any]] = []
            stock_updates: List[Dict[str, Any]] = []

            for good in wb_goods:
                nm_id = good.get("nmID")
                raw_vendor_code = good.get("vendorCode")
                sizes = good.get("sizes", [])

                if not sizes or not raw_vendor_code:
                    continue

                size = sizes[0]
                size_id = size.get("sizeID")
                wb_price = size.get("price", 0)

                # Парсим суффикс кратности
                clean_code, multiplier = parse_vendor_code(raw_vendor_code)

                if multiplier < 1:
                    # битый суффикс — не должны сюда попасть (см. parse_vendor_code), но на всякий
                    result["multiplier_errors"] += 1
                    continue

                yml_item = yml_items.get(clean_code)

                if yml_item:
                    # ─── ТОВАР СОПОСТАВЛЕН ───
                    result["matched"] += 1

                    # ── Цена: 1в1 из XML, × кратность ──
                    target_price = apply_multiplier_to_price(yml_item["price"], multiplier)

                    # WB сравниваем с точностью до рубля
                    if abs(target_price - wb_price) > 1:
                        price_updates.append({
                            "nmID": nm_id,
                            "price": int(target_price),
                            "discount": WB_DISCOUNT,
                        })
                        result["prices_updated"] += 1
                    else:
                        result["prices_skipped"] += 1

                    # ── Остаток: XML instock / кратность, floor ──
                    target_stock = apply_multiplier_to_stock(
                        yml_item["instock"], multiplier
                    )

                    stock_updates.append({
                        "chrtId": size_id,
                        "amount": target_stock,
                    })

                    if target_stock == 0:
                        result["stocks_zeroed"] += 1
                    else:
                        result["stocks_updated"] += 1

                else:
                    # ─── ТОВАР НЕ СОПОСТАВЛЕН ───
                    result["unmatched_wb"] += 1

                    stock_updates.append({
                        "chrtId": size_id,
                        "amount": 0,
                    })
                    result["stocks_zeroed"] += 1

            # ─── ШАГ 4: Обновляем цены ───
            if price_updates:
                print(f"📤 [{self.cabinet_name}] Обновляем {len(price_updates)} цен...")
                for chunk in self._chunk(price_updates, WB_BATCH_SIZE):
                    await self.adapter.upload_prices(chunk)
                print(f"✅ [{self.cabinet_name}] Цены обновлены: {len(price_updates)}")
            else:
                print(f"ℹ️ [{self.cabinet_name}] Цены не требуют обновления")

            # ─── ШАГ 5: Обновляем остатки ───
            if stock_updates:
                print(
                    f"📤 [{self.cabinet_name}] Обновляем {len(stock_updates)} остатков "
                    f"на складе {warehouse_id} "
                    f"(из них обнулений: {result['stocks_zeroed']})..."
                )
                for chunk in self._chunk(stock_updates, WB_BATCH_SIZE):
                    await self.adapter.upload_stocks(warehouse_id, chunk)
                print(f"✅ [{self.cabinet_name}] Остатки обновлены: {len(stock_updates)}")
            else:
                print(f"ℹ️ [{self.cabinet_name}] Остатки не требуют обновления")

            # ─── ЛОГ: успех ───
            finished_at = now_ts()
            result["duration_seconds"] = round(finished_at - started_at, 3)

            await self.log_repo.update_sync_log(log_id, {
                "finished_at": finished_at,
                "duration_seconds": result["duration_seconds"],
                "status": "success",

                # общее
                "total_items": result["wb_goods_total"],
                "success_count": result["prices_updated"] + result["stocks_updated"],
                "failed_count": 0,

                # детализация по подтипам
                "items": [
                    {
                        "sync_type": "prices",
                        "count": result["matched"],
                        "updated": result["prices_updated"],
                        "skipped": result["prices_skipped"],
                        "zeroed": 0,
                    },
                    {
                        "sync_type": "stocks",
                        "count": result["matched"] + result["unmatched_wb"],
                        "updated": result["stocks_updated"],
                        "skipped": result["stocks_skipped"],
                        "zeroed": result["stocks_zeroed"],
                    },
                ],

                # плоские поля — удобно и для фронта, и для аналитики
                "yml_items_total": result["yml_items_total"],
                "wb_goods_total": result["wb_goods_total"],
                "matched": result["matched"],
                "unmatched_wb": result["unmatched_wb"],

                "prices_updated": result["prices_updated"],
                "prices_skipped": result["prices_skipped"],

                "stocks_updated": result["stocks_updated"],
                "stocks_zeroed": result["stocks_zeroed"],
                "stocks_skipped": result["stocks_skipped"],
            })

            return result

        except Exception as e:
            error_msg = str(e)
            print(f"❌ [{self.cabinet_name}] SYNC ERROR: {error_msg}")

            finished_at = now_ts()
            result["duration_seconds"] = round(finished_at - started_at, 3)
            result["success"] = False
            result["errors"].append(error_msg)

            await self.log_repo.update_sync_log(log_id, {
                "finished_at": finished_at,
                "duration_seconds": result["duration_seconds"],
                "status": "error",
                "error_message": error_msg,
                "errors": [{"error": error_msg, "timestamp": finished_at}],
            })

            return result

    @staticmethod
    def _chunk(lst: List, size: int) -> List[List]:
        """Разбивает список на чанки по size элементов."""
        return [lst[i:i + size] for i in range(0, len(lst), size)]