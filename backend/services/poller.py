# services/poller.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bson import ObjectId
from marketplaces.wb_adapter import WildberriesAdapter
from marketplaces.yandex_adapter import YandexMarketAdapter
from repositories.order_repo import OrderRepository
from repositories.log_repo import LogRepository
from typing import Dict, Type, List, Any
import asyncio
from datetime import datetime, timezone
import os
import time
from routers.v1.websocket import manager
from utils.time import now_ts

# --- Импорт всех адаптеров ---
from marketplaces.base import BaseMarketplaceAdapter
from marketplaces.ozon_adapter import OzonAdapter

# Словарь для динамического выбора адаптера по market_slug
ADAPTER_MAP: Dict[str, Type[BaseMarketplaceAdapter]] = {
    "ozon": OzonAdapter,
    "yandex": YandexMarketAdapter,
    "wb": WildberriesAdapter
}

# Глобальный объект планировщика
scheduler = AsyncIOScheduler()


# ------------------------------------------------------------------------
# CORE LOGIC: Запуск опроса всех активных кабинетов
# ------------------------------------------------------------------------

async def fetch_all_active_cabinets():
    """Центральная функция для запуска опроса API всех активных магазинов."""
    started_at = now_ts()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Polling Cycle...")
    
    repo = OrderRepository() 
    
    # 1. Получаем все активные кабинеты из БД
    active_cabinets: List[Dict[str, Any]] = await repo.get_all_active_cabinets() 
    
    if not active_cabinets:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] No active cabinets found.")
        return
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(active_cabinets)} active cabinets")

    # 2. Запускаем все задачи параллельно
    tasks = []
    for cabinet_data in active_cabinets:
        slug = cabinet_data.get('market_slug')
        AdapterClass = ADAPTER_MAP.get(slug)
        
        if AdapterClass:
            tasks.append(run_adapter_fetch(AdapterClass, cabinet_data, repo))
        else:
            print(f"WARNING: Adapter not found for slug: {slug}")

    # 3. Ждём завершения всех задач (изолированно)
    await asyncio.gather(*tasks, return_exceptions=True)
    
    finished_at = now_ts()
    duration = finished_at - started_at
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Polling Cycle Finished. Duration: {duration}s")


# Функция-помощник для превращения объектов MongoDB в JSON-строки
def serialize_mongo_data(data):
    """Преобразует ObjectId и datetime в JSON-совместимые типы."""
    if isinstance(data, (list, tuple)):
        return [serialize_mongo_data(item) for item in data]
    
    if isinstance(data, dict):
        return {k: serialize_mongo_data(v) for k, v in data.items()}
    
    if isinstance(data, ObjectId):
        return str(data)
    
    if isinstance(data, datetime):
        return data.isoformat()
    
    return data


import time

