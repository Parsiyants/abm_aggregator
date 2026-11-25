# backend/repositories/reference_repo.py

from database.mongodb import get_db
# Импортируем только то, что используется в коде репозитория
from typing import List, Dict, Any, Optional
from bson import ObjectId

class ReferenceRepository:
    def __init__(self):
        # __init__ остается пустым, так как коллекции инициализируются 
        # отложенно в асинхронных методах.
        pass

    def _get_db(self):
        """Вспомогательный метод для получения объекта базы данных."""
        db = get_db()
        if db is None:
            # Выброс исключения, если база данных не подключена
            raise Exception("Database connection is not available.") 
        return db

    def _get_collection(self, collection_name: str):
        """Вспомогательный метод для получения объекта коллекции."""
        db = self._get_db() # Используем метод для получения БД
        return db[collection_name] # Возвращаем объект коллекции, не проверяя его

    # ------------------------------------------------------------------------
    # CRUD: CREATE
    # ------------------------------------------------------------------------
    
    async def create(self, collection_name: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Создает новый документ в указанной коллекции."""
        
        collection = self._get_collection(collection_name)
        
        # УДАЛЯЕМ if not collection: - это вызывает NotImplementedError!
        # Коллекция будет создана автоматически при insert_one.
        
        result = await collection.insert_one(data)
        
        # Получаем итоговый документ для возврата, гарантируя, что _id будет строкой
        new_doc = await collection.find_one({"_id": result.inserted_id})
        
        if new_doc:
            # Преобразование ObjectId в строку для корректного JSON-ответа FastAPI
            new_doc["_id"] = str(new_doc["_id"])
        
        return new_doc

    # ------------------------------------------------------------------------
    # CRUD: READ (LIST)
    # ------------------------------------------------------------------------

    async def get_all(self, collection_name: str) -> List[Dict[str, Any]]:
        """Получает все документы из указанной коллекции."""
        
        collection = self._get_collection(collection_name) # <-- Используем унифицированный метод
        
        cursor = collection.find()
        documents = await cursor.to_list(length=None)
        
        # Преобразуем _id во всех документах в строку
        for doc in documents:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
                
        return documents

    # ------------------------------------------------------------------------
    # CRUD: READ (BY ID)
    # ------------------------------------------------------------------------

    async def get_by_id(self, collection_name: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Получает документ по ID."""
        
        collection = self._get_collection(collection_name) # <-- Используем унифицированный метод
        
        try:
            # Преобразуем входящую строку item_id в ObjectId
            object_id = ObjectId(item_id)
            doc = await collection.find_one({"_id": object_id})
            
            if doc and '_id' in doc:
                doc['_id'] = str(doc['_id']) # Преобразуем _id в строку
            
            return doc
            
        except Exception:
            # Возвращаем None при невалидном ID
            return None

    # ------------------------------------------------------------------------
    # CRUD: UPDATE
    # ------------------------------------------------------------------------

    async def update(self, collection_name: str, item_id: str, data: Dict[str, Any]) -> int:
        """Обновляет документ по ID."""
        
        collection = self._get_collection(collection_name) # <-- Используем унифицированный метод
        
        try:
            object_id = ObjectId(item_id)
        except Exception:
            return 0 # Невалидный ID
            
        # Исключаем поле _id при обновлении
        update_data = data.copy()
        update_data.pop("_id", None) 
        
        result = await collection.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )
        return result.modified_count

    # ------------------------------------------------------------------------
    # CRUD: DELETE
    # ------------------------------------------------------------------------

    async def delete(self, collection_name: str, item_id: str) -> int:
        """Удаляет документ по ID."""
        
        collection = self._get_collection(collection_name) # <-- Используем унифицированный метод
        
        try:
            object_id = ObjectId(item_id)
        except Exception:
            return 0 # Невалидный ID
            
        result = await collection.delete_one({"_id": object_id})
        return result.deleted_count

    # ------------------------------------------------------------------------
    # REORDER: массовое обновление index по порядку
    # ------------------------------------------------------------------------

    async def reorder(self, collection_name: str, ids: List[str]) -> int:
        """
        Устанавливает поле index документам в порядке переданных id.
        Первый элемент получает index=1, второй — 2 и т.д.
        Возвращает количество реально изменённых документов.
        """
        collection = self._get_collection(collection_name)
        updated = 0

        for position, item_id in enumerate(ids, start=1):
            try:
                object_id = ObjectId(str(item_id))
            except Exception:
                continue

            result = await collection.update_one(
                {"_id": object_id},
                {"$set": {"index": position}},
            )
            updated += result.modified_count

        return updated