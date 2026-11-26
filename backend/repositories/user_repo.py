from database.mongodb import get_db
from models.user import User
from typing import Optional, Dict, Any
from bson import ObjectId

class UserRepository:
    def _get_db(self):
        db = get_db()
        if db is None:
            raise Exception("Database connection is not available.")
        return db

    def _get_collection(self):
        db = self._get_db()
        return db["users"] # Наша коллекция пользователей

    async def create_user(self, email: str, hashed_password: str) -> Optional[Dict[str, Any]]:
        """Создает нового пользователя."""
        collection = self._get_collection()
        user_doc = {"email": email, "hashed_password": hashed_password}
        
        # Проверяем, существует ли пользователь с таким email
        if await collection.find_one({"email": email}):
            return None # Пользователь уже существует
            
        result = await collection.insert_one(user_doc)
        
        # Возвращаем созданный документ (без пароля)
        new_user = await collection.find_one({"_id": result.inserted_id}, {"hashed_password": 0})
        
        if new_user:
            new_user["_id"] = str(new_user["_id"])
            
        return new_user

    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Получает пользователя по email, включая захэшированный пароль."""
        collection = self._get_collection()
        user_doc = await collection.find_one({"email": email})
        
        if user_doc and "_id" in user_doc:
            user_doc["_id"] = str(user_doc["_id"])
            
        return user_doc

    async def set_password(self, email: str, hashed_password: str) -> bool:
        """Меняет пароль существующего пользователя. True — если обновлён."""
        collection = self._get_collection()
        result = await collection.update_one(
            {"email": email},
            {"$set": {"hashed_password": hashed_password}},
        )
        return result.modified_count > 0

    async def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получает пользователя по ID."""
        collection = self._get_collection()
        try:
            user_doc = await collection.find_one({"_id": ObjectId(user_id)}, {"hashed_password": 0})
            if user_doc and "_id" in user_doc:
                user_doc["_id"] = str(user_doc["_id"])
            return user_doc
        except Exception:
            return None