# routers/v1/migrations.py
from fastapi import APIRouter, Depends, Query
from typing import Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId

from repositories.order_repo import OrderRepository
from utils.time import now_ts

router = APIRouter(prefix="/migrations", tags=["Migrations"])


# Все поля, которые должны храниться как int (Unix Timestamp).
# Если появится новое поле с датой — добавьте сюда.
DATETIME_FIELDS = (
    "order_date",
    "send_date",
    "my_send_date",
    "created_at",
    "updated_at",
    "started_at",
    "finished_at",
    "timestamp",
)

# Коллекции, в которых вообще бывают даты
COLLECTIONS = (
    "orders",
    "orderitems",
    "order_history",
    "polling_logs",
    "sync_logs",
)


def _to_ts(value) -> int | None:
    """datetime/str/int/None → int Unix Timestamp (секунды)."""
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())

    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            return None

    if isinstance(value, (int, float)):
        # Если это миллисекунды — конвертируем в секунды
        if value > 1e11:
            return int(value / 1000)
        return int(value)

    # bson.timestamp.Timestamp (oplog-совместимый тип) — тоже сюда
    # если он вдруг окажется в документе
    try:
        from bson.timestamp import Timestamp as BsonTimestamp
        if isinstance(value, BsonTimestamp):
            return int(value.time)
    except Exception:
        pass

    return None


def _migrate_doc(doc: dict, path: str = "", debug: bool = False) -> tuple[dict, int, bool]:
    """
    Рекурсивно проходит по документу и конвертирует все datetime → int
    для полей из DATETIME_FIELDS.
    Возвращает: (обновлённый_doc, количество_полей_изменено, нужно_ли_обновление).
    """
    updated = dict(doc)
    changes = 0

    for key, value in list(updated.items()):
        full_path = f"{path}.{key}" if path else key

        # ── Дебаг: показать тип для целевых полей ──
        if debug and key in DATETIME_FIELDS:
            print(f"[MIGRATE] {full_path}: type={type(value).__name__} value={value!r}")

        # Рекурсивно по вложенным документам
        if isinstance(value, dict):
            new_val, sub_changes, _ = _migrate_doc(value, full_path, debug=debug)
            if sub_changes:
                updated[key] = new_val
                changes += sub_changes
            continue

        # Рекурсивно по массивам словарей
        if isinstance(value, list):
            new_list = []
            list_changed = False
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    new_item, sub_changes, _ = _migrate_doc(
                        item, f"{full_path}[{i}]", debug=debug
                    )
                    if sub_changes:
                        new_list.append(new_item)
                        list_changed = True
                        changes += sub_changes
                    else:
                        new_list.append(item)
                else:
                    new_list.append(item)
            if list_changed:
                updated[key] = new_list
            continue

        # ── Конвертируем только целевые поля, которые сейчас datetime ──
        if key in DATETIME_FIELDS and isinstance(value, datetime):
            ts = _to_ts(value)
            if ts is not None:
                updated[key] = ts
                changes += 1

    return updated, changes, changes > 0


