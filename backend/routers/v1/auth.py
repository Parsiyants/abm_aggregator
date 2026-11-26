# backend/routers/v1/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Dict, Any
from repositories.user_repo import UserRepository
from models.user import UserRegister, UserLogin
from services.security import (
    get_password_hash, 
    verify_password, 
    create_access_token,
    get_current_user_id # Используется для тестирования
)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

# -------------------------------------------------------------
# РЕГИСТРАЦИЯ (только для авторизованных пользователей)
# -------------------------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    repo: UserRepository = Depends(UserRepository),
    current_user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """
    Создаёт нового пользователя.

    Требует Bearer-токен: самостоятельная регистрация закрыта,
    первого администратора создаёт скрипт seed_admin.py.
    """

    # 1. Проверяем, существует ли пользователь
    if await repo.get_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )

    # 2. Хэшируем пароль
    hashed_password = get_password_hash(user_data.password)

    # 3. Создаем пользователя
    new_user_doc = await repo.create_user(user_data.email, hashed_password)

    if not new_user_doc:
         raise HTTPException(status_code=500, detail="User creation failed")

    # 4. Токен нового пользователя наружу не отдаём — создатель сессии не меняет
    return {"user": new_user_doc}

# -------------------------------------------------------------
# ВХОД Через JSON
# -------------------------------------------------------------

@router.post("/login")
async def login(
    user_data: UserLogin, 
    repo: UserRepository = Depends(UserRepository)
) -> Dict[str, str]:
    
    # 1. Получаем пользователя по email (включая захэшированный пароль)
    user_doc = await repo.get_by_email(user_data.email)
    
    # 2. Проверяем существование и пароль
    if not user_doc or not verify_password(user_data.password, user_doc.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Создаем JWT-токен
    access_token = create_access_token(data={"user_id": user_doc["_id"]})
    
    return {"access_token": access_token, "token_type": "bearer", "user_email": user_doc.get("email", "")}

# -------------------------------------------------------------
# ТЕСТОВЫЙ ЭНДПОИНТ (для проверки токена)
# -------------------------------------------------------------

@router.get("/me")
async def read_users_me(current_user_id: str = Depends(get_current_user_id)):
    """Тестовый эндпоинт, требующий авторизации."""
    return {"user_id": current_user_id, "message": "You are authenticated!"}