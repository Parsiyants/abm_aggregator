# routers/v1/logs.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from repositories.log_repo import LogRepository
from repositories.order_history_repo import OrderHistoryRepository


router = APIRouter(prefix="/logs", tags=["Logs"])


# ═══════════════════════════════════════════════════════════════════════
# POLLING LOGS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/polling")
async def get_polling_logs(
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    market_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    cabinet_id: Optional[str] = Query(None),
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """
    Получает список логов поллинга.
    
    Фильтры:
    - market_type: ozon, yandex, wb
    - status: success, error, pending
    - cabinet_id: ID кабинета
    """
    result = await repo.get_polling_logs(
        limit=limit,
        skip=skip,
        market_type=market_type,
        status=status,
        cabinet_id=cabinet_id,
    )
    return result


@router.get("/polling/{log_id}")
async def get_polling_log(
    log_id: str,
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """Получает лог поллинга по ID."""
    log = await repo.get_polling_log_by_id(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log


@router.delete("/polling/{log_id}")
async def delete_polling_log(
    log_id: str,
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """Удаляет лог поллинга."""
    success = await repo.delete_polling_log(log_id)
    if not success:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"success": True, "message": "Log deleted"}


@router.delete("/polling")
async def clear_polling_logs(
    older_than_days: Optional[int] = Query(None, ge=1),
    market_type: Optional[str] = Query(None),
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """
    Очищает логи поллинга.
    
    - older_than_days: удалить логи старше N дней
    - market_type: удалить только для конкретного маркета
    """
    deleted_count = await repo.clear_polling_logs(
        older_than_days=older_than_days,
        market_type=market_type,
    )
    return {"success": True, "deleted_count": deleted_count}


# ═══════════════════════════════════════════════════════════════════════
# SYNC LOGS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/sync")
async def get_sync_logs(
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    market_type: Optional[str] = Query(None),
    sync_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    cabinet_id: Optional[str] = Query(None),
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """
    Получает список логов синхронизации.
    
    Фильтры:
    - market_type: ozon, yandex, wb
    - sync_type: prices, stocks, orders, full
    - status: pending, success, partial, error
    - cabinet_id: ID кабинета
    """
    result = await repo.get_sync_logs(
        limit=limit,
        skip=skip,
        market_type=market_type,
        sync_type=sync_type,
        status=status,
        cabinet_id=cabinet_id,
    )
    return result


@router.get("/sync/{log_id}")
async def get_sync_log(
    log_id: str,
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """Получает лог синхронизации по ID."""
    log = await repo.get_sync_log_by_id(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log


@router.delete("/sync/{log_id}")
async def delete_sync_log(
    log_id: str,
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """Удаляет лог синхронизации."""
    success = await repo.delete_sync_log(log_id)
    if not success:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"success": True, "message": "Log deleted"}


@router.delete("/sync")
async def clear_sync_logs(
    older_than_days: Optional[int] = Query(None, ge=1),
    market_type: Optional[str] = Query(None),
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """Очищает логи синхронизации."""
    deleted_count = await repo.clear_sync_logs(
        older_than_days=older_than_days,
        market_type=market_type,
    )
    return {"success": True, "deleted_count": deleted_count}


# ═══════════════════════════════════════════════════════════════════════
# ORDER HISTORY
# ═══════════════════════════════════════════════════════════════════════

@router.get("/history")
async def get_recent_history(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    event_type: Optional[str] = Query(None),
    event_source: Optional[str] = Query(None),
    market_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    repo: OrderHistoryRepository = Depends(),
) -> Dict[str, Any]:
    """
    Получает последние события по всем заказам.
    
    Фильтры:
    - event_type: created, status_changed, updated, handled, synced
    - event_source: poller, user, webhook, system
    - market_type: ozon, yandex, wb
    - user_id: ID пользователя
    """
    result = await repo.get_recent_history(
        limit=limit,
        skip=skip,
        event_type=event_type,
        event_source=event_source,
        market_type=market_type,
        user_id=user_id,
    )
    return result


@router.get("/history/{order_id_ref}")
async def get_order_history(
    order_id_ref: str,
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    repo: OrderHistoryRepository = Depends(),
) -> Dict[str, Any]:
    """
    Получает историю конкретного заказа.
    
    order_id_ref — это _id заказа в MongoDB (строка).
    """
    result = await repo.get_order_history(
        order_id_ref=order_id_ref,
        limit=limit,
        skip=skip,
    )
    return result


@router.delete("/history/{history_id}")
async def delete_history_entry(
    history_id: str,
    repo: OrderHistoryRepository = Depends(),
) -> Dict[str, Any]:
    """Удаляет запись из истории."""
    success = await repo.delete_history_entry(history_id)
    if not success:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"success": True, "message": "History entry deleted"}


@router.delete("/history")
async def clear_order_history(
    order_id_ref: Optional[str] = Query(None),
    older_than_days: Optional[int] = Query(None, ge=1),
    repo: OrderHistoryRepository = Depends(),
) -> Dict[str, Any]:
    """
    Очищает историю заказов.
    
    - order_id_ref: удалить только для конкретного заказа
    - older_than_days: удалить записи старше N дней
    """
    deleted_count = await repo.clear_history(
        order_id_ref=order_id_ref,
        older_than_days=older_than_days,
    )
    return {"success": True, "deleted_count": deleted_count}


# ═══════════════════════════════════════════════════════════════════════
# STATS / DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_logs_stats(
    days: int = Query(7, ge=1, le=90),
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """
    Агрегированная статистика по логам за N дней.
    Используется для дашборда.
    """
    return await repo.get_logs_stats(days=days)


@router.get("/stats/cabinet/{cabinet_id}")
async def get_cabinet_stats(
    cabinet_id: str,
    days: int = Query(7, ge=1, le=90),
    repo: LogRepository = Depends(),
) -> Dict[str, Any]:
    """Статистика по конкретному кабинету."""
    return await repo.get_cabinet_stats(cabinet_id=cabinet_id, days=days)