# routers/v1/sync.py
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from repositories.order_repo import OrderRepository
from services.wb_sync_service import WBSyncService

router = APIRouter(prefix="/sync", tags=["Sync"])


class ManualSyncRequest(BaseModel):
    cabinet_id: Optional[str] = None  # если None — все кабинеты WB


@router.post("/wb/run")
async def run_wb_sync(request: Optional[ManualSyncRequest] = None) -> Dict[str, Any]:
    """
    Ручной запуск синхронизации цен и остатков WB.

    - Если cabinet_id не указан — синхронизирует все активные кабинеты WB.
    - Если указан — только выбранный кабинет.
    """
    repo = OrderRepository()
    all_cabinets = await repo.get_all_active_cabinets()
    wb_cabinets = [c for c in all_cabinets if c.get('market_slug') == 'wb']

    if request and request.cabinet_id:
        wb_cabinets = [
            c for c in wb_cabinets
            if str(c.get('_id')) == str(request.cabinet_id)
        ]

    if not wb_cabinets:
        raise HTTPException(status_code=404, detail="No active WB cabinets found")

    results = []
    total_prices = 0
    total_stocks = 0
    total_zeroed = 0
    errors = []

    for cabinet in wb_cabinets:
        try:
            service = WBSyncService(cabinet, repo)
            result = await service.sync_cabinet()
            results.append(result)

            if result["success"]:
                total_prices += result["prices_updated"]
                total_stocks += result["stocks_updated"]
                total_zeroed += result.get("stocks_zeroed", 0)
            else:
                errors.extend(result["errors"])
        except Exception as e:
            errors.append(f"{cabinet.get('name')}: {e}")

    return {
        "success": len(errors) == 0,
        "cabinets_processed": len(wb_cabinets),
        "total_prices_updated": total_prices,
        "total_stocks_updated": total_stocks,
        "total_stocks_zeroed": total_zeroed,
        "results": results,
        "errors": errors,
    }