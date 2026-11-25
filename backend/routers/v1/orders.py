import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from services.poller import run_manual_polling
from services.adapter_factory import AdapterFactory, get_adapter_factory
from repositories.order_repo import OrderRepository
from models.order import BulkItemStatusUpdate, OrderHandleRequest
from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime

router = APIRouter()
order_repo = OrderRepository()

class OrderLabelRequest(BaseModel):
    order_id: str  # Внешний ID заказа (posting_number, order_id и т.д.)
    status: str    # Текущий статус с фронта
    cabinet_id: str  # ID кабинета в БД

class LabelPrintRequest(BaseModel):
    orders: List[OrderLabelRequest]

class LabelPrintResponse(BaseModel):
    results: List[dict]
    labels: Optional[str] = None  # base64 PDF
    ready_count: int = 0

class ManualPollRequest(BaseModel):
    cabinet_ids: Optional[List[str]] = None  # Если None — все активные

# --- Вспомогательная функция для преобразования ObjectId в str ---
def serialize_order(order: Dict[str, Any]) -> Dict[str, Any]:
    if order is None:
        return None
    # Преобразование основного _id
    order['_id'] = str(order['_id'])
    
    # Преобразование _id в позициях заказа (если они есть)
    if 'items' in order:
        for item in order['items']:
            item['_id'] = str(item['_id'])
            # Можем также убедиться, что order_id_ref корректно отображается
            if 'order_id_ref' in item and isinstance(item['order_id_ref'], ObjectId):
                 item['order_id_ref'] = str(item['order_id_ref'])
    
    return order

def serialize_analytics(result: Dict[str, Any]) -> Dict[str, Any]:
    if not result:
        return result

    # Сериализуем orders_list
    if "orders_list" in result:
        result["orders_list"] = [
            serialize_order(order) for order in result["orders_list"]
        ]

    # На всякий случай пробегаемся по market_groups и providers (там тоже могут быть _id)
    if "market_groups" in result:
        for group in result["market_groups"]:
            if "cabinet_details" in group:
                for detail in group["cabinet_details"]:
                    if "_id" in detail:
                        detail["_id"] = str(detail["_id"]) if detail["_id"] else None

    # providers обычно чистые, но на всякий случай
    if "providers" in result:
        for p in result["providers"]:
            if "_id" in p and isinstance(p["_id"], ObjectId):
                p["_id"] = str(p["_id"])

    return result

# ------------------------------------------------------------------------
# I. ПОЛУЧЕНИЕ И ФИЛЬТРАЦИЯ СПИСКА ЗАКАЗОВ
# ------------------------------------------------------------------------

