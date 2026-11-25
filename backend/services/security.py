# backend/services/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import os
import hashlib
import jwt # <-- Используем PyJWT
# from jose import JWTError, jwt as jose_jwt # Оставляем импорт jose_jwt для совместимости с FastAPI OAuth2PasswordBearer

# -------------------------------------------------------------
# КОНФИГУРАЦИЯ БЕЗОПАСНОСТИ
# -------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "YOUR_SUPER_SECRET_KEY_DOCKER")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 300 # 5 часов

# Схема для FastAPI, чтобы получать токен из заголовка Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login") 

# -------------------------------------------------------------
# ХЭШИРОВАНИЕ ПАРОЛЕЙ (Используем hashlib SHA-256 как простую замену)
# -------------------------------------------------------------

def get_password_hash(password: str) -> str:
    """Хэширует пароль с помощью SHA-256."""
    # Используем соль (SECRET_KEY) для дополнительной защиты
    salted_password = password + SECRET_KEY
    return hashlib.sha256(salted_password.encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет соответствие открытого пароля хэшу."""
    return get_password_hash(plain_password) == hashed_password

# -------------------------------------------------------------
# УПРАВЛЕНИЕ JWT-ТОКЕНАМИ (Используем ваш код на PyJWT)
# -------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создает JWT-токен."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    # Добавляем стандартные поля exp и sub
    to_encode.update({"exp": expire.timestamp(), "sub": "access"})
    
    # Используем PyJWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Декодирует JWT-токен и возвращает payload (данные)."""
    try:
        # Используем PyJWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError: # Ловим общую ошибку PyJWT
        return None

# -------------------------------------------------------------
# ЗАВИСИМОСТЬ: ТРЕБОВАНИЕ АВТОРИЗАЦИИ В REST
# -------------------------------------------------------------

async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """
    Получает токен из заголовка, декодирует его и возвращает ID пользователя.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    
    if payload is None or "user_id" not in payload:
        raise credentials_exception
        
    user_id: str = payload.get("user_id")
    
    # Можно добавить проверку существования пользователя в БД,
    # но пока достаточно наличия ID в токене.
    
    return user_id