@router.post("/datetime-to-ts")
async def migrate_datetime_to_ts(
    order_repo: OrderRepository = Depends(),
    dry_run: bool = Query(False, description="Если True — только показать, что будет изменено"),
    debug: bool = Query(False, description="Если True — печатать типы полей в лог"),
) -> Dict[str, Any]:
    """
    Обобщённая миграция: все поля-даты во всех коллекциях → int (Unix Timestamp).

    Проходит по orders, orderitems, order_history, polling_logs, sync_logs
    и конвертирует datetime в int для полей из DATETIME_FIELDS.
    Идемпотентна: повторный запуск ничего не портит.
    """
    db = order_repo._get_db()

    results: Dict[str, Any] = {"dry_run": dry_run, "collections": {}}
    total_migrated = 0
    total_checked = 0

    for coll_name in COLLECTIONS:
        coll = db[coll_name]

        # Ищем только те документы, где есть хотя бы одно поле с BSON Date
        date_query = {
            "$or": [{field: {"$type": "date"}} for field in DATETIME_FIELDS]
        }
        count_to_migrate = await coll.count_documents(date_query)

        if count_to_migrate == 0:
            results["collections"][coll_name] = {
                "total": await coll.count_documents({}),
                "needed": 0,
                "migrated": 0,
                "skipped": "no datetime fields",
            }
            continue

        migrated = 0
        no_op = 0
        cursor = coll.find(date_query)

        async for doc in cursor:
            total_checked += 1

            # ✅ ВАЖНО: сохраняем результат _migrate_doc
            migrated_doc, changes, needs_update = _migrate_doc(
                doc, debug=debug
            )
            if not needs_update:
                no_op += 1
                continue

            if dry_run:
                migrated += 1
                continue

            # Собираем ТОЛЬКО реально изменившиеся поля
            update_fields: Dict[str, Any] = {}
            for key, new_val in migrated_doc.items():
                if key == "_id":
                    continue
                if doc.get(key) != new_val:
                    update_fields[key] = new_val

            if not update_fields:
                no_op += 1
                continue

            result = await coll.update_one(
                {"_id": doc["_id"]},
                {"$set": update_fields},
            )

            if result.modified_count > 0:
                migrated += 1
            else:
                no_op += 1
                print(f"⚠️ no-op update for {coll_name}/{doc['_id']}: {update_fields}")

        results["collections"][coll_name] = {
            "total": await coll.count_documents({}),
            "needed": count_to_migrate,
            "migrated": migrated,
            "no_op": no_op,
        }
        total_migrated += migrated

    results["total_checked"] = total_checked
    results["total_migrated"] = total_migrated
    results["success"] = True
    return results


@router.post("/wb-prices")
async def migrate_wb_prices(
    order_repo: OrderRepository = Depends(),
) -> Dict[str, Any]:
    """
    Миграция цен WB: делит на 100 все старые заказы и товары.

    ВНИМАНИЕ: эвристика — если price > 0, price % 100 == 0 и price >= 100,
    считаем, что цена пришла в копейках. При повторном запуске НЕ идемпотентна!
    """
    db = order_repo._get_db()

    orders = await db["orders"].find({"market_type": "wb"}).to_list(None)
    total_orders = len(orders)

    if total_orders == 0:
        return {
            "success": True,
            "message": "Заказов WB не найдено",
            "orders_updated": 0,
            "items_updated": 0,
        }

    updated_orders = 0
    updated_items = 0

    for order in orders:
        price = order.get("price", 0)
        if price > 0 and price % 100 == 0 and price >= 100:
            await db["orders"].update_one(
                {"_id": order["_id"]},
                {"$set": {"price": price / 100}},
            )
            updated_orders += 1

    wb_order_ids = await db["orders"].distinct("_id", {"market_type": "wb"})
    wb_order_ids_str = [str(oid) for oid in wb_order_ids]

    if wb_order_ids_str:
        items = await db["orderitems"].find({
            "order_id_ref": {"$in": wb_order_ids_str},
            "price": {"$gt": 0},
        }).to_list(None)

        for item in items:
            item_price = item.get("price", 0)
            if item_price > 0 and item_price % 100 == 0 and item_price >= 100:
                await db["orderitems"].update_one(
                    {"_id": item["_id"]},
                    {"$set": {"price": item_price / 100}},
                )
                updated_items += 1

    sample = await db["orders"].find(
        {"market_type": "wb"},
        {"order_id": 1, "price": 1},
    ).limit(3).to_list(None)

    for order in sample:
        order["_id"] = str(order["_id"])

    return {
        "success": True,
        "message": f"Обновлено {updated_orders} заказов и {updated_items} товаров WB",
        "orders_updated": updated_orders,
        "items_updated": updated_items,
        "sample": sample,
    }