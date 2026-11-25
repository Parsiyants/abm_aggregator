# repositories/order_history_repo.py
from typing import List, Optional, Dict, Any
from bson import ObjectId
from database.mongodb import get_db
from utils.time import now_ts, ts_to_iso


class OrderHistoryRepository:
    def __init__(self):
        pass

    def _get_db(self):
        db = get_db()
        if db is None:
            raise Exception("Database connection is not available.")
        return db

    async def add_entry(
        self,
        order_id_ref: str,
        order_id: str,
        market_type: str,
        event_type: str,
        event_source: str,
        changes: Dict[str, Any] = None,
        user_id: str = None,
        user_email: str = None,
        comment: str = None,
        old_status: str = None,
        new_status: str = None,
    ) -> str:
        """Добавляет запись в историю заказа"""
        db = self._get_db()
        doc = {
            "order_id_ref": order_id_ref,
            "order_id": order_id,
            "market_type": market_type,
            "event_type": event_type,
            "event_source": event_source,
            "changes": changes or {},
            "user_id": user_id,
            "user_email": user_email,
            "comment": comment,
            "old_status": old_status,
            "new_status": new_status,
            "created_at": now_ts(),  # ← Unix Timestamp
        }
        result = await db["order_history"].insert_one(doc)
        return str(result.inserted_id)

    async def get_order_history(
        self,
        order_id_ref: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Получает историю конкретного заказа"""
        db = self._get_db()
        cursor = db["order_history"].find(
            {"order_id_ref": order_id_ref}
        ).sort("created_at", -1).limit(limit)
        history = await cursor.to_list(None)
        
        # Конвертируем Unix Timestamp в ISO
        for entry in history:
            entry["_id"] = str(entry["_id"])
            entry["created_at_iso"] = ts_to_iso(entry.get("created_at"))
        
        return history

    async def get_recent_history(
        self,
        limit: int = 100,
        skip: int = 0,
        event_type: str = None,
        event_source: str = None,
        market_type: str = None,
        user_id: str = None,
    ) -> Dict[str, Any]:
        """Получает последние события с пагинацией"""
        db = self._get_db()
        query = {}
        
        if event_type:
            query["event_type"] = event_type
        if event_source:
            query["event_source"] = event_source
        if market_type:
            query["market_type"] = market_type
        if user_id:
            query["user_id"] = user_id
        
        total = await db["order_history"].count_documents(query)
        cursor = db["order_history"].find(query).sort("created_at", -1).skip(skip).limit(limit)
        history = await cursor.to_list(None)
        
        for entry in history:
            entry["_id"] = str(entry["_id"])
            entry["created_at_iso"] = ts_to_iso(entry.get("created_at"))
        
        return {
            "items": history,
            "total": total,
            "limit": limit,
            "skip": skip,
        }
    
    async def get_order_history(
        self,
        order_id_ref: str,
        limit: int = 100,
        skip: int = 0,
    ) -> Dict[str, Any]:
        """Получает историю конкретного заказа"""
        db = self._get_db()
        query = {"order_id_ref": order_id_ref}
        
        total = await db["order_history"].count_documents(query)
        cursor = db["order_history"].find(query).sort("created_at", -1).skip(skip).limit(limit)
        history = await cursor.to_list(None)
        
        for entry in history:
            entry["_id"] = str(entry["_id"])
            entry["created_at_iso"] = ts_to_iso(entry.get("created_at"))
        
        return {
            "items": history,
            "total": total,
            "limit": limit,
            "skip": skip,
        }
    
    async def delete_history_entry(self, history_id: str) -> bool:
        """Удаляет запись из истории"""
        db = self._get_db()
        try:
            result = await db["order_history"].delete_one({"_id": ObjectId(history_id)})
            return result.deleted_count > 0
        except:
            return False
    
    async def clear_history(
        self,
        order_id_ref: str = None,
        older_than_days: int = None,
    ) -> int:
        """Очищает историю"""
        db = self._get_db()
        query = {}
        
        if order_id_ref:
            query["order_id_ref"] = order_id_ref
        if older_than_days:
            min_ts = now_ts() - (older_than_days * 86400)
            query["created_at"] = {"$lt": min_ts}
        
        result = await db["order_history"].delete_many(query)
        return result.deleted_count