@router.get("/", response_model=Dict[str, Any])
async def list_orders(
    # Пагинация — теперь НЕОБЯЗАТЕЛЬНАЯ
    page: Optional[int] = Query(None, ge=1, description="Номер страницы (начиная с 1)"),
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Количество элементов на странице"),
    
    # Фильтры
    process_status: Optional[List[str]] = Query(None, description="Фильтр по статусу обработки (process_status)"),
    market_type: Optional[List[str]] = Query(None, description="Фильтр по маркетплейсу"),
    market_status: Optional[List[str]] = Query(None, description="Фильтр по статусу на маркетплейсе (market_status)"),
    search: Optional[str] = Query(None, description="Поиск по order_id / item.name / item.article"),
    cabinet_name: Optional[List[str]] = Query(None),
    cancellation_type: Optional[str] = Query(None),
    order_date_from: Optional[datetime] = Query(None),
    order_date_to: Optional[datetime] = Query(None),
    send_date_from: Optional[datetime] = Query(None),
    send_date_to: Optional[datetime] = Query(None),
    my_send_date_from: Optional[datetime] = Query(None),
    my_send_date_to: Optional[datetime] = Query(None),
    item_status: Optional[List[str]] = Query(None, description="Статус позиции (из orderitems.status)"),
    item_provider: Optional[List[str]] = Query(None, description="Поставщик позиции"),
    all: bool = Query(False, description="Загрузить все заказы (игнорировать page/limit)"),
):
    """
    Получение списка заказов с фильтрацией.
    Если all=true — возвращает все заказы без пагинации.
    """
    
    # Если all=true — отключаем пагинацию
    if all:
        skip = 0
        limit = 1000000
    else:
        if page is None:
            page = 1
        if limit is None:
            limit = 20
        skip = (page - 1) * limit
    
    orders = await order_repo.get_orders_list(
        skip=skip,
        limit=limit,
        process_status=process_status,
        market_type=market_type,
        market_status=market_status,  # ← добавлено
        cancellation_type=cancellation_type,
        search=search,
        cabinet_name=cabinet_name,
        order_date_from=order_date_from,
        order_date_to=order_date_to,
        send_date_from=send_date_from,
        send_date_to=send_date_to,
        my_send_date_from=my_send_date_from,
        my_send_date_to=my_send_date_to,
        item_status=item_status,
        item_provider=item_provider,
    )
    
    total = await order_repo.get_orders_list_count(
        skip=0,
        limit=1000000,
        process_status=process_status,
        market_type=market_type,
        market_status=market_status,  # ← добавлено
        cancellation_type=cancellation_type,
        search=search,
        cabinet_name=cabinet_name,
        order_date_from=order_date_from,
        order_date_to=order_date_to,
        send_date_from=send_date_from,
        send_date_to=send_date_to,
        my_send_date_from=my_send_date_from,
        my_send_date_to=my_send_date_to,
        item_status=item_status,
        item_provider=item_provider,
    )
    
    total_price = sum(
        (item.get('price') or 0) * item.get('count', 1)
        for order in orders
        for item in order.get('items', [])
    )
    total_purchase = sum(
        (item.get('purchase') or 0) * item.get('count', 1)
        for order in orders
        for item in order.get('items', [])
    )
    
    return {
        "items": [serialize_order(o) for o in orders],
        "total": total,
        "page": page or 1,
        "limit": limit or 20,
        "pages": (total + (limit or 20) - 1) // (limit or 20) if (limit or 20) > 0 else 1,
        "skip": skip,
        "total_price": total_price,
        "total_purchase": total_purchase,
    }

@router.get("/analytics")
async def analytics_orders(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    market_types: Optional[List[str]] = Query(None),
    cabinet_names: Optional[List[str]] = Query(None),
    process_statuses: Optional[List[str]] = Query(None),
    item_providers: Optional[List[str]] = Query(None),
    item_statuses: Optional[List[str]] = Query(None),
    search: Optional[str] = Query(None),
):
    """
    Аналитика по маркетплейсам и кабинетам за период.
    Фильтры по статусам и поставщикам теперь принимают списки.
    """

    print("Analytics filters:", {
        "date_from": date_from,
        "date_to": date_to,
        "market_types": market_types,
        "cabinet_names": cabinet_names,
        "process_statuses": process_statuses,
        "item_providers": item_providers,
        "item_statuses": item_statuses,
        "search": search,
    })

    raw_result = await order_repo.get_analytics(
        date_from=date_from,
        date_to=date_to,
        market_types=market_types,
        cabinet_names=cabinet_names,
        process_statuses=process_statuses,    # теперь List
        item_providers=item_providers,
        item_statuses=item_statuses,
        search=search,
    )

    # Сериализуем ObjectId перед возвратом
    serialized_result = serialize_analytics(raw_result)

    return serialized_result

@router.get("/status-stats", response_model=Dict[str, Any])
async def get_status_stats(
    order_repo: OrderRepository = Depends()
) -> Dict[str, Any]:
    """
    Получение статистики по market_status в разрезе маркетплейсов.
    
    Возвращает для каждого маркетплейса:
    - market_type: название маркетплейса
    - total: общее количество заказов на этом маркетплейсе
    - statuses: список статусов с количеством заказов в каждом
    - total_orders: общее количество заказов по всем маркетплейсам
    """
    return await order_repo.get_market_status_stats()

@router.get("/{order_id}", response_model=Dict[str, Any])
async def get_order_details(order_id: str):
    """
    Получение полной информации о заказе и всех его позициях.
    """
    order = await order_repo.get_order_details(order_id)
    
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
        
    return serialize_order(order)

# ------------------------------------------------------------------------
# II. ОБНОВЛЕНИЕ ДАННЫХ ОПЕРАТОРА (НАШЕЙ ЛОГИКИ)
# ------------------------------------------------------------------------

