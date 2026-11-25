# repositories/telegram_repo.py
from typing import List, Optional
from datetime import datetime
from database.mongodb import get_db

class TelegramSubscriberRepository:
    def __init__(self):
        self.collection_name = "telegram_subscribers"
    
    def _get_collection(self):
        db = get_db()
        return db[self.collection_name]
    
    async def add_subscriber(self, chat_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        collection = self._get_collection()
        existing = await collection.find_one({"chat_id": chat_id})
        if existing:
            await collection.update_one(
                {"chat_id": chat_id},
                {"$set": {
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "subscribed_at": datetime.now(),
                    "is_active": True
                }}
            )
            return True
        
        subscriber = {
            "chat_id": chat_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "subscribed_at": datetime.now(),
            "is_active": True
        }
        result = await collection.insert_one(subscriber)
        return result.inserted_id is not None
    
    async def remove_subscriber(self, chat_id: int) -> bool:
        collection = self._get_collection()
        result = await collection.update_one(
            {"chat_id": chat_id},
            {"$set": {"is_active": False}}
        )
        return result.modified_count > 0
    
    async def get_all_active_subscribers(self) -> List[int]:
        collection = self._get_collection()
        subscribers = await collection.find({"is_active": True}).to_list(None)
        return [sub["chat_id"] for sub in subscribers]
    
    async def get_subscriber_count(self) -> int:
        collection = self._get_collection()
        return await collection.count_documents({"is_active": True})
    
    async def is_subscribed(self, chat_id: int) -> bool:
        collection = self._get_collection()
        subscriber = await collection.find_one({"chat_id": chat_id, "is_active": True})
        return subscriber is not None