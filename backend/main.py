import asyncio

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.datastructures import QueryParams
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
# from telegram_bot import start_bot, stop_bot
import os

from database.mongodb import connect_to_mongo, close_mongo_connection, init_indexes
from routers.v1 import references, orders, auth, websocket as ws, migrations, logs, sync
from services.poller import start_polling, stop_polling
from services.security import get_current_user_id
from services.wb_sync_scheduler import start_wb_sync, stop_wb_sync

# 1. Загрузка переменных окружения
load_dotenv()

class FixBracketQueryParamsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.query:
            # Преобразуем cabinet_name[]=val → cabinet_name=val
            new_query_items = []
            for key, value in request.query_params.multi_items():
                if key.endswith("[]"):
                    key = key[:-2]  # убираем []
                new_query_items.append((key, value))

            # Перезаписываем query_string
            request.scope["query_string"] = str(QueryParams(new_query_items)).encode("ascii")

        response = await call_next(request)
        return response

# Документация (/docs, /openapi.json) по умолчанию выключена:
# открытая схема API — лишняя информация для посторонних.
# Включить для отладки: ENABLE_DOCS=true
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").strip().lower() in ("1", "true", "yes", "on")

app = FastAPI(
    title="ABM Marketplace Aggregator API",
    version="1.0.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

origins = [
    "http://localhost:3005",
    "http://127.0.0.1:3005",
    "http://192.168.0.81:3005",
    "http://172.20.80.1:3005",
    "http://abm-order.ru",
    "https://abm-order.ru"
]
# 1. Сначала добавляем наш фикс для query params (важно — до CORS)
app.add_middleware(FixBracketQueryParamsMiddleware)

# 2. Потом CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Разрешаем все методы (GET, POST, и т.д.)
    allow_headers=["*"], # Разрешаем все заголовки
)

# 2. Подключение роутеров
#
# ВСЕ бизнес-эндпоинты требуют JWT (Bearer-токен в заголовке Authorization).
# Открытыми остаются только:
#   POST /api/v1/auth/login  — вход и выдача токена
#   GET  /health             — проверка живости (docker healthcheck)
#   WS   /api/v1/ws          — проверяет токен в query (?token=...)
# Регистрация (POST /api/v1/auth/register) тоже требует токен — см. auth.py.
PROTECTED = [Depends(get_current_user_id)]

app.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders"], dependencies=PROTECTED)
app.include_router(references.router, prefix="/api/v1/references", tags=["References"], dependencies=PROTECTED)
app.include_router(sync.router, prefix="/api/v1", dependencies=PROTECTED)
app.include_router(migrations.router, prefix="/api/v1", dependencies=PROTECTED)
app.include_router(logs.router, prefix="/api/v1", dependencies=PROTECTED)
# В auth.py каждый маршрут подключается отдельно (login — открыт, register — закрыт)
app.include_router(auth.router, prefix="/api/v1")
# WebSocket: токен проверяется внутри хендлера
app.include_router(ws.router, prefix="/api", tags=["websocket"])

# Глобальная переменная для задачи бота
bot_task = None

@app.on_event("startup")
async def startup_event():
    """Событие при запуске приложения."""
    global bot_task
    
    # 1. Подключение к MongoDB
    print("Connecting to MongoDB...")
    await connect_to_mongo()
    print("MongoDB connected.")

    # 2. Создание индексов
    await init_indexes()
    
    # 3. Запуск фоновой задачи Poller
    await start_polling(int(os.getenv('POLLING_INTERVAL_SECONDS', 180)))
    print(f"Polling service started with interval: {os.getenv('POLLING_INTERVAL_SECONDS', 180)}s")

    # Запуск планировщика WB
    await start_wb_sync()
    
    # 4. Запуск Telegram бота (параллельно)
    # print("Starting Telegram bot...")
    # bot_task = asyncio.create_task(start_bot())
    # print("Telegram bot started.")

@app.on_event("shutdown")
async def shutdown_event():
    """Событие при выключении приложения."""
    global bot_task
    
    # 1. Остановка поллера
    stop_polling()
    print("Polling service stopped.")
    
    # 2. Остановка бота
    # if bot_task and not bot_task.done():
    #     print("Stopping Telegram bot...")
    #     bot_task.cancel()
    #     try:
    #         await asyncio.wait_for(bot_task, timeout=5.0)
    #     except (asyncio.CancelledError, asyncio.TimeoutError):
    #         pass
    #     print("Telegram bot stopped.")
    
    # 3. Закрытие соединения с MongoDB
    await close_mongo_connection()
    print("MongoDB connection closed.")

    stop_wb_sync()

@app.get("/health")
async def health_check():
    """Проверка здоровья API."""
    return {"status": "ok"}