@router.patch("/{order_id}/handle", response_model=Dict[str, Any])
async def handle_order(
    order_id: str,
    payload: OrderHandleRequest,
):
    """
    Универсальный эндпоинт для работы с заказом:
    - Обновление my_send_date, comment
    - Обновление данных по позициям (purchase, provider, status)
    - Автоматическая смена статуса с 'New' на 'Process' (если все позиции обработаны)
    """
    updated = await order_repo.handle_order_processing(
        order_id=order_id,
        my_send_date=payload.my_send_date,
        comment=payload.comment,
        items=payload.items,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Order not found or no changes applied"
        )

    # Получаем обновлённый заказ для ответа
    updated_order = await order_repo.get_order_details(order_id)

    return {
        "message": "Order updated successfully",
        "order_id": order_id,
        "order": serialize_order(updated_order),
        "updated_fields": {
            "order": bool(payload.my_send_date is not None or payload.comment is not None),
            "items_count": len(payload.items) if payload.items else 0,
            "status_changed": updated.get("status_changed", False),
        }
    }


@router.patch("/items/status")
async def update_items_status(data: BulkItemStatusUpdate,
):
    """
    Массовое обновление статусов позиций заказа.
    """
    print("Received bulk status update request with data:", data)
    updated_count = await order_repo.bulk_update_item_statuses(data)

    if updated_count == 0:
        raise HTTPException(
            status_code=404,
            detail="No items found for the provided IDs"
        )

    return {
        "message": f"Statuses updated for {updated_count} items",
        "updated_count": updated_count
    }


# ------------------------------------------------------------------------
# III. ДЕЙСТВИЯ С МАРКЕТПЛЕЙСОМ (ЧЕРЕЗ АДАПТЕР)
# ------------------------------------------------------------------------

# (Этот раздел требует DI или получения адаптера, что мы сделаем позже,
# но пока оставим его для структуры)