async def run_adapter_fetch(
    AdapterClass: Type[BaseMarketplaceAdapter], 
    cabinet_data: dict, 
    repo: OrderRepository
) -> Dict[str, Any]:
    """
    Оборачивает запуск адаптера, логирует и возвращает статистику.
    is_new берётся из upsert_order (НЕ перезаписывается).
    """
    adapter = AdapterClass(cabinet_data, repo)
    cabinet_id = cabinet_data.get('_id')
    cabinet_name = cabinet_data.get('name')
    market_slug = adapter.market_slug
    
    log_repo = LogRepository()
    started_perf = time.perf_counter()  # 🔥 точное время
    started_at = now_ts()
    
    try:
        new_orders = await adapter.fetch_new_and_updated_orders()
        
        if new_orders is None:
            raise Exception("Adapter returned None")
        
        created_count = 0
        updated_count = 0
        touched_count = 0
        
        if isinstance(new_orders, list):
            clean_orders = serialize_mongo_data(new_orders)
            
            for order in clean_orders:
                is_new = order.get('is_new', False)
                status_changed = order.get('status_changed', False)

                touched_count += 1
                
                if is_new:
                    created_count += 1
                    if order.get('process_status') == 'New':
                        await manager.broadcast({
                            "type": "new_order",
                            "data": order
                        })
                elif status_changed:
                    updated_count += 1
                    await manager.broadcast({
                        "type": "update_order",
                        "data": order
                    })
        
        finished_at = now_ts()
        duration = round(time.perf_counter() - started_perf, 3)  # 🔥 float
        
        # Логируем при любых действиях (даже если просто "касались")
        if touched_count > 0:
            log_id = await log_repo.create_polling_log(
                market_type=market_slug,
                cabinet_id=str(cabinet_id),
                cabinet_name=cabinet_name,
            )
            await log_repo.update_polling_log(log_id, {
                "finished_at": finished_at,
                "duration_seconds": duration,  # 🔥 float
                "status": "success",
                "orders_touched": touched_count,
                "orders_created": created_count,
                "orders_updated": updated_count,
            })
        
        print(f"✅ {market_slug} ({cabinet_name}): touched: {touched_count}, "
              f"created {created_count}, updated {updated_count} за {duration}s")
        
        return {
            "success": True,
            "market_slug": market_slug,
            "cabinet_name": cabinet_name,
            "touched": touched_count,
            "created": created_count,
            "updated": updated_count,
            "duration": duration,
        }
        
    except Exception as e:
        finished_at = now_ts()
        duration = round(time.perf_counter() - started_perf, 3)
        error_msg = str(e)
        
        log_id = await log_repo.create_polling_log(
            market_type=market_slug,
            cabinet_id=str(cabinet_id),
            cabinet_name=cabinet_name,
        )
        await log_repo.update_polling_log(log_id, {
            "finished_at": finished_at,
            "duration_seconds": duration,
            "status": "error",
            "error_message": error_msg,
            "errors": [{
                "error": error_msg,
                "timestamp": finished_at,
                "type": type(e).__name__,
            }],
        })
        
        print(f"❌ ERROR: {market_slug} ({cabinet_name}) за {duration}s: {error_msg}")
        
        return {
            "success": False,
            "market_slug": market_slug,
            "cabinet_name": cabinet_name,
            "touched": 0,
            "created": 0,
            "updated": 0,
            "duration": duration,
            "error": error_msg,
        }

async def run_manual_polling(cabinet_ids: List[str] = None) -> Dict[str, Any]:
    started_perf = time.perf_counter()
    started_at = now_ts()
    print(f"🚀 Manual polling started at {datetime.now().strftime('%H:%M:%S')}")
    
    repo = OrderRepository()
    active_cabinets = await repo.get_all_active_cabinets()
    
    if cabinet_ids:
        cabinet_ids_str = [str(cid) for cid in cabinet_ids]
        active_cabinets = [
            c for c in active_cabinets 
            if str(c.get('_id')) in cabinet_ids_str
        ]
    
    if not active_cabinets:
        return {
            "success": False,
            "message": "No active cabinets found",
            "total_cabinets": 0,
        }
    
    print(f"📦 Found {len(active_cabinets)} active cabinets")
    
    tasks = []
    for cabinet_data in active_cabinets:
        slug = cabinet_data.get('market_slug')
        AdapterClass = ADAPTER_MAP.get(slug)
        
        if AdapterClass:
            tasks.append(run_adapter_fetch(AdapterClass, cabinet_data, repo))
        else:
            print(f"⚠️ Adapter not found for slug: {slug}")
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    duration = round(time.perf_counter() - started_perf, 3)
    
    total_touched = 0
    total_created = 0
    total_updated = 0
    errors = []
    
    for result in results:
        if isinstance(result, Exception):
            errors.append(str(result))
        elif isinstance(result, dict):
            total_touched += result.get('touched', 0)
            total_created += result.get('created', 0)
            total_updated += result.get('updated', 0)
    
    print(f"✅ Manual polling finished. Duration: {duration}s, "
          f"touched: {total_touched}, created: {total_created}, "
          f"updated: {total_updated}, errors: {len(errors)}")
    
    return {
        "success": True,
        "duration_seconds": duration,
        "total_cabinets": len(active_cabinets),
        "total_touched": total_touched,
        "total_created": total_created,
        "total_updated": total_updated,
        "errors": errors,
    }


# ------------------------------------------------------------------------
# SCHEDULER CONTROL
# ------------------------------------------------------------------------

async def start_polling(interval_seconds: int):
    """Инициализирует и запускает планировщик."""
    
    scheduler.add_job(
        fetch_all_active_cabinets, 
        'interval', 
        seconds=interval_seconds, 
        id='main_poller',
        max_instances=1,  # Защита от наложения циклов
        coalesce=True,    # Объединяет пропущенные запуски
    )
    
    if not scheduler.running:
        scheduler.start()
        print(f"⏰ Polling started with interval: {interval_seconds}s")


def stop_polling():
    """Останавливает планировщик при выключении приложения."""
    if scheduler.running:
        scheduler.shutdown()
        print("🛑 Polling stopped")