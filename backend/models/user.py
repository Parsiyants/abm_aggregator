from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from bson import ObjectId

from pydantic_core import core_schema
from typing import Any, Callable, Type

# Вспомогательный класс для работы с ObjectId в Pydantic
class PyObjectId(ObjectId):
    """
    Кастомный тип для корректной работы bson.ObjectId с Pydantic v2.
    """
    @classmethod
    def __get_validators__(cls):
        # В v2 это не используется, но оставлено для совместимости
        yield cls.validate

    @classmethod
    def validate(cls, v: Any) -> ObjectId:
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError('Invalid ObjectId format')

    # !!! ГЛАВНОЕ ИСПРАВЛЕНИЕ ДЛЯ PYDANTIC V2 !!!
    
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[[Any], core_schema.CoreSchema]
    ) -> core_schema.CoreSchema:
        
        # Мы говорим Pydantic: 
        # 1. При парсинге (со входа) используй нашу функцию `validate`.
        # 2. При выводе (в JSON) он должен быть строкой.
        
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.to_string_ser_schema(),
        )

# -------------------------------------------------------------
# Модели для входных данных
# -------------------------------------------------------------

class UserRegister(BaseModel):
    """Модель для регистрации нового пользователя."""
    email: EmailStr
    password: str
    
    # Можно добавить поле для имени, но пока оставим минимальный набор

class UserLogin(BaseModel):
    """Модель для входа пользователя."""
    email: EmailStr
    password: str

# -------------------------------------------------------------
# Модели для базы данных и ответа
# -------------------------------------------------------------

class User(BaseModel):
    """Основная модель пользователя в базе данных."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    email: EmailStr
    # Внимание: password хранится только в репозитории (захэшированный)
    
    # Для ответа (response) мы исключаем захэшированный пароль
    
    class Config:
        json_encoders = {ObjectId: str}
        allow_population_by_field_name = True