@router.post("/{order_id}/status/{new_market_status}", status_code=200)
async def update_market_status(order_id: str, new_market_status: str):
    """
    Запрос на изменение статуса заказа на стороне маркетплейса (например, 'ship').
    """
    # 1. Получить заказ из БД, чтобы узнать market_type и external_id
    order = await order_repo.get_order_details(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    # 2. Инициализировать нужный адаптер (OzonAdapter, WBAdapter...)
    # (Эта логика будет реализована с помощью DI или сервиса-фабрики)
    # adapter = AdapterFactory.get_adapter(order['market_type'], cabinet_data)
    
    # 3. Вызвать метод адаптера
    # success = await adapter.update_market_status(order['order_id'], new_market_status)
    
    # if not success:
    #     raise HTTPException(status_code=500, detail="Failed to update status on Marketplace API")

    return {"message": f"Marketplace status update requested for order {order_id}"}


@router.post("/labels/print", response_model=LabelPrintResponse)
async def print_shipping_labels(
    request: LabelPrintRequest,
    adapter_factory: AdapterFactory = Depends(get_adapter_factory),
    order_repo: OrderRepository = Depends()
):
    """
    Универсальная печать этикеток для всех маркетплейсов.
    Получает cabinet_id, order_id и статус с фронта.
    """
    # Группируем заказы по кабинетам
    print(f'Начинаем процесс принта - {datetime.now()}')

    orders_by_cabinet = {}
    for order in request.orders:
        if order.cabinet_id not in orders_by_cabinet:
            orders_by_cabinet[order.cabinet_id] = []
        orders_by_cabinet[order.cabinet_id].append(order)
    
    all_results = []
    all_ready_ids = []

    print(f'Сгрупировали заказы по кабинетам - {datetime.now()}')
    
    # Обрабатываем каждый кабинет отдельно
    for cabinet_id, cabinet_orders in orders_by_cabinet.items():
        # Получаем адаптер для кабинета
        adapter = await adapter_factory.get_adapter_for_cabinet_id(cabinet_id)
        
        if not adapter:
            all_results.extend([
                {
                    "order_id": order.order_id,
                    "status": "error",
                    "message": f"Adapter not found for cabinet {cabinet_id}"
                }
                for order in cabinet_orders
            ])
            continue
        
        ready_for_labels = []
        
        for order in cabinet_orders:
            # Проверяем, можно ли сразу печатать
            if await adapter.can_print_label(order.status):
                ready_for_labels.append(order.order_id)
                all_results.append({
                    "order_id": order.order_id,
                    "status": "ready",
                    "message": f"Already ready for printing"
                })
            else:
                # Пытаемся перевести в нужный статус
                success = await adapter.update_market_status(order.order_id)
                if success:
                    ready_for_labels.append(order.order_id)
                    all_results.append({
                        "order_id": order.order_id,
                        "status": "ready",
                        "message": f"Status changed successfully"
                    })
                else:
                    all_results.append({
                        "order_id": order.order_id,
                        "status": "error",
                        "message": f"Failed to change status from {order.status}"
                    })
        
        # Если есть заказы для печати
        if ready_for_labels:
            all_ready_ids.extend(ready_for_labels)

            print(f'Собрали все заказы по маркетам, и получили их  - {datetime.now()}')

            
            # Задержка по необходимости (для Ozon 30 сек, для других меньше)
            if adapter.market_slug == "ozon":
                await asyncio.sleep(15)

            print(f'Задержка если нужна, и 15с для озона и начинаем  - {datetime.now()}')
            
            # Получаем этикетки
            labels = await adapter.get_shipping_label(ready_for_labels)

            print(f'Получили все ответы  - {datetime.now()}')
            
            return LabelPrintResponse(
                results=all_results,
                labels=labels,
                ready_count=len(all_ready_ids)
            )
    
    return LabelPrintResponse(
        results=all_results,
        labels=None,
        ready_count=0
    )



CANCELED_STATUSES = ['cancelled', 'canceled', 'CANCELLED', 'canceled_by_client', 'declined_by_client', 'defect', 'canceled_by_carrier', 'cancelled_from_split_pending', 'not_accepted', 'arbitration', 'client_arbitration', 'UNKNOWN']
DELIVERED_STATUSES = ['delivered', 'sold', 'DELIVERED']

@router.post("/fix/statuses")
async def fix_order_statuses_v2(
    order_repo: OrderRepository = Depends()
) -> Dict[str, Any]:
    """
    Исправляет process_status через агрегацию (одним запросом).
    """
    db = order_repo._get_db()
    
    # 1. Считаем, сколько заказов нужно исправить
    canceled_count = await db["orders"].count_documents({
        "market_status": {"$in": CANCELED_STATUSES},
        "process_status": {"$ne": "Cancel"}
    })
    
    delivered_count = await db["orders"].count_documents({
        "market_status": {"$in": DELIVERED_STATUSES},
        "process_status": {"$ne": "Done"}
    })
    
    # 2. Обновляем через update_many (один запрос для каждого типа)
    canceled_result = await db["orders"].update_many(
        {
            "market_status": {"$in": CANCELED_STATUSES},
            "process_status": {"$ne": "Cancel"}
        },
        {"$set": {"process_status": "Cancel"}}
    )
    
    delivered_result = await db["orders"].update_many(
        {
            "market_status": {"$in": DELIVERED_STATUSES},
            "process_status": {"$ne": "Done"}
        },
        {"$set": {"process_status": "Done"}}
    )
    
    total_fixed = canceled_result.modified_count + delivered_result.modified_count
    
    # 3. Статистика
    stats = await db["orders"].aggregate([
        {"$group": {
            "_id": "$process_status",
            "count": {"$sum": 1}
        }}
    ]).to_list(None)
    
    return {
        "success": True,
        "fixed": total_fixed,
        "canceled_fixed": canceled_result.modified_count,
        "delivered_fixed": delivered_result.modified_count,
        "stats": {s["_id"] or "None": s["count"] for s in stats}
    }



@router.post("/poller/run", response_model=Dict[str, Any])
async def run_poller_manually(
    request: Optional[ManualPollRequest] = None,
) -> Dict[str, Any]:
    """
    Ручной запуск поллинга.
    
    Если `cabinet_ids` не указан — запускает для всех активных кабинетов.
    """
    try:
        result = await run_manual_polling(
            cabinet_ids=request.cabinet_ids if request else None
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/poller/run/{cabinet_id}", response_model=Dict[str, Any])
async def run_poller_for_cabinet(cabinet_id: str) -> Dict[str, Any]:
    """Ручной запуск поллинга для одного кабинета"""
    try:
        result = await run_manual_polling(cabinet_ids=[cabinet_id])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))