# repositories/log_repo.py
from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from database.mongodb import get_db
from utils.time import now_ts, ts_to_iso


class LogRepository:
    def __init__(self):
        pass

    def _get_db(self):
        db = get_db()
        if db is None:
            raise Exception("Database connection is not available.")
        return db

    # ═══════════════════════════════════════════════════════════════════════
    # POLLING LOGS
    # ═══════════════════════════════════════════════════════════════════════

    async def create_polling_log(
        self,
        market_type: str = None,
        cabinet_id: str = None,
        cabinet_name: str = None,
    ) -> str:
        """Создаёт запись о начале поллинга"""
        db = self._get_db()
        doc = {
            "started_at": now_ts(),
            "finished_at": None,
            "duration_seconds": None,
            "status": "pending",
            "market_type": market_type,
            "cabinet_id": cabinet_id,
            "cabinet_name": cabinet_name,
            "orders_created": 0,
            "orders_updated": 0,
            "orders_touched": 0,
            "orders_failed": 0,
            "items_created": 0,
            "items_updated": 0,
            "errors": [],
            "error_message": None,
        }
        result = await db["polling_logs"].insert_one(doc)
        return str(result.inserted_id)

    async def update_polling_log(
        self,
        log_id: str,
        data: Dict[str, Any],
    ) -> bool:
        """Обновляет лог поллинга"""
        db = self._get_db()
        
        # 🔥 Считаем duration ТОЛЬКО если он не передан явно
        if "finished_at" in data and data["finished_at"] and "duration_seconds" not in data:
            start = await db["polling_logs"].find_one({"_id": ObjectId(log_id)})
            if start and start.get("started_at"):
                data["duration_seconds"] = data["finished_at"] - start["started_at"]

        result = await db["polling_logs"].update_one(
            {"_id": ObjectId(log_id)},
            {"$set": data}
        )
        return result.modified_count > 0

    async def get_polling_logs(
        self,
        limit: int = 50,
        skip: int = 0,
        market_type: str = None,
        status: str = None,
        cabinet_id: str = None,
    ) -> Dict[str, Any]:
        """Получает логи поллинга с пагинацией"""
        db = self._get_db()
        query = {}
        
        if market_type:
            query["market_type"] = market_type
        if status:
            query["status"] = status
        if cabinet_id:
            query["cabinet_id"] = cabinet_id
        
        total = await db["polling_logs"].count_documents(query)
        cursor = db["polling_logs"].find(query).sort("started_at", -1).skip(skip).limit(limit)
        logs = await cursor.to_list(None)
        
        # Конвертируем Unix Timestamp в ISO
        for log in logs:
            log["_id"] = str(log["_id"])
            log["started_at_iso"] = ts_to_iso(log.get("started_at"))
            log["finished_at_iso"] = ts_to_iso(log.get("finished_at"))
        
        return {
            "items": logs,
            "total": total,
            "limit": limit,
            "skip": skip,
        }

    async def get_polling_log_by_id(self, log_id: str) -> Optional[Dict]:
        """Получает один лог по ID"""
        db = self._get_db()
        try:
            log = await db["polling_logs"].find_one({"_id": ObjectId(log_id)})
        except:
            return None
        
        if log:
            log["_id"] = str(log["_id"])
            log["started_at_iso"] = ts_to_iso(log.get("started_at"))
            log["finished_at_iso"] = ts_to_iso(log.get("finished_at"))
        
        return log

    async def delete_polling_log(self, log_id: str) -> bool:
        """Удаляет лог по ID"""
        db = self._get_db()
        try:
            result = await db["polling_logs"].delete_one({"_id": ObjectId(log_id)})
            return result.deleted_count > 0
        except:
            return False

    async def clear_polling_logs(
        self,
        older_than_days: int = None,
        market_type: str = None,
    ) -> int:
        """Очищает логи поллинга"""
        db = self._get_db()
        query = {}
        
        if older_than_days:
            min_ts = now_ts() - (older_than_days * 86400)
            query["started_at"] = {"$lt": min_ts}
        if market_type:
            query["market_type"] = market_type
        
        result = await db["polling_logs"].delete_many(query)
        return result.deleted_count

    # ═══════════════════════════════════════════════════════════════════════
    # SYNC LOGS
    # ═══════════════════════════════════════════════════════════════════════

    async def create_sync_log(
        self,
        sync_type: str,
        market_type: str,
        cabinet_id: str,
        cabinet_name: str,
        total_items: int = 0,
    ) -> str:
        """Создаёт запись о начале синхронизации"""
        db = self._get_db()
        doc = {
            "sync_type": sync_type,
            "market_type": market_type,
            "cabinet_id": cabinet_id,
            "cabinet_name": cabinet_name,
            "started_at": now_ts(),
            "finished_at": None,
            "duration_seconds": None,
            "status": "pending",

            # Общая статистика
            "total_items": total_items,
            "success_count": 0,
            "failed_count": 0,

            # Детализация
            "items": [],
            "errors": [],

            # ── WB-specific: инициализируем сразу ──
            "yml_items_total": 0,
            "wb_goods_total": 0,
            "matched": 0,
            "unmatched_wb": 0,

            "prices_updated": 0,
            "prices_skipped": 0,

            "stocks_updated": 0,
            "stocks_zeroed": 0,
            "stocks_skipped": 0,

            "error_message": None,
        }
        result = await db["sync_logs"].insert_one(doc)
        return str(result.inserted_id)

    async def update_sync_log(
        self,
        log_id: str,
        data: Dict[str, Any],
    ) -> bool:
        """Обновляет лог синхронизации"""
        db = self._get_db()
        
        # 🔥 Считаем duration ТОЛЬКО если он не передан явно
        if "finished_at" in data and data["finished_at"] and "duration_seconds" not in data:
            start = await db["sync_logs"].find_one({"_id": ObjectId(log_id)})
            if start and start.get("started_at"):
                data["duration_seconds"] = data["finished_at"] - start["started_at"]

        result = await db["sync_logs"].update_one(
            {"_id": ObjectId(log_id)},
            {"$set": data}
        )
        return result.modified_count > 0

    async def get_sync_logs(
        self,
        limit: int = 50,
        skip: int = 0,
        market_type: str = None,
        sync_type: str = None,
        status: str = None,
        cabinet_id: str = None,
    ) -> Dict[str, Any]:
        """Получает логи синхронизации с пагинацией"""
        db = self._get_db()
        query = {}
        
        if market_type:
            query["market_type"] = market_type
        if sync_type:
            query["sync_type"] = sync_type
        if status:
            query["status"] = status
        if cabinet_id:
            query["cabinet_id"] = cabinet_id
        
        total = await db["sync_logs"].count_documents(query)
        cursor = db["sync_logs"].find(query).sort("started_at", -1).skip(skip).limit(limit)
        logs = await cursor.to_list(None)
        
        for log in logs:
            log["_id"] = str(log["_id"])
            log["started_at_iso"] = ts_to_iso(log.get("started_at"))
            log["finished_at_iso"] = ts_to_iso(log.get("finished_at"))
        
        return {
            "items": logs,
            "total": total,
            "limit": limit,
            "skip": skip,
        }

    async def get_sync_log_by_id(self, log_id: str) -> Optional[Dict]:
        """Получает один лог синхронизации"""
        db = self._get_db()
        try:
            log = await db["sync_logs"].find_one({"_id": ObjectId(log_id)})
        except:
            return None
        
        if log:
            log["_id"] = str(log["_id"])
            log["started_at_iso"] = ts_to_iso(log.get("started_at"))
            log["finished_at_iso"] = ts_to_iso(log.get("finished_at"))
        
        return log

    async def delete_sync_log(self, log_id: str) -> bool:
        """Удаляет лог синхронизации"""
        db = self._get_db()
        try:
            result = await db["sync_logs"].delete_one({"_id": ObjectId(log_id)})
            return result.deleted_count > 0
        except:
            return False

    async def clear_sync_logs(
        self,
        older_than_days: int = None,
        market_type: str = None,
    ) -> int:
        """Очищает логи синхронизации"""
        db = self._get_db()
        query = {}
        
        if older_than_days:
            min_ts = now_ts() - (older_than_days * 86400)
            query["started_at"] = {"$lt": min_ts}
        if market_type:
            query["market_type"] = market_type
        
        result = await db["sync_logs"].delete_many(query)
        return result.deleted_count

    # ═══════════════════════════════════════════════════════════════════════
    # STATS
    # ═══════════════════════════════════════════════════════════════════════

    async def get_logs_stats(self, days: int = 7) -> Dict[str, Any]:
        """Агрегированная статистика по логам за N дней"""
        db = self._get_db()
        min_ts = now_ts() - (days * 86400)

        # ─── Поллинг ───
        polling_stats = await db["polling_logs"].aggregate([
            {"$match": {"started_at": {"$gte": min_ts}}},
            {
                "$group": {
                    "_id": {"market_type": "$market_type", "status": "$status"},
                    "count": {"$sum": 1},
                    "total_touched": {"$sum": {"$ifNull": ["$orders_touched", 0]}},
                    "total_created": {"$sum": {"$ifNull": ["$orders_created", 0]}},
                    "total_updated": {"$sum": {"$ifNull": ["$orders_updated", 0]}},
                }
            }
        ]).to_list(None)

        total_logs = await db["polling_logs"].count_documents({"started_at": {"$gte": min_ts}})
        total_errors = await db["polling_logs"].count_documents({
            "started_at": {"$gte": min_ts},
            "status": "error"
        })

        totals = await db["polling_logs"].aggregate([
            {"$match": {"started_at": {"$gte": min_ts}}},
            {
                "$group": {
                    "_id": None,
                    "total_touched": {"$sum": {"$ifNull": ["$orders_touched", 0]}},
                    "total_created": {"$sum": {"$ifNull": ["$orders_created", 0]}},
                    "total_updated": {"$sum": {"$ifNull": ["$orders_updated", 0]}},
                }
            }
        ]).to_list(1)

        grand = totals[0] if totals else {
            "total_touched": 0,
            "total_created": 0,
            "total_updated": 0,
        }

        # ─── Синхронизация ───
        sync_logs_total = await db["sync_logs"].count_documents({"started_at": {"$gte": min_ts}})
        sync_errors_total = await db["sync_logs"].count_documents({
            "started_at": {"$gte": min_ts},
            "status": "error"
        })

        sync_totals = await db["sync_logs"].aggregate([
            {"$match": {"started_at": {"$gte": min_ts}}},
            {
                "$group": {
                    "_id": None,
                    "total_prices_updated": {"$sum": {"$ifNull": ["$prices_updated", 0]}},
                    "total_stocks_updated": {"$sum": {"$ifNull": ["$stocks_updated", 0]}},
                    "total_stocks_zeroed": {"$sum": {"$ifNull": ["$stocks_zeroed", 0]}},
                    "total_matched": {"$sum": {"$ifNull": ["$matched", 0]}},
                    "total_unmatched_wb": {"$sum": {"$ifNull": ["$unmatched_wb", 0]}},
                }
            }
        ]).to_list(1)

        sync_grand = sync_totals[0] if sync_totals else {
            "total_prices_updated": 0,
            "total_stocks_updated": 0,
            "total_stocks_zeroed": 0,
            "total_matched": 0,
            "total_unmatched_wb": 0,
        }

        return {
            "period_days": days,

            # Поллинг
            "total_logs": total_logs,
            "total_errors": total_errors,
            "total_touched": grand.get("total_touched", 0),
            "total_created": grand.get("total_created", 0),
            "total_updated": grand.get("total_updated", 0),
            "by_market": polling_stats,

            # Синхронизация
            "sync_logs_total": sync_logs_total,
            "sync_errors_total": sync_errors_total,
            "total_prices_updated": sync_grand.get("total_prices_updated", 0),
            "total_stocks_updated": sync_grand.get("total_stocks_updated", 0),
            "total_stocks_zeroed": sync_grand.get("total_stocks_zeroed", 0),
            "total_matched": sync_grand.get("total_matched", 0),
            "total_unmatched_wb": sync_grand.get("total_unmatched_wb", 0),
        }

    async def get_cabinet_stats(self, cabinet_id: str, days: int = 7) -> Dict[str, Any]:
        """Статистика по конкретному кабинету"""
        db = self._get_db()
        min_ts = now_ts() - (days * 86400)
        
        stats = await db["polling_logs"].aggregate([
            {"$match": {"cabinet_id": cabinet_id, "started_at": {"$gte": min_ts}}},
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "total_touched": {"$sum": {"$ifNull": ["$orders_touched", 0]}},
                    "total_created": {"$sum": {"$ifNull": ["$orders_created", 0]}},
                    "total_updated": {"$sum": {"$ifNull": ["$orders_updated", 0]}},
                }
            }
        ]).to_list(None)
        
        return {
            "cabinet_id": cabinet_id,
            "period_days": days,
            "stats": stats